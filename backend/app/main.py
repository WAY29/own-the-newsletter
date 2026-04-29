from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
import secrets
from typing import Annotated, Any

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse

from .body_processor import BodyProcessor
from .config import Settings, get_settings
from .feed_publisher import FeedPublisher
from .imap_source import ImapSource
from .schemas import FeedCreate, FeedUpdate, LoginRequest, PreviewRequest
from .scheduler import BackendScheduler
from .security import CredentialCipher, constant_time_equal, new_secret_token, token_hash
from .store import MessageStore, folders_from_row
from .sync_engine import SyncEngine
from .timeutil import iso_now, parse_iso, utc_now

SESSION_COOKIE = "onn_session"


def create_app(settings: Settings | None = None, imap_source: ImapSource | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_paths()
    store = MessageStore(settings.database_path)
    store.init_db()
    cipher = CredentialCipher(settings.secret_key)
    publisher = FeedPublisher(store, settings.feeds_dir, settings.public_origin)
    sync_engine = SyncEngine(
        store=store,
        cipher=cipher,
        imap_source=imap_source or ImapSource(),
        body_processor=BodyProcessor(),
        publisher=publisher,
        imap_timeout_seconds=settings.imap_timeout_seconds,
    )
    scheduler = BackendScheduler(sync_engine, settings.scheduler_tick_seconds)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if settings.scheduler_enabled:
            scheduler.start()
        yield
        await scheduler.stop()

    app = FastAPI(title="Own New Newsletter", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.sync_engine = sync_engine
    app.state.publisher = publisher

    def require_admin(session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> bool:
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        session = store.get_session(token_hash(session_token))
        if session is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        expires_at = parse_iso(session["expires_at"])
        if expires_at is None or expires_at <= utc_now():
            store.delete_session(token_hash(session_token))
            raise HTTPException(status_code=401, detail="Session expired")
        return True

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/login")
    def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
        if not constant_time_equal(payload.token, settings.admin_token):
            raise HTTPException(status_code=401, detail="Invalid token")
        session_token = new_secret_token()
        expires_at = utc_now() + timedelta(days=settings.session_days)
        store.create_session(token_hash(session_token), expires_at.isoformat())
        response.set_cookie(
            SESSION_COOKIE,
            session_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.session_days * 24 * 60 * 60,
            path="/",
        )
        return {"authenticated": True, "expires_at": expires_at.isoformat()}

    @app.post("/api/auth/logout")
    def logout(
        response: Response,
        _admin: bool = Depends(require_admin),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> dict[str, bool]:
        if session_token:
            store.delete_session(token_hash(session_token))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"authenticated": False}

    @app.get("/api/auth/me")
    def me(_admin: bool = Depends(require_admin)) -> dict[str, bool]:
        return {"authenticated": True}

    @app.get("/api/feeds")
    def list_feeds(_admin: bool = Depends(require_admin)) -> dict[str, Any]:
        return {"feeds": [_serialize_feed(feed, settings) for feed in store.list_feeds()]}

    @app.post("/api/feeds/preview")
    def preview_feed(payload: PreviewRequest, _admin: bool = Depends(require_admin)) -> dict[str, Any]:
        try:
            return sync_engine.preview(payload.model_dump())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/feeds")
    def create_feed(payload: FeedCreate, _admin: bool = Depends(require_admin)) -> dict[str, Any]:
        data = payload.model_dump()
        try:
            sync_engine.validate_feed_settings(data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        password = data.pop("imap_password")
        data["imap_password_encrypted"] = cipher.encrypt(password)
        data["random_slug"] = secrets.token_urlsafe(24)
        feed = store.create_feed(data)
        publisher.publish(feed)
        return {"feed": _serialize_feed(feed, settings)}

    @app.get("/api/feeds/{feed_id}")
    def get_feed(feed_id: int, _admin: bool = Depends(require_admin)) -> dict[str, Any]:
        feed = store.get_feed(feed_id)
        if feed is None:
            raise HTTPException(status_code=404, detail="Feed not found")
        return {"feed": _serialize_feed(feed, settings)}

    @app.put("/api/feeds/{feed_id}")
    def update_feed(feed_id: int, payload: FeedUpdate, _admin: bool = Depends(require_admin)) -> dict[str, Any]:
        existing = store.get_feed(feed_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Feed not found")
        updates = payload.model_dump(exclude_unset=True)
        if "imap_password" in updates:
            updates["imap_password_encrypted"] = cipher.encrypt(updates.pop("imap_password"))
        validation_data = _feed_row_to_validation_data(existing, cipher)
        validation_data.update(updates)
        if "imap_password_encrypted" in validation_data:
            validation_data["imap_password"] = cipher.decrypt(validation_data.pop("imap_password_encrypted"))
        try:
            sync_engine.validate_feed_settings(validation_data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        feed = store.update_feed(feed_id, updates)
        if feed is None:
            raise HTTPException(status_code=404, detail="Feed not found")
        publisher.publish(feed)
        return {"feed": _serialize_feed(feed, settings)}

    @app.delete("/api/feeds/{feed_id}")
    def delete_feed(feed_id: int, _admin: bool = Depends(require_admin)) -> dict[str, bool]:
        feed = store.get_feed(feed_id)
        if feed is None:
            raise HTTPException(status_code=404, detail="Feed not found")
        publisher.delete_files(feed["random_slug"])
        store.delete_feed(feed_id)
        return {"deleted": True}

    @app.post("/api/feeds/{feed_id}/sync")
    def sync_feed(feed_id: int, _admin: bool = Depends(require_admin)) -> dict[str, Any]:
        if store.get_feed(feed_id) is None:
            raise HTTPException(status_code=404, detail="Feed not found")
        result = sync_engine.sync_feed(feed_id, manual=True)
        return result.__dict__

    @app.get("/api/feeds/{feed_id}/status")
    def feed_status(feed_id: int, _admin: bool = Depends(require_admin)) -> dict[str, Any]:
        feed = store.get_feed(feed_id)
        if feed is None:
            raise HTTPException(status_code=404, detail="Feed not found")
        return {"status": _serialize_status(feed)}

    @app.get("/f/{slug}.xml")
    def rss_feed(slug: str, body: str = "clean") -> FileResponse:
        feed = store.get_feed_by_slug(slug)
        if feed is None:
            raise HTTPException(status_code=404, detail="Feed not found")
        raw = body == "raw"
        path = publisher.feed_path(slug, raw=raw)
        if not path.exists():
            publisher.publish(feed)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Feed file not found")
        return FileResponse(path, media_type="application/rss+xml; charset=utf-8")

    return app


def _serialize_feed(feed, settings: Settings) -> dict[str, Any]:
    return {
        "id": feed["id"],
        "title": feed["title"],
        "recipient": feed["recipient"],
        "imap_host": feed["imap_host"],
        "imap_port": feed["imap_port"],
        "imap_tls": feed["imap_tls"],
        "imap_username": feed["imap_username"],
        "folders": folders_from_row(feed),
        "random_slug": feed["random_slug"],
        "feed_url": f"{settings.public_origin}/f/{feed['random_slug']}.xml",
        "raw_feed_url": f"{settings.public_origin}/f/{feed['random_slug']}.xml?body=raw",
        "backfill_days": feed["backfill_days"],
        "retention_count": feed["retention_count"],
        "sync_interval_minutes": feed["sync_interval_minutes"],
        "created_at": feed["created_at"],
        "updated_at": feed["updated_at"],
        "sync_status": _serialize_status(feed),
    }


def _serialize_status(feed) -> dict[str, Any]:
    return {
        "first_sync_completed": bool(feed["first_sync_completed"]),
        "last_sync_started_at": feed["last_sync_started_at"],
        "last_sync_finished_at": feed["last_sync_finished_at"],
        "last_sync_status": feed["last_sync_status"],
        "last_sync_error": feed["last_sync_error"],
        "last_sync_imported_count": feed["last_sync_imported_count"],
        "last_sync_skipped_count": feed["last_sync_skipped_count"],
    }


def _feed_row_to_validation_data(feed, cipher: CredentialCipher) -> dict[str, Any]:
    return {
        "title": feed["title"],
        "recipient": feed["recipient"],
        "imap_host": feed["imap_host"],
        "imap_port": feed["imap_port"],
        "imap_tls": feed["imap_tls"],
        "imap_username": feed["imap_username"],
        "imap_password": cipher.decrypt(feed["imap_password_encrypted"]),
        "folders": folders_from_row(feed),
        "backfill_days": feed["backfill_days"],
        "retention_count": feed["retention_count"],
        "sync_interval_minutes": feed["sync_interval_minutes"],
    }


app = create_app()
