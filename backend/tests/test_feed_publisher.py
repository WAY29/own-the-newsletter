import xml.etree.ElementTree as ET
from pathlib import Path

from app.feed_publisher import FeedPublisher
from app.store import MessageStore


def test_feed_publisher_writes_clean_and_raw_body_modes(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    feed = store.create_feed(
        {
            "title": "Feed",
            "recipient": "target@example.test",
            "imap_host": "imap.example.test",
            "imap_port": 993,
            "imap_tls": "ssl",
            "imap_username": "user@example.test",
            "imap_password_encrypted": "secret",
            "folders": ["INBOX"],
            "random_slug": "random",
            "backfill_days": 30,
            "retention_count": 50,
            "sync_interval_minutes": 60,
        }
    )
    message_id = store.upsert_imported_message(
        {
            "account_key": "account",
            "folder": "INBOX",
            "uidvalidity": "1",
            "uid": 1,
            "message_id": "<1@example.test>",
            "subject": "Subject",
            "author": "Sender",
            "published_at": "2026-04-29T00:00:00+00:00",
            "raw_html": '<div class="shell"><p>Raw body</p></div>',
            "sanitized_html": "<p>Clean body</p>",
            "summary": "Summary",
        }
    )
    store.link_feed_item(feed["id"], message_id)
    publisher = FeedPublisher(store, tmp_path / "feeds", "https://example.test")

    publisher.publish(feed)

    clean_body = _first_content_encoded(publisher.feed_path("random").read_text(encoding="utf-8"))
    raw_body = _first_content_encoded(publisher.feed_path("random", raw=True).read_text(encoding="utf-8"))
    assert clean_body == "<p>Clean body</p>"
    assert raw_body == '<div class="shell"><p>Raw body</p></div>'


def _first_content_encoded(xml: str) -> str:
    item = ET.fromstring(xml).find("./channel/item")
    assert item is not None
    body = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
    assert body is not None
    return body
