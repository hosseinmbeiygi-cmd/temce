from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


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


async def run_in_parallel(tasks: list[Callable[[], Coroutine[Any, Any, T]]], max_concurrent: int = 10) -> list[T]:
    sem = asyncio.Semaphore(max_concurrent)

    async def worker(task: Callable[[], Coroutine[Any, Any, T]]) -> T:
        async with sem:
            return await task()

    return await asyncio.gather(*[worker(t) for t in tasks])
