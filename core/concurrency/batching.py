from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class BatchProcessor:
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0) -> None:
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._batch: list[tuple[Callable[[], Coroutine[Any, Any, Any]], asyncio.Future[Any]]] = []
        self._timer_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._running = False

    async def add(self, task: Callable[[], Coroutine[Any, Any, T]]) -> T:
        future: asyncio.Future[T] = asyncio.get_event_loop().create_future()
        async with self._lock:
            self._batch.append((task, future))
            if len(self._batch) >= self.batch_size:
                asyncio.create_task(self._flush())
            elif self._timer_task is None:
                self._timer_task = asyncio.create_task(self._timer_loop())
        return await future

    async def _timer_loop(self) -> None:
        try:
            while self._running or len(self._batch) > 0:
                await asyncio.sleep(self.flush_interval)
                async with self._lock:
                    if self._batch:
                        asyncio.create_task(self._flush())
        except asyncio.CancelledError:
            pass

    async def _flush(self) -> None:
        async with self._lock:
            batch = self._batch[:]
            self._batch.clear()
            self._timer_task = None
        if not batch:
            return
        logger.debug("Flushing %d batched items", len(batch))
        results = await asyncio.gather(*[t[0]() for t in batch], return_exceptions=True)
        for (_, future), result in zip(batch, results, strict=False):
            if isinstance(result, Exception):
                future.set_exception(result)
            else:
                future.set_result(result)

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
        await self._flush()
