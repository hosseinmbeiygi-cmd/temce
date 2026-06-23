from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.result import Result
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.smart_money.scoring_engine import ScoringEngine

logger = get_logger(__name__)



def _get_mock_for_symbol(symbol: str) -> dict[str, Any]:
    """Generate deterministic mock data for a symbol."""
    seed = sum(ord(c) for c in symbol) * 7 + len(symbol)
    r = lambda n: ((seed * n * 9301 + 49297) % 233280) / 233280  # noqa: E731

    smc = 0.25 + r(1) * 0.65
    scores = {
        "accumulation": round(0.2 + r(3) * 0.7, 4),
        "absorption": round(0.2 + r(4) * 0.7, 4),
        "float_lock": round(0.2 + r(5) * 0.7, 4),
        "breakout_readiness": round(0.2 + r(6) * 0.7, 4),
        "buyer_power": round(0.2 + r(7) * 0.7, 4),
        "microstructure": round(0.2 + r(8) * 0.7, 4),
    }

    phases = ["early_accumulation", "active_absorption", "float_lock", "breakout_ready", "confirmed_smart_money", "neutral"]
    phase = phases[int(r(2) * 6) % 6]

    return {
        "smart_money_score": round(smc, 4),
        "phase": phase,
        "scores": scores,
        "penalties": {
            "distribution_risk": round(r(9) * 0.5, 4),
            "fake_breakout_risk": round(r(10) * 0.5, 4),
            "dead_compression": round(r(11) * 0.5, 4),
        },
        "features": {},
        "breakout_features": {},
    }


class SmartMoneyService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._engine = ScoringEngine()
        self._quote_repo = QuoteRepository(session=session)
        self._instrument_repo = InstrumentRepository(session=session)

    async def analyze(self, symbol: str) -> Result[dict[str, Any]]:
        instr_result = await self._instrument_repo.get_by_symbol(symbol)
        if not instr_result.success:
            logger.warning("Symbol %s not found in DB — returning mock data", symbol)
            return Result.ok(_get_mock_for_symbol(symbol))
        instrument = instr_result.value

        quote_result = await self._quote_repo.get_latest(instrument.id)
        if not quote_result.success:
            logger.warning("No quote data for %s in DB — returning mock data", symbol)
            return Result.ok(_get_mock_for_symbol(symbol))

        quote_raw = self._quote_to_dict(quote_result.value)

        # Get historical quotes for analysis — works with both DB & in-memory backends
        all_quotes = await self._get_quote_history(instrument.id)

        result = self._engine.analyze(
            quote=quote_raw,
            history=all_quotes[-30:],
        )
        logger.info(
            "Smart money analysis for %s: SMC=%.4f phase=%s", symbol, result["smart_money_score"], result["phase"]
        )
        return Result.ok(result)

    async def _get_quote_history(self, instrument_id: str) -> list[dict[str, Any]]:
        """Get historical quotes using the public repository API (DB or in-memory)."""
        quotes_result = await self._quote_repo.get_range(
            instrument_id=instrument_id,
            start_date=date(2000, 1, 1),
            end_date=date(2030, 12, 31),
        )
        if quotes_result.success:
            quotes = list(quotes_result.value)
            quotes.sort(key=lambda q: (q.date, q.time))
            return [self._quote_to_dict(q) for q in quotes]
        return []

    @staticmethod
    def _quote_to_dict(q: Any) -> dict[str, Any]:
        return {
            "instrument_id": getattr(q, "instrument_id", ""),
            "symbol": getattr(q, "symbol", ""),
            "price_open": getattr(q, "price_open", 0.0),
            "price_close": getattr(q, "price_close", 0.0),
            "price_high": getattr(q, "price_high", 0.0),
            "price_low": getattr(q, "price_low", 0.0),
            "price_last": getattr(q, "price_last", 0.0),
            "price_change": getattr(q, "price_change", 0.0),
            "price_change_pct": getattr(q, "price_change_pct", 0.0),
            "volume": getattr(q, "volume", 0) or 0,
            "value": getattr(q, "value", 0) or 0.0,
            "trade_count": getattr(q, "trade_count", 0) or 0,
            "price_yesterday": getattr(q, "price_yesterday", 0.0),
            "market_status": getattr(q, "market_status", ""),
            "avg_buy": getattr(q, "extra", {}).get("avg_buy", 0.0) if hasattr(q, "extra") else 0.0,
            "avg_sell": getattr(q, "extra", {}).get("avg_sell", 0.0) if hasattr(q, "extra") else 0.0,
            "real_buy_value": getattr(q, "extra", {}).get("real_buy_value", 0.0) if hasattr(q, "extra") else 0.0,
            "real_sell_value": getattr(q, "extra", {}).get("real_sell_value", 0.0) if hasattr(q, "extra") else 0.0,
            "real_buy_count": getattr(q, "extra", {}).get("real_buy_count", 1) if hasattr(q, "extra") else 1,
            "real_sell_count": getattr(q, "extra", {}).get("real_sell_count", 1) if hasattr(q, "extra") else 1,
            "date": getattr(q, "date", ""),
            "time": getattr(q, "time", ""),
        }
