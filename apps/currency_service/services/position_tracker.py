"""Manual position tracker — CRUD + PnL against current snapshot.

Uses the shared ``core.database.async_session_factory``. User identity is an
opaque string passed by the endpoint (auth layer's job).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.currency_service.domain import (
    ManualPosition,
    PositionPnL,
    position_pnl_toman,
    simple_return_pct,
)
from models.currency import CurrencyManualPositionModel


def _to_entity(row: CurrencyManualPositionModel) -> ManualPosition:
    return ManualPosition(
        id=int(row.id),
        user_id=row.user_id,
        asset_type=row.asset_type,  # type: ignore[arg-type]
        entry_price=float(row.entry_price),
        volume=float(row.volume),
        entry_date=row.entry_date,
        created_at=row.created_at,
        note=row.note,
    )


class PositionTracker:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: str,
        asset_type: str,
        entry_price: float,
        volume: float,
        entry_date: date | None = None,
        note: str | None = None,
    ) -> ManualPosition:
        row = CurrencyManualPositionModel(
            user_id=user_id,
            asset_type=asset_type,
            entry_price=Decimal(str(entry_price)),
            volume=Decimal(str(volume)),
            entry_date=entry_date or date.today(),
            note=note,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entity(row)

    async def list_for_user(self, user_id: str) -> Sequence[ManualPosition]:
        result = await self._session.execute(
            select(CurrencyManualPositionModel)
            .where(CurrencyManualPositionModel.user_id == user_id)
            .order_by(CurrencyManualPositionModel.created_at.desc())
        )
        return [_to_entity(r) for r in result.scalars().all()]

    async def delete(self, position_id: int, user_id: str) -> bool:
        result = await self._session.execute(
            select(CurrencyManualPositionModel).where(
                CurrencyManualPositionModel.id == position_id,
                CurrencyManualPositionModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    @staticmethod
    def pnl_for(position: ManualPosition, current_price: float) -> PositionPnL:
        pnl = position_pnl_toman(current_price, position.entry_price, position.volume)
        ret = simple_return_pct(current_price, position.entry_price)
        return PositionPnL(
            position=position,
            current_price=current_price,
            pnl_toman=pnl,
            return_pct=ret,
        )

    @staticmethod
    def price_for(position: ManualPosition, snapshot_prices: dict[str, float]) -> float:
        # CASH_USD uses free-market sell (exit price); USDT uses USDT sell.
        if position.asset_type == "CASH_USD":
            return snapshot_prices["free_sell"]
        if position.asset_type == "USDT":
            return snapshot_prices["usdt_sell"]
        return snapshot_prices.get("free_sell", 0.0)
