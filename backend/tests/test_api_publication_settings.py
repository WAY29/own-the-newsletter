from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import CredentialCipher


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


def test_publication_settings_require_admin_session(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        response = client.get("/api/publication/settings")

    assert response.status_code == 401


def test_publication_settings_default_response(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.get("/api/publication/settings")

    assert response.status_code == 200
    assert response.json()["settings"] == {
        "active_target": "backend",
        "github_repository": "",
        "github_branch": "main",
        "github_directory": "feeds",
        "github_public_url": "",
        "github_token_present": False,
        "last_publication_started_at": None,
        "last_publication_finished_at": None,
        "last_publication_status": None,
        "last_publication_error": None,
        "last_publication_feed_id": None,
        "last_publication_feed_title": None,
    }


def test_publication_settings_token_is_write_only_and_encrypted(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings=settings, imap_source=FakeImapSource())

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.put(
            "/api/publication/settings",
            json={
                "github_repository": "https://github.com/Owner/Repo.git",
                "github_branch": "pages",
                "github_directory": " feeds ",
                "github_public_url": "https://cdn.example.test/rss/",
                "github_token": "ghp_secret-token",
            },
        )
        reread = client.get("/api/publication/settings")
        keep_token = client.put(
            "/api/publication/settings",
            json={
                "github_repository": "Owner/Repo",
                "github_branch": "main",
                "github_directory": "",
                "github_public_url": "https://cdn.example.test/root",
                "github_token": "",
            },
        )

    assert response.status_code == 200
    body = response.json()["settings"]
    assert body["github_repository"] == "Owner/Repo"
    assert body["github_branch"] == "pages"
    assert body["github_directory"] == "feeds"
    assert body["github_public_url"] == "https://cdn.example.test/rss"
    assert body["github_token_present"] is True
    assert "github_token" not in body
    assert reread.json()["settings"] == body
    assert keep_token.json()["settings"]["github_token_present"] is True
    assert keep_token.json()["settings"]["github_directory"] == ""

    with app.state.store.connect() as conn:
        row = conn.execute(
            "SELECT setting_value FROM admin_settings WHERE setting_key = ?",
            ("publication_github_token_encrypted",),
        ).fetchone()

    assert row is not None
    encrypted = row["setting_value"]
    assert encrypted != "ghp_secret-token"
    assert "ghp_secret-token" not in encrypted
    assert CredentialCipher(settings.secret_key).decrypt(encrypted) == "ghp_secret-token"


def test_publication_settings_reject_invalid_github_config(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.put(
            "/api/publication/settings",
            json={
                "github_repository": "https://gitlab.com/Owner/Repo",
                "github_branch": "main",
                "github_directory": "../feeds",
                "github_public_url": "ftp://cdn.example.test/rss",
                "github_token": "ghp_secret-token",
            },
        )

    assert response.status_code == 422


def test_publication_settings_reject_non_ascii_github_token(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.put(
            "/api/publication/settings",
            json={
                "github_repository": "owner/repo",
                "github_branch": "main",
                "github_directory": "feeds",
                "github_public_url": "https://cdn.example.test/rss",
                "github_token": "ghp_secret◊token",
            },
        )

    assert response.status_code == 422
    assert "printable ASCII" in response.text


def test_feed_api_uses_active_publication_target_urls(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())
    app.state.store.update_publication_settings(
        {
            "active_target": "github",
            "github_public_url": "https://cdn.example.test/rss",
            "github_directory": "own",
        }
    )
    feed = app.state.store.create_feed(
        {
            "title": "Feed",
            "sender": "target@example.test",
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

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.get(f"/api/feeds/{feed['id']}")

    assert response.status_code == 200
    body = response.json()["feed"]
    assert body["feed_url"] == "https://cdn.example.test/rss/own/random.xml"
    assert body["raw_feed_url"] == "https://cdn.example.test/rss/own/random.raw.xml"
