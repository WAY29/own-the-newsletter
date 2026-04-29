import asyncio
import logging

from app.scheduler import BackendScheduler
from app.sync_engine import SyncResult


class FakeSyncEngine:
    def __init__(self, results=None, error: Exception | None = None) -> None:
        self.results = results or []
        self.error = error

    def sync_due_feeds(self):
        if self.error is not None:
            raise self.error
        return self.results


def test_scheduler_logs_sync_result_summary(caplog) -> None:
    scheduler = BackendScheduler(
        FakeSyncEngine(
            [
                SyncResult(status="success", imported_count=2, skipped_count=1, feed_id=1, feed_title="Daily Feed"),
                SyncResult(status="failed", error="boom", feed_id=2, feed_title="Weekly Feed"),
            ]
        ),
        tick_seconds=60,
    )

    with caplog.at_level(logging.INFO, logger="app.scheduler"):
        asyncio.run(scheduler.run_once())

    assert "Scheduled feed sync check finished results=2 success=1 failed=1 imported=2 skipped=1" in caplog.text
    assert (
        "Scheduled feed sync result feed_id=1 title='Daily Feed' status=success imported=2 skipped=1"
        in caplog.text
    )
    assert (
        "Scheduled feed sync result feed_id=2 title='Weekly Feed' status=failed imported=0 skipped=0 error='boom'"
        in caplog.text
    )


def test_scheduler_logs_sync_errors(caplog) -> None:
    scheduler = BackendScheduler(FakeSyncEngine(error=RuntimeError("database unavailable")), tick_seconds=60)

    with caplog.at_level(logging.ERROR, logger="app.scheduler"):
        asyncio.run(scheduler.run_once())

    assert "Scheduled feed sync check failed" in caplog.text
    assert "database unavailable" in caplog.text
