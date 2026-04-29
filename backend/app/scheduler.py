from __future__ import annotations

import asyncio
from contextlib import suppress

from .sync_engine import SyncEngine


class BackendScheduler:
    def __init__(self, sync_engine: SyncEngine, tick_seconds: int) -> None:
        self.sync_engine = sync_engine
        self.tick_seconds = max(5, tick_seconds)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            await asyncio.to_thread(self.sync_engine.sync_due_feeds)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.tick_seconds)
            except TimeoutError:
                continue

