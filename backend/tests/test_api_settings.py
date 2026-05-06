from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


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
        public_origin="https://example.test",
        cookie_secure=False,
        session_days=30,
        scheduler_enabled=False,
        scheduler_tick_seconds=60,
        imap_timeout_seconds=10,
    )


def feed_payload() -> dict[str, object]:
    return {
        "title": "Target Feed",
        "sender": "target@example.test",
        "imap_host": "imap.example.test",
        "imap_port": 993,
        "imap_tls": "ssl",
        "imap_username": "user@example.test",
        "imap_password": "password",
        "folders": ["INBOX"],
        "backfill_days": 30,
        "retention_count": 50,
    }


def test_settings_require_admin_session(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        response = client.get("/api/settings")

    assert response.status_code == 401


def test_settings_default_and_update_round_trip(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        initial = client.get("/api/settings")
        updated = client.put(
            "/api/settings",
            json={
                "default_proxy_url": " socks5://127.0.0.1:1080 ",
                "default_sync_interval_minutes": 15,
            },
        )
        reread = client.get("/api/settings")

    assert initial.status_code == 200
    assert initial.json()["settings"] == {
        "default_proxy_url": "",
        "default_sync_interval_minutes": 60,
    }
    assert updated.status_code == 200
    assert updated.json()["settings"] == {
        "default_proxy_url": "socks5://127.0.0.1:1080",
        "default_sync_interval_minutes": 15,
    }
    assert reread.json() == updated.json()


def test_settings_reject_invalid_proxy_url(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.put(
            "/api/settings",
            json={
                "default_proxy_url": "localhost:7890",
                "default_sync_interval_minutes": 60,
            },
        )

    assert response.status_code == 422


def test_create_feed_uses_settings_default_sync_interval_when_omitted(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        client.put(
            "/api/settings",
            json={
                "default_proxy_url": "",
                "default_sync_interval_minutes": 15,
            },
        )
        response = client.post("/api/feeds", json=feed_payload())

    assert response.status_code == 200
    assert response.json()["feed"]["sync_interval_minutes"] == 15
