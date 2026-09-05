"""GET /currency/overview — snapshot + matrix + signals + kill_switch."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.currency_service.config import settings
from apps.currency_service.infra.cache import cached_overview
from apps.currency_service.services.signal_engine import SignalEngine

router = APIRouter()
_engine = SignalEngine()


def _serialize_signal(s) -> dict[str, Any]:
    out: dict[str, Any] = {
        "asset_type": s.asset_type,
        "signal_type": s.signal_type,
        "confidence": s.confidence,
        "reason": s.reason,
        "risk_level": s.risk_level,
    }
    if s.entry_range is not None:
        lo, hi = s.entry_range
        out["entry_range"] = {"min": lo, "max": hi}
    if s.target_price is not None:
        out["target_price"] = s.target_price
    if s.stop_loss is not None:
        out["stop_loss"] = s.stop_loss
    if s.holding_period is not None:
        out["holding_period"] = s.holding_period
    return out


def _serialize_snapshot(snap) -> dict[str, Any]:
    return {
        "free": {
            "buy": snap.free.buy_price,
            "sell": snap.free.sell_price,
            "daily_change": snap.free.daily_change_pct,
            "spread": ((snap.free.sell_price - snap.free.buy_price) / snap.free.sell_price) * 100.0,
            "source": snap.free.source,
        },
        "usdt": {
            "buy": snap.usdt.buy_price,
            "sell": snap.usdt.sell_price,
            "daily_change": snap.usdt.daily_change_pct,
            "spread": ((snap.usdt.sell_price - snap.usdt.buy_price) / snap.usdt.sell_price) * 100.0,
            "source": snap.usdt.source,
        },
        "nima": {
            "buy": snap.nima.buy_price,
            "sell": snap.nima.sell_price,
            "daily_change": snap.nima.daily_change_pct,
            "spread": ((snap.nima.sell_price - snap.nima.buy_price) / snap.nima.sell_price) * 100.0,
            "source": snap.nima.source,
        },
        "official_cbi": snap.official_cbi,
        "timestamp": snap.timestamp.isoformat(),
    }


async def _compute_overview() -> dict[str, Any]:
    payload = await _engine.overview()
    return {
        "timestamp": payload.snapshot.timestamp.isoformat(),
        "rates": _serialize_snapshot(payload.snapshot),
        "market_summary": {
            "free_market_usd": payload.market_summary.free_market_usd,
            "official_cbi_usd": payload.market_summary.official_cbi_usd,
            "nima_usd": payload.market_summary.nima_usd,
            "usdt_irt": payload.market_summary.usdt_irt,
            "bubble_index": round(payload.market_summary.bubble_index, 2),
            "daily_volatility": round(payload.market_summary.daily_volatility, 2),
            "bid_ask_spread": round(payload.market_summary.bid_ask_spread, 2),
            "tether_arbitrage": round(payload.market_summary.tether_arbitrage, 2),
            "sentiment": payload.market_summary.sentiment,
        },
        "arbitrage_matrix": [
            {
                "name": r.name,
                "price": r.price,
                "difference_with_free_market": r.difference_with_free_market,
                "spread_pct": round(r.spread_pct, 2),
                "status": r.status,
            }
            for r in payload.arbitrage_matrix
        ],
        "signals": [_serialize_signal(s) for s in payload.signals],
        "kill_switch": {
            "active": payload.kill_switch.active,
            "reasons": payload.kill_switch.reasons,
            "action": payload.kill_switch.action,
        },
    }


@router.get("/overview")
async def overview() -> dict[str, Any]:
    return await cached_overview(_compute_overview, ttl=settings.cache_ttl_seconds)
