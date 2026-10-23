from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

from app.alert_hub.models import SymbolAssessmentSnapshotOut, SymbolAssessmentTask


class AssessmentOrchestrator:
    """Orchestrate parallel assessment modules for a single symbol.

    Each module is intended to be a thin wrapper around existing services
    (Market / Codal / ML / Backtest). Modules can return partial results,
    and the orchestrator merges them into a snapshot for storage.
    """

    def __init__(self, *, max_concurrency: int = 4) -> None:
        self._max_concurrency = max_concurrency

    async def assess(self, task: SymbolAssessmentTask) -> SymbolAssessmentSnapshotOut:
        slots = asyncio.Semaphore(self._max_concurrency)

        async def with_slot(fn):
            async with slots:
                return await fn()

        market, codal, ml, backtest = await asyncio.gather(
            with_slot(lambda: self._run_market(task)),
            with_slot(lambda: self._run_codal(task)),
            with_slot(lambda: self._run_ml(task)),
            with_slot(lambda: self._run_backtest(task)),
        )

        decision = self._synthesize_decision(task.symbol, market, codal, ml, backtest)

        return SymbolAssessmentSnapshotOut(
            symbol=task.symbol,
            market_metrics=market,
            ml_prediction=ml,
            backtest_summary=backtest,
            codal_signals=codal,
            decision_summary=decision,
            last_evaluated_at=datetime.now(UTC).isoformat(),
        )

    # ── modules ──────────────────────────────────────────────────────────

    async def _run_market(self, task: SymbolAssessmentTask) -> dict[str, Any]:
        try:
            from app.alert_hub.services import market as market_mod

            return await market_mod.get_market_metrics(task.symbol)
        except Exception as e:
            logger.warning("market module failed for %s: %s", task.symbol, e)
            return {}

    async def _run_codal(self, task: SymbolAssessmentTask) -> dict[str, Any]:
        try:
            from app.alert_hub.services import codal as codal_mod

            return await codal_mod.get_codal_signals(task.symbol)
        except Exception as e:
            logger.warning("codal module failed for %s: %s", task.symbol, e)
            return {}

    async def _run_ml(self, task: SymbolAssessmentTask) -> dict[str, Any]:
        try:
            from app.alert_hub.services import ml as ml_mod

            return await ml_mod.get_ml_prediction(task.symbol)
        except Exception as e:
            logger.warning("ml module failed for %s: %s", task.symbol, e)
            return {}

    async def _run_backtest(self, task: SymbolAssessmentTask) -> dict[str, Any]:
        try:
            from app.alert_hub.services import backtest as backtest_mod

            return await backtest_mod.get_backtest_summary(task.symbol)
        except Exception as e:
            logger.warning("backtest module failed for %s: %s", task.symbol, e)
            return {}

    # ── synthesis ────────────────────────────────────────────────────────

    def _synthesize_decision(
        self,
        symbol: str,
        market: dict[str, Any],
        codal: dict[str, Any],
        ml: dict[str, Any],
        backtest: dict[str, Any],
    ) -> dict[str, Any]:
        buy_points: list[str] = []
        risk_points: list[str] = []

        ml_confidence = (ml.get("confidence") or 0)
        ml_direction = (ml.get("direction") or "").lower()
        if ml_confidence and ml_confidence >= 0.6:
            buy_points.append("ML Direction with acceptable confidence")
        if market.get("buyerPower"):
            buy_points.append("Buyer power flow detected")
        if codal.get("sentiment") == "positive":
            buy_points.append("Recent Codal sentiment positive")
        if backtest.get("bestStrategy"):
            buy_points.append("Backtest best strategy aligned")

        if ml_confidence and ml_confidence < 0.4:
            risk_points.append("Low ML confidence")
        if market.get("spreadHigh"):
            risk_points.append("Wide spread observed")
        if codal.get("sentiment") == "negative":
            risk_points.append("Recent Codal sentiment negative")
        if backtest.get("maxDrawdown") and backtest.get("maxDrawdown", 0) <= -20:
            risk_points.append("Historical max drawdown severe")

        return {
            "buy_points": buy_points,
            "risk_points": risk_points,
            "summary": (
                "Buy-oriented" if len(buy_points) > len(risk_points)
                else "Watch/Cautious" if len(buy_points) == len(risk_points)
                else "Sell/Risk-oriented"
            ),
        }
