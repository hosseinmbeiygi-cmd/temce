from __future__ import annotations

import asyncio
import time

from core.logging import get_logger

logger = get_logger(__name__)


class RateBudget:
    def __init__(self, name: str, limit: int, window_seconds: int = 60) -> None:
        self.name = name
        self.limit = limit
        self.window_seconds = window_seconds
        self._tokens: list[float] = []
        self._lock = asyncio.Lock()

    async def consume(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._tokens = [t for t in self._tokens if t > cutoff]
            if len(self._tokens) >= self.limit:
                return False
            self._tokens.append(now)
            return True

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._tokens = [t for t in self._tokens if t > cutoff]
        return max(0, self.limit - len(self._tokens))

    @property
    def used(self) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._tokens = [t for t in self._tokens if t > cutoff]
        return len(self._tokens)

    def reset(self) -> None:
        self._tokens.clear()


class BudgetManager:
    def __init__(self) -> None:
        self._budgets: dict[str, RateBudget] = {}

    def create_budget(self, name: str, limit: int, window_seconds: int = 60) -> RateBudget:
        budget = RateBudget(name, limit, window_seconds)
        self._budgets[name] = budget
        return budget

    def get_budget(self, name: str) -> RateBudget | None:
        return self._budgets.get(name)

    async def try_consume(self, name: str) -> bool:
        budget = self._budgets.get(name)
        if budget is None:
            return True
        return await budget.consume()

    def reset_all(self) -> None:
        for budget in self._budgets.values():
            budget.reset()
