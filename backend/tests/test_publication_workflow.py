from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.imap_source import FetchedMessage
from app.main import create_app
from app.publication import GitHubFileChange, GitHubPublicationConfig, PublicationError
from app.security import CredentialCipher


class FakeImapSource:
    def __init__(self) -> None:
        self.fetch_calls = []
        self.messages = [
            FetchedMessage(
                "INBOX",
                "1",
                1,
                (
                    "From: Sender <target@example.test>\n"
                    "To: mailbox@example.test\n"
                    "Subject: One\n"
                    "Date: Wed, 29 Apr 2026 10:01:00 +0000\n"
                    "Message-ID: <1@example.test>\n"
                    "Content-Type: text/html; charset=utf-8\n\n"
                    "<p>Body</p>"
                ).encode(),
            )
        ]

    def validate(self, config) -> None:
        return None

    def preview_messages(self, config, limit_per_folder: int = 50):
        return []

    def fetch_messages(self, config, folder: str, *, uid_start=None, since=None, limit=None):
        self.fetch_calls.append({"folder": folder, "uid_start": uid_start, "since": since, "limit": limit})
        return self.messages


class FakeGitHubClient:
    def __init__(self, config: GitHubPublicationConfig, *, fail_upsert: bool = False) -> None:
        self.config = config
        self.fail_upsert = fail_upsert
        self.validated = False
        self.upserts = []
        self.deletes = []
        self.commits = []

    def validate_write_access(self) -> None:
        self.validated = True

    def commit_files(self, changes: list[GitHubFileChange], message: str) -> None:
        if self.fail_upsert:
            raise PublicationError(f"GitHub rejected token {self.config.token}")
        self.commits.append({"changes": changes, "message": message})
        for change in changes:
            if change.content is not None:
                self.upserts.append({"path": change.path, "content": change.content, "message": message})

    def upsert_file(self, path: str, content: str, message: str) -> None:
        if self.fail_upsert:
            raise PublicationError(f"GitHub rejected token {self.config.token}")
        self.upserts.append({"path": path, "content": content, "message": message})

    def delete_files(self, paths: list[str], message: str) -> None:
        self.commits.append({"changes": [GitHubFileChange(path, None) for path in paths], "message": message})
        for path in paths:
            self.deletes.append({"path": path, "message": message})

    def delete_file(self, path: str, message: str) -> None:
        self.deletes.append({"path": path, "message": message})


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


def save_github_settings(client: TestClient) -> None:
    response = client.put(
        "/api/publication/settings",
        json={
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token": "ghp_secret-token",
        },
    )
    assert response.status_code == 200


def test_activate_github_publishes_all_feeds_before_switching_target(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    source = FakeImapSource()
    github_client = None

    def factory(config: GitHubPublicationConfig):
        nonlocal github_client
        github_client = FakeGitHubClient(config)
        return github_client

    app = create_app(settings=settings, imap_source=source, github_client_factory=factory)
    cipher = CredentialCipher(settings.secret_key)
    feed = create_feed(app.state.store, cipher)
    create_feed(app.state.store, cipher, title="Second Feed", slug="second-random")
    message_id = app.state.store.upsert_imported_message(
        {
            "account_key": "account",
            "folder": "INBOX",
            "uidvalidity": "1",
            "uid": 1,
            "message_id": "<1@example.test>",
            "subject": "Subject",
            "author": "Sender",
            "published_at": "2026-04-29T00:00:00+00:00",
            "raw_html": "<p>Raw</p>",
            "sanitized_html": "<p>Clean</p>",
            "summary": "Summary",
        }
    )
    app.state.store.link_feed_item(feed["id"], message_id)

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        save_github_settings(client)
        response = client.post("/api/publication/github/activate")

    assert response.status_code == 200
    body = response.json()["settings"]
    assert body["active_target"] == "github"
    assert body["last_publication_status"] == "success"
    assert github_client is not None
    assert github_client.validated is True
    assert len(github_client.commits) == 1
    assert "Feed" in github_client.commits[0]["message"]
    assert "Second Feed" in github_client.commits[0]["message"]
    assert {change.path for change in github_client.commits[0]["changes"]} == {
        "feeds/random.xml",
        "feeds/random.raw.xml",
        "feeds/second-random.xml",
        "feeds/second-random.raw.xml",
    }
    assert {item["path"] for item in github_client.upserts} == {
        "feeds/random.xml",
        "feeds/random.raw.xml",
        "feeds/second-random.xml",
        "feeds/second-random.raw.xml",
    }
    random_file = next(item for item in github_client.upserts if item["path"] == "feeds/random.xml")
    assert "https://cdn.example.test/rss/feeds/random.xml" in random_file["content"]


def test_failed_github_activation_does_not_switch_active_target(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)

    def factory(config: GitHubPublicationConfig):
        return FakeGitHubClient(config, fail_upsert=True)

    app = create_app(settings=settings, imap_source=FakeImapSource(), github_client_factory=factory)
    create_feed(app.state.store, CredentialCipher(settings.secret_key))

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        save_github_settings(client)
        response = client.post("/api/publication/github/activate")
        reread = client.get("/api/publication/settings")

    assert response.status_code == 400
    settings_body = reread.json()["settings"]
    assert settings_body["active_target"] == "backend"
    assert settings_body["last_publication_status"] == "failed"
    assert "ghp_secret-token" not in settings_body["last_publication_error"]


def test_github_activation_reports_invalid_stored_token_without_header_codec_error(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings=settings, imap_source=FakeImapSource())
    cipher = CredentialCipher(settings.secret_key)
    create_feed(app.state.store, cipher)
    app.state.store.update_publication_settings(
        {
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret◊token"),
        }
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.post("/api/publication/github/activate")

    assert response.status_code == 400
    assert "printable ASCII" in response.text
    assert "latin-1" not in response.text


def test_publication_retry_does_not_fetch_imap_or_change_sync_status(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    source = FakeImapSource()
    github_client = None

    def factory(config: GitHubPublicationConfig):
        nonlocal github_client
        github_client = FakeGitHubClient(config)
        return github_client

    app = create_app(settings=settings, imap_source=source, github_client_factory=factory)
    store = app.state.store
    cipher = CredentialCipher(settings.secret_key)
    feed = create_feed(store, cipher)
    store.mark_sync_finished(feed["id"], status="success", imported_count=3, skipped_count=1)
    store.update_publication_settings(
        {
            "active_target": "github",
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret-token"),
        }
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.post("/api/publication/retry")

    assert response.status_code == 200
    assert source.fetch_calls == []
    assert github_client is not None
    assert len(github_client.commits) == 1
    assert "Feed" in github_client.commits[0]["message"]
    assert [item["path"] for item in github_client.upserts] == ["feeds/random.xml", "feeds/random.raw.xml"]
    refreshed = store.get_feed(feed["id"])
    assert refreshed["last_sync_status"] == "success"
    assert refreshed["last_sync_imported_count"] == 3
    assert refreshed["last_sync_skipped_count"] == 1


def test_sync_success_and_publication_failure_are_reported_separately(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)

    def factory(config: GitHubPublicationConfig):
        return FakeGitHubClient(config, fail_upsert=True)

    app = create_app(settings=settings, imap_source=FakeImapSource(), github_client_factory=factory)
    store = app.state.store
    cipher = CredentialCipher(settings.secret_key)
    feed = create_feed(store, cipher)
    store.update_publication_settings(
        {
            "active_target": "github",
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret-token"),
        }
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.post(f"/api/feeds/{feed['id']}/sync")
        publication = client.get("/api/publication/settings")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    refreshed = store.get_feed(feed["id"])
    assert refreshed["last_sync_status"] == "success"
    assert publication.json()["settings"]["last_publication_status"] == "failed"


def test_create_edit_and_scheduled_sync_publish_to_active_github_target(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    github_client = None

    def factory(config: GitHubPublicationConfig):
        nonlocal github_client
        github_client = FakeGitHubClient(config)
        return github_client

    app = create_app(settings=settings, imap_source=FakeImapSource(), github_client_factory=factory)
    store = app.state.store
    cipher = CredentialCipher(settings.secret_key)
    store.update_publication_settings(
        {
            "active_target": "github",
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret-token"),
        }
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        created = client.post("/api/feeds", json=feed_payload())
        assert created.status_code == 200
        created_id = created.json()["feed"]["id"]

        assert github_client is not None
        assert len(github_client.commits) == 1
        assert "Feed" in github_client.commits[-1]["message"]
        assert "feeds/" in github_client.upserts[-2]["path"]
        github_client.upserts.clear()
        github_client.commits.clear()

        updated = client.put(f"/api/feeds/{created_id}", json={"title": "Updated"})
        assert updated.status_code == 200
        assert len(github_client.commits) == 1
        assert "Updated" in github_client.commits[-1]["message"]
        assert [item["path"] for item in github_client.upserts] == [
            f"feeds/{created.json()['feed']['random_slug']}.xml",
            f"feeds/{created.json()['feed']['random_slug']}.raw.xml",
        ]

    github_client.upserts.clear()
    github_client.commits.clear()
    due_feed = create_feed(store, cipher)
    results = app.state.sync_engine.sync_due_feeds()

    assert results[-1].status == "success"
    assert len(github_client.commits) == 1
    assert "Feed" in github_client.commits[-1]["message"]
    assert [item["path"] for item in github_client.upserts[-2:]] == ["feeds/random.xml", "feeds/random.raw.xml"]


def test_deleting_feed_removes_github_static_files_when_github_is_active(tmp_path: Path) -> None:
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
    store.update_publication_settings(
        {
            "active_target": "github",
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret-token"),
        }
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        response = client.delete(f"/api/feeds/{feed['id']}")

    assert response.status_code == 200
    assert github_client is not None
    assert len(github_client.commits) == 1
    assert "Feed" in github_client.commits[0]["message"]
    assert [item["path"] for item in github_client.deletes] == ["feeds/random.xml", "feeds/random.raw.xml"]


def test_switching_back_to_backend_stops_github_pushes(tmp_path: Path) -> None:
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
    store.update_publication_settings(
        {
            "active_target": "github",
            "github_repository": "owner/repo",
            "github_branch": "pages",
            "github_directory": "feeds",
            "github_public_url": "https://cdn.example.test/rss",
            "github_token_encrypted": cipher.encrypt("ghp_secret-token"),
        }
    )

    with TestClient(app) as client:
        client.post("/api/auth/login", json={"token": "admin-token"})
        switch_response = client.post("/api/publication/backend/activate")
        update_response = client.put(f"/api/feeds/{feed['id']}", json={"title": "Updated"})

    assert switch_response.status_code == 200
    assert switch_response.json()["settings"]["active_target"] == "backend"
    assert update_response.status_code == 200
    assert update_response.json()["feed"]["feed_url"] == "https://backend.example.test/f/random.xml"
    assert github_client is None
