from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.activity_log import ActivityLogQuery, ActivityLogRecorder
from app.publication import PublicationTarget
from app.store import MessageStore


def create_feed(store: MessageStore, title: str = "Feed"):
    return store.create_feed(
        {
            "title": title,
            "sender": "target@example.test",
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


def iso_at(offset: int) -> str:
    return (datetime(2026, 4, 29, tzinfo=timezone.utc) + timedelta(seconds=offset)).isoformat()


def test_activity_log_store_queries_filters_paginates_and_retains_newest_entries(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    feed = create_feed(store)

    for i in range(1005):
        store.create_activity_log_entry(
            {
                "operation_type": "sync" if i % 2 else "publish",
                "status": "failed" if i == 1004 else "success",
                "trigger": "manual_sync" if i % 3 else "scheduled_sync",
                "feed_id": int(feed["id"]),
                "feed_title_snapshot": f"Feed {i}",
                "publication_target": PublicationTarget.BACKEND if i % 2 else None,
                "imported_count": i if i % 2 else None,
                "skipped_count": 1 if i % 2 else None,
                "feed_count": None if i % 2 else 1,
                "file_count": None if i % 2 else 2,
                "completed_at": iso_at(i),
                "duration_ms": i,
            }
        )

    first_page = store.list_activity_log_entries(limit=2, offset=0)
    second_page = store.list_activity_log_entries(limit=2, offset=2)
    failed = store.list_activity_log_entries(limit=10, offset=0, status="failed")
    sync_count = store.count_activity_log_entries(operation_type="sync")
    feed_count = store.count_activity_log_entries(feed_id=int(feed["id"]))

    assert store.count_activity_log_entries() == 1000
    assert [row["feed_title_snapshot"] for row in first_page] == ["Feed 1004", "Feed 1003"]
    assert [row["feed_title_snapshot"] for row in second_page] == ["Feed 1002", "Feed 1001"]
    assert [row["feed_title_snapshot"] for row in failed] == ["Feed 1004"]
    assert sync_count == 500
    assert feed_count == 1000


def test_activity_log_query_returns_pagination_metadata(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    recorder = ActivityLogRecorder(store)
    query = ActivityLogQuery(store)

    recorder.record_publish(
        trigger="publication_retry",
        status="success",
        publication_target=PublicationTarget.BACKEND,
        feed_count=2,
        file_count=4,
        completed_at=iso_at(1),
        duration_ms=12,
    )
    recorder.record_sync(
        trigger="manual_sync",
        status="skipped",
        feed_id=7,
        feed_title="Missing Feed",
        imported_count=0,
        skipped_count=0,
        completed_at=iso_at(2),
        duration_ms=3,
        error="Sync skipped because another sync is already running.",
    )

    result = query.list(page=1, page_size=1, status="skipped")

    assert result["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total": 1,
        "total_pages": 1,
        "has_next": False,
        "has_previous": False,
    }
    assert result["entries"][0]["operation_type"] == "sync"
    assert result["entries"][0]["feed_title"] == "Missing Feed"


def test_activity_log_recorder_redacts_sensitive_values_before_persisting(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    recorder = ActivityLogRecorder(store)

    recorder.record_sync(
        trigger="manual_sync",
        status="failed",
        feed_id=1,
        feed_title="Target Feed",
        imported_count=0,
        skipped_count=0,
        completed_at=iso_at(1),
        duration_ms=10,
        error=(
            "Failed password=hunter2 token=ghp_secret-token user=admin@example.test "
            "url=https://backend.example.test/f/abcdefghijklmnopqrstuvwxyz.xml "
            "body=<p>Private body text</p>"
        ),
        error_detail=(
            "Traceback for admin@example.test with ghp_secret-token and "
            "https://cdn.example.test/feeds/abcdefghijklmnopqrstuvwxyz.raw.xml "
            "<div>Private body text</div>"
        ),
    )

    row = store.list_activity_log_entries(limit=1, offset=0)[0]
    persisted = " ".join(str(row[key] or "") for key in ["error_summary", "error_detail"])

    assert "hunter2" not in persisted
    assert "ghp_secret-token" not in persisted
    assert "admin@example.test" not in persisted
    assert "abcdefghijklmnopqrstuvwxyz" not in persisted
    assert "Private body text" not in persisted
    assert "***" in persisted


def test_deleted_feed_title_snapshot_remains_in_activity_log(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "test.sqlite")
    store.init_db()
    feed = create_feed(store, "Historical Feed")
    recorder = ActivityLogRecorder(store)

    recorder.record_publish(
        trigger="feed_change_publication",
        status="success",
        publication_target=PublicationTarget.BACKEND,
        feed_id=int(feed["id"]),
        feed_title=str(feed["title"]),
        feed_count=1,
        file_count=2,
        completed_at=iso_at(1),
        duration_ms=4,
    )
    store.delete_feed(int(feed["id"]))

    row = store.list_activity_log_entries(limit=1, offset=0)[0]

    assert store.get_feed(int(feed["id"])) is None
    assert row["feed_id"] == feed["id"]
    assert row["feed_title_snapshot"] == "Historical Feed"
