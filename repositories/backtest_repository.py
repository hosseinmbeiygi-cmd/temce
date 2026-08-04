from __future__ import annotations

import contextlib

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.backtest.entities import BacktestRun
from domain.backtest.trades import BacktestTrade
from domain.common.enum_types import OrderSide
from models.backtest import BacktestRunModel, BacktestTradeModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class BacktestRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[BacktestRun] | None = None if session else InMemoryRepository[BacktestRun]()
        self._db: _BacktestDbRepo | None = None if not session else _BacktestDbRepo(session)

    async def get(self, id: str) -> Result[BacktestRun]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: BacktestRun) -> Result[BacktestRun]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[BacktestRun]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_status(self, status: str) -> Result[list[BacktestRun]]:
        if self._db:
            return await self._db.get_by_status(status)
        matches = [r for r in self._mem._store.values() if r.status == status]
        return Result.ok(matches)

    async def get_by_strategy(self, strategy_name: str) -> Result[list[BacktestRun]]:
        if self._db:
            return await self._db.get_by_strategy(strategy_name)
        matches = [r for r in self._mem._store.values() if r.strategy_name == strategy_name]
        return Result.ok(matches)

    async def save_trade(self, entity: BacktestTrade) -> Result[BacktestTrade]:
        if self._db:
            return await self._db.save_trade(entity)
        return Result.ok(entity)

    async def get_trades_by_run(self, run_id: str) -> Result[list[BacktestTrade]]:
        if self._db:
            return await self._db.get_trades_by_run(run_id)
        return Result.ok([])

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)


class _BacktestDbRepo(DbRepository[BacktestRun, BacktestRunModel]):
    model_class = BacktestRunModel

    async def get_by_status(self, status: str) -> Result[list[BacktestRun]]:
        stmt = select(BacktestRunModel).where(BacktestRunModel.status == status).order_by(desc(BacktestRunModel.created_at))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_by_strategy(self, strategy_name: str) -> Result[list[BacktestRun]]:
        stmt = select(BacktestRunModel).where(BacktestRunModel.strategy_type == strategy_name).order_by(desc(BacktestRunModel.created_at))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def save_trade(self, entity: BacktestTrade) -> Result[BacktestTrade]:
        orm = BacktestTradeModel(
            id=entity.id,
            run_id=entity.backtest_run_id,
            symbol=entity.symbol or None,
            direction=entity.side.value if entity.side else None,
            entry_date=entity.entry_date or None,
            exit_date=entity.exit_date or None,
            entry_price=entity.entry_price or None,
            exit_price=entity.exit_price or None,
            quantity=entity.quantity or None,
            gross_profit=entity.pnl or None,
            net_profit=entity.pnl or None,
            return_pct=entity.return_pct or None,
            exit_reason=entity.exit_reason or None,
            created_at=entity.created_at,
        )
        self.session.add(orm)
        await self.session.flush()
        return Result.ok(self._trade_to_domain(orm))

    async def get_trades_by_run(self, run_id: str) -> Result[list[BacktestTrade]]:
        stmt = select(BacktestTradeModel).where(BacktestTradeModel.run_id == run_id).order_by(BacktestTradeModel.entry_date)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._trade_to_domain(r) for r in rows])

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(BacktestRunModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _trade_to_domain(self, orm: BacktestTradeModel) -> BacktestTrade:
        side = OrderSide(orm.direction) if orm.direction else OrderSide.BUY
        return BacktestTrade(
            id=orm.id,
            backtest_run_id=orm.run_id,
            instrument_id="",
            side=side,
            symbol=orm.symbol or "",
            entry_price=orm.entry_price or 0.0,
            exit_price=orm.exit_price or 0.0,
            quantity=orm.quantity or 0,
            entry_date=orm.entry_date or "",
            exit_date=orm.exit_date or "",
            pnl=orm.gross_profit or 0.0,
            return_pct=orm.return_pct or 0.0,
            exit_reason=orm.exit_reason or "",
            created_at=orm.created_at,
        )

    def _to_domain(self, orm: BacktestRunModel) -> BacktestRun:
        import json
        from datetime import date

        symbols = []
        if orm.symbols:
            try:
                symbols = json.loads(orm.symbols)
            except (json.JSONDecodeError, TypeError):
                symbols = [s.strip() for s in orm.symbols.split(",") if s.strip()]

        start = None
        if orm.start_date:
            with contextlib.suppress(ValueError, TypeError):
                start = date.fromisoformat(orm.start_date)
        end = None
        if orm.end_date:
            with contextlib.suppress(ValueError, TypeError):
                end = date.fromisoformat(orm.end_date)

        extra = {}
        if orm.metrics:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                extra = json.loads(orm.metrics)

        return BacktestRun(
            id=orm.id,
            name=orm.name,
            strategy_name=orm.strategy_type or "",
            instrument_ids=symbols,
            start_date=start,
            end_date=end,
            initial_capital=orm.initial_capital or 1000000.0,
            current_capital=orm.current_value or 0.0,
            total_pnl=0.0,
            total_return_pct=orm.total_return_pct or 0.0,
            status=orm.status or "draft",
            extra=extra,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, domain: BacktestRun) -> BacktestRunModel:
        import json

        symbols_json = json.dumps(domain.instrument_ids, ensure_ascii=False) if domain.instrument_ids else None
        metrics_json = json.dumps(domain.extra, ensure_ascii=False) if domain.extra else None
        return BacktestRunModel(
            id=domain.id,
            name=domain.name,
            strategy_type=domain.strategy_name or None,
            symbols=symbols_json,
            status=domain.status or "draft",
            start_date=domain.start_date.isoformat() if domain.start_date else None,
            end_date=domain.end_date.isoformat() if domain.end_date else None,
            initial_capital=domain.initial_capital or None,
            current_value=domain.current_capital or None,
            total_return_pct=domain.total_return_pct or None,
            metrics=metrics_json,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
