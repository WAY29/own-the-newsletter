from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    admin_token: str
    secret_key: str
    database_path: Path
    feeds_dir: Path
    public_origin: str
    cookie_secure: bool
    session_days: int
    scheduler_enabled: bool
    scheduler_tick_seconds: int
    imap_timeout_seconds: int
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            admin_token=os.getenv("OTN_ADMIN_TOKEN", "change-this-admin-token"),
            secret_key=os.getenv("OTN_SECRET_KEY", "change-this-long-random-secret-key"),
            database_path=Path(os.getenv("OTN_DATABASE_PATH", "./data/own-newsletter.sqlite")),
            feeds_dir=Path(os.getenv("OTN_FEEDS_DIR", "./data/feeds")),
            public_origin=os.getenv("OTN_PUBLIC_ORIGIN", "http://localhost:8000").rstrip("/"),
            cookie_secure=_bool_env("OTN_COOKIE_SECURE", False),
            session_days=_int_env("OTN_SESSION_DAYS", 30),
            scheduler_enabled=_bool_env("OTN_SCHEDULER_ENABLED", True),
            scheduler_tick_seconds=_int_env("OTN_SCHEDULER_TICK_SECONDS", 60),
            imap_timeout_seconds=_int_env("OTN_IMAP_TIMEOUT_SECONDS", 30),
            log_level=os.getenv("OTN_LOG_LEVEL", "INFO"),
        )

    def ensure_paths(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.feeds_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings.from_env()
    settings.ensure_paths()
    return settings
