from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.smart_money.scoring_engine import ScoringEngine

logger = get_logger(__name__)


class SmartMoneyService:
    def __init__(self) -> None:
        self._engine = ScoringEngine()
        self._quote_repo = QuoteRepository()
        self._instrument_repo = InstrumentRepository()

    async def analyze(self, symbol: str) -> Result[dict[str, Any]]:
        instr_result = await self._instrument_repo.get_by_symbol(symbol)
        if not instr_result.success:
            return Result.fail(f"Symbol not found: {symbol}")
        instrument = instr_result.value

        quote_result = await self._quote_repo.get_latest(instrument.id)
        if not quote_result.success:
            return Result.fail(f"No quote data for {symbol}")

        quote_raw = self._quote_to_dict(quote_result.value)
        all_quotes = [
            self._quote_to_dict(q)
            for q in self._quote_repo._store.values()
            if hasattr(q, "instrument_id") and q.instrument_id == instrument.id
        ]
        all_quotes.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))

        result = self._engine.analyze(
            quote=quote_raw,
            history=all_quotes[-30:],
        )
        logger.info(
            "Smart money analysis for %s: SMC=%.4f phase=%s", symbol, result["smart_money_score"], result["phase"]
        )
        return Result.ok(result)

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
