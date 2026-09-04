"""GET /currency/signals — current signals only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.currency_service.services.signal_engine import SignalEngine

router = APIRouter()
_engine = SignalEngine()


@router.get("/signals")
async def signals() -> dict[str, Any]:
    payload = await _engine.overview()
    return {
        "timestamp": payload.snapshot.timestamp.isoformat(),
        "kill_switch_active": payload.kill_switch.active,
        "count": len(payload.signals),
        "signals": [
            {
                "asset_type": s.asset_type,
                "signal_type": s.signal_type,
                "confidence": s.confidence,
                "reason": s.reason,
                "risk_level": s.risk_level,
            }
            for s in payload.signals
        ],
    }
