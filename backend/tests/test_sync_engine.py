from pathlib import Path

from app.body_processor import BodyProcessor
from app.feed_publisher import FeedPublisher
from app.imap_source import FetchedMessage
from app.security import CredentialCipher
from app.store import MessageStore
from app.sync_engine import SyncEngine


def message_bytes(uid: int, recipient: str, subject: str, sender: str = "sender@example.test") -> bytes:
    return (
        f"From: Sender <{sender}>\n"
        f"To: {recipient}\n"
        f"Subject: {subject}\n"
        f"Date: Wed, 29 Apr 2026 10:0{uid}:00 +0000\n"
        f"Message-ID: <{uid}@example.test>\n"
        f"Content-Type: text/html; charset=utf-8\n\n"
        f"<p>Body {uid}</p>"
    ).encode()


class FakeImapSource:
    def __init__(self) -> None:
        self.messages = [
            FetchedMessage("INBOX", "1", 1, message_bytes(1, "mailbox@example.test", "One", sender="Target@Example.Test")),
            FetchedMessage("INBOX", "1", 2, message_bytes(2, "target@example.test", "Two", sender="other@example.test")),
        ]
        self.fetch_calls = []

    def validate(self, config) -> None:
        return None

    def preview_messages(self, config, limit_per_folder: int = 50):
        return self.messages[-limit_per_folder:]

    def fetch_messages(self, config, folder: str, *, uid_start=None, since=None, limit=None):
        self.fetch_calls.append({"folder": folder, "uid_start": uid_start, "since": since, "limit": limit})
        messages = [message for message in self.messages if message.folder == folder]
        if uid_start is not None:
            messages = [message for message in messages if message.uid >= uid_start]
        if limit is not None:
            messages = messages[-limit:]
        return messages


def build_engine(tmp_path: Path):
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    cipher = CredentialCipher("secret")
    source = FakeImapSource()
    publisher = FeedPublisher(store, tmp_path / "feeds", "https://example.test")
    engine = SyncEngine(store, cipher, source, BodyProcessor(), publisher, 10)
    feed = store.create_feed(
        {
            "title": "Feed",
            "sender": "target@example.test",
            "imap_host": "imap.example.test",
            "imap_port": 993,
            "imap_tls": "ssl",
            "imap_username": "user@example.test",
            "imap_password_encrypted": cipher.encrypt("password"),
            "folders": ["INBOX"],
            "random_slug": "random",
            "backfill_days": 30,
            "retention_count": 50,
            "sync_interval_minutes": 60,
        }
    )
    return engine, store, source, feed


def test_preview_allows_matches_without_saving(tmp_path: Path) -> None:
    engine, _store, _source, _feed = build_engine(tmp_path)

    result = engine.preview(
        {
            "title": "Preview",
            "sender": "target@example.test",
            "imap_host": "imap.example.test",
            "imap_port": 993,
            "imap_tls": "ssl",
            "imap_username": "user@example.test",
            "imap_password": "password",
            "folders": ["INBOX"],
            "backfill_days": 30,
            "retention_count": 50,
            "sync_interval_minutes": 60,
            "limit_per_folder": 50,
        }
    )

    assert result["match_count"] == 1
    assert result["scanned_count"] == 2
    assert result["samples"][0]["subject"] == "One"


def test_preview_ignores_recipient_only_messages(tmp_path: Path) -> None:
    engine, _store, source, _feed = build_engine(tmp_path)
    source.messages = [
        FetchedMessage(
            "INBOX",
            "1",
            3,
            message_bytes(3, "target@example.test", "Recipient Only", sender="other@example.test"),
        )
    ]

    result = engine.preview(
        {
            "title": "Preview",
            "sender": "target@example.test",
            "imap_host": "imap.example.test",
            "imap_port": 993,
            "imap_tls": "ssl",
            "imap_username": "user@example.test",
            "imap_password": "password",
            "folders": ["INBOX"],
            "backfill_days": 30,
            "retention_count": 50,
            "sync_interval_minutes": 60,
            "limit_per_folder": 50,
        }
    )

    assert result["match_count"] == 0
    assert result["scanned_count"] == 1


def test_sync_imports_matching_messages_and_uses_cursor_incrementally(tmp_path: Path) -> None:
    engine, store, source, feed = build_engine(tmp_path)

    first = engine.sync_feed(feed["id"], manual=True)
    second = engine.sync_feed(feed["id"], manual=True)

    assert first.status == "success"
    assert first.feed_id == feed["id"]
    assert first.feed_title == "Feed"
    assert first.imported_count == 1
    assert first.skipped_count == 1
    assert second.status == "success"
    assert second.imported_count == 0
    assert source.fetch_calls[-1]["uid_start"] == 3
    items = store.list_feed_items(feed["id"])
    assert [item["subject"] for item in items] == ["One"]


def test_sync_due_feeds_returns_feed_metadata(tmp_path: Path) -> None:
    engine, _store, _source, feed = build_engine(tmp_path)

    results = engine.sync_due_feeds()

    assert len(results) == 1
    assert results[0].feed_id == feed["id"]
    assert results[0].feed_title == "Feed"
    assert results[0].imported_count == 1
    assert results[0].skipped_count == 1
