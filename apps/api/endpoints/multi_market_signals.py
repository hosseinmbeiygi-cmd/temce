"""Multi-Market Signal Dashboard API endpoint.

Uses the QuantSignalOrchestrator for the full pipeline:
  Engine → ML predictions → Voting → Confidence calibration → Cross-market signals.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Query

from core.logging import get_logger
from core.time import utc_now_naive
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()

# ── In-memory cache ──────────────────────────────────────────────────────────
# The full pipeline (rule engine → ML → voting → calibration → decision →
# persistence) takes tens of seconds on a single call. Signals change every
# few minutes at most, so we cache the generated report for a short TTL and
# rebuild it in the background (stale-while-revalidate) so the API never
# blocks a user request on a slow regeneration.
#
# IMPORTANT: the cache key deliberately covers ONLY the filters that change
# the pipeline output shape (market/timeframe/signal/ML switches).
# min_confidence, min_strength and limit are applied server-side AFTER the
# cache hit (they only slice/filter the generated superset), so every
# dashboard/filter combination reuses the same cached build instead of
# triggering a fresh 60s synchronous pipeline run per request.
_CACHE_TTL_SECONDS = 90.0
_cache: dict[str, Any] | None = None
_cache_at: float = 0.0

# Tracks keys with a background rebuild already in flight so requests during
# a rebuild don't each spawn another one.
_rebuild_in_flight: set[str] = set()

# The pipeline is always built with a generous superset so any requested
# (min_confidence, min_strength, limit) can be derived from the cache.
_PIPELINE_LIMIT = 200
_PIPELINE_MIN_CONFIDENCE = 0.0

# Serialize pipeline builds: the full pipeline is heavy (tens of seconds)
# and two concurrent builds (frontend polling + dashboard) would hammer the DB
# and each other. Only one build runs at a time; other requests wait for the
# cached result.
_pipeline_semaphore = asyncio.Semaphore(1)


async def _build_report(key: str, factory: Any) -> dict[str, Any]:
    """Build (and store) a fresh report for ``key`` under the semaphore.

    The cache is re-checked AFTER acquiring the semaphore, and the cache is
    set BEFORE releasing it, so concurrent callers (startup warm-up + first
    user request, or polling frontends) never run the pipeline twice for the
    same key and never observe a half-built cache.
    """
    global _cache, _cache_at
    async with _pipeline_semaphore:
        now = time.monotonic()
        if _cache is not None and _cache[0] == key and (now - _cache_at) < _CACHE_TTL_SECONDS:
            return _cache[1]
        report = await factory()
        _cache = (key, report)
        _cache_at = time.monotonic()
        return report


async def warm_signal_cache() -> None:
    """Pre-build the cache for the most-used frontend filter at startup.

    Called from the app lifespan after DB init so the first user request on
    the signals page hits a warm cache instead of blocking on a 60s pipeline.
    """
    try:
        from services.quant_signal_orchestrator import QuantSignalOrchestrator

        key = _cache_key(True, True)

        async def _build() -> dict[str, Any]:
            orchestrator = QuantSignalOrchestrator()
            report = await orchestrator.generate(
                market_filter="all",
                timeframe_filter="all",
                signal_filter="all",
                min_strength=0.0,
                min_confidence=_PIPELINE_MIN_CONFIDENCE,
                limit=_PIPELINE_LIMIT,
                use_ml=True,
                use_voting=True,
                use_confidence_calibration=True,
            )
            return report.to_dict()

        report = await _build_report(key, _build)  # stores into _cache itself
        logger.info("Signal cache warmed at startup: %d signals", len(report.get("signals", [])))
    except Exception:
        logger.exception("Startup signal cache warm-up failed")


def _cache_key(use_ml: bool, use_confidence: bool) -> str:
    """Cache key.

    The pipeline is always built as the FULL superset (all markets / all
    timeframes / all directions) so a single cache entry serves every filter
    combination. market / timeframe / signal / min_strength / min_confidence /
    limit are applied server-side after the cache hit — otherwise switching
    any dashboard filter would trigger a fresh multi-minute pipeline build.
    """
    return f"{use_ml}|{use_confidence}"


async def _get_cached_report(
    key: str, factory: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (cached_report, rebuild_task).

    If the cache is fresh, returns it. If stale, kicks off a background
    rebuild (only one at a time) and returns the previous snapshot.
    If empty, builds synchronously on first call.
    """
    global _cache, _cache_at
    now = time.monotonic()
    if _cache is not None and _cache[0] == key and (now - _cache_at) < _CACHE_TTL_SECONDS:
        return _cache[1], None
    if _cache is not None and _cache[0] == key:
        # Stale value: refresh in background, serve current data.
        if key not in _rebuild_in_flight:
            _cache_at = time.monotonic()  # avoid re-triggering per request
            _rebuild_in_flight.add(key)
            task = asyncio.create_task(_run_background_rebuild(key, factory))
            return _cache[1], task
        return _cache[1], None
    # Empty/different key — build synchronously (the semaphore re-checks the
    # cache, so a just-completed warm-up is reused instead of rebuilt).
    return await _build_report(key, factory), None


async def _run_background_rebuild(key: str, factory: Any) -> None:
    """Background task that regenerates the report for the current key."""
    try:
        await _build_report(key, factory)  # stores into _cache under the semaphore
        logger.info("Signal cache rebuilt in background (%s)", key)
    except Exception:
        logger.exception("Background signal cache rebuild failed (%s)", key)
    finally:
        _rebuild_in_flight.discard(key)


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

        # The cache holds ONE full superset build (all markets/timeframes/
        # directions); every request filter is applied server-side below so no
        # filter change ever triggers a pipeline rebuild.
        key = _cache_key(use_ml, use_confidence)

        async def _build() -> dict[str, Any]:
            # The pipeline is serialized inside _build_report (semaphore).
            orchestrator = QuantSignalOrchestrator()
            report = await orchestrator.generate(
                market_filter="all",
                timeframe_filter="all",
                signal_filter="all",
                min_strength=0.0,
                min_confidence=_PIPELINE_MIN_CONFIDENCE,
                limit=_PIPELINE_LIMIT,
                use_ml=use_ml,
                use_voting=use_ml,
                use_confidence_calibration=use_confidence,
            )
            return report.to_dict()

        data, _rebuild_task = await _get_cached_report(key, _build)
        if data is None:
            data = {
                "signals": [],
                "summary": {
                    "total_signals": 0, "buy_count": 0, "sell_count": 0,
                    "hold_count": 0, "avg_confidence": 0,
                },
                "generated_at": utc_now_naive().isoformat(),
            }

        # Work on a COPY — the cached report is shared across requests and
        # filtering it in place would permanently shrink/mutate the cache for
        # every later request (e.g. a gold+buy query writing [] into the cache).
        data = dict(data)
        signals_list = list(data.get("signals", []))
        if market != "all":
            signals_list = [s for s in signals_list if s.get("market") == market]
        if timeframe != "all":
            signals_list = [s for s in signals_list if s.get("timeframe") == timeframe]
        if signal != "all":
            signals_list = [s for s in signals_list if s.get("direction") == signal]
        if min_confidence > 0:
            signals_list = [s for s in signals_list if (s.get("confidence") or 0) >= min_confidence]
        if min_strength > 0:
            signals_list = [s for s in signals_list if (s.get("boosted_score") or 0) / 100.0 >= min_strength]

        # Sort

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
        signals_list = signals_list[:limit]
        data["signals"] = signals_list

        # Recompute the summary from the FILTERED list so the returned counts
        # always match the returned signals (the cached summary describes the
        # full superset and would otherwise lie after market/conf filters).
        summary = dict(data.get("summary") or {})
        buy_count = sum(1 for s in signals_list if s.get("direction") == "buy")
        sell_count = sum(1 for s in signals_list if s.get("direction") == "sell")
        hold_count = sum(1 for s in signals_list if s.get("direction") in ("hold", "wait"))
        summary["total_signals"] = len(signals_list)
        summary["buy_count"] = buy_count
        summary["sell_count"] = sell_count
        summary["hold_count"] = hold_count
        summary["avg_confidence"] = round(
            sum((s.get("confidence") or 0) for s in signals_list) / max(len(signals_list), 1), 3
        ) if signals_list else 0.0
        by_market: dict[str, dict[str, int]] = {}
        for s in signals_list:
            m = s.get("market", "?")
            d = s.get("direction", "hold")
            bucket = by_market.setdefault(m, {"buy": 0, "sell": 0, "hold": 0})
            bucket[d if d in ("buy", "sell") else "hold"] += 1
        summary["markets"] = by_market
        data["summary"] = summary

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
                "generated_at": utc_now_naive().isoformat(),
            },
        )
    except Exception as e:
        logger.exception("Signal summary failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})
