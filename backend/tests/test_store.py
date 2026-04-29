from pathlib import Path

from app.store import MessageStore


def create_feed(store: MessageStore, title: str = "Feed"):
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
            "random_slug": f"slug-{title}",
            "backfill_days": 30,
            "retention_count": 1,
            "sync_interval_minutes": 60,
        }
    )


def add_message(store: MessageStore, uid: int, published_at: str) -> int:
    return store.upsert_imported_message(
        {
            "account_key": "account",
            "folder": "INBOX",
            "uidvalidity": "1",
            "uid": uid,
            "message_id": f"<{uid}@example.test>",
            "subject": f"Subject {uid}",
            "author": "Sender",
            "published_at": published_at,
            "raw_html": "<p>Raw</p>",
            "sanitized_html": "<p>Clean</p>",
            "summary": "Summary",
        }
    )


def test_retention_archives_without_deleting_items(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    feed = create_feed(store)
    old_message = add_message(store, 1, "2026-04-28T00:00:00+00:00")
    new_message = add_message(store, 2, "2026-04-29T00:00:00+00:00")
    store.link_feed_item(feed["id"], old_message)
    store.link_feed_item(feed["id"], new_message)

    store.apply_retention(feed["id"], 1)

    visible = store.list_feed_items(feed["id"])
    all_items = store.list_feed_items(feed["id"], include_archived=True)
    assert [row["uid"] for row in visible] == [2]
    assert len(all_items) == 2


def test_delete_feed_cleans_only_orphan_messages(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    first = create_feed(store, "first")
    second = create_feed(store, "second")
    shared_message = add_message(store, 1, "2026-04-29T00:00:00+00:00")
    orphan_message = add_message(store, 2, "2026-04-28T00:00:00+00:00")
    store.link_feed_item(first["id"], shared_message)
    store.link_feed_item(second["id"], shared_message)
    store.link_feed_item(first["id"], orphan_message)

    store.delete_feed(first["id"])

    remaining = store.list_feed_items(second["id"], include_archived=True)
    assert [row["uid"] for row in remaining] == [1]

