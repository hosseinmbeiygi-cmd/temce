from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class TaskGroup:
    def __init__(self, max_concurrent: int = 10) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: list[asyncio.Task[Any]] = []

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        async with self._semaphore:
            task = asyncio.create_task(coro)
            self._tasks.append(task)
            return await task

    def create_task(self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    async def gather(self) -> list[Any]:
        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        return results

    async def wait_all(self) -> None:
        if self._tasks:
            await asyncio.wait(self._tasks)
            self._tasks.clear()

    def cancel_all(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    @property
    def pending(self) -> int:
        return len(self._tasks)


class TaskCollection:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def add(self, name: str, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.create_task(coro, name=name)
        self._tasks[name] = task
        return task

    async def cancel(self, name: str) -> None:
        task = self._tasks.pop(name, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def cancel_all(self) -> None:
        for name in list(self._tasks.keys()):
            await self.cancel(name)

    def get(self, name: str) -> asyncio.Task[Any] | None:
        return self._tasks.get(name)
