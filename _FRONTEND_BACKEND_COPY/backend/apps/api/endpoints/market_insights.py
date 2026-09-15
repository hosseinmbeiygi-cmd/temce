"""Market Insights API — endpoints for new market intelligence services.

Covers: fake queue detection, hidden accumulation, manipulation alerts,
fear & greed index, market health, block trades, real returns, gap prediction.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_block_trade_detector_service,
    get_db_session,
    get_fake_queue_detector_service,
    get_gap_prediction_service,
    get_hidden_accumulation_service,
    get_historical_level_analyzer_service,
    get_iran_fear_greed_service,
    get_manipulation_detector_service,
    get_market_health_index_service,
    get_real_return_calculator_service,
)
from schemas.common.responses import ApiResponse

router = APIRouter()


# ── Fake Queue Detection ─────────────────────────────────────────────────


@router.get("/fake-queues", summary="تشخیص صف‌های کاذب")
async def detect_fake_queues(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """شناسایی صف‌های کاذب خرید و فروش در بازار."""
    detector = get_fake_queue_detector_service(session)
    results = await detector.detect_all(limit=limit)
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "fake_buy_queue": r.fake_buy_queue,
                    "fake_sell_queue": r.fake_sell_queue,
                    "confidence": r.confidence,
                    "reason": r.reason,
                    "details": r.details,
                }
                for r in results
            ],
            "total": len(results),
        },
    )


@router.get("/fake-queues/{symbol}", summary="تشخیص صف کاذب نماد")
async def detect_fake_queue_symbol(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
):
    """شناسایی صف کاذب برای یک نماد خاص."""
    detector = get_fake_queue_detector_service(session)
    result = await detector.detect_symbol(symbol)
    if result:
        return ApiResponse(
            success=True,
            data={
                "symbol": result.symbol,
                "name": result.name,
                "fake_buy_queue": result.fake_buy_queue,
                "fake_sell_queue": result.fake_sell_queue,
                "confidence": result.confidence,
                "reason": result.reason,
                "details": result.details,
            },
        )
    return ApiResponse(success=True, data=None, message="سیگنالی شناسایی نشد")


# ── Hidden Accumulation ──────────────────────────────────────────────────


@router.get("/accumulation", summary="تشخیص انباشت پنهان")
async def detect_accumulation(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """شناسایی نمادهایی که در حال انباشت پنهان هستند."""
    detector = get_hidden_accumulation_service(session)
    results = await detector.scan_all(limit=limit)
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "score": r.score,
                    "volume_ratio": r.volume_ratio,
                    "price_change_pct": r.price_change_pct,
                    "net_real_flow": r.net_real_flow,
                    "reason": r.reason,
                }
                for r in results
            ],
            "total": len(results),
        },
    )


# ── Manipulation Detection ──────────────────────────────────────────────


@router.get("/manipulation", summary="تشخیص دستکاری قیمت")
async def detect_manipulation(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """شناسایی الگوهای دستکاری قیمت در بازار."""
    detector = get_manipulation_detector_service(session)
    results = await detector.scan_all(limit=limit)
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "pattern": r.pattern,
                    "confidence": r.confidence,
                    "severity": r.severity,
                    "reason": r.reason,
                    "recommendation": r.recommendation,
                    "details": r.details,
                }
                for r in results
            ],
            "total": len(results),
        },
    )


@router.get("/manipulation/{symbol}", summary="تشخیص دستکاری نماد")
async def detect_manipulation_symbol(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
):
    """شناسایی دستکاری قیمت برای یک نماد خاص."""
    detector = get_manipulation_detector_service(session)
    results = await detector.detect_symbol(symbol)
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "pattern": r.pattern,
                    "confidence": r.confidence,
                    "severity": r.severity,
                    "reason": r.reason,
                    "recommendation": r.recommendation,
                }
                for r in results
            ],
            "total": len(results),
        },
    )


# ── Fear & Greed Index ──────────────────────────────────────────────────


@router.get("/fear-greed", summary="شاخص ترس و طمع ایران")
async def get_fear_greed(
    session: AsyncSession = Depends(get_db_session),
):
    """محاسبه شاخص ترس و طمع اختصاصی بازار ایران."""
    service = get_iran_fear_greed_service(session)
    result = await service.calculate()
    return ApiResponse(
        success=True,
        data={
            "overall_score": result.overall_score,
            "label": result.label,
            "components": result.components,
            "date": result.date,
        },
    )


# ── Market Health Index ──────────────────────────────────────────────────


@router.get("/market-health", summary="شاخص سلامت بازار")
async def get_market_health(
    session: AsyncSession = Depends(get_db_session),
):
    """محاسبه شاخص سلامت کلی بازار."""
    service = get_market_health_index_service(session)
    result = await service.calculate()
    return ApiResponse(
        success=True,
        data={
            "overall_score": result.overall_score,
            "label": result.label,
            "components": result.components,
            "recommendations": result.recommendations,
            "date": result.date,
        },
    )


# ── Block Trade Detection ───────────────────────────────────────────────


@router.get("/block-trades", summary="تشخیص معاملات بلوکی")
async def detect_block_trades(
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """شناسایی معاملات بلوکی غیرعادی در بازار."""
    detector = get_block_trade_detector_service(session)
    results = await detector.scan_all(limit=limit)
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "symbol": bt.symbol,
                    "name": bt.name,
                    "trade_time": bt.trade_time,
                    "price": bt.price,
                    "volume": bt.volume,
                    "value": bt.value,
                    "direction": bt.direction,
                    "z_score": bt.z_score,
                    "confidence": bt.confidence,
                }
                for bt in results
            ],
            "total": len(results),
        },
    )


@router.get("/block-trades/summary", summary="خلاصه معاملات بلوکی")
async def block_trade_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """خلاصه معاملات بلوکی بازار."""
    detector = get_block_trade_detector_service(session)
    summary = await detector.get_block_trade_summary()
    return ApiResponse(success=True, data=summary)


# ── Real Return Calculator ──────────────────────────────────────────────


@router.get("/real-return/{symbol}", summary="بازده واقعی نماد")
async def get_real_return(
    symbol: str,
    period_days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db_session),
):
    """محاسبه بازده واقعی (تعدیل‌شده با تورم و ارز) یک نماد."""
    calculator = get_real_return_calculator_service(session)
    result = await calculator.calculate_real_return(symbol, period_days)
    if result:
        return ApiResponse(
            success=True,
            data={
                "symbol": result.symbol,
                "nominal_return_pct": result.nominal_return_pct,
                "inflation_adjustment_pct": result.inflation_adjustment_pct,
                "fx_adjustment_pct": result.fx_adjustment_pct,
                "real_return_pct": result.real_return_pct,
                "period_days": result.period_days,
            },
        )
    return ApiResponse(success=False, error="داده کافی موجود نیست")


@router.get("/real-return", summary="بازده واقعی بازار")
async def get_market_real_return(
    session: AsyncSession = Depends(get_db_session),
):
    """خلاصه بازده واقعی بازار."""
    calculator = get_real_return_calculator_service(session)
    summary = await calculator.get_market_real_return_summary()
    return ApiResponse(success=True, data=summary)


# ── Historical Levels ───────────────────────────────────────────────────


@router.get("/levels/{symbol}", summary="سطوح تاریخی حمایت/مقاومت")
async def get_historical_levels(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
):
    """تحلیل سطوح حمایت و مقاومت تاریخی یک نماد."""
    analyzer = get_historical_level_analyzer_service(session)
    result = await analyzer.analyze_symbol(symbol)
    if result:
        return ApiResponse(
            success=True,
            data={
                "symbol": result.symbol,
                "current_price": result.current_price,
                "nearest_support": result.nearest_support,
                "nearest_resistance": result.nearest_resistance,
                "support_distance_pct": result.support_distance_pct,
                "resistance_distance_pct": result.resistance_distance_pct,
                "congestion_zone": result.congestion_zone,
                "congestion_details": result.congestion_details,
                "levels": [
                    {
                        "price": lvl.price,
                        "level_type": lvl.level_type,
                        "strength": lvl.strength,
                        "confidence": lvl.confidence,
                    }
                    for lvl in result.levels
                ],
            },
        )
    return ApiResponse(success=False, error="داده کافی موجود نیست")


# ── Gap Prediction ──────────────────────────────────────────────────────


@router.get("/gap-prediction", summary="پیش‌بینی شکاف قیمتی")
async def get_gap_predictions(
    limit: int = Query(30, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """پیش‌بینی شکاف قیمتی بازگشایی فردا."""
    predictor = get_gap_prediction_service(session)
    results = await predictor.predict_all(limit=limit)
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "symbol": p.symbol,
                    "name": p.name,
                    "predicted_gap_pct": p.predicted_gap_pct,
                    "confidence": p.confidence,
                    "recommended_buy_price": p.recommended_buy_price,
                    "recommended_sell_price": p.recommended_sell_price,
                    "reason": p.reason,
                }
                for p in results
            ],
            "total": len(results),
        },
    )
