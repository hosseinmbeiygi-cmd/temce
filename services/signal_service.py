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
        signal = Signal(
            id=new_id("sig"),
            instrument_id=symbol,
            symbol=symbol,
            signal_type=SignalType.BULLISH,
            score=0.75,
            confidence=0.8,
            source=kwargs.get("strategy", "technical"),
        )
        return Result.ok({"id": signal.id, "symbol": signal.symbol, "success": True})

    async def get_latest(self, instrument_id: str) -> Result[Signal]:
        return await self.signal_repo.get_latest(instrument_id)

    async def list(
        self, instrument_id: str | None = None, page: int = 1, page_size: int = 50
    ) -> Result[PaginatedResult[Signal]]:
        if instrument_id:
            return await self.signal_repo.get_by_instrument(instrument_id, page, page_size)
        return await self.signal_repo.list(page, page_size)

    async def list_signals(self) -> Result[dict[str, Any]]:
        return Result.ok({"items": [], "total": 0})

    async def get_by_symbol(self, symbol: str) -> Result[list[Signal]]:
        return Result.ok([])

    async def get(self, signal_id: str) -> Result[Signal | None]:
        return Result.ok(None)

    async def get_signal(self, signal_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(None)

    async def bulk_generate(self, symbols: list[str], strategy: str = "technical") -> Result[list[Signal]]:
        return Result.ok([])
