from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.manual import ManualDataProvider

logger = get_logger(__name__)


QUOTE_FIELDS = ["symbol", "open", "high", "low", "close", "volume", "value", "count", "date"]


class ManualQuoteProvider(ManualDataProvider):
    def __init__(self) -> None:
        super().__init__(name="manual_quote")
        self._quotes: list[dict[str, Any]] = []

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            return Result.ok([q for q in self._quotes if q.get("symbol") == symbol])
        return Result.ok(self._quotes)

    async def submit(self, data: dict[str, Any], **kwargs: Any) -> Result[dict[str, Any]]:
        validation = await self.validate(data)
        if not validation.success:
            return Result.fail(validation.error or "Validation failed")
        quote = {
            **data,
            "submitted_at": datetime.now(UTC).isoformat(),
            "status": "pending",
            "id": len(self._quotes) + 1,
        }
        self._quotes.append(quote)
        logger.info("Manual quote submitted for: %s", quote.get("symbol"))
        return Result.ok(quote)

    async def validate(self, data: dict[str, Any]) -> Result[bool]:
        missing = [f for f in QUOTE_FIELDS if f not in data]
        if missing:
            return Result.fail(f"Missing required fields: {missing}")
        return Result.ok(True)

    async def get_pending(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([q for q in self._quotes if q.get("status") == "pending"])

    async def approve(self, quote_id: int) -> Result[dict[str, Any]]:
        for q in self._quotes:
            if q.get("id") == quote_id:
                q["status"] = "approved"
                q["approved_at"] = datetime.now(UTC).isoformat()
                return Result.ok(q)
        return Result.fail(f"Quote {quote_id} not found")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self._quotes)} quotes"}
