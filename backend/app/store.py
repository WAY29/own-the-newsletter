from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
import sqlite3
from typing import Any

from .timeutil import iso_now, parse_iso, utc_now

FEED_SORT_COLUMNS = {
    "created_at": "fr.created_at",
    "updated_at": "fr.updated_at",
    "title": "LOWER(fr.title)",
    "item_count": "COALESCE(item_counts.item_count, 0)",
    "last_sync": "fr.last_sync_finished_at",
}


class MessageStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS feed_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    imap_host TEXT NOT NULL,
                    imap_port INTEGER NOT NULL,
                    imap_tls TEXT NOT NULL,
                    imap_username TEXT NOT NULL,
                    imap_password_encrypted TEXT NOT NULL,
                    folders_json TEXT NOT NULL,
                    random_slug TEXT NOT NULL UNIQUE,
                    backfill_days INTEGER NOT NULL,
                    retention_count INTEGER NOT NULL,
                    sync_interval_minutes INTEGER NOT NULL,
                    first_sync_completed INTEGER NOT NULL DEFAULT 0,
                    last_sync_started_at TEXT,
                    last_sync_finished_at TEXT,
                    last_sync_status TEXT,
                    last_sync_error TEXT,
                    last_sync_imported_count INTEGER NOT NULL DEFAULT 0,
                    last_sync_skipped_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS imported_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_key TEXT NOT NULL,
                    folder TEXT NOT NULL,
                    uidvalidity TEXT NOT NULL,
                    uid INTEGER NOT NULL,
                    message_id TEXT,
                    subject TEXT NOT NULL,
                    author TEXT,
                    published_at TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    raw_html TEXT NOT NULL,
                    sanitized_html TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    UNIQUE(account_key, folder, uidvalidity, uid)
                );

                CREATE TABLE IF NOT EXISTS feed_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_id INTEGER NOT NULL REFERENCES feed_rules(id) ON DELETE CASCADE,
                    imported_message_id INTEGER NOT NULL REFERENCES imported_messages(id) ON DELETE CASCADE,
                    guid TEXT UNIQUE,
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(feed_id, imported_message_id)
                );

                CREATE TABLE IF NOT EXISTS sync_cursors (
                    feed_id INTEGER NOT NULL REFERENCES feed_rules(id) ON DELETE CASCADE,
                    account_key TEXT NOT NULL,
                    folder TEXT NOT NULL,
                    uidvalidity TEXT NOT NULL,
                    last_uid INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(feed_id, account_key, folder)
                );

                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token_hash TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                """
            )
            self._migrate_feed_rules_sender_column(conn)

    def _migrate_feed_rules_sender_column(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(feed_rules)").fetchall()}
        if "recipient" in columns and "sender" not in columns:
            conn.execute("ALTER TABLE feed_rules RENAME COLUMN recipient TO sender")

    def create_session(self, hashed_token: str, expires_at: str) -> None:
        with self.connect() as conn:
            now = iso_now()
            conn.execute(
                "INSERT INTO admin_sessions(token_hash, created_at, expires_at) VALUES (?, ?, ?)",
                (hashed_token, now, expires_at),
            )

    def get_session(self, hashed_token: str) -> sqlite3.Row | None:
        self.delete_expired_sessions()
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM admin_sessions WHERE token_hash = ?",
                (hashed_token,),
            ).fetchone()

    def delete_session(self, hashed_token: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE token_hash = ?", (hashed_token,))

    def delete_expired_sessions(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE expires_at <= ?", (iso_now(),))

    def list_feeds(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> list[sqlite3.Row]:
        sort_column = FEED_SORT_COLUMNS.get(sort_by, FEED_SORT_COLUMNS["created_at"])
        direction = "ASC" if sort_dir == "asc" else "DESC"
        pagination_clause = ""
        values: list[Any] = []
        if limit is not None:
            pagination_clause = "LIMIT ? OFFSET ?"
            values.extend([limit, offset])
        null_order = f"{sort_column} IS NULL"
        with self.connect() as conn:
            return list(
                conn.execute(
                    f"""
                    SELECT fr.*, COALESCE(item_counts.item_count, 0) AS item_count
                    FROM feed_rules fr
                    LEFT JOIN (
                        SELECT feed_id, COUNT(*) AS item_count
                        FROM feed_items
                        WHERE archived = 0
                        GROUP BY feed_id
                    ) item_counts ON item_counts.feed_id = fr.id
                    ORDER BY {null_order} ASC, {sort_column} {direction}, fr.id {direction}
                    {pagination_clause}
                    """,
                    values,
                )
            )

    def count_feeds(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM feed_rules").fetchone()
            return row[0] if row else 0

    def get_feed(self, feed_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM feed_rules WHERE id = ?", (feed_id,)).fetchone()

    def get_feed_by_slug(self, slug: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM feed_rules WHERE random_slug = ?", (slug,)).fetchone()

    def create_feed(self, data: dict[str, Any]) -> sqlite3.Row:
        now = iso_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO feed_rules(
                    title, sender, imap_host, imap_port, imap_tls, imap_username,
                    imap_password_encrypted, folders_json, random_slug, backfill_days,
                    retention_count, sync_interval_minutes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["title"],
                    data["sender"],
                    data["imap_host"],
                    data["imap_port"],
                    data["imap_tls"],
                    data["imap_username"],
                    data["imap_password_encrypted"],
                    json.dumps(data["folders"]),
                    data["random_slug"],
                    data["backfill_days"],
                    data["retention_count"],
                    data["sync_interval_minutes"],
                    now,
                    now,
                ),
            )
            feed_id = cursor.lastrowid
            return conn.execute("SELECT * FROM feed_rules WHERE id = ?", (feed_id,)).fetchone()

    def update_feed(self, feed_id: int, data: dict[str, Any]) -> sqlite3.Row | None:
        if not data:
            return self.get_feed(feed_id)
        fields: list[str] = []
        values: list[Any] = []
        for key, value in data.items():
            column = "folders_json" if key == "folders" else key
            fields.append(f"{column} = ?")
            values.append(json.dumps(value) if key == "folders" else value)
        fields.append("updated_at = ?")
        values.append(iso_now())
        values.append(feed_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE feed_rules SET {', '.join(fields)} WHERE id = ?", values)
            return conn.execute("SELECT * FROM feed_rules WHERE id = ?", (feed_id,)).fetchone()

    def delete_feed(self, feed_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM feed_rules WHERE id = ?", (feed_id,))
            conn.execute(
                """
                DELETE FROM imported_messages
                WHERE id NOT IN (SELECT imported_message_id FROM feed_items)
                """
            )

    def mark_sync_started(self, feed_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE feed_rules
                SET last_sync_started_at = ?, last_sync_status = ?, last_sync_error = NULL
                WHERE id = ?
                """,
                (iso_now(), "running", feed_id),
            )

    def mark_sync_finished(
        self,
        feed_id: int,
        *,
        status: str,
        imported_count: int,
        skipped_count: int,
        error: str | None = None,
        first_sync_completed: bool | None = None,
    ) -> None:
        fields = [
            "last_sync_finished_at = ?",
            "last_sync_status = ?",
            "last_sync_imported_count = ?",
            "last_sync_skipped_count = ?",
            "last_sync_error = ?",
        ]
        values: list[Any] = [iso_now(), status, imported_count, skipped_count, error]
        if first_sync_completed is not None:
            fields.append("first_sync_completed = ?")
            values.append(1 if first_sync_completed else 0)
        values.append(feed_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE feed_rules SET {', '.join(fields)} WHERE id = ?", values)

    def get_cursor(self, feed_id: int, account_key: str, folder: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM sync_cursors
                WHERE feed_id = ? AND account_key = ? AND folder = ?
                """,
                (feed_id, account_key, folder),
            ).fetchone()

    def upsert_cursor(self, feed_id: int, account_key: str, folder: str, uidvalidity: str, last_uid: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_cursors(feed_id, account_key, folder, uidvalidity, last_uid, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(feed_id, account_key, folder)
                DO UPDATE SET uidvalidity = excluded.uidvalidity,
                              last_uid = excluded.last_uid,
                              updated_at = excluded.updated_at
                """,
                (feed_id, account_key, folder, uidvalidity, last_uid, iso_now()),
            )

    def upsert_imported_message(self, data: dict[str, Any]) -> int:
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM imported_messages
                WHERE account_key = ? AND folder = ? AND uidvalidity = ? AND uid = ?
                """,
                (data["account_key"], data["folder"], data["uidvalidity"], data["uid"]),
            ).fetchone()
            if existing:
                return int(existing["id"])
            cursor = conn.execute(
                """
                INSERT INTO imported_messages(
                    account_key, folder, uidvalidity, uid, message_id, subject, author,
                    published_at, imported_at, raw_html, sanitized_html, summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["account_key"],
                    data["folder"],
                    data["uidvalidity"],
                    data["uid"],
                    data["message_id"],
                    data["subject"],
                    data["author"],
                    data["published_at"],
                    iso_now(),
                    data["raw_html"],
                    data["sanitized_html"],
                    data["summary"],
                ),
            )
            return int(cursor.lastrowid)

    def link_feed_item(self, feed_id: int, imported_message_id: int) -> tuple[int, bool]:
        now = iso_now()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM feed_items WHERE feed_id = ? AND imported_message_id = ?",
                (feed_id, imported_message_id),
            ).fetchone()
            if existing:
                return int(existing["id"]), False
            cursor = conn.execute(
                "INSERT INTO feed_items(feed_id, imported_message_id, created_at) VALUES (?, ?, ?)",
                (feed_id, imported_message_id, now),
            )
            item_id = int(cursor.lastrowid)
            guid = f"own-newsletter:item:{item_id}"
            conn.execute("UPDATE feed_items SET guid = ? WHERE id = ?", (guid, item_id))
            return item_id, True

    def apply_retention(self, feed_id: int, retention_count: int) -> None:
        with self.connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT fi.id
                    FROM feed_items fi
                    JOIN imported_messages im ON im.id = fi.imported_message_id
                    WHERE fi.feed_id = ?
                    ORDER BY im.published_at DESC, fi.id DESC
                    """,
                    (feed_id,),
                )
            )
            visible = {int(row["id"]) for row in rows[:retention_count]}
            all_ids = [int(row["id"]) for row in rows]
            if not all_ids:
                return
            placeholders = ",".join("?" for _ in all_ids)
            conn.execute(f"UPDATE feed_items SET archived = 1 WHERE id IN ({placeholders})", all_ids)
            if visible:
                visible_placeholders = ",".join("?" for _ in visible)
                conn.execute(f"UPDATE feed_items SET archived = 0 WHERE id IN ({visible_placeholders})", list(visible))

    def count_feed_items(self, feed_id: int) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM feed_items WHERE feed_id = ? AND archived = 0",
                (feed_id,),
            ).fetchone()
            return row[0] if row else 0

    def count_all_feed_items(self) -> dict[int, int]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT feed_id, COUNT(*) FROM feed_items WHERE archived = 0 GROUP BY feed_id"
            ).fetchall()
            return {row[0]: row[1] for row in rows}

    def list_feed_items(self, feed_id: int, *, include_archived: bool = False) -> list[sqlite3.Row]:
        archived_clause = "" if include_archived else "AND fi.archived = 0"
        with self.connect() as conn:
            return list(
                conn.execute(
                    f"""
                    SELECT fi.id AS feed_item_id, fi.guid, fi.archived, im.*
                    FROM feed_items fi
                    JOIN imported_messages im ON im.id = fi.imported_message_id
                    WHERE fi.feed_id = ? {archived_clause}
                    ORDER BY im.published_at DESC, fi.id DESC
                    """,
                    (feed_id,),
                )
            )

    def feeds_due_for_sync(self) -> list[sqlite3.Row]:
        feeds = self.list_feeds()
        due: list[sqlite3.Row] = []
        now = utc_now()
        for feed in feeds:
            interval = int(feed["sync_interval_minutes"])
            if interval <= 0:
                continue
            if feed["last_sync_status"] == "running":
                continue
            finished_at = parse_iso(feed["last_sync_finished_at"])
            if finished_at is None:
                due.append(feed)
                continue
            if (now - finished_at).total_seconds() >= interval * 60:
                due.append(feed)
        return due


def folders_from_row(feed: sqlite3.Row | dict[str, Any]) -> list[str]:
    raw = feed["folders_json"] if "folders_json" in feed.keys() else feed["folders"]
    if isinstance(raw, str):
        parsed = json.loads(raw)
        return [str(item) for item in parsed]
    return [str(item) for item in raw]
