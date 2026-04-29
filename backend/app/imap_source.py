from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import imaplib
from typing import Iterable

_IMAP_CLIENT_ID = '("name" "Own New Newsletter" "version" "0.1.0" "vendor" "own-the-newsletter")'


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    tls: str
    username: str
    password: str
    folders: list[str]
    timeout_seconds: int = 30


@dataclass(frozen=True)
class FetchedMessage:
    folder: str
    uidvalidity: str
    uid: int
    raw_bytes: bytes


class ImapSource:
    def validate(self, config: ImapConfig) -> None:
        with self._session(config) as client:
            for folder in config.folders:
                self._select_folder(client, folder)

    def fetch_messages(
        self,
        config: ImapConfig,
        folder: str,
        *,
        uid_start: int | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[FetchedMessage]:
        with self._session(config) as client:
            uidvalidity = self._select_folder(client, folder)
            uids = self._search_uids(client, uid_start=uid_start, since=since)
            if limit is not None:
                uids = uids[-limit:]
            messages: list[FetchedMessage] = []
            for uid in uids:
                typ, data = client.uid("FETCH", str(uid), "(RFC822)")
                if typ != "OK":
                    continue
                raw = self._extract_fetch_bytes(data)
                if raw is None:
                    continue
                messages.append(FetchedMessage(folder=folder, uidvalidity=uidvalidity, uid=uid, raw_bytes=raw))
            return messages

    def preview_messages(self, config: ImapConfig, limit_per_folder: int = 50) -> list[FetchedMessage]:
        messages: list[FetchedMessage] = []
        for folder in config.folders:
            messages.extend(self.fetch_messages(config, folder, limit=limit_per_folder))
        return messages

    def _session(self, config: ImapConfig) -> "_ImapSession":
        return _ImapSession(config)

    def _select_folder(self, client: imaplib.IMAP4, folder: str) -> str:
        typ, data = client.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            detail = _format_imap_response(data)
            message = f"Could not select IMAP folder: {folder}"
            if detail:
                message = f"{message} ({detail})"
            raise RuntimeError(message)
        response = client.response("UIDVALIDITY")
        if response and response[1] and response[1][0]:
            value = response[1][0]
            if isinstance(value, bytes):
                return value.decode("ascii", errors="replace")
            return str(value)
        return "0"

    def _search_uids(
        self,
        client: imaplib.IMAP4,
        *,
        uid_start: int | None,
        since: datetime | None,
    ) -> list[int]:
        if uid_start is not None:
            typ, data = client.uid("SEARCH", None, f"UID {uid_start}:*")
        elif since is not None:
            date_value = since.strftime("%d-%b-%Y")
            typ, data = client.uid("SEARCH", None, "SINCE", date_value)
        else:
            typ, data = client.uid("SEARCH", None, "ALL")
        if typ != "OK" or not data:
            return []
        raw = data[0] or b""
        if isinstance(raw, str):
            raw = raw.encode("ascii")
        return sorted(int(uid) for uid in raw.split() if uid.isdigit())

    def _extract_fetch_bytes(self, data: Iterable[object]) -> bytes | None:
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                return item[1]
        return None


class _ImapSession:
    def __init__(self, config: ImapConfig) -> None:
        self._config = config
        self._client: imaplib.IMAP4 | None = None

    def __enter__(self) -> imaplib.IMAP4:
        tls = self._config.tls.lower()
        if tls == "ssl":
            client: imaplib.IMAP4 = imaplib.IMAP4_SSL(
                self._config.host,
                self._config.port,
                timeout=self._config.timeout_seconds,
            )
        else:
            client = imaplib.IMAP4(self._config.host, self._config.port, timeout=self._config.timeout_seconds)
            if tls == "starttls":
                client.starttls()
        client.login(self._config.username, self._config.password)
        self._identify_client(client)
        self._client = client
        return client

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._client is None:
            return
        try:
            self._client.close()
        except imaplib.IMAP4.error:
            pass
        try:
            self._client.logout()
        finally:
            self._client = None

    def _identify_client(self, client: imaplib.IMAP4) -> None:
        try:
            client.xatom("ID", _IMAP_CLIENT_ID)
        except imaplib.IMAP4.error:
            return


def backfill_since(days: int) -> datetime | None:
    if days <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _format_imap_response(data: Iterable[object] | None) -> str:
    if not data:
        return ""
    parts: list[str] = []
    for item in data:
        if item is None:
            continue
        if isinstance(item, bytes):
            parts.append(item.decode("utf-8", errors="replace"))
        else:
            parts.append(str(item))
    return "; ".join(part for part in parts if part)
