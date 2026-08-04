"""Multi-Market Signal Dashboard API endpoint.

Uses the QuantSignalOrchestrator for the full pipeline:
  Engine → ML predictions → Voting → Confidence calibration → Cross-market signals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


@router.get("", summary="Multi-market signals", description="Aggregated buy/sell signals from all markets with ML voting & calibrated confidence")
async def get_multi_market_signals(
    timeframe: str = Query("all", description="daily / 2day / 3day / weekly / monthly / quarterly / all"),
    market: str = Query("all", description="stock / gold / currency / crypto / option / commodity / ime / all"),
    signal: str = Query("all", description="buy / sell / hold / all"),
    min_strength: float = Query(0.0, ge=0.0, le=1.0),
    min_confidence: float = Query(0.40, ge=0.0, le=1.0, description="Minimum calibrated confidence threshold"),
    sort_by: str = Query("boosted_score", description="boosted_score / confidence / rule_score / strength / change_pct"),
    use_ml: bool = Query(True, description="Enable ML predictions & voting"),
    use_confidence: bool = Query(True, description="Enable confidence calibration"),
    limit: int = Query(50, ge=1, le=200),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.quant_signal_orchestrator import QuantSignalOrchestrator

        orchestrator = QuantSignalOrchestrator()
        report = await orchestrator.generate(
            market_filter=market,
            timeframe_filter=timeframe,
            signal_filter=signal,
            min_strength=min_strength,
            min_confidence=min_confidence,
            limit=limit,
            use_ml=use_ml,
            use_voting=use_ml,
            use_confidence_calibration=use_confidence,
        )

        data = report.to_dict()

        # Sort
        signals_list = data.get("signals", [])
        if sort_by == "confidence":
            signals_list.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        elif sort_by == "rule_score":
            signals_list.sort(key=lambda s: s.get("rule_score", 0), reverse=True)
        elif sort_by == "strength":
            signals_list.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        elif sort_by == "change_pct":
            signals_list.sort(key=lambda s: abs(s.get("change_pct", 0)), reverse=True)
        else:
            signals_list.sort(key=lambda s: s.get("boosted_score", 0), reverse=True)
        data["signals"] = signals_list

        return ApiResponse(
            success=True,
            data=data,
        )
    except Exception as e:
        logger.exception("Multi-market signal generation failed")
        return ApiResponse(
            success=False,
            data=None,
            error={"message": str(e)},
        )


@router.get("/retrain", summary="Auto-retrain status", description="Trigger auto-retrain for markets with low accuracy. Note: triggers actual model retraining which may take 30+ seconds.")
async def trigger_retrain(
    market: str = Query("all", description="stock / gold / currency / crypto / option / commodity / ime / all — retrain specific market"),
    force: bool = Query(False, description="Force retrain regardless of accuracy threshold"),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.auto_retrain_pipeline import AutoRetrainPipeline
        from services.signal_accuracy_tracker import SignalAccuracyTracker

        pipeline = AutoRetrainPipeline()
        tracker = SignalAccuracyTracker()

        # Get current accuracy first
        accuracy_result = await tracker.get_accuracy_by_market(days=30)
        current_accuracy: dict[str, float] = {}
        if accuracy_result.success and accuracy_result.value:
            items = accuracy_result.value.items if hasattr(accuracy_result.value, "items") else []
            for item in items:
                current_accuracy[item.get("market", "?")] = item.get("accuracy_pct", 0.0)

        if market != "all":
            # Retrain a single market
            result = await pipeline.check_and_retrain(market=market, force=force, trigger="manual")
            reports = [result.value.to_dict()] if result.success and result.value else []
        else:
            # Retrain all markets
            result = await pipeline.retrain_all_markets(force=force)
            reports = [r.to_dict() for r in (result.value if result.success else [])]

        return ApiResponse(
            success=True,
            data={
                "retrain_reports": reports,
                "accuracy_before": current_accuracy,
                "force": force,
                "market": market,
            },
        )
    except Exception as e:
        logger.exception("Retrain trigger failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.get("/summary", summary="Signal summary by market", description="Quick summary of signal counts per market with confidence & cross-market insights")
async def get_signal_summary() -> ApiResponse[dict[str, Any]]:
    try:
        from services.quant_signal_orchestrator import QuantSignalOrchestrator

        orchestrator = QuantSignalOrchestrator()
        report = await orchestrator.generate(
            timeframe_filter="daily",
            min_confidence=0.35,
            limit=200,
        )

        data = report.to_dict()
        signals_list = data.get("signals", [])
        summary = data.get("summary", {})

        # Top 10 best buy signals sorted by confidence
        buys = [s for s in signals_list if s.get("direction") == "buy"]
        buys.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        top_buys = buys[:10]

        return ApiResponse(
            success=True,
            data={
                "total": summary.get("total_signals", 0),  # backward compat
                "total_signals": summary.get("total_signals", 0),
                "buy_count": summary.get("buy_count", 0),
                "sell_count": summary.get("sell_count", 0),
                "hold_count": summary.get("hold_count", 0),
                "avg_confidence": summary.get("avg_confidence", 0),
                "calibration_counts": summary.get("calibration_counts", {}),
                "markets": summary.get("markets", {}),
                "top_buys": top_buys,
                "cross_market": data.get("cross_market", []),
                "accuracy": data.get("accuracy", {}),
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.exception("Signal summary failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})
