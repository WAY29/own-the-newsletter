from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import logging
import sqlite3
import threading
from typing import Any

from .body_processor import BodyProcessor
from .email_parser import ParsedEmail, parse_email
from .feed_publisher import FeedPublisher
from .imap_source import FetchedMessage, ImapConfig, ImapSource, backfill_since
from .logging_config import safe_log_text
from .sender_matcher import extract_source_values, matches_source, normalize_match_text
from .security import CredentialCipher, redact_sensitive
from .store import MessageStore, folders_from_row
from .timeutil import parse_iso, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    status: str
    imported_count: int = 0
    skipped_count: int = 0
    error: str | None = None


class SyncEngine:
    def __init__(
        self,
        store: MessageStore,
        cipher: CredentialCipher,
        imap_source: ImapSource,
        body_processor: BodyProcessor,
        publisher: FeedPublisher,
        imap_timeout_seconds: int,
    ) -> None:
        self.store = store
        self.cipher = cipher
        self.imap_source = imap_source
        self.body_processor = body_processor
        self.publisher = publisher
        self.imap_timeout_seconds = imap_timeout_seconds
        self._locks: dict[int, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def validate_feed_settings(self, data: dict[str, Any], encrypted_password: str | None = None) -> None:
        password = data.get("imap_password")
        if password is None and encrypted_password is not None:
            password = self.cipher.decrypt(encrypted_password)
        if password is None:
            raise ValueError("IMAP password is required")
        config = self._imap_config_from_mapping(data, password=password)
        self.imap_source.validate(config)

    def preview(self, data: dict[str, Any]) -> dict[str, Any]:
        target = normalize_match_text(data["recipient"])
        config = self._imap_config_from_mapping(data, password=data["imap_password"])
        logger.info(
            "Preview started target=%s host=%s port=%s tls=%s username=%s folders=%s limit_per_folder=%s",
            redact_sensitive(target),
            safe_log_text(config.host),
            config.port,
            config.tls,
            redact_sensitive(config.username),
            config.folders,
            int(data.get("limit_per_folder", 50)),
        )
        self.imap_source.validate(config)
        messages = self.imap_source.preview_messages(config, limit_per_folder=int(data.get("limit_per_folder", 50)))
        samples: list[dict[str, str]] = []
        mismatch_debug_count = 0
        for message in messages:
            parsed = parse_email(message.raw_bytes)
            if not matches_source(parsed.source_headers, data["recipient"]):
                if mismatch_debug_count < 5:
                    mismatch_debug_count += 1
                    logger.debug(
                        "Preview skipped non-matching message folder=%s uid=%s subject=%s sender=%s sources=%s",
                        safe_log_text(message.folder),
                        message.uid,
                        safe_log_text(parsed.subject),
                        redact_sensitive(parsed.author),
                        _safe_values(extract_source_values(parsed.source_headers)),
                    )
                continue
            samples.append(
                {
                    "folder": message.folder,
                    "uid": str(message.uid),
                    "subject": parsed.subject,
                    "author": parsed.author,
                    "published_at": parsed.published_at,
                }
            )
        logger.info(
            "Preview finished target=%s scanned=%s matches=%s",
            redact_sensitive(target),
            len(messages),
            len(samples),
        )
        return {
            "match_count": len(samples),
            "samples": samples[:10],
            "scanned_count": len(messages),
        }

    def sync_feed(self, feed_id: int, *, manual: bool) -> SyncResult:
        lock = self._lock_for(feed_id)
        if not lock.acquire(blocking=False):
            self.store.mark_sync_finished(
                feed_id,
                status="skipped",
                imported_count=0,
                skipped_count=0,
                error="Sync skipped because another sync is already running.",
            )
            return SyncResult(status="skipped")
        try:
            feed = self.store.get_feed(feed_id)
            if feed is None:
                return SyncResult(status="missing", error="Feed not found")
            self.store.mark_sync_started(feed_id)
            result = self._sync_single_feed(feed)
            self.store.mark_sync_finished(
                feed_id,
                status=result.status,
                imported_count=result.imported_count,
                skipped_count=result.skipped_count,
                error=result.error,
                first_sync_completed=result.status == "success",
            )
            if result.status == "success":
                self.publisher.publish_by_id(feed_id)
            return result
        except Exception as exc:  # pragma: no cover - exercised through integration
            error = redact_sensitive(str(exc))
            self.store.mark_sync_finished(
                feed_id,
                status="failed",
                imported_count=0,
                skipped_count=0,
                error=error,
            )
            return SyncResult(status="failed", error=error)
        finally:
            lock.release()

    def sync_due_feeds(self) -> list[SyncResult]:
        feeds = self.store.feeds_due_for_sync()
        return self.sync_feeds_grouped([int(feed["id"]) for feed in feeds])

    def sync_feeds_grouped(self, feed_ids: list[int]) -> list[SyncResult]:
        feeds = [self.store.get_feed(feed_id) for feed_id in feed_ids]
        feeds = [feed for feed in feeds if feed is not None]
        acquired: list[tuple[int, threading.Lock]] = []
        runnable: list[sqlite3.Row] = []
        results: list[SyncResult] = []
        for feed in feeds:
            feed_id = int(feed["id"])
            lock = self._lock_for(feed_id)
            if not lock.acquire(blocking=False):
                results.append(SyncResult(status="skipped"))
                continue
            acquired.append((feed_id, lock))
            runnable.append(feed)
            self.store.mark_sync_started(feed_id)
        try:
            groups: dict[str, list[sqlite3.Row]] = defaultdict(list)
            for feed in runnable:
                groups[self.mailbox_group_key(feed)].append(feed)
            per_feed: dict[int, SyncResult] = {}
            for group_feeds in groups.values():
                per_feed.update(self._sync_group(group_feeds))
            for feed in runnable:
                feed_id = int(feed["id"])
                result = per_feed.get(feed_id, SyncResult(status="success"))
                self.store.mark_sync_finished(
                    feed_id,
                    status=result.status,
                    imported_count=result.imported_count,
                    skipped_count=result.skipped_count,
                    error=result.error,
                    first_sync_completed=result.status == "success",
                )
                if result.status == "success":
                    self.publisher.publish_by_id(feed_id)
                results.append(result)
            return results
        except Exception as exc:  # pragma: no cover - defensive
            error = redact_sensitive(str(exc))
            for feed in runnable:
                self.store.mark_sync_finished(
                    int(feed["id"]),
                    status="failed",
                    imported_count=0,
                    skipped_count=0,
                    error=error,
                )
                results.append(SyncResult(status="failed", error=error))
            return results
        finally:
            for _feed_id, lock in acquired:
                lock.release()

    def mailbox_group_key(self, feed: sqlite3.Row) -> str:
        payload = {
            "host": feed["imap_host"],
            "port": feed["imap_port"],
            "tls": feed["imap_tls"],
            "username": feed["imap_username"],
            "folders": sorted(folders_from_row(feed)),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def account_key(self, feed: sqlite3.Row) -> str:
        payload = {
            "host": feed["imap_host"],
            "port": feed["imap_port"],
            "tls": feed["imap_tls"],
            "username": feed["imap_username"],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _sync_single_feed(self, feed: sqlite3.Row) -> SyncResult:
        password = self.cipher.decrypt(feed["imap_password_encrypted"])
        config = self._imap_config_from_feed(feed, password=password)
        account_key = self.account_key(feed)
        imported = 0
        skipped = 0
        for folder in folders_from_row(feed):
            cursor = self.store.get_cursor(int(feed["id"]), account_key, folder)
            uid_start = None
            since = None
            if cursor is not None and int(feed["first_sync_completed"]):
                uid_start = int(cursor["last_uid"]) + 1
            elif not int(feed["first_sync_completed"]):
                since = backfill_since(int(feed["backfill_days"]))
            messages = self.imap_source.fetch_messages(config, folder, uid_start=uid_start, since=since)
            folder_result = self._process_messages_for_feed(feed, account_key, messages)
            imported += folder_result.imported_count
            skipped += folder_result.skipped_count
            self._advance_cursor(feed, account_key, folder, messages)
        self.store.apply_retention(int(feed["id"]), int(feed["retention_count"]))
        return SyncResult(status="success", imported_count=imported, skipped_count=skipped)

    def _sync_group(self, feeds: list[sqlite3.Row]) -> dict[int, SyncResult]:
        first = feeds[0]
        password = self.cipher.decrypt(first["imap_password_encrypted"])
        config = self._imap_config_from_feed(first, password=password)
        account_key = self.account_key(first)
        totals = {int(feed["id"]): {"imported": 0, "skipped": 0} for feed in feeds}
        for folder in folders_from_row(first):
            messages = self._fetch_group_folder_messages(feeds, config, account_key, folder)
            parsed_cache: dict[tuple[str, int], ParsedEmail] = {}
            body_cache: dict[tuple[str, int], Any] = {}
            for feed in feeds:
                eligible = self._eligible_messages_for_feed(feed, account_key, folder, messages)
                for message in eligible:
                    cache_key = (message.folder, message.uid)
                    parsed = parsed_cache.get(cache_key)
                    if parsed is None:
                        parsed = parse_email(message.raw_bytes)
                        parsed_cache[cache_key] = parsed
                    if not matches_source(parsed.source_headers, feed["recipient"]):
                        totals[int(feed["id"])]["skipped"] += 1
                        continue
                    processed = body_cache.get(cache_key)
                    if processed is None:
                        processed = self.body_processor.process(parsed.raw_html)
                        body_cache[cache_key] = processed
                    imported_message_id = self.store.upsert_imported_message(
                        {
                            "account_key": account_key,
                            "folder": message.folder,
                            "uidvalidity": message.uidvalidity,
                            "uid": message.uid,
                            "message_id": parsed.message_id,
                            "subject": parsed.subject,
                            "author": parsed.author,
                            "published_at": parsed.published_at,
                            "raw_html": processed.raw_html,
                            "sanitized_html": processed.sanitized_html,
                            "summary": processed.summary,
                        }
                    )
                    _item_id, created = self.store.link_feed_item(int(feed["id"]), imported_message_id)
                    if created:
                        totals[int(feed["id"])]["imported"] += 1
                self._advance_cursor(feed, account_key, folder, eligible)
        results: dict[int, SyncResult] = {}
        for feed in feeds:
            feed_id = int(feed["id"])
            self.store.apply_retention(feed_id, int(feed["retention_count"]))
            results[feed_id] = SyncResult(
                status="success",
                imported_count=totals[feed_id]["imported"],
                skipped_count=totals[feed_id]["skipped"],
            )
        return results

    def _process_messages_for_feed(
        self,
        feed: sqlite3.Row,
        account_key: str,
        messages: list[FetchedMessage],
    ) -> SyncResult:
        imported = 0
        skipped = 0
        for message in messages:
            parsed = parse_email(message.raw_bytes)
            if not matches_source(parsed.source_headers, feed["recipient"]):
                skipped += 1
                continue
            processed = self.body_processor.process(parsed.raw_html)
            imported_message_id = self.store.upsert_imported_message(
                {
                    "account_key": account_key,
                    "folder": message.folder,
                    "uidvalidity": message.uidvalidity,
                    "uid": message.uid,
                    "message_id": parsed.message_id,
                    "subject": parsed.subject,
                    "author": parsed.author,
                    "published_at": parsed.published_at,
                    "raw_html": processed.raw_html,
                    "sanitized_html": processed.sanitized_html,
                    "summary": processed.summary,
                }
            )
            _item_id, created = self.store.link_feed_item(int(feed["id"]), imported_message_id)
            if created:
                imported += 1
        return SyncResult(status="success", imported_count=imported, skipped_count=skipped)

    def _fetch_group_folder_messages(
        self,
        feeds: list[sqlite3.Row],
        config: ImapConfig,
        account_key: str,
        folder: str,
    ) -> list[FetchedMessage]:
        any_initial = any(not int(feed["first_sync_completed"]) for feed in feeds)
        if any_initial:
            max_backfill = max(int(feed["backfill_days"]) for feed in feeds)
            return self.imap_source.fetch_messages(config, folder, since=backfill_since(max_backfill))
        cursor_values: list[int] = []
        for feed in feeds:
            cursor = self.store.get_cursor(int(feed["id"]), account_key, folder)
            if cursor is not None:
                cursor_values.append(int(cursor["last_uid"]))
        uid_start = min(cursor_values) + 1 if cursor_values else None
        return self.imap_source.fetch_messages(config, folder, uid_start=uid_start)

    def _eligible_messages_for_feed(
        self,
        feed: sqlite3.Row,
        account_key: str,
        folder: str,
        messages: list[FetchedMessage],
    ) -> list[FetchedMessage]:
        cursor = self.store.get_cursor(int(feed["id"]), account_key, folder)
        if cursor is not None and int(feed["first_sync_completed"]):
            last_uid = int(cursor["last_uid"])
            return [message for message in messages if message.uid > last_uid]
        if int(feed["first_sync_completed"]):
            return messages
        backfill_days = int(feed["backfill_days"])
        if backfill_days <= 0:
            return messages
        cutoff = utc_now() - timedelta(days=backfill_days)
        eligible: list[FetchedMessage] = []
        for message in messages:
            try:
                parsed = parse_email(message.raw_bytes)
                published = parse_iso(parsed.published_at)
            except Exception:
                published = None
            if published is None or published >= cutoff:
                eligible.append(message)
        return eligible

    def _advance_cursor(
        self,
        feed: sqlite3.Row,
        account_key: str,
        folder: str,
        messages: list[FetchedMessage],
    ) -> None:
        if not messages:
            return
        max_message = max(messages, key=lambda message: message.uid)
        self.store.upsert_cursor(int(feed["id"]), account_key, folder, max_message.uidvalidity, max_message.uid)

    def _imap_config_from_feed(self, feed: sqlite3.Row, *, password: str) -> ImapConfig:
        return ImapConfig(
            host=feed["imap_host"],
            port=int(feed["imap_port"]),
            tls=feed["imap_tls"],
            username=feed["imap_username"],
            password=password,
            folders=folders_from_row(feed),
            timeout_seconds=self.imap_timeout_seconds,
        )

    def _imap_config_from_mapping(self, data: dict[str, Any], *, password: str) -> ImapConfig:
        return ImapConfig(
            host=data["imap_host"],
            port=int(data["imap_port"]),
            tls=data["imap_tls"],
            username=data["imap_username"],
            password=password,
            folders=list(data["folders"]),
            timeout_seconds=self.imap_timeout_seconds,
        )

    def _lock_for(self, feed_id: int) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(feed_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[feed_id] = lock
            return lock


def _safe_values(values: list[str]) -> list[str]:
    return sorted(redact_sensitive(value) for value in values)
