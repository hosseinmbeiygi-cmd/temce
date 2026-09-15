from __future__ import annotations

import contextlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, cast, not_, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.result import PaginatedResult, Result
from models.ml import MlPredictionModel


class PredictionRepository:
    """Repository for persisting ML prediction results to the database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_batch(self, predictions: list[dict[str, Any]]) -> Result[int]:
        """Save a list of prediction results to the database.

        Each dict is mapped to an MlPredictionModel row.
        Returns the count of saved rows.
        """
        rows = []
        for pred in predictions:
            feat_imp = pred.get("feature_importance")
            rows.append(
                MlPredictionModel(
                    id=new_id("mlpred"),
                    batch_id=pred.get("batch_id", ""),
                    symbol=pred.get("symbol", ""),
                    model_type=pred.get("model_type", ""),
                    prediction=pred.get("prediction"),
                    accuracy=pred.get("accuracy", 0),
                    confidence=pred.get("confidence", 0),
                    f1_score=pred.get("f1_score", 0),
                    mse=pred.get("mse", 0),
                    samples=pred.get("samples", 0),
                    duration_seconds=pred.get("duration_seconds", 0),
                    predicted_change_pct=pred.get("predicted_change_pct"),
                    last_price=pred.get("last_price"),
                    feature_importance=json.dumps(feat_imp, ensure_ascii=False) if feat_imp else None,
                    model_loaded_from=pred.get("model_loaded_from"),
                    prediction_failed=pred.get("prediction_failed", False),
                    model_id=pred.get("model_id"),
                    executed_at=datetime.now(),
                )
            )
        self.session.add_all(rows)
        await self.session.flush()
        return Result.ok(len(rows))

    async def list_by_batch(self, batch_id: str) -> Result[list[dict[str, Any]]]:
        """Retrieve all predictions for a given batch."""
        stmt = (
            select(MlPredictionModel).where(MlPredictionModel.batch_id == batch_id).order_by(MlPredictionModel.symbol)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_dict(r) for r in rows])

    async def list_recent(self, limit: int = 500, symbol: str | None = None) -> Result[list[dict[str, Any]]]:
        """Retrieve the most recent predictions, optionally filtered by symbol."""
        stmt = select(MlPredictionModel)
        if symbol:
            stmt = stmt.where(MlPredictionModel.symbol.ilike(f"%{symbol}%"))
        stmt = stmt.order_by(MlPredictionModel.executed_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_dict(r) for r in rows])

    async def list_batches(self, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[dict[str, Any]]]:
        """List distinct batch IDs with their execution times."""
        count_stmt = select(sa_func.count()).select_from(select(MlPredictionModel.batch_id).distinct().subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(
                MlPredictionModel.batch_id,
                sa_func.max(MlPredictionModel.executed_at).label("last_executed"),
                sa_func.count().label("total_symbols"),
                sa_func.sum(cast(not_(MlPredictionModel.prediction_failed), Integer)).label("successful"),
            )
            .group_by(MlPredictionModel.batch_id)
            .order_by(sa_func.max(MlPredictionModel.executed_at).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        batches = [
            {
                "batch_id": row.batch_id,
                "executed_at": row.last_executed.isoformat() if row.last_executed else "",
                "total_symbols": row.total_symbols,
                "successful": row.successful or 0,
            }
            for row in result
        ]
        return Result.ok(
            PaginatedResult(
                items=batches,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    def _to_dict(self, row: MlPredictionModel) -> dict[str, Any]:
        feat = None
        if row.feature_importance:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                feat = json.loads(row.feature_importance)
        return {
            "id": row.id,
            "batch_id": row.batch_id,
            "symbol": row.symbol,
            "model_type": row.model_type,
            "prediction": row.prediction or 0,
            "accuracy": row.accuracy or 0,
            "confidence": row.confidence or 0,
            "f1_score": row.f1_score or 0,
            "mse": row.mse or 0,
            "samples": row.samples or 0,
            "duration_seconds": row.duration_seconds or 0,
            "predicted_change_pct": row.predicted_change_pct,
            "last_price": row.last_price,
            "feature_importance": feat or {},
            "model_loaded_from": row.model_loaded_from or "",
            "prediction_failed": row.prediction_failed or False,
            "executed_at": row.executed_at.isoformat() if row.executed_at else "",
            "timestamp": row.executed_at.isoformat() if row.executed_at else "",
        }
