from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.publication import PublicationTarget


class FakeImapSource:
    def validate(self, config) -> None:
        return None

    def preview_messages(self, config, limit_per_folder: int = 50):
        return []

    def fetch_messages(self, config, folder: str, *, uid_start=None, since=None, limit=None):
        return []


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        admin_token="admin-token",
        secret_key="secret",
        database_path=tmp_path / "test.sqlite",
        feeds_dir=tmp_path / "feeds",
        public_origin="https://backend.example.test",
        cookie_secure=False,
        session_days=30,
        scheduler_enabled=False,
        scheduler_tick_seconds=60,
        imap_timeout_seconds=10,
    )


def iso_at(offset: int) -> str:
    return (datetime(2026, 4, 29, tzinfo=timezone.utc) + timedelta(seconds=offset)).isoformat()


def test_activity_logs_endpoint_requires_admin_session(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        response = client.get("/api/activity-logs")

    assert response.status_code == 401


def test_activity_logs_endpoint_defaults_newest_first_and_page_size_50(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())
    for i in range(55):
        app.state.activity_log_recorder.record_sync(
            trigger="manual_sync",
            status="success",
            feed_id=i + 1,
            feed_title=f"Feed {i}",
            imported_count=i,
            skipped_count=0,
            completed_at=iso_at(i),
            duration_ms=i,
        )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.get("/api/activity-logs")

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {
        "page": 1,
        "page_size": 50,
        "total": 55,
        "total_pages": 2,
        "has_next": True,
        "has_previous": False,
    }
    assert len(body["entries"]) == 50
    assert body["entries"][0]["feed_title"] == "Feed 54"
    assert body["entries"][-1]["feed_title"] == "Feed 5"


def test_activity_logs_endpoint_filters_operation_status_trigger_and_feed(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())
    app.state.activity_log_recorder.record_sync(
        trigger="manual_sync",
        status="failed",
        feed_id=9,
        feed_title="Target Feed",
        imported_count=0,
        skipped_count=0,
        completed_at=iso_at(1),
        duration_ms=1,
        error="failed",
    )
    app.state.activity_log_recorder.record_publish(
        trigger="publication_retry",
        status="success",
        publication_target=PublicationTarget.BACKEND,
        feed_count=1,
        file_count=2,
        completed_at=iso_at(2),
        duration_ms=1,
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.get(
            "/api/activity-logs?operation_type=sync&status=failed&trigger=manual_sync&feed_id=9"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["entries"][0]["operation_type"] == "sync"
    assert body["entries"][0]["feed_id"] == 9


def test_activity_logs_endpoint_returns_redacted_display_data(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())
    app.state.activity_log_recorder.record_publish(
        trigger="publication_activation",
        status="failed",
        publication_target=PublicationTarget.GITHUB,
        feed_count=1,
        file_count=2,
        completed_at=iso_at(1),
        duration_ms=1,
        error="GitHub rejected token ghp_secret-token for admin@example.test",
        error_detail="https://backend.example.test/f/abcdefghijklmnopqrstuvwxyz.xml <p>Private body text</p>",
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.get("/api/activity-logs")

    entry = response.json()["entries"][0]
    payload = f"{entry['error_summary']} {entry['error_detail']}"
    assert "ghp_secret-token" not in payload
    assert "admin@example.test" not in payload
    assert "abcdefghijklmnopqrstuvwxyz" not in payload
    assert "Private body text" not in payload
