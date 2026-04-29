from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.imap_source import FetchedMessage
from app.main import SESSION_COOKIE, create_app


def message_bytes(uid: int, recipient: str, subject: str, sender: str = "sender@example.test") -> bytes:
    return (
        f"From: Sender <{sender}>\n"
        f"To: {recipient}\n"
        f"Subject: {subject}\n"
        f"Date: Wed, 29 Apr 2026 10:0{uid}:00 +0000\n"
        f"Message-ID: <api-{uid}@example.test>\n"
        f"Content-Type: text/html; charset=utf-8\n\n"
        f"<p>Body {uid}</p>"
    ).encode()


class FakeImapSource:
    def __init__(self) -> None:
        self.messages = [
            FetchedMessage(
                "INBOX",
                "1",
                1,
                message_bytes(1, "mailbox@example.test", "One", sender="target@example.test"),
            ),
            FetchedMessage(
                "INBOX",
                "1",
                2,
                message_bytes(2, "target@example.test", "Two", sender="other@example.test"),
            ),
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


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        admin_token="admin-token",
        secret_key="secret",
        database_path=tmp_path / "test.sqlite",
        feeds_dir=tmp_path / "feeds",
        public_origin="https://example.test",
        cookie_secure=False,
        session_days=30,
        scheduler_enabled=False,
        scheduler_tick_seconds=60,
        imap_timeout_seconds=10,
    )


def seed_feed(store, title: str):
    return store.create_feed(
        {
            "title": title,
            "recipient": "target@example.test",
            "imap_host": "imap.example.test",
            "imap_port": 993,
            "imap_tls": "ssl",
            "imap_username": "user@example.test",
            "imap_password_encrypted": "secret",
            "folders": ["INBOX"],
            "random_slug": f"slug-{title.lower()}",
            "backfill_days": 30,
            "retention_count": 50,
            "sync_interval_minutes": 60,
        }
    )


def test_login_sets_httponly_session_cookie(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        denied = client.get("/api/feeds")
        login = client.post("/api/auth/login", json={"token": "admin-token"})
        allowed = client.get("/api/feeds")

    assert denied.status_code == 401
    assert login.status_code == 200
    assert SESSION_COOKIE in login.cookies
    assert "httponly" in login.headers["set-cookie"].lower()
    assert allowed.status_code == 200


def test_list_feeds_paginates_and_sorts(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings=settings)
    seed_feed(app.state.store, "Charlie")
    seed_feed(app.state.store, "Alpha")
    seed_feed(app.state.store, "Bravo")

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        first_page = client.get("/api/feeds?page=1&page_size=2&sort_by=title&sort_dir=asc")
        second_page = client.get("/api/feeds?page=2&page_size=2&sort_by=title&sort_dir=asc")

    assert first_page.status_code == 200
    assert [feed["title"] for feed in first_page.json()["feeds"]] == ["Alpha", "Bravo"]
    assert first_page.json()["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "total_pages": 2,
        "has_next": True,
        "has_previous": False,
    }
    assert second_page.status_code == 200
    assert [feed["title"] for feed in second_page.json()["feeds"]] == ["Charlie"]
    assert second_page.json()["pagination"]["has_previous"] is True


def test_create_feed_runs_initial_sync(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    imap_source = FakeImapSource()
    app = create_app(settings=settings, imap_source=imap_source)

    payload = {
        "title": "Target Feed",
        "recipient": "target@example.test",
        "imap_host": "imap.example.test",
        "imap_port": 993,
        "imap_tls": "ssl",
        "imap_username": "user@example.test",
        "imap_password": "password",
        "folders": ["INBOX"],
        "backfill_days": 30,
        "retention_count": 50,
        "sync_interval_minutes": 60,
    }

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.post("/api/feeds", json=payload)

    assert response.status_code == 200
    feed = response.json()["feed"]
    assert feed["sync_status"]["first_sync_completed"] is True
    assert feed["sync_status"]["last_sync_status"] == "success"
    assert feed["sync_status"]["last_sync_imported_count"] == 1
    assert feed["sync_status"]["last_sync_skipped_count"] == 1
    assert len(imap_source.fetch_calls) == 1
    assert imap_source.fetch_calls[0]["folder"] == "INBOX"
    assert imap_source.fetch_calls[0]["uid_start"] is None
    assert imap_source.fetch_calls[0]["since"] is not None
    assert imap_source.fetch_calls[0]["limit"] is None
