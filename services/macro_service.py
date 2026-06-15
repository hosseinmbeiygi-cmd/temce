from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class MacroService:
    async def get_indicator(self, indicator: str) -> Result[dict[str, Any]]:
        return Result.fail(f"Indicator {indicator} not found")

    async def list_indicators(self) -> Result[list[str]]:
        return Result.ok([])

    async def get_history(self, indicator: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def save(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        return Result.ok(data)
