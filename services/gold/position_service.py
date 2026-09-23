"""Position Service — ذخیره/بازیابی پوزیشن‌های آتی (DB-backed)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.time import utc_now_naive
from models.gold import GoldFuturesPositionModel
from services.gold.futures_risk import FuturesRiskCalculator

logger = get_logger(__name__)


class GoldFuturesPositionService:
    """سرویس پوزیشن‌های آتی سکه (IME)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_open_positions(self) -> list[dict[str, Any]]:
        stmt = (
            select(GoldFuturesPositionModel)
            .where(GoldFuturesPositionModel.status == "OPEN")
            .order_by(GoldFuturesPositionModel.opened_at.desc())
        )
        result = await self.session.execute(stmt)
        return [self._to_dict(r) for r in result.scalars().all()]

    async def list_positions(self, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(GoldFuturesPositionModel).order_by(GoldFuturesPositionModel.opened_at.desc())
        if status:
            stmt = stmt.where(GoldFuturesPositionModel.status == status.upper())
        result = await self.session.execute(stmt)
        return [self._to_dict(r) for r in result.scalars().all()]

    async def open_position(
        self,
        contract_symbol: str,
        position_type: str,
        entry_price: float,
        quantity: int,
        leverage: int = 10,
        stop_loss: float | None = None,
        target_1: float | None = None,
        target_2: float | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        calc = FuturesRiskCalculator(leverage=leverage)
        init_margin = calc.initial_margin(entry_price, quantity)
        maint_margin = calc.maintenance_margin(entry_price, quantity)
        liq = calc.liquidation_price(entry_price, position_type.upper())  # type: ignore[arg-type]

        pos = GoldFuturesPositionModel(
            id=new_id("gpos"),
            contract_symbol=contract_symbol,
            position_type=position_type.upper(),
            leverage=leverage,
            entry_price=entry_price,
            quantity=quantity,
            initial_margin=init_margin,
            maintenance_margin=maint_margin,
            liquidation_price=liq,
            opened_at=utc_now_naive(),
            entry_notes=notes,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            status="OPEN",
        )
        self.session.add(pos)
        await self.session.commit()
        logger.info(
            "Gold futures position opened: %s %s qty=%d entry=%.0f liq=%.0f",
            position_type,
            contract_symbol,
            quantity,
            entry_price,
            liq,
        )
        return self._to_dict(pos)

    async def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "MANUAL",
    ) -> dict[str, Any]:
        stmt = select(GoldFuturesPositionModel).where(GoldFuturesPositionModel.id == position_id)
        result = await self.session.execute(stmt)
        pos = result.scalar_one_or_none()
        if not pos:
            raise ValueError(f"position {position_id} not found")
        if pos.status != "OPEN":
            raise ValueError(f"position {position_id} already {pos.status}")

        direction = 1 if pos.position_type == "LONG" else -1
        pnl_irr = (exit_price - pos.entry_price) * direction * pos.quantity * FuturesRiskCalculator.CONTRACT_SIZE
        pnl_pct = ((exit_price - pos.entry_price) / pos.entry_price) * 100.0 * direction

        pos.exit_price = exit_price
        pos.exit_reason = reason
        pos.closed_at = utc_now_naive()
        pos.status = "CLOSED"
        pos.realized_pnl = round(pnl_irr, 2)
        pos.realized_pnl_pct = round(pnl_pct, 2)
        await self.session.commit()
        logger.info(
            "Gold futures position closed: %s exit=%.0f pnl=%.0f",
            position_id,
            exit_price,
            pnl_irr,
        )
        return self._to_dict(pos)

    @staticmethod
    def _to_dict(pos: GoldFuturesPositionModel) -> dict[str, Any]:
        return {
            "id": pos.id,
            "contract_symbol": pos.contract_symbol,
            "position_type": pos.position_type,
            "leverage": pos.leverage,
            "entry_price": pos.entry_price,
            "quantity": pos.quantity,
            "current_price": pos.current_price,
            "initial_margin": pos.initial_margin,
            "maintenance_margin": pos.maintenance_margin,
            "liquidation_price": pos.liquidation_price,
            "distance_to_liquidation_pct": pos.distance_to_liquidation_pct,
            "health_ratio": pos.health_ratio,
            "unrealized_pnl": pos.unrealized_pnl,
            "unrealized_pnl_pct": pos.unrealized_pnl_pct,
            "stop_loss": pos.stop_loss,
            "target_1": pos.target_1,
            "target_2": pos.target_2,
            "status": pos.status,
            "exit_price": pos.exit_price,
            "exit_reason": pos.exit_reason,
            "realized_pnl": pos.realized_pnl,
            "realized_pnl_pct": pos.realized_pnl_pct,
            "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
            "closed_at": pos.closed_at.isoformat() if pos.closed_at else None,
        }
