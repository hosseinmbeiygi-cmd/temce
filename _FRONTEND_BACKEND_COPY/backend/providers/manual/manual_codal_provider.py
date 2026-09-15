from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.manual import ManualDataProvider

logger = get_logger(__name__)


class ManualCodalProvider(ManualDataProvider):
    def __init__(self) -> None:
        super().__init__(name="manual_codal")
        self._pending: list[dict[str, Any]] = []

    async def fetch(self, **kwargs: Any) -> Result[Any]:
        return Result.ok(self._pending)

    async def submit(self, data: dict[str, Any], **kwargs: Any) -> Result[dict[str, Any]]:
        record = {
            **data,
            "submitted_at": datetime.now(UTC).isoformat(),
            "status": "pending",
            "id": len(self._pending) + 1,
        }
        self._pending.append(record)
        logger.info("Manual codal entry submitted: %s", record.get("id"))
        return Result.ok(record)

    async def validate(self, data: dict[str, Any]) -> Result[bool]:
        required = ["symbol", "report_type", "report_date"]
        missing = [f for f in required if f not in data]
        if missing:
            return Result.fail(f"Missing required fields: {missing}")
        return Result.ok(True)

    async def get_pending(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([p for p in self._pending if p.get("status") == "pending"])

    async def approve(self, entry_id: int) -> Result[dict[str, Any]]:
        for entry in self._pending:
            if entry.get("id") == entry_id:
                entry["status"] = "approved"
                entry["approved_at"] = datetime.now(UTC).isoformat()
                return Result.ok(entry)
        return Result.fail(f"Entry {entry_id} not found")

    async def reject(self, entry_id: int, reason: str = "") -> Result[dict[str, Any]]:
        for entry in self._pending:
            if entry.get("id") == entry_id:
                entry["status"] = "rejected"
                entry["rejected_at"] = datetime.now(UTC).isoformat()
                entry["reject_reason"] = reason
                return Result.ok(entry)
        return Result.fail(f"Entry {entry_id} not found")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self._pending)} pending entries"}
