from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.manual import ManualDataProvider

logger = get_logger(__name__)


MACRO_CATEGORIES = ["fx", "gold", "oil", "commodity", "index", "rate", "inflation"]


class ManualMacroProvider(ManualDataProvider):
    def __init__(self) -> None:
        super().__init__(name="manual_macro")
        self._entries: list[dict[str, Any]] = []

    async def fetch(self, **kwargs: Any) -> Result[Any]:
        category = kwargs.get("category")
        if category:
            return Result.ok([e for e in self._entries if e.get("category") == category])
        return Result.ok(self._entries)

    async def submit(self, data: dict[str, Any], **kwargs: Any) -> Result[dict[str, Any]]:
        validation = await self.validate(data)
        if not validation.success:
            return Result.fail(validation.error or "Validation failed")
        record = {
            **data,
            "submitted_at": datetime.now(UTC).isoformat(),
            "status": "pending",
            "id": len(self._entries) + 1,
        }
        self._entries.append(record)
        logger.info("Manual macro entry submitted: %s", record.get("id"))
        return Result.ok(record)

    async def validate(self, data: dict[str, Any]) -> Result[bool]:
        if "category" not in data:
            return Result.fail("category is required")
        if data["category"] not in MACRO_CATEGORIES:
            return Result.fail(f"Invalid category: {data['category']}")
        if "value" not in data:
            return Result.fail("value is required")
        return Result.ok(True)

    async def get_pending(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([e for e in self._entries if e.get("status") == "pending"])

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self._entries)} entries"}
