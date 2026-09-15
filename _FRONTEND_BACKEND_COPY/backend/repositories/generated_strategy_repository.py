"""Repository for generated strategies DB operations."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from models.generated_strategy import GeneratedStrategyModel, GenerationBatchModel


class GeneratedStrategyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, data: dict[str, Any]) -> Result[str]:
        """Save a generated strategy result. Returns the ID."""
        orm = GeneratedStrategyModel(
            id=data["id"],
            symbol=data.get("symbol", ""),
            entry_indicator=data.get("entry_indicator"),
            entry_params=json.dumps(data.get("entry_params", {}), ensure_ascii=False)
            if data.get("entry_params")
            else None,
            entry_condition=data.get("entry_condition"),
            exit_indicator=data.get("exit_indicator"),
            exit_params=json.dumps(data.get("exit_params", {}), ensure_ascii=False)
            if data.get("exit_params")
            else None,
            exit_condition=data.get("exit_condition"),
            filter1_indicator=data.get("filter1_indicator"),
            filter1_params=json.dumps(data.get("filter1_params", {}), ensure_ascii=False)
            if data.get("filter1_params")
            else None,
            filter1_condition=data.get("filter1_condition"),
            filter2_indicator=data.get("filter2_indicator"),
            filter2_params=json.dumps(data.get("filter2_params", {}), ensure_ascii=False)
            if data.get("filter2_params")
            else None,
            filter2_condition=data.get("filter2_condition"),
            stop_loss_pct=data.get("stop_loss_pct"),
            take_profit_pct=data.get("take_profit_pct"),
            trailing_stop=str(data.get("trailing_stop", False)),
            sizing_method=data.get("sizing_method"),
            sizing_value=data.get("sizing_value"),
            total_return_pct=data.get("total_return_pct"),
            annualized_return_pct=data.get("annualized_return_pct"),
            sharpe_ratio=data.get("sharpe_ratio"),
            sortino_ratio=data.get("sortino_ratio"),
            calmar_ratio=data.get("calmar_ratio"),
            max_drawdown_pct=data.get("max_drawdown_pct"),
            win_rate=data.get("win_rate"),
            profit_factor=data.get("profit_factor"),
            total_trades=data.get("total_trades"),
            winning_trades=data.get("winning_trades"),
            losing_trades=data.get("losing_trades"),
            score=data.get("score", 0),
            strategy_type=data.get("strategy_type"),
            batch_id=data.get("batch_id"),
            status="active",
        )
        self._session.add(orm)
        await self._session.flush()
        return Result.ok(orm.id)

    async def save_batch(self, items: list[dict[str, Any]]) -> Result[int]:
        """Save multiple strategies in one batch. Returns count saved."""
        count = 0
        for data in items:
            await self.save(data)
            count += 1
        return Result.ok(count)

    async def list_top(
        self,
        symbol: str | None = None,
        entry_indicator: str | None = None,
        exit_indicator: str | None = None,
        min_score: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Result[PaginatedResult[dict[str, Any]]]:
        """List top strategies with optional filters."""
        stmt = select(GeneratedStrategyModel).where(GeneratedStrategyModel.status == "active")

        if symbol:
            stmt = stmt.where(GeneratedStrategyModel.symbol == symbol)
        if entry_indicator:
            stmt = stmt.where(GeneratedStrategyModel.entry_indicator == entry_indicator)
        if exit_indicator:
            stmt = stmt.where(GeneratedStrategyModel.exit_indicator == exit_indicator)
        if min_score is not None:
            stmt = stmt.where(GeneratedStrategyModel.score >= min_score)

        # Count
        count_q = select(sa_func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_q)).scalar() or 0

        # Paginated fetch
        stmt = stmt.order_by(desc(GeneratedStrategyModel.score)).offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()

        items = [self._to_dict(r) for r in rows]
        total_pages = max(1, (total + limit - 1) // limit)

        return Result.ok(
            PaginatedResult(
                items=items,
                total=total,
                page=offset // limit + 1,
                page_size=limit,
                total_pages=total_pages,
            )
        )

    async def get(self, strategy_id: str) -> Result[dict[str, Any] | None]:
        stmt = select(GeneratedStrategyModel).where(GeneratedStrategyModel.id == strategy_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row:
            return Result.ok(self._to_dict(row))
        return Result.ok(None)

    async def count(self, symbol: str | None = None) -> int:
        stmt = select(sa_func.count()).select_from(GeneratedStrategyModel)
        if symbol:
            stmt = stmt.where(GeneratedStrategyModel.symbol == symbol)
        return (await self._session.execute(stmt)).scalar() or 0

    async def get_indicator_stats(self) -> list[dict[str, Any]]:
        """Get aggregate stats per entry indicator."""
        stmt = (
            select(
                GeneratedStrategyModel.entry_indicator,
                sa_func.count(),
                sa_func.avg(GeneratedStrategyModel.score),
                sa_func.avg(GeneratedStrategyModel.total_return_pct),
                sa_func.avg(GeneratedStrategyModel.sharpe_ratio),
            )
            .where(GeneratedStrategyModel.status == "active")
            .group_by(GeneratedStrategyModel.entry_indicator)
        )

        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "indicator": r[0],
                "count": r[1],
                "avg_score": round(r[2] or 0, 2),
                "avg_return": round(r[3] or 0, 2),
                "avg_sharpe": round(r[4] or 0, 2),
            }
            for r in rows
        ]

    async def save_batch_info(self, batch_data: dict[str, Any]) -> Result[str]:
        orm = GenerationBatchModel(
            id=batch_data["id"],
            symbols=json.dumps(batch_data.get("symbols", []), ensure_ascii=False),
            total_configs=batch_data.get("total_configs"),
            pre_filtered=batch_data.get("pre_filtered"),
            tested=batch_data.get("tested"),
            passed_filter=batch_data.get("passed_filter"),
            saved_to_db=batch_data.get("saved_to_db"),
            status=batch_data.get("status", "running"),
            started_at=batch_data.get("started_at"),
            completed_at=batch_data.get("completed_at"),
        )
        self._session.add(orm)
        await self._session.flush()
        return Result.ok(orm.id)

    def _to_dict(self, orm: GeneratedStrategyModel) -> dict[str, Any]:
        return {
            "id": orm.id,
            "symbol": orm.symbol,
            "entry_indicator": orm.entry_indicator,
            "entry_params": json.loads(orm.entry_params) if orm.entry_params else {},
            "entry_condition": orm.entry_condition,
            "exit_indicator": orm.exit_indicator,
            "exit_params": json.loads(orm.exit_params) if orm.exit_params else {},
            "exit_condition": orm.exit_condition,
            "filter1_indicator": orm.filter1_indicator,
            "filter1_condition": orm.filter1_condition,
            "stop_loss_pct": orm.stop_loss_pct,
            "take_profit_pct": orm.take_profit_pct,
            "sizing_method": orm.sizing_method,
            "total_return_pct": orm.total_return_pct,
            "annualized_return_pct": orm.annualized_return_pct,
            "sharpe_ratio": orm.sharpe_ratio,
            "sortino_ratio": orm.sortino_ratio,
            "calmar_ratio": orm.calmar_ratio,
            "max_drawdown_pct": orm.max_drawdown_pct,
            "win_rate": orm.win_rate,
            "profit_factor": orm.profit_factor,
            "total_trades": orm.total_trades,
            "winning_trades": orm.winning_trades,
            "losing_trades": orm.losing_trades,
            "score": orm.score,
            "strategy_type": orm.strategy_type,
            "batch_id": orm.batch_id,
            "status": orm.status,
            "created_at": orm.created_at.isoformat() if orm.created_at else None,
        }
