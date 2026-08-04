"""Signal Insights & Performance Dashboard API.

Provides endpoints for:
  - Signal accuracy by market/source/symbol
  - Signal backtesting against historical data
  - Walk-forward validation results
  - Ensemble optimization status
  - Confidence scoring breakdowns
  - Risk-adjusted filter results
  - Auto-retrain pipeline triggers
  - Multi-timeframe confirmation
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


@router.get("/accuracy", summary="Signal accuracy by market",
            description="Get signal accuracy metrics grouped by market and source")
async def get_signal_accuracy(
    market: str = Query("all", description="stock / gold / currency / crypto / option / commodity / ime / all"),
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.signal_accuracy_tracker import SignalAccuracyTracker

        tracker = SignalAccuracyTracker()
        market_filter = None if market == "all" else market
        result = await tracker.get_accuracy_by_market(
            market=market_filter, days=days, page=page, page_size=page_size
        )

        if not result.success:
            return ApiResponse(success=False, data=None, error={"message": result.error or "Unknown error"})

        return ApiResponse(
            success=True,
            data={
                "items": result.value.items,
                "total": result.value.total,
                "page": result.value.page,
                "page_size": result.value.page_size,
                "total_pages": result.value.total_pages,
                "filters": {"market": market, "days": days},
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.exception("Signal accuracy endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.get("/accuracy/symbol/{symbol}", summary="Signal accuracy by symbol",
            description="Get detailed accuracy metrics for a specific symbol")
async def get_symbol_accuracy(
    symbol: str,
    days: int = Query(90, ge=1, le=365),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.signal_accuracy_tracker import SignalAccuracyTracker

        tracker = SignalAccuracyTracker()
        result = await tracker.get_accuracy_by_symbol(symbol=symbol, days=days)

        if not result.success:
            return ApiResponse(success=False, data=None, error={"message": result.error or "Unknown error"})

        return ApiResponse(success=True, data=result.value)
    except Exception as e:
        logger.exception("Symbol accuracy endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.post("/backtest", summary="Backtest signals",
             description="Run backtest on generated signals against historical price data")
async def backtest_signals(
    market: str = Query("all", description="Market filter: stock / gold / etc."),
    source: str = Query("all", description="Source filter: rule_based / ml_ensemble / etc."),
    days_forward: int = Query(30, ge=5, le=90),
    limit: int = Query(100, ge=1, le=500),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.multi_market_signal_engine import MultiMarketSignalEngine
        from services.signal_backtest_engine import SignalBacktestEngine

        # Generate signals first
        engine = MultiMarketSignalEngine()
        signals, _ = await engine.generate_all(
            market_filter=market,
            signal_filter="all",
            limit=limit,
        )

        if not signals:
            return ApiResponse(
                success=True,
                data={
                    "total_signals": 0,
                    "note": "No signals generated to backtest",
                    "filters": {"market": market, "days_forward": days_forward},
                },
            )

        # Backtest
        backtester = SignalBacktestEngine()
        result = await backtester.backtest_signals(
            signals=[s.to_dict() for s in signals],
            days_forward=days_forward,
            market=None if market == "all" else market,
            source=None if source == "all" else source,
        )

        if not result.success:
            return ApiResponse(success=False, data=None, error={"message": result.error or "Backtest failed"})

        return ApiResponse(
            success=True,
            data={
                **result.value.to_dict(),
                "signals_tested": len(signals),
                "filters": {"market": market, "source": source, "days_forward": days_forward},
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.exception("Backtest endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.get("/walk-forward", summary="Walk-forward validation",
            description="Run walk-forward validation for ML models on a market")
async def get_walk_forward(
    market: str = Query("stock", description="Market to validate"),
    model_name: str = Query("xgboost", description="ML model name"),
    num_windows: int = Query(5, ge=2, le=20),
) -> ApiResponse[dict[str, Any]]:
    try:
        from sqlalchemy import text

        from core.database import async_session_factory
        from services.signal_feature_pipeline import SignalFeaturePipeline
        from services.walk_forward_validator import WalkForwardValidator

        if async_session_factory is None:
            return ApiResponse(success=False, data=None, error={"message": "Database not available"})

        async with async_session_factory() as session:
            table_map = {
                "stock": "brsapi_historical_daily",
                "gold": "brsapi_gold_coin_history",
                "currency": "brsapi_currency_history",
                "crypto": "brsapi_gold_currency_pro_daily_history",
            }
            table = table_map.get(market, "brsapi_historical_daily")

            # Get highest-volume symbol
            r = await session.execute(text(f"""
                SELECT symbol FROM {table}
                WHERE price_close > 0 AND trade_volume > 0
                GROUP BY symbol
                ORDER BY SUM(trade_volume) DESC LIMIT 1
            """))
            row = r.fetchone()
            if not row:
                return ApiResponse(success=False, data=None, error={"message": "No data available"})

            symbol = row[0]

            # Fetch price history
            r2 = await session.execute(text(f"""
                SELECT price_close, trade_volume, price_max, price_min
                FROM {table}
                WHERE symbol = :symbol AND price_close > 0
                ORDER BY date DESC LIMIT 500
            """), {"symbol": symbol})
            hist = r2.fetchall()

            closes = [float(row[0]) for row in reversed(hist)]
            volumes = [float(row[1] or 0) for row in reversed(hist)]
            highs = [float(row[2] or 0) for row in reversed(hist)]
            lows = [float(row[3] or 0) for row in reversed(hist)]

            if len(closes) < 100:
                return ApiResponse(success=False, data=None, error={"message": "Not enough historical data"})

            pipeline = SignalFeaturePipeline()
            all_features = []
            all_targets = []

            # Create rolling features
            for i in range(50, len(closes)):
                price_data = {
                    "closes": closes[:i],
                    "volumes": volumes[:i],
                    "highs": highs[:i],
                    "lows": lows[:i],
                    "values": [v * c for v, c in zip(volumes[:i], closes[:i], strict=False)],
                    "last_price": closes[i - 1],
                }
                features = await pipeline.extract(
                    symbol=symbol, market=market, price_data=price_data,
                )
                all_features.append(features)

                # Target: next 5-day return
                min(5, len(closes) - i - 1)
                future_ret = (closes[i] - closes[i - 1]) / max(closes[i - 1], 0.001)
                all_targets.append(future_ret)

            if len(all_features) < 50:
                return ApiResponse(success=False, data=None, error={"message": "Not enough feature samples"})

            validator = WalkForwardValidator()
            result = await validator.validate_model(
                market=market,
                model_name=model_name,
                feature_sequence=all_features,
                targets=all_targets,
                num_windows=num_windows,
            )

            if not result.success:
                return ApiResponse(success=False, data=None, error={"message": result.error or "Validation failed"})

            return ApiResponse(
                success=True,
                data={
                    **result.value.to_dict(),
                    "symbol": symbol,
                    "generated_at": datetime.now().isoformat(),
                },
            )

    except Exception as e:
        logger.exception("Walk-forward endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.get("/ensemble", summary="Ensemble optimization",
            description="Get optimal ensemble configuration for each market")
async def get_ensemble_optimization(
    market: str = Query("all", description="Market to optimize or 'all'"),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.ensemble_optimizer import EnsembleOptimizer

        optimizer = EnsembleOptimizer()

        if market == "all":
            result = await optimizer.optimize_all_markets()
            if not result.success:
                return ApiResponse(success=False, data=None, error={"message": result.error or "Optimization failed"})
            return ApiResponse(
                success=True,
                data={
                    "markets": {
                        m: e.to_dict() for m, e in result.value.items()
                    },
                    "generated_at": datetime.now().isoformat(),
                },
            )
        else:
            result = await optimizer.optimize(market)
            if not result.success:
                return ApiResponse(success=False, data=None, error={"message": result.error or "Optimization failed"})
            return ApiResponse(
                success=True,
                data={
                    **result.value.to_dict(),
                    "generated_at": datetime.now().isoformat(),
                },
            )
    except Exception as e:
        logger.exception("Ensemble optimization endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.get("/confidence", summary="Confidence scoring breakdown",
            description="Get confidence score breakdown for a signal")
async def get_confidence_scoring(
    symbol: str = Query(..., description="Symbol to score"),
    market: str = Query("stock", description="Market type"),
    direction: str = Query("buy", description="Signal direction"),
    source: str = Query("rule_based", description="Signal source"),
    signal_strength: float = Query(0.5, ge=0.0, le=1.0),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()
        result = await scorer.compute_confidence(
            symbol=symbol,
            market=market,
            direction=direction,
            source=source,
            signal_strength=signal_strength,
        )

        return ApiResponse(
            success=True,
            data={
                **result.to_dict(),
                "symbol": symbol,
                "market": market,
                "direction": direction,
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.exception("Confidence scoring endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.post("/retrain", summary="Trigger model retrain",
             description="Trigger auto-retrain for a market or all markets")
async def trigger_retrain(
    market: str = Query("all", description="Market to retrain or 'all'"),
    force: bool = Query(False, description="Force retrain regardless of accuracy"),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.auto_retrain_pipeline import AutoRetrainPipeline

        pipeline = AutoRetrainPipeline()

        if market == "all":
            result = await pipeline.retrain_all_markets(force=force)
            if not result.success:
                return ApiResponse(success=False, data=None, error={"message": result.error or "Retrain failed"})
            return ApiResponse(
                success=True,
                data={
                    "reports": [r.to_dict() for r in result.value],
                    "total_retrained": sum(len(r.models_retrained) for r in result.value),
                    "generated_at": datetime.now().isoformat(),
                },
            )
        else:
            result = await pipeline.check_and_retrain(market=market, force=force)
            if not result.success:
                return ApiResponse(success=False, data=None, error={"message": result.error or "Retrain failed"})
            return ApiResponse(
                success=True,
                data={
                    **result.value.to_dict(),
                    "generated_at": datetime.now().isoformat(),
                },
            )
    except Exception as e:
        logger.exception("Retrain endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.get("/multi-timeframe", summary="Multi-timeframe confirmation",
            description="Confirm a signal across multiple timeframes")
async def get_multi_timeframe_confirmation(
    symbol: str = Query(..., description="Symbol to confirm"),
    market: str = Query("stock", description="Market type"),
    direction: str = Query("buy", description="Primary signal direction"),
    timeframe: str = Query("daily", description="Primary timeframe"),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.multi_timeframe_confirmer import MultiTimeframeConfirmer

        confirmer = MultiTimeframeConfirmer()
        result = await confirmer.confirm_signal(
            symbol=symbol,
            market=market,
            primary_direction=direction,
            primary_timeframe=timeframe,
        )

        return ApiResponse(
            success=True,
            data={
                **result.to_dict(),
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.exception("Multi-timeframe endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})


@router.get("/risk-filter", summary="Risk-adjusted signal filter",
            description="Apply risk filter to check if a signal passes risk thresholds")
async def get_risk_filter(
    symbol: str = Query(..., description="Symbol to check"),
    market: str = Query("stock", description="Market type"),
    direction: str = Query("buy", description="Signal direction"),
    score: float = Query(50.0, ge=0, le=100),
    confidence: float = Query(0.5, ge=0.0, le=1.0),
    risk_tolerance: str = Query("moderate", description="conservative / moderate / aggressive"),
) -> ApiResponse[dict[str, Any]]:
    try:
        from services.risk_adjusted_filter import RiskAdjustedFilter

        signal = {
            "symbol": symbol,
            "market": market,
            "direction": direction,
            "score": score,
            "confidence": confidence,
        }

        risk_filter = RiskAdjustedFilter()
        result = await risk_filter.filter_signal(
            signal=signal,
            risk_tolerance=risk_tolerance,
        )

        return ApiResponse(
            success=True,
            data={
                **result.to_dict(),
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.exception("Risk filter endpoint failed")
        return ApiResponse(success=False, data=None, error={"message": str(e)})
