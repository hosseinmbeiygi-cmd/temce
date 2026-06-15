from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from services.signal_service import SignalService

logger = get_logger(__name__)


class SignalReportBuilder:
    def __init__(self, signal_service: SignalService | None = None):
        self._service = signal_service or SignalService()

    async def build(
        self, instrument_id: str | None = None, strategy: str = "", limit: int = 50
    ) -> Result[dict[str, Any]]:
        if instrument_id:
            signals_result = await self._service.get_by_instrument(instrument_id)
        else:
            signals_result = await self._service.list(limit=limit)
        data: dict[str, Any] = {
            "title": f"Signal Report{f' for {instrument_id}' if instrument_id else ''}",
            "report_type": "signal",
            "generated_at": datetime.now(UTC).isoformat(),
            "instrument_id": instrument_id or "all",
            "strategy": strategy,
            "total_signals": 0,
            "bullish": 0,
            "bearish": 0,
            "signals": [],
        }
        if signals_result.success:
            signals = signals_result.value if isinstance(signals_result.value, list) else []
            data["total_signals"] = len(signals)
            for s in signals:
                entry = {
                    "id": getattr(s, "id", ""),
                    "symbol": getattr(s, "symbol", ""),
                    "signal_type": getattr(s, "signal_type", ""),
                    "score": getattr(s, "score", 0),
                    "confidence": getattr(s, "confidence", 0),
                    "strategy": getattr(s, "strategy", ""),
                    "date": getattr(s, "date", ""),
                }
                data["signals"].append(entry)
                stype = str(getattr(s, "signal_type", ""))
                if "bull" in stype.lower() or "buy" in stype.lower():
                    data["bullish"] += 1
                elif "bear" in stype.lower() or "sell" in stype.lower():
                    data["bearish"] += 1
        return Result.ok(data)
