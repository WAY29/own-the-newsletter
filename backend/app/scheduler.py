from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import suppress
import logging

from .logging_config import safe_log_text
from .sync_engine import SyncEngine, SyncResult

logger = logging.getLogger(__name__)


class BackendScheduler:
    def __init__(self, sync_engine: SyncEngine, tick_seconds: int) -> None:
        self.sync_engine = sync_engine
        self.tick_seconds = max(5, tick_seconds)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None:
            if self._stop.is_set():
                self._stop = asyncio.Event()
            logger.info("Backend scheduler started tick_seconds=%s", self.tick_seconds)
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        logger.info("Backend scheduler stopping")
        self._stop.set()
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("Backend scheduler stopped")

    async def run_once(self) -> None:
        logger.debug("Scheduled feed sync check started")
        try:
            results = await asyncio.to_thread(self.sync_engine.sync_due_feeds)
        except Exception:
            logger.exception("Scheduled feed sync check failed")
            return
        for result in results:
            logger.info(_result_detail(result))
        logger.info(_result_summary(results))

    async def _run(self) -> None:
        while not self._stop.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.tick_seconds)
            except TimeoutError:
                continue


def _result_summary(results: list[SyncResult]) -> str:
    statuses = Counter(result.status for result in results)
    imported = sum(result.imported_count for result in results)
    skipped = sum(result.skipped_count for result in results)
    ordered_statuses = ["success", "failed", "skipped", "missing"]
    status_names = [status for status in ordered_statuses if status in statuses]
    status_names.extend(sorted(status for status in statuses if status not in ordered_statuses))
    status_parts = " ".join(f"{status}={statuses[status]}" for status in status_names)
    if status_parts:
        status_parts = f" {status_parts}"
    return (
        "Scheduled feed sync check finished "
        f"results={len(results)}{status_parts} imported={imported} skipped={skipped}"
    )


def _result_detail(result: SyncResult) -> str:
    feed_id = result.feed_id if result.feed_id is not None else "unknown"
    title = safe_log_text(result.feed_title or "unknown")
    message = (
        "Scheduled feed sync result "
        f"feed_id={feed_id} title={title!r} status={result.status} "
        f"imported={result.imported_count} skipped={result.skipped_count}"
    )
    if result.error:
        message = f"{message} error={safe_log_text(result.error)!r}"
    return message
