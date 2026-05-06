from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.imap_source import FetchedMessage
from app.publication import GitHubFileChange, GitHubPublicationConfig, PublicationError, PublicationTarget
from app.security import CredentialCipher
from app.main import create_app


def message_bytes(uid: int, subject: str = "One", sender: str = "target@example.test") -> bytes:
    return (
        f"From: Sender <{sender}>\n"
        "To: mailbox@example.test\n"
        f"Subject: {subject}\n"
        f"Date: Wed, 29 Apr 2026 10:0{uid}:00 +0000\n"
        f"Message-ID: <activity-{uid}@example.test>\n"
        "Content-Type: text/html; charset=utf-8\n\n"
        f"<p>Body {uid}</p>"
    ).encode()


class FakeImapSource:
    def __init__(self) -> None:
        self.fetch_calls = []
        self.messages = [
            FetchedMessage("INBOX", "1", 1, message_bytes(1)),
            FetchedMessage("INBOX", "1", 2, message_bytes(2, sender="other@example.test")),
        ]

    def validate(self, config) -> None:
        return None

    def preview_messages(self, config, limit_per_folder: int = 50):
        return self.messages[-limit_per_folder:]

    def fetch_messages(self, config, folder: str, *, uid_start=None, since=None, limit=None):
        self.fetch_calls.append({"folder": folder, "uid_start": uid_start, "since": since, "limit": limit})
        return [message for message in self.messages if message.folder == folder]


class FakeGitHubClient:
    def __init__(self, config: GitHubPublicationConfig, *, fail: bool = False) -> None:
        self.config = config
        self.fail = fail
        self.commits = []
        self.deletes = []

    def validate_write_access(self) -> None:
        return None

    def commit_files(self, changes: list[GitHubFileChange], message: str) -> None:
        if self.fail:
            raise PublicationError(f"GitHub rejected token {self.config.token}")
        self.commits.append({"changes": changes, "message": message})

    def delete_files(self, paths: list[str], message: str) -> None:
        self.deletes.append({"paths": paths, "message": message})


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


def feed_payload(title: str = "Feed") -> dict[str, object]:
    return {
        "title": title,
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
    }


def create_feed(store, cipher: CredentialCipher, *, title: str = "Feed", slug: str = "random"):
    return store.create_feed(
        {
            **feed_payload(title),
            "imap_password_encrypted": cipher.encrypt("password"),
            "random_slug": slug,
        }
        | {"imap_password": None}
    )


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"token": "admin-token"})
    assert response.status_code == 200


def test_create_feed_logs_feed_change_publish_initial_sync_and_followup_publish(tmp_path: Path) -> None:
    app = create_app(settings=build_settings(tmp_path), imap_source=FakeImapSource())

    with TestClient(app) as client:
        login(client)
        response = client.post("/api/feeds", json=feed_payload("Target Feed"))
        logs = client.get("/api/activity-logs?page_size=10")

    assert response.status_code == 200
    assert logs.status_code == 200
    entries = logs.json()["entries"]
    assert [(entry["operation_type"], entry["trigger"], entry["status"]) for entry in entries] == [
        ("publish", "initial_sync", "success"),
        ("sync", "initial_sync", "success"),
        ("publish", "feed_change_publication", "success"),
    ]
    assert entries[1]["imported_count"] == 1
    assert entries[1]["skipped_count"] == 1
    assert entries[0]["publication_target"] == "backend"
    assert entries[0]["file_count"] == 2


def test_manual_sync_logs_sync_and_publish_as_separate_entries(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings=settings, imap_source=FakeImapSource())
    feed = create_feed(app.state.store, CredentialCipher(settings.secret_key))

    with TestClient(app) as client:
        login(client)
        response = client.post(f"/api/feeds/{feed['id']}/sync")
        logs = client.get("/api/activity-logs?trigger=manual_sync&page_size=10")

    assert response.status_code == 200
    entries = logs.json()["entries"]
    assert [(entry["operation_type"], entry["status"]) for entry in entries] == [
        ("publish", "success"),
        ("sync", "success"),
    ]
    assert entries[1]["imported_count"] == 1
    assert entries[1]["skipped_count"] == 1


def test_duplicate_sync_skip_is_recorded_as_completed_activity(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings=settings, imap_source=FakeImapSource())
    feed = create_feed(app.state.store, CredentialCipher(settings.secret_key))
    lock = app.state.sync_engine._lock_for(int(feed["id"]))
    lock.acquire()
    try:
        result = app.state.sync_engine.sync_feed(int(feed["id"]), manual=True)
    finally:
        lock.release()

    entries = app.state.activity_log_query.list(page=1, page_size=10, status="skipped")["entries"]

    assert result.status == "skipped"
    assert len(entries) == 1
    assert entries[0]["operation_type"] == "sync"
    assert entries[0]["trigger"] == "manual_sync"
    assert "already running" in entries[0]["error_summary"]


def test_publication_retry_logs_all_feed_publish_without_changing_sync_status(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    github_client = None

    def factory(config: GitHubPublicationConfig):
        nonlocal github_client
        github_client = FakeGitHubClient(config)
        return github_client

    app = create_app(settings=settings, imap_source=FakeImapSource(), github_client_factory=factory)
    store = app.state.store
    cipher = CredentialCipher(settings.secret_key)
    feed = create_feed(store, cipher)
    store.mark_sync_finished(feed["id"], status="success", imported_count=3, skipped_count=1)
    store.update_publication_settings(
        {
            "active_target": PublicationTarget.GITHUB,
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret-token"),
        }
    )

    with TestClient(app) as client:
        login(client)
        response = client.post("/api/publication/retry")
        logs = client.get("/api/activity-logs?trigger=publication_retry")

    assert response.status_code == 200
    assert github_client is not None
    entry = logs.json()["entries"][0]
    assert entry["operation_type"] == "publish"
    assert entry["publication_target"] == "github"
    assert entry["feed_id"] is None
    assert entry["feed_count"] == 1
    assert entry["file_count"] == 2
    assert store.get_feed(feed["id"])["last_sync_imported_count"] == 3


def test_failed_github_activation_logs_redacted_failed_publish_without_switching_target(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)

    def factory(config: GitHubPublicationConfig):
        return FakeGitHubClient(config, fail=True)

    app = create_app(settings=settings, imap_source=FakeImapSource(), github_client_factory=factory)
    create_feed(app.state.store, CredentialCipher(settings.secret_key))

    with TestClient(app) as client:
        login(client)
        client.put(
            "/api/publication/settings",
            json={
                "github_repository": "owner/repo",
                "github_branch": "pages",
                "github_directory": "feeds",
                "github_public_url": "https://cdn.example.test/rss",
                "github_token": "ghp_secret-token",
            },
        )
        response = client.post("/api/publication/github/activate")
        settings_response = client.get("/api/publication/settings")
        logs = client.get("/api/activity-logs?trigger=publication_activation")

    assert response.status_code == 400
    assert settings_response.json()["settings"]["active_target"] == "backend"
    entry = logs.json()["entries"][0]
    assert entry["status"] == "failed"
    assert entry["publication_target"] == "github"
    assert "ghp_secret-token" not in entry["error_summary"]


def test_feed_delete_logs_publication_with_deleted_feed_title_context(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    github_client = None

    def factory(config: GitHubPublicationConfig):
        nonlocal github_client
        github_client = FakeGitHubClient(config)
        return github_client

    app = create_app(settings=settings, imap_source=FakeImapSource(), github_client_factory=factory)
    store = app.state.store
    cipher = CredentialCipher(settings.secret_key)
    feed = create_feed(store, cipher, title="Deleted Feed", slug="deleted-random")
    store.update_publication_settings(
        {
            "active_target": PublicationTarget.GITHUB,
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret-token"),
        }
    )

    with TestClient(app) as client:
        login(client)
        response = client.delete(f"/api/feeds/{feed['id']}")
        logs = client.get(f"/api/activity-logs?feed_id={feed['id']}")

    assert response.status_code == 200
    assert store.get_feed(feed["id"]) is None
    assert github_client is not None
    entry = logs.json()["entries"][0]
    assert entry["operation_type"] == "publish"
    assert entry["trigger"] == "feed_change_publication"
    assert entry["feed_title"] == "Deleted Feed"
    assert entry["file_count"] == 2
