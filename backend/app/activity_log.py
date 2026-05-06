from __future__ import annotations

from collections.abc import Mapping
import json
import re
from typing import Any

from .publication import PublicationTarget
from .security import redact_sensitive
from .store import MessageStore
from .timeutil import iso_now

ACTIVITY_OPERATION_TYPES = {"sync", "publish"}
ACTIVITY_STATUSES = {"success", "failed", "skipped"}
ACTIVITY_TRIGGERS = {
    "manual_sync",
    "scheduled_sync",
    "initial_sync",
    "publication_retry",
    "publication_activation",
    "feed_change_publication",
}
PUBLICATION_TARGET_VALUES = frozenset(target.value for target in PublicationTarget)

_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|authorization|api[_-]?key)\s*=\s*[^,\s;]+"
)
_HTML_BLOCK_RE = re.compile(
    r"<(html|body|div|p|article|section|main|span|table|pre|code|blockquote)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


class ActivityLogRecorder:
    def __init__(self, store: MessageStore) -> None:
        self.store = store

    def record_sync(
        self,
        *,
        trigger: str,
        status: str,
        feed_id: int | None,
        feed_title: str | None,
        imported_count: int,
        skipped_count: int,
        completed_at: str | None = None,
        duration_ms: int = 0,
        started_at: str | None = None,
        error: str | None = None,
        error_detail: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if status not in ACTIVITY_STATUSES:
            status = "failed"
        self.store.create_activity_log_entry(
            {
                "operation_type": "sync",
                "status": status,
                "trigger": _activity_trigger(trigger),
                "feed_id": feed_id,
                "feed_title_snapshot": feed_title,
                "imported_count": int(imported_count),
                "skipped_count": int(skipped_count),
                "started_at": started_at,
                "completed_at": completed_at or iso_now(),
                "duration_ms": max(0, int(duration_ms)),
                **_redacted_error_fields(error, error_detail),
                "metadata": redact_activity_metadata(metadata or {}),
            }
        )

    def record_publish(
        self,
        *,
        trigger: str,
        status: str,
        publication_target: str | PublicationTarget,
        feed_count: int,
        file_count: int,
        feed_id: int | None = None,
        feed_title: str | None = None,
        completed_at: str | None = None,
        duration_ms: int = 0,
        started_at: str | None = None,
        error: str | None = None,
        error_detail: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if status not in ACTIVITY_STATUSES:
            status = "failed"
        target = str(publication_target)
        self.store.create_activity_log_entry(
            {
                "operation_type": "publish",
                "status": status,
                "trigger": _activity_trigger(trigger),
                "feed_id": feed_id,
                "feed_title_snapshot": feed_title,
                "publication_target": target if target in PUBLICATION_TARGET_VALUES else None,
                "feed_count": max(0, int(feed_count)),
                "file_count": max(0, int(file_count)),
                "started_at": started_at,
                "completed_at": completed_at or iso_now(),
                "duration_ms": max(0, int(duration_ms)),
                **_redacted_error_fields(error, error_detail),
                "metadata": redact_activity_metadata(metadata or {}),
            }
        )


class ActivityLogQuery:
    def __init__(self, store: MessageStore) -> None:
        self.store = store

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        operation_type: str | None = None,
        status: str | None = None,
        trigger: str | None = None,
        feed_id: int | None = None,
    ) -> dict[str, Any]:
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
        total = self.store.count_activity_log_entries(
            operation_type=operation_type,
            status=status,
            trigger=trigger,
            feed_id=feed_id,
        )
        rows = self.store.list_activity_log_entries(
            limit=page_size,
            offset=(page - 1) * page_size,
            operation_type=operation_type,
            status=status,
            trigger=trigger,
            feed_id=feed_id,
        )
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "entries": [_serialize_activity_row(row) for row in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1,
            },
            "filters": {
                "operation_type": operation_type,
                "status": status,
                "trigger": trigger,
                "feed_id": feed_id,
            },
        }


def redact_activity_text(value: object, *, max_length: int = 4000) -> str:
    text = str(value)
    text = _HTML_BLOCK_RE.sub("[redacted-html]", text)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=***", text)
    text = redact_sensitive(text)
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1].rstrip()}..."


def redact_activity_metadata(value: Any) -> Any:
    if isinstance(value, str):
        return redact_activity_text(value)
    if isinstance(value, Mapping):
        return {str(key): redact_activity_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_activity_metadata(item) for item in value]
    if value is None or isinstance(value, bool | int | float):
        return value
    return redact_activity_text(value)


def _redacted_error_fields(error: str | None, error_detail: str | None) -> dict[str, str | None]:
    if not error and not error_detail:
        return {"error_summary": None, "error_detail": None}
    source = error or error_detail or ""
    summary = redact_activity_text(source, max_length=240)
    detail_source = error_detail if error_detail is not None else source if len(str(source)) > 240 else None
    detail = redact_activity_text(detail_source, max_length=4000) if detail_source else None
    return {"error_summary": summary, "error_detail": detail}


def _activity_trigger(trigger: str) -> str:
    return trigger if trigger in ACTIVITY_TRIGGERS else "manual_sync"


def _serialize_activity_row(row: Any) -> dict[str, Any]:
    metadata: Any
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    feed_id = row["feed_id"]
    feed_title = row["feed_title_snapshot"]
    return {
        "id": row["id"],
        "operation_type": row["operation_type"],
        "status": row["status"],
        "trigger": row["trigger"],
        "feed_id": feed_id,
        "feed_title": feed_title,
        "feed": {"id": feed_id, "title": feed_title} if feed_id is not None or feed_title else None,
        "publication_target": row["publication_target"],
        "imported_count": row["imported_count"],
        "skipped_count": row["skipped_count"],
        "feed_count": row["feed_count"],
        "file_count": row["file_count"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "duration_ms": row["duration_ms"],
        "error_summary": row["error_summary"],
        "error_detail": row["error_detail"],
        "metadata": metadata,
    }
