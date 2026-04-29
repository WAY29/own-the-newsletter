from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


ImapTls = Literal["ssl", "starttls", "none"]


class LoginRequest(BaseModel):
    token: str = Field(min_length=1)


class ImapPreviewBase(BaseModel):
    sender: str = Field(min_length=3, max_length=320)
    imap_host: str = Field(min_length=1, max_length=255)
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_tls: ImapTls = "ssl"
    imap_username: str = Field(min_length=1, max_length=320)
    folders: list[str] = Field(default_factory=lambda: ["INBOX"])

    @field_validator("folders")
    @classmethod
    def normalize_folders(cls, folders: list[str]) -> list[str]:
        normalized = [folder.strip() for folder in folders if folder.strip()]
        return normalized or ["INBOX"]

    @field_validator("sender")
    @classmethod
    def normalize_sender(cls, sender: str) -> str:
        return sender.strip()


class FeedBase(ImapPreviewBase):
    title: str = Field(min_length=1, max_length=200)
    backfill_days: int = Field(default=30, ge=0, le=3650)
    retention_count: int = Field(default=50, ge=1, le=1000)
    sync_interval_minutes: int = Field(default=60, ge=0, le=10080)


class FeedCreate(FeedBase):
    imap_password: str = Field(min_length=1, max_length=4096)


class FeedUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    sender: str | None = Field(default=None, min_length=3, max_length=320)
    imap_host: str | None = Field(default=None, min_length=1, max_length=255)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_tls: ImapTls | None = None
    imap_username: str | None = Field(default=None, min_length=1, max_length=320)
    imap_password: str | None = Field(default=None, min_length=1, max_length=4096)
    folders: list[str] | None = None
    backfill_days: int | None = Field(default=None, ge=0, le=3650)
    retention_count: int | None = Field(default=None, ge=1, le=1000)
    sync_interval_minutes: int | None = Field(default=None, ge=0, le=10080)

    @field_validator("folders")
    @classmethod
    def normalize_folders(cls, folders: list[str] | None) -> list[str] | None:
        if folders is None:
            return None
        normalized = [folder.strip() for folder in folders if folder.strip()]
        return normalized or ["INBOX"]

    @field_validator("sender")
    @classmethod
    def normalize_sender(cls, sender: str | None) -> str | None:
        return sender.strip() if sender is not None else None


class PreviewRequest(ImapPreviewBase):
    imap_password: str = Field(min_length=1, max_length=4096)
    limit_per_folder: int = Field(default=50, ge=1, le=200)
