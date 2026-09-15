"""Ensemble Optimizer — finds the optimal combination of ML models for each market.

Uses historical accuracy data to:
  - Determine optimal model weights per market
  - Select the best model subset (eliminate low-performers)
  - Adapt to changing market conditions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


@dataclass
class ModelPerformance:
    """Performance data for a single model in a market."""

    model_name: str
    market: str
    accuracy_pct: float
    total_signals: int
    avg_return_pct: float
    sharpe: float
    weight: float = 0.0  # to be optimized
    is_selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "market": self.market,
            "accuracy_pct": round(self.accuracy_pct, 2),
            "total_signals": self.total_signals,
            "avg_return_pct": round(self.avg_return_pct, 2),
            "sharpe": round(self.sharpe, 3),
            "weight": round(self.weight, 3),
            "is_selected": self.is_selected,
        }


@dataclass
class OptimizedEnsemble:
    """Result of ensemble optimization for a market."""

    market: str
    models: list[ModelPerformance]
    num_selected: int
    expected_accuracy: float
    strategy: str  # accuracy_weighted / sharpe_weighted / top_n / equal
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "models": [m.to_dict() for m in self.models],
            "num_selected": self.num_selected,
            "expected_accuracy_pct": round(self.expected_accuracy, 2),
            "strategy": self.strategy,
        }


class EnsembleOptimizer:
    """Finds the optimal model weights and selection for each market."""

    # Minimum signals required to consider a model reliable
    MIN_SIGNALS = 20

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def optimize(
        self,
        market: str,
        strategy: str = "accuracy_weighted",
        min_models: int = 2,
        max_models: int = 4,
    ) -> Result[OptimizedEnsemble]:
        """Optimize ensemble for a given market using historical accuracy data."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return self._default_ensemble(market, strategy)

            async with async_session_factory() as session:
                # Get accuracy by source (model) for this market
                r = await session.execute(
                    text("""
                    SELECT source,
                           COUNT(*) as total,
                           SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct,
                           AVG(actual_return_pct) as avg_return,
                           AVG(actual_return_pct) / NULLIF(STDDEV(actual_return_pct), 0) as sharpe
                    FROM signal_accuracy
                    WHERE market = :market
                      AND outcome_set_at >= NOW() - INTERVAL '90 days'
                    GROUP BY source
                    HAVING COUNT(*) >= :min_signals
                    ORDER BY correct * 1.0 / COUNT(*) DESC
                """),
                    {"market": market, "min_signals": self.MIN_SIGNALS},
                )

                rows = r.fetchall()

                if not rows:
                    logger.info("No accuracy data for %s, using default ensemble", market)
                    return self._default_ensemble(market, strategy)

                # Build performance list
                performances: list[ModelPerformance] = []
                for row in rows:
                    total = row[1] or 0
                    correct = row[2] or 0
                    avg_return = row[3] or 0
                    sharpe = row[4] or 0

                    if total < self.MIN_SIGNALS:
                        continue

                    accuracy = correct / max(total, 1)
                    performances.append(
                        ModelPerformance(
                            model_name=row[0],
                            market=market,
                            accuracy_pct=accuracy * 100,
                            total_signals=total,
                            avg_return_pct=avg_return,
                            sharpe=sharpe,
                        )
                    )

                if not performances:
                    return self._default_ensemble(market, strategy)

                # Apply strategy
                if strategy == "accuracy_weighted":
                    return self._accuracy_weighted(performances, market, min_models, max_models)
                elif strategy == "sharpe_weighted":
                    return self._sharpe_weighted(performances, market, min_models, max_models)
                elif strategy == "top_n":
                    return self._top_n(performances, market, max_models)
                else:
                    return self._equal_weight(performances, market, max_models)

        except Exception as e:
            logger.error("Ensemble optimization failed for %s: %s", market, e)
            return self._default_ensemble(market, strategy)

    def _accuracy_weighted(
        self,
        models: list[ModelPerformance],
        market: str,
        min_models: int,
        max_models: int,
    ) -> Result[OptimizedEnsemble]:
        """Weight models by their accuracy, filter by threshold."""
        threshold = max(m.accuracy_pct for m in models) * 0.8
        selected = [m for m in models if m.accuracy_pct >= threshold]

        if len(selected) < min_models:
            selected = models[:max_models]

        selected = selected[:max_models]
        total_accuracy = sum(m.accuracy_pct for m in selected)

        for m in selected:
            m.weight = m.accuracy_pct / max(total_accuracy, 0.001)
            m.is_selected = True

        expected = sum(m.accuracy_pct * m.weight for m in selected)

        return Result.ok(
            OptimizedEnsemble(
                market=market,
                models=selected,
                num_selected=len(selected),
                expected_accuracy=expected,
                strategy="accuracy_weighted",
            )
        )

    def _sharpe_weighted(
        self,
        models: list[ModelPerformance],
        market: str,
        min_models: int,
        max_models: int,
    ) -> Result[OptimizedEnsemble]:
        """Weight models by Sharpe ratio."""
        selected = sorted(models, key=lambda m: m.sharpe, reverse=True)[:max_models]

        if len(selected) < min_models:
            selected = models[:max_models]

        total_sharpe = sum(max(m.sharpe, 0.01) for m in selected)

        for m in selected:
            m.weight = max(m.sharpe, 0.01) / max(total_sharpe, 0.001)
            m.is_selected = True

        expected = sum(m.accuracy_pct * m.weight for m in selected)

        return Result.ok(
            OptimizedEnsemble(
                market=market,
                models=selected,
                num_selected=len(selected),
                expected_accuracy=expected,
                strategy="sharpe_weighted",
            )
        )

    def _top_n(
        self,
        models: list[ModelPerformance],
        market: str,
        n: int,
    ) -> Result[OptimizedEnsemble]:
        """Select top N models by accuracy with equal weights."""
        selected = sorted(models, key=lambda m: m.accuracy_pct, reverse=True)[:n]

        weight = 1.0 / max(len(selected), 1)
        for m in selected:
            m.weight = weight
            m.is_selected = True

        expected = sum(m.accuracy_pct * m.weight for m in selected)

        return Result.ok(
            OptimizedEnsemble(
                market=market,
                models=selected,
                num_selected=len(selected),
                expected_accuracy=expected,
                strategy="top_n",
            )
        )

    def _equal_weight(
        self,
        models: list[ModelPerformance],
        market: str,
        n: int,
    ) -> Result[OptimizedEnsemble]:
        """Equal weight to top N models."""
        return self._top_n(models, market, n)

    def _default_ensemble(self, market: str, strategy: str) -> Result[OptimizedEnsemble]:
        """Return default ensemble configuration."""
        default_models = {
            "stock": ["xgboost", "lstm", "random_forest"],
            "gold": ["xgboost", "lstm", "gru"],
            "currency": ["xgboost", "lstm", "linear_regression"],
            "crypto": ["xgboost", "lstm", "transformer"],
            "option": ["xgboost", "random_forest", "linear_regression"],
            "commodity": ["xgboost", "lstm", "gru"],
            "ime": ["xgboost", "linear_regression", "random_forest"],
        }
        model_names = default_models.get(market, ["xgboost", "random_forest"])

        performances = [
            ModelPerformance(
                model_name=name,
                market=market,
                accuracy_pct=55.0,
                total_signals=0,
                avg_return_pct=0.0,
                sharpe=0.0,
                weight=1.0 / max(len(model_names), 1),
                is_selected=True,
            )
            for name in model_names
        ]

        return Result.ok(
            OptimizedEnsemble(
                market=market,
                models=performances,
                num_selected=len(performances),
                expected_accuracy=55.0,
                strategy="default",
            )
        )

    async def optimize_all_markets(self, strategy: str = "accuracy_weighted") -> Result[dict[str, OptimizedEnsemble]]:
        """Run optimization for all markets."""
        markets = ["stock", "gold", "currency", "crypto", "option", "commodity", "ime"]
        result: dict[str, OptimizedEnsemble] = {}

        for market in markets:
            r = await self.optimize(market, strategy=strategy)
            if r.success:
                result[market] = r.value

        return Result.ok(result)
