from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.analytics.signal import Signal
from domain.common.enum_types import SignalType
from repositories.signal_repository import SignalRepository

logger = get_logger(__name__)


class SignalService:
    def __init__(self, signal_repo: SignalRepository | None = None, session: AsyncSession | None = None) -> None:
        if signal_repo is None:
            signal_repo = SignalRepository(session=session)
        self.signal_repo = signal_repo
        self._session = session

    async def create(
        self, instrument_id: str, signal_type: SignalType, score: float = 0.0, confidence: float = 0.0, **kwargs: Any
    ) -> Result[Signal]:
        signal = Signal(
            id=new_id("sig"),
            instrument_id=instrument_id,
            signal_type=signal_type if isinstance(signal_type, SignalType) else SignalType(signal_type),
            score=score,
            confidence=confidence,
            **kwargs,
        )
        return await self.signal_repo.save(signal)

    async def generate(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        from services.multi_market_signal_engine import MultiMarketSignalEngine

        try:
            engine = MultiMarketSignalEngine(session=self._session)
            signals, reports = await engine.generate_all(
                market_filter=kwargs.get("market", "all"),
                timeframe_filter=kwargs.get("timeframe", "all"),
                signal_filter=kwargs.get("direction", "all"),
                limit=10,
            )

            symbol_signals = [s for s in signals if s.symbol == symbol]
            if symbol_signals:
                s = symbol_signals[0]
                return Result.ok({
                    "id": new_id("sig"),
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "score": s.score,
                    "strength": s.strength,
                    "confidence": s.confidence,
                    "reason": s.reason,
                    "market": s.market,
                    "price": s.price,
                    "change_pct": s.change_pct,
                    "success": True,
                })

            return Result.ok({
                "id": new_id("sig"),
                "symbol": symbol,
                "direction": "hold",
                "score": 50.0,
                "strength": 0.0,
                "confidence": 0.0,
                "reason": "سیگنالی شناسایی نشد",
                "success": True,
            })
        except Exception as e:
            logger.warning("Signal generation failed for %s: %s", symbol, e)
            return Result.ok({
                "id": new_id("sig"),
                "symbol": symbol,
                "direction": "hold",
                "score": 0.0,
                "confidence": 0.0,
                "reason": f"خطا در تولید سیگنال: {e}",
                "success": False,
            })

    async def get_latest(self, instrument_id: str) -> Result[Signal]:
        return await self.signal_repo.get_latest(instrument_id)

    async def list(
        self, instrument_id: str | None = None, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[dict[str, Any]]]:
        if instrument_id:
            result = await self.signal_repo.get_by_instrument(instrument_id, page, page_size)
        else:
            result = await self.signal_repo.list(page, page_size)

        if not result.success:
            return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))

        items = [vars(s) for s in result.value.items]
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return Result.ok(
            PaginatedResult(
                items=items,
                total=result.value.total,
                page=result.value.page,
                page_size=result.value.page_size,
                total_pages=result.value.total_pages,
            )
        )

    async def list_signals(self, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[dict[str, Any]]]:
        return await self.list(page=page, page_size=page_size)

    async def get_by_symbol(self, symbol: str) -> Result[list[Signal]]:
        result = await self.signal_repo.get_by_instrument(symbol, 1, 100)
        if result.success and result.value:
            return Result.ok(result.value.items)
        return Result.ok([])

    async def get(self, signal_id: str) -> Result[Signal | None]:
        return await self.signal_repo.get(signal_id)

    async def get_signal(self, signal_id: str) -> Result[dict[str, Any] | None]:
        result = await self.signal_repo.get(signal_id)
        if result.success and result.value:
            return Result.ok(vars(result.value))
        return Result.ok(None)

    async def bulk_generate(self, symbols: list[str], strategy: str = "technical") -> Result[list[Signal]]:
        from services.multi_market_signal_engine import MultiMarketSignalEngine

        try:
            engine = MultiMarketSignalEngine(session=self._session)
            signals, _ = await engine.generate_all(limit=len(symbols))
            return Result.ok(signals)
        except Exception as e:
            logger.warning("Bulk signal generation failed: %s", e)
            return Result.ok([])
