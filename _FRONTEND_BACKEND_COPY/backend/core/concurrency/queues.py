from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class AsyncQueue(Generic[T]):
    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self._closed = False

    async def put(self, item: T) -> None:
        if self._closed:
            raise RuntimeError("Queue is closed")
        await self._queue.put(item)

    async def get(self) -> T:
        if self._closed and self._queue.empty():
            raise RuntimeError("Queue is closed and empty")
        return await self._queue.get()

    def get_nowait(self) -> T:
        return self._queue.get_nowait()

    def put_nowait(self, item: T) -> None:
        if self._closed:
            raise RuntimeError("Queue is closed")
        self._queue.put_nowait(item)

    async def join(self) -> None:
        await self._queue.join()

    def task_done(self) -> None:
        self._queue.task_done()

    def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def empty(self) -> bool:
        return self._queue.empty()

    @property
    def maxsize(self) -> int:
        return self._queue.maxsize


class PriorityQueue(Generic[T]):
    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, T]] = asyncio.PriorityQueue(maxsize=maxsize)

    async def put(self, item: T, priority: int = 0) -> None:
        await self._queue.put((priority, item))

    async def get(self) -> T:
        _, item = await self._queue.get()
        return item
