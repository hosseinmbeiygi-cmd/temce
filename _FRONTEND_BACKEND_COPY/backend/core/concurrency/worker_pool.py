from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class WorkerPool:
    def __init__(self, num_workers: int = 4, queue_maxsize: int = 0) -> None:
        self.num_workers = num_workers
        self._queue: asyncio.Queue[Callable[[], Coroutine[Any, Any, Any]]] = asyncio.Queue(maxsize=queue_maxsize)
        self._workers: list[asyncio.Task[None]] = []
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self.num_workers)]
        logger.info("Started %d workers", self.num_workers)

    async def _worker(self, worker_id: int) -> None:
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                try:
                    await task()
                except Exception as e:
                    logger.error("Worker %d task failed: %s", worker_id, e)
                finally:
                    self._queue.task_done()
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def submit(self, task: Callable[[], Coroutine[Any, Any, T]]) -> asyncio.Future[T]:
        future: asyncio.Future[T] = asyncio.get_event_loop().create_future()

        async def wrapper() -> None:
            try:
                result = await task()
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)

        await self._queue.put(wrapper)
        return future

    async def join(self) -> None:
        await self._queue.join()

    async def stop(self) -> None:
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("All workers stopped")

    @property
    def pending(self) -> int:
        return self._queue.qsize()
