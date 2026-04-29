from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import SESSION_COOKIE, create_app


def test_login_sets_httponly_session_cookie(tmp_path: Path) -> None:
    settings = Settings(
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

