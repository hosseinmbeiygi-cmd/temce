"""Gold analytics API — pure calculators from Phases 1–4.

Mounts under ``/api/v1/gold/analytics``.  The POST routes only run the math in
``services/gold``; the GET physical-market reports read the existing BrsApi and
``gold_snapshots`` tables through the service layer.  Nothing here touches
positions or portfolios, so no route changes trading state.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db_session
from core.logging import get_logger
from schemas.api.gold.analytics import (
    AedParityRequest,
    AssayAdjustmentRequest,
    Black76Request,
    CoinBubblesRequest,
    EnrichChainRequest,
    FuturesTermRequest,
    ImeArbitrageRequest,
    ImpliedVolatilityRequest,
    IranManualEventRequest,
    IranManualEventResponse,
    MacroCalendarEventResponse,
    MacroLiveResponse,
    MacroPostureRequest,
    MesghalPriceRequest,
    OptionsChainRequest,
    OptionsMarginRequest,
    OptionsStrategyRequest,
    RiskStressRequest,
)
from schemas.common.responses import ApiResponse
from services.gold import (
    AED_HISTORY_LIMIT,
    COIN_HISTORY_LIMIT,
    DEFAULT_FEED_HEALTH_LIMIT,
    GoldFeedUnavailableError,
    adjust_melted_by_assay,
    analyze_futures_curve,
    black76_price,
    calculate_aed_implied_usd,
    calculate_coin_bubbles,
    calculate_gram18_from_mesghal,
    calculate_greeks,
    calculate_ime_vs_melted_arbitrage,
    calculate_max_pain,
    calculate_pcr,
    check_gold_feed_health,
    enrich_options_chain,
    evaluate_gold_macro_posture,
    get_aed_history_report,
    get_coin_bubble_report,
    get_gold_macro_live,
    get_ime_arbitrage_report,
    implied_volatility,
    list_risk_scenarios,
    load_recent_feed_health_attempts,
    stress_test_gold_portfolio,
    summarize_primary_status,
)
from services.gold.economic_calendar import (
    add_iran_manual_event,
    list_economic_calendar,
    list_iran_manual_events,
)
from services.gold.margin_model import simulate_margin_path
from services.gold.options_chain_service import get_options_chain_report
from services.gold.strategies import analyze_strategy

logger = get_logger(__name__)

# Auth policy for this mount (STEP 7D-1), decided per operation:
#
#   * JWT (``Depends(get_current_user)``) — every write, and every read that
#     returns platform-derived analytics or a recommendation: coin bubbles,
#     arbitrage spreads, option-chain IV rank/skew, AED-spread z-score + alert,
#     macro posture, curated event importance tags, margin/stop-out and the
#     stress/risk engines. The POSTs stay gated even when they are pure
#     calculators, because ``SecurityMiddleware`` already demands a bearer token
#     for any write under ``/api/v1/gold/``.
#   * anonymous — four reference/price reads that carry no platform-derived
#     signal: ``GET /summary`` (live gold price), ``GET /macro/calendar`` and
#     ``GET /macro/iran-events`` (event dates, the same public reference class
#     as the ``/macro`` mount) and ``GET /feed-health`` (provider telemetry).
#     This is the contract those four routes had before, and their HTTP tests
#     still assert it.
#
# The exempt list is enforced by scripts/check_router_auth.py, which resolves the
# real dependency graph rather than grepping decorators.
router = APIRouter()

REDIS_KEY_GOLD_SUMMARY = "golddesk:gold_summary:latest"
CACHE_TTL_SECONDS = 10


async def _get_cached_summary() -> dict[str, Any] | None:
    try:
        from src.forecast_engine.redis_adapter import get_cached_gold_summary

        return await get_cached_gold_summary()
    except Exception:
        logger.exception("Redis cache read failed")
        return None


async def _set_cached_summary(data: dict[str, Any]) -> None:
    try:
        from src.forecast_engine.redis_adapter import set_cached_gold_summary

        await set_cached_gold_summary(data, ttl=CACHE_TTL_SECONDS)
    except Exception:
        logger.exception("Redis cache write failed")


@router.get(
    "/summary",
    summary="خلاصهٔ زندهٔ طلا",
)
async def get_gold_summary() -> ApiResponse[dict[str, Any]]:
    from services.gold.summary import build_gold_summary

    # Check cache first
    cached = await _get_cached_summary()
    if cached:
        return ApiResponse[dict[str, Any]](success=True, data=cached)

    try:
        summary = await build_gold_summary()
    except Exception as exc:
        logger.exception("build_gold_summary failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Cache the result
    await _set_cached_summary(summary)

    return ApiResponse[dict[str, Any]](success=True, data=summary)



def _calculate(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a pure calculator and turn validation errors into 422 responses."""
    try:
        return func(*args, **kwargs)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── Physical gold ─────────────────────────────────────────────────


@router.post(
    "/physical/mesghal",
    summary="تبدیل مظنهٔ مثقال ۱۷ عیار به گرم ۱۸ عیار",
    dependencies=[Depends(get_current_user)],
)
async def post_mesghal_to_gram18(
    body: MesghalPriceRequest,
) -> ApiResponse[dict[str, Any]]:
    gram18 = _calculate(calculate_gram18_from_mesghal, body.mesghal_price)
    return ApiResponse[dict[str, Any]](
        success=True,
        data={"mesghal_price": body.mesghal_price, "gram18_price": gram18},
    )


@router.post(
    "/physical/assay",
    summary="ارزش طلای آب‌شده با عیار دلخواه بر پایهٔ گرم ۱۸ عیار",
    dependencies=[Depends(get_current_user)],
)
async def post_assay_adjustment(
    body: AssayAdjustmentRequest,
) -> ApiResponse[dict[str, Any]]:
    result = _calculate(
        adjust_melted_by_assay,
        body.weight_grams,
        body.assay,
        body.base_gram18_price,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post(
    "/physical/coin-bubbles",
    summary="حباب/تخفیف سکه‌های امامی، نیم، ربع و گرمی",
    dependencies=[Depends(get_current_user)],
)
async def post_coin_bubbles(
    body: CoinBubblesRequest,
) -> ApiResponse[dict[str, Any]]:
    kwargs: dict[str, Any] = {}
    if body.gerami_minting_fee_irr is not None:
        kwargs["gerami_minting_fee_irr"] = body.gerami_minting_fee_irr
    result = _calculate(
        calculate_coin_bubbles,
        body.ounce_usd,
        body.usd_irr,
        body.coin_prices,
        **kwargs,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post(
    "/physical/ime-arbitrage",
    summary="آربیتراژ گواهی شمش بورس کالا در برابر آب‌شدهٔ تهران",
    dependencies=[Depends(get_current_user)],
)
async def post_ime_arbitrage(
    body: ImeArbitrageRequest,
) -> ApiResponse[dict[str, Any]]:
    result = _calculate(
        calculate_ime_vs_melted_arbitrage,
        body.ime_cert_price_irr,
        body.melted_gram18_price_irr,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


# ── Black-76 options ──────────────────────────────────────────────


@router.post(
    "/options/black76",
    summary="قیمت و یونانی‌های Black-76",
    dependencies=[Depends(get_current_user)],
)
async def post_black76(body: Black76Request) -> ApiResponse[dict[str, Any]]:
    price = _calculate(
        black76_price, body.F, body.K, body.T, body.r, body.sigma, body.option_type
    )
    greeks = _calculate(
        calculate_greeks,
        body.F,
        body.K,
        body.T,
        body.r,
        body.sigma,
        body.option_type,
    )
    return ApiResponse[dict[str, Any]](
        success=True, data={"price": price, "greeks": greeks}
    )


@router.post(
    "/options/implied-volatility",
    summary="استخراج نوسان ضمنی از قیمت بازار",
    dependencies=[Depends(get_current_user)],
)
async def post_implied_volatility(
    body: ImpliedVolatilityRequest,
) -> ApiResponse[dict[str, Any]]:
    iv = _calculate(
        implied_volatility,
        body.market_price,
        body.F,
        body.K,
        body.T,
        body.r,
        body.option_type,
    )
    return ApiResponse[dict[str, Any]](
        success=True, data={"implied_volatility": iv}
    )


@router.post(
    "/options/pcr",
    summary="نسبت Put/Call بر پایهٔ حجم و OI",
    dependencies=[Depends(get_current_user)],
)
async def post_pcr(body: OptionsChainRequest) -> ApiResponse[dict[str, Any]]:
    result = _calculate(calculate_pcr, body.options_chain)
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post(
    "/options/max-pain",
    summary="استرایک Max Pain",
    dependencies=[Depends(get_current_user)],
)
async def post_max_pain(body: OptionsChainRequest) -> ApiResponse[dict[str, Any]]:
    strike = _calculate(calculate_max_pain, body.options_chain)
    return ApiResponse[dict[str, Any]](
        success=True, data={"max_pain_strike": strike}
    )


@router.post(
    "/options/enrich",
    summary="محاسبهٔ IV، یونانی‌ها و Moneyness برای کل زنجیره",
    dependencies=[Depends(get_current_user)],
)
async def post_enrich_chain(
    body: EnrichChainRequest,
) -> ApiResponse[dict[str, Any]]:
    rows = _calculate(
        enrich_options_chain,
        body.options_chain,
        body.forward_price,
        body.risk_free_rate,
        body.days_to_expiry,
    )
    return ApiResponse[dict[str, Any]](success=True, data={"contracts": rows})


# Derivatives layer ---------------------------------------------------------


@router.get(
    "/options/chain",
    summary="IME option chain with IV rank/percentile, skew, term structure and OI",
    dependencies=[Depends(get_current_user)],
)
async def get_options_chain(
    commodity: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    forward_price: float | None = Query(None, gt=0),
    risk_free_rate: float = Query(0.0, ge=0),
    min_volume: float | None = Query(None, ge=0),
    min_open_interest: float | None = Query(None, ge=0),
    max_bid_ask_spread_pct: float | None = Query(None, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    thresholds: dict[str, float] = {}
    if min_volume is not None:
        thresholds["min_volume"] = min_volume
    if min_open_interest is not None:
        thresholds["min_open_interest"] = min_open_interest
    if max_bid_ask_spread_pct is not None:
        thresholds["max_bid_ask_spread_pct"] = max_bid_ask_spread_pct

    result = await get_options_chain_report(
        session,
        commodity=commodity,
        limit=limit,
        forward_price=forward_price,
        risk_free_rate=risk_free_rate,
        liquidity_thresholds=thresholds or None,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post(
    "/options/strategy",
    summary="Expiry payoff, pre-expiry value and P&L extrema for option strategies",
    dependencies=[Depends(get_current_user)],
)
async def post_options_strategy(
    body: OptionsStrategyRequest,
) -> ApiResponse[dict[str, Any]]:
    legs = [leg.model_dump() for leg in body.legs]
    result = _calculate(
        analyze_strategy,
        legs,
        expiry_price=body.expiry_price,
        forward_price=body.forward_price,
        risk_free_rate=body.risk_free_rate,
        days_to_expiry=body.days_to_expiry,
        pre_expiry_days=body.pre_expiry_days,
        pre_expiry_forward=body.pre_expiry_forward,
    )
    result["strategy"] = body.strategy
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post(
    "/options/margin",
    summary="Config-driven margin, margin-call and stop-out simulation",
    dependencies=[Depends(get_current_user)],
)
async def post_options_margin(
    body: OptionsMarginRequest,
) -> ApiResponse[dict[str, Any]]:
    result = _calculate(
        simulate_margin_path,
        body.entry_price,
        body.prices,
        direction=body.direction,
        quantity=body.quantity,
        starting_equity=body.starting_equity,
        config=body.config,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


# ── Futures term structure ────────────────────────────────────────


@router.post(
    "/futures/term-structure",
    summary="ساختار زمانی، بیسیس، رپوی ضمنی و آربیتراژ کری",
    dependencies=[Depends(get_current_user)],
)
async def post_futures_term(
    body: FuturesTermRequest,
) -> ApiResponse[dict[str, Any]]:
    result = _calculate(
        analyze_futures_curve,
        body.spot_price,
        body.contracts,
        body.benchmark_yield,
        body.transaction_frictions_pct,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


# ── Macro drivers ─────────────────────────────────────────────────


@router.post(
    "/macro/aed-parity",
    summary="سیگنال پاریتهٔ درهم دبی و اسپرد تهران",
    dependencies=[Depends(get_current_user)],
)
async def post_aed_parity(body: AedParityRequest) -> ApiResponse[dict[str, Any]]:
    result = _calculate(
        calculate_aed_implied_usd, body.aed_rate, body.tehran_usd_rate
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post(
    "/macro/posture",
    summary="وضعیت کلان طلا (TIPS / DXY / روند)",
    dependencies=[Depends(get_current_user)],
)
async def post_macro_posture(
    body: MacroPostureRequest,
) -> ApiResponse[dict[str, Any]]:
    result = _calculate(
        evaluate_gold_macro_posture,
        body.tips_yield,
        body.dxy_index,
        body.gold_trend,
        # The stateless calculator accepts a classic DXY level; the stored
        # DTWEXBGS percentile path is used by GET /macro/live, which has
        # history available.
        dxy_series="DXY",
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get(
    "/macro/live",
    summary="وضعیت کلان طلا از داده‌های ذخیره‌شده (TIPS / DXY / روند)",
    dependencies=[Depends(get_current_user)],
)
async def get_macro_posture_live(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[MacroLiveResponse]:
    """Evaluate gold macro posture from stored macro indicators + snapshots.

    Reads the latest stored FRED DFII10 (10Y TIPS real yield) and
    DTWEXBGS (broad dollar index) from ``gold_macro_indicators``, derives
    ``gold_trend`` from recent XAUUSD snapshots, and runs the posture model.
    Returns ``available=False`` with a ``missing`` list when inputs are absent
    or stale rather than raising.
    """
    result = await get_gold_macro_live(session)
    return ApiResponse[MacroLiveResponse](
        success=True,
        data={
            "available": result.available,
            "missing": result.missing,
            "posture": result.posture,
            "inputs": result.inputs,
            "tips_staleness_seconds": result.tips_staleness_seconds,
            "dxy_staleness_seconds": result.dxy_staleness_seconds,
            "trend_staleness_seconds": result.trend_staleness_seconds,
            "high_vol_window": result.high_vol_window,
            "error": result.error,
        },
    )


# â”€â”€ Feed health â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get(
    "/coins",
    summary="All coin bubbles with nominal/percent bubble and rolling history stats",
    dependencies=[Depends(get_current_user)],
)
async def get_coins(
    history_limit: int = Query(COIN_HISTORY_LIMIT, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Live BrsApi coin quotes plus ``gold_snapshots`` history.

    The service caches the result for 30 seconds.  Missing quotes are reported
    in ``missing_symbols`` rather than filled with synthetic prices.
    """
    result = await get_coin_bubble_report(session, history_limit=history_limit)
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get(
    "/arbitrage",
    summary="IME 995 certificate vs Tehran 750 melted spread (both legs + costs)",
    dependencies=[Depends(get_current_user)],
)
async def get_arbitrage(
    quantity_grams: float = Query(1.0, gt=0),
    holding_days: int = Query(0, ge=0),
    storage_irr_per_gram_per_day: float | None = Query(None, ge=0),
    delivery_irr_per_gram: float | None = Query(None, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Assay-adjusted spread with fees, storage/delivery and configured limits.

    ``quantity_grams`` is certificate (995) grams; the service converts it to
    the equivalent physical 750 quantity for storage/delivery.
    """
    result = await get_ime_arbitrage_report(
        session,
        quantity_grams=quantity_grams,
        holding_days=holding_days,
        storage_irr_per_gram_per_day=storage_irr_per_gram_per_day,
        delivery_irr_per_gram=delivery_irr_per_gram,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get(
    "/aed-history",
    summary="AED hawala spread history with z-score and alert flag",
    dependencies=[Depends(get_current_user)],
)
async def get_aed_history(
    limit: int = Query(AED_HISTORY_LIMIT, ge=1, le=2000),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Spread history from persisted ``gold_snapshots`` (USD and AED refs)."""
    result = await get_aed_history_report(session, limit=limit)
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get(
    "/feed-health",
    summary="Gold feed health (BrsApi / Yahoo)",
    response_model=None,
)
async def get_feed_health(
    limit: int = Query(DEFAULT_FEED_HEALTH_LIMIT, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]] | JSONResponse:
    """Run one failover check, persist it, and return recent attempts.

    The route stays public like the other gold calculators. It answers 503
    only when every provider failed on this check.
    """
    error_message: str | None = None
    try:
        current = await check_gold_feed_health(session)
    except GoldFeedUnavailableError as exc:
        error_message = str(exc)
        checked_at = getattr(exc, "checked_at", None)
        current = {
            "check_id": getattr(exc, "check_id", None),
            "checked_at": checked_at.isoformat() if checked_at else None,
            "ok": False,
            "primary": getattr(exc, "primary", None)
            or summarize_primary_status(exc.attempts, checked_at),
        }

    current["attempts"] = await load_recent_feed_health_attempts(session, limit)
    if error_message is not None:
        body = ApiResponse[dict[str, Any]](
            success=False,
            data=current,
            error={"message": error_message},
        )
        return JSONResponse(status_code=503, content=body.model_dump())

    return ApiResponse[dict[str, Any]](success=True, data=current)


# ── Economic calendar (CPI / NFP / FOMC) + Iran manual events ────────────


@router.get(
    "/macro/calendar",
    summary="تقویم اقتصادی ذخیره‌شده (CPI / NFP / FOMC)",
)
async def get_macro_calendar(
    session: AsyncSession = Depends(get_db_session),
    start: date | None = Query(None, description="Earliest event date (inclusive)"),
    end: date | None = Query(None, description="Latest event date (inclusive)"),
    limit: int = Query(100, ge=1, le=500),
) -> ApiResponse[list[MacroCalendarEventResponse]]:
    """List the ingested economic-calendar events, newest first."""
    events = await list_economic_calendar(session, start=start, end=end, limit=limit)
    return ApiResponse[list[MacroCalendarEventResponse]](
        success=True,
        data=[
            MacroCalendarEventResponse(
                event_id=row.event_id,
                event_date=row.event_date,
                event_time=row.event_time,
                title=row.title,
                country=row.country,
                category=row.category,
                importance=row.importance,
                is_high_volatility=bool(row.is_high_volatility),
                source=row.source,
            )
            for row in events
        ],
    )


@router.get(
    "/macro/iran-events",
    summary="رویدادهای دستی ایران (بدون فید خودکار)",
)
async def get_iran_manual_events(
    session: AsyncSession = Depends(get_db_session),
    start: date | None = Query(None, description="Earliest event date (inclusive)"),
    end: date | None = Query(None, description="Latest event date (inclusive)"),
    limit: int = Query(100, ge=1, le=500),
) -> ApiResponse[list[IranManualEventResponse]]:
    """List the Iran-specific manual-entry events, newest first."""
    events = await list_iran_manual_events(
        session, start=start, end=end, limit=limit
    )
    return ApiResponse[list[IranManualEventResponse]](
        success=True,
        data=[
            IranManualEventResponse(
                event_id=row.event_id,
                event_date=row.event_date,
                event_time=row.event_time,
                title=row.title,
                category=row.category,
                importance=row.importance,
                note=row.note,
                is_high_volatility=bool(row.is_high_volatility),
            )
            for row in events
        ],
    )


@router.post(
    "/macro/iran-events",
    summary="ثبت دستی رویداد ایران در تقویم",
)
async def post_iran_manual_event(
    body: IranManualEventRequest,
    session: AsyncSession = Depends(get_db_session),
    _user: dict[str, Any] = Depends(get_current_user),
) -> ApiResponse[IranManualEventResponse]:
    """Insert an Iran-specific manual calendar event (idempotent by event_id).

    Iran events have no provider feed, so this manual entry is the only way
    they enter the calendar. Writing requires an authenticated user.
    """
    row = await add_iran_manual_event(
        session,
        event_id=body.event_id,
        event_date=body.event_date,
        event_time=body.event_time,
        title=body.title,
        category=body.category,
        importance=body.importance,
        note=body.note,
        is_high_volatility=body.is_high_volatility,
    )
    return ApiResponse[IranManualEventResponse](
        success=True,
        data=IranManualEventResponse(
            event_id=row.event_id,
            event_date=row.event_date,
            event_time=row.event_time,
            title=row.title,
            category=row.category,
            importance=row.importance,
            note=row.note,
            is_high_volatility=bool(row.is_high_volatility),
        ),
    )


# Portfolio stress testing -------------------------------------------------


@router.get(
    "/risk/scenarios",
    summary="Built-in Iran gold stress scenarios",
    dependencies=[Depends(get_current_user)],
)
async def get_risk_scenarios() -> ApiResponse[list[dict[str, Any]]]:
    """Return the scenario catalogue used by the portfolio stress engine."""
    return ApiResponse[list[dict[str, Any]]](
        success=True, data=list_risk_scenarios()
    )


@router.post(
    "/risk/stress",
    summary="Stress-test a gold portfolio against Iran-market scenarios",
    dependencies=[Depends(get_current_user)],
)
async def post_risk_stress(
    body: RiskStressRequest,
) -> ApiResponse[dict[str, Any]]:
    """Run the pure stress engine over caller-supplied positions.

    The endpoint reads no account data; positions and equity are supplied in
    the request body. Scenario shocks are decimal returns (``0.10`` = +10%).
    """
    positions = [position.model_dump() for position in body.positions]
    scenarios = (
        [scenario.model_dump() for scenario in body.scenarios]
        if body.scenarios is not None
        else None
    )
    result = _calculate(
        stress_test_gold_portfolio,
        body.equity_irr,
        positions,
        scenarios,
    )
    return ApiResponse[dict[str, Any]](success=True, data=result)
