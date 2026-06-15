from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from services.recommendation_service import RecommendationService

logger = get_logger(__name__)


class RecommendationReportBuilder:
    def __init__(self, recommendation_service: RecommendationService | None = None):
        self._service = recommendation_service or RecommendationService()

    async def build(self, instrument_id: str | None = None, limit: int = 50) -> Result[dict[str, Any]]:
        if instrument_id:
            recs_result = await self._service.get_active(instrument_id)
        else:
            recs_result = await self._service.list(page=1, page_size=limit)
        data: dict[str, Any] = {
            "title": f"Recommendation Report{f' for {instrument_id}' if instrument_id else ''}",
            "report_type": "recommendation",
            "generated_at": datetime.now(UTC).isoformat(),
            "instrument_id": instrument_id or "all",
            "total": 0,
            "recommendations": [],
        }
        if recs_result.success:
            recs = recs_result.value
            if hasattr(recs, "items"):
                recs = recs.items
            data["total"] = len(recs)
            for r in recs:
                entry = {
                    "id": getattr(r, "id", ""),
                    "symbol": getattr(r, "symbol", ""),
                    "action": str(getattr(r, "action", "")),
                    "target_price": getattr(r, "target_price", None),
                    "current_price": getattr(r, "current_price", 0),
                    "confidence": getattr(r, "confidence", 0),
                    "source": getattr(r, "source", ""),
                    "analyst": getattr(r, "analyst", ""),
                    "rationale": getattr(r, "rationale", ""),
                    "horizon": getattr(r, "horizon", ""),
                }
                data["recommendations"].append(entry)
        return Result.ok(data)
