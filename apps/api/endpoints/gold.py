"""Gold Module — Iranian gold market API.

نقاط ورود:
  GET  /gold/live-prices                    قیمت لحظه‌ای (BrsApi)
  POST /gold/coin-bubble                    محاسبه حباب/تخفیف سکه
  GET  /gold/etf-nav-premium                جدول NAV Premium صندوق‌ها
  GET  /gold/arbitrage                      اسکنر آربیتراژ ETF ↔ فیزیکی
  POST /gold/futures/margin-calculator      محاسبه مارجین + لیکوئید (10x IME)
  GET  /gold/futures/positions              لیست پوزیشن‌های باز
  POST /gold/futures/positions              ثبت پوزیشن جدید
  POST /gold/futures/positions/{id}/close   بستن پوزیشن
  GET  /gold/futures/health                 سلامت کل پورتفولیو آتی
  GET  /gold/kill-switch                    وضعیت ACTIVE/WARNING/NORMAL
  GET  /gold/ime/futures                    لیست قراردادهای آتی IME
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from apps.api.dependencies import (
    get_brsapi_query_service,
    get_gold_live_service,
    get_gold_position_service,
)
from core.logging import get_logger
from schemas.api.gold import (
    CoinBubbleRequest,
    CoinBubbleResponse,
    ETFNavPremiumResponse,
    ETFNavPremiumRow,
    FuturesHealthResponse,
    FuturesMarginRequest,
    FuturesMarginResponse,
    FuturesPosition,
    GoldKillSwitchStatus,
    GoldLivePrices,
    GoldLivePricesRequest,
)
from schemas.api.gold.etf import ETF_UNIVERSE
from schemas.common.responses import ApiResponse
from services.gold import (
    FuturesRiskCalculator,
    GoldFuturesPositionService,
    GoldLiveService,
    calculate_coin_bubble,
    calculate_nav_premium,
    evaluate_kill_switch,
    scan_gold_arbitrage,
)

logger = get_logger(__name__)

router = APIRouter()

# ── 1. Live Prices ────────────────────────────────────────────


@router.get(
    "/live-prices",
    summary="قیمت لحظه‌ای طلا، سکه و دلار",
    response_model=ApiResponse[GoldLivePrices],
)
async def get_live_prices(
    refresh: bool = Query(False, description="اجبار به بازخوانی از BrsApi"),
    service: GoldLiveService = Depends(get_gold_live_service),
) -> ApiResponse[dict[str, Any]]:
    data = await service.get_live_prices(force_refresh=refresh)
    return ApiResponse[GoldLivePrices](success=True, data=data)


@router.post(
    "/live-prices",
    summary="همانند GET اما با body برای سازگاری با فرانت",
    response_model=ApiResponse[GoldLivePrices],
)
async def post_live_prices(
    body: GoldLivePricesRequest = Body(default_factory=GoldLivePricesRequest),
    service: GoldLiveService = Depends(get_gold_live_service),
) -> ApiResponse[dict[str, Any]]:
    data = await service.get_live_prices(force_refresh=body.refresh)
    return ApiResponse[GoldLivePrices](success=True, data=data)


# ── 2. Coin Bubble ─────────────────────────────────────────────


@router.post(
    "/coin-bubble",
    summary="محاسبه حباب/تخفیف سکه بهار آزادی",
    response_model=ApiResponse[CoinBubbleResponse],
)
async def post_coin_bubble(body: CoinBubbleRequest) -> ApiResponse[dict[str, Any]]:
    try:
        result = calculate_coin_bubble(
            coin_price_irr=body.coin_price_irr,
            gold_oz_usd=body.gold_oz_usd,
            usd_irr=body.usd_irr,
            weight_g=body.weight_g,
            purity=body.purity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ApiResponse[CoinBubbleResponse](
        success=True,
        data=CoinBubbleResponse(
            coin_intrinsic_irr=result.coin_intrinsic_irr,
            coin_market_irr=result.coin_market_irr,
            bubble_pct=result.bubble_pct,
            signal=result.signal,
            reason=result.reason,
            inputs=body,
        ),
    )


# ── 3. ETF NAV Premium ─────────────────────────────────────────


@router.get(
    "/etf-nav-premium",
    summary="جدول NAV Premium/Discount صندوق‌های طلا",
    response_model=ApiResponse[ETFNavPremiumResponse],
)
async def get_etf_nav_premium(
    service: GoldLiveService = Depends(get_gold_live_service),
) -> ApiResponse[dict[str, Any]]:
    """اگر داده بازار در دسترس نباشد، مقادیر نمونه برمی‌گردد تا UI خراب نشود."""
    from core.time import utc_now_iso

    live = await service.get_live_prices()
    coin_price = float(live.get("coin_bahar_irr") or 0)
    oz_usd = float(live.get("gold_oz_usd") or 0)
    usd_irr = float(live.get("usd_irr") or 0)

    # NAV تقریبی هر صندوق: 0.1 گرم طلای ۱۸ عیار (برای صندوق‌های کوچک) —
    # در production از BrsApi NAV per ETF استفاده می‌شود
    items: list[ETFNavPremiumRow] = []
    best: str | None = None
    best_score = -999.0

    for symbol, info in ETF_UNIVERSE.items():  # type: ignore[var-annotated]
        if oz_usd and usd_irr:
            # NAV = قیمت ذاتی هر واحد (فرض: هر واحد ≈ 0.1 گرم ۱۸ عیار)
            nav = (oz_usd / 31.1035) * 0.1 * 0.750 * usd_irr * 1000  # گرم × ریال
            market = nav * 1.005  # تخمین 0.5% پرمیوم
        else:
            nav, market = 0.0, 0.0

        result = calculate_nav_premium(market_price=market or 1, nav=nav or 1)
        row = ETFNavPremiumRow(
            symbol=symbol,
            name_fa=info["name_fa"],
            isin=info["isin"],
            market_price=round(market, 0),
            nav=round(nav, 0),
            premium_pct=result.premium_pct,
            signal=result.signal,
            reason=result.reason,
            liquidity="high" if symbol in ("ZARFSHANG", "LOTUS") else "medium",
            management_fee=info["management_fee"],
        )
        items.append(row)
        # بهترین فرصت خرید = بیشترین تخفیف
        if result.premium_pct < best_score:
            best_score = result.premium_pct
            best = symbol

    return ApiResponse[ETFNavPremiumResponse](
        success=True,
        data=ETFNavPremiumResponse(
            items=items,
            best_opportunity=best,
            generated_at=utc_now_iso(),
        ),
    )


# ── 4. Arbitrage Scanner ───────────────────────────────────────


@router.get(
    "/arbitrage",
    summary="اسکنر آربیتراژ ETF طلا ↔ بازار فیزیکی",
)
async def get_arbitrage(
    service: GoldLiveService = Depends(get_gold_live_service),
) -> ApiResponse[dict[str, Any]]:
    live = await service.get_live_prices()
    oz_usd = float(live.get("gold_oz_usd") or 0)
    usd_irr = float(live.get("usd_irr") or 0)
    gold_18k = float(live.get("gold_18k_irr") or 0)

    if not (oz_usd and usd_irr and gold_18k):
        return ApiResponse[dict[str, Any]](
            success=False,
            data=None,
            error={"message": "داده‌های بازار برای محاسبه آربیتراژ کافی نیست"},
        )

    # صندوق طلا در بورس ≈ قیمت گرم طلا + 0.5% کارمزد مدیریت
    etf_per_gram = gold_18k * 1.005
    # طلای فیزیکی (آب‌شده) ≈ قیمت ۱۸ عیار - 2% تخفیف عیار
    physical_per_gram = gold_18k * 0.98

    result = scan_gold_arbitrage(
        etf_price_per_gram=etf_per_gram,
        physical_gold_price_per_gram=physical_per_gram,
        pair_label="ETF طلا (میانگین) ↔ طلای آب‌شده بازار",
    )
    return ApiResponse[dict[str, Any]](success=True, data=result.__dict__)


# ── 5. Futures Margin Calculator ──────────────────────────────


@router.post(
    "/futures/margin-calculator",
    summary="محاسبه مارجین، لیکوئیدیشن و Health Ratio (آتی سکه IME)",
    response_model=ApiResponse[FuturesMarginResponse],
)
async def post_margin_calculator(body: FuturesMarginRequest) -> ApiResponse[dict[str, Any]]:
    try:
        calc = FuturesRiskCalculator(leverage=body.leverage)
        result = calc.calculate(
            entry_price=body.entry_price,
            position_type=body.position_type,  # type: ignore[arg-type]
            quantity=body.quantity,
            current_price=body.current_price,
            account_equity=body.account_equity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ApiResponse[FuturesMarginResponse](
        success=True,
        data=FuturesMarginResponse(
            contract_value=result.contract_value,
            initial_margin=result.initial_margin,
            maintenance_margin=result.maintenance_margin,
            liquidation_price=result.liquidation_price,
            leverage=body.leverage,
            position_type=body.position_type,
            health_ratio=result.health_ratio,
            distance_to_liquidation_pct=result.distance_to_liquidation_pct,
            alert_level=result.alert_level,
            alert_message=result.alert_message,
            recommended_stop_loss=result.recommended_stop_loss,
        ),
    )


# ── 6. Futures Positions (DB) ─────────────────────────────────


@router.get(
    "/futures/positions",
    summary="لیست پوزیشن‌های آتی ثبت‌شده",
)
async def list_futures_positions(
    status: str | None = Query(None, description="OPEN / CLOSED / LIQUIDATED"),
    service: GoldFuturesPositionService = Depends(get_gold_position_service),
) -> ApiResponse[list[dict[str, Any]]]:
    items = await service.list_positions(status=status)
    return ApiResponse[list[dict[str, Any]]](success=True, data=items)


@router.post(
    "/futures/positions",
    summary="ثبت پوزیشن آتی جدید",
)
async def open_futures_position(
    contract_symbol: str = Body(..., embed=True),
    position_type: str = Body(..., embed=True),
    entry_price: float = Body(..., embed=True),
    quantity: int = Body(..., embed=True),
    leverage: int = Body(10, embed=True),
    stop_loss: float | None = Body(None, embed=True),
    target_1: float | None = Body(None, embed=True),
    target_2: float | None = Body(None, embed=True),
    notes: str | None = Body(None, embed=True),
    service: GoldFuturesPositionService = Depends(get_gold_position_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await service.open_position(
            contract_symbol=contract_symbol,
            position_type=position_type,
            entry_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post(
    "/futures/positions/{position_id}/close",
    summary="بستن پوزیشن آتی",
)
async def close_futures_position(
    position_id: str,
    exit_price: float = Body(..., embed=True),
    reason: str = Body("MANUAL", embed=True),
    service: GoldFuturesPositionService = Depends(get_gold_position_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await service.close_position(position_id=position_id, exit_price=exit_price, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get(
    "/futures/health",
    summary="سلامت کل پورتفولیو آتی",
    response_model=ApiResponse[FuturesHealthResponse],
)
async def get_futures_health(
    service: GoldFuturesPositionService = Depends(get_gold_position_service),
) -> ApiResponse[dict[str, Any]]:
    rows = await service.list_open_positions()
    positions: list[FuturesPosition] = []
    total_used = 0.0
    crit = warn = 0

    for r in rows:
        pos = FuturesPosition(
            id=r["id"],
            symbol=r["contract_symbol"],
            position_type=r["position_type"],
            entry_price=r["entry_price"],
            current_price=r.get("current_price"),
            quantity=r["quantity"],
            unrealized_pnl_pct=r.get("unrealized_pnl_pct"),
            unrealized_pnl_irr=r.get("unrealized_pnl"),
            liquidation_price=r["liquidation_price"],
            distance_to_liquidation_pct=r.get("distance_to_liquidation_pct"),
            health_ratio=r.get("health_ratio"),
            leverage=r["leverage"],
            status=r["status"],
        )
        positions.append(pos)
        total_used += r["initial_margin"]
        hr = r.get("health_ratio")
        if hr is not None:
            if hr < 1.2:
                crit += 1
            elif hr < 2.0:
                warn += 1

    return ApiResponse[FuturesHealthResponse](
        success=True,
        data=FuturesHealthResponse(
            positions=positions,
            total_used_margin=round(total_used, 2),
            total_equity=0.0,  # TODO: زمانی که account snapshot اضافه شد
            aggregate_health_ratio=None,
            critical_count=crit,
            warning_count=warn,
        ),
    )


# ── 7. Kill-Switch ─────────────────────────────────────────────


@router.get(
    "/kill-switch",
    summary="وضعیت ACTIVE/WARNING/NORMAL سیستم هشدار بحرانی",
    response_model=ApiResponse[GoldKillSwitchStatus],
)
async def get_kill_switch(
    service: GoldLiveService = Depends(get_gold_live_service),
) -> ApiResponse[dict[str, Any]]:
    # TODO: oz_history / usd_history از TimescaleDB (در phase بعدی)
    live = await service.get_live_prices()
    eval_result = evaluate_kill_switch(
        current_oz_usd=float(live.get("gold_oz_usd") or 0),
        current_usd_irr=float(live.get("usd_irr") or 0),
        oz_history=None,
        usd_history=None,
        market_frozen=False,
    )
    return ApiResponse[GoldKillSwitchStatus](
        success=True,
        data=GoldKillSwitchStatus(
            status=eval_result.status,
            reason=eval_result.reason,
            triggered_at=eval_result.triggered_at,
            active_rules=eval_result.active_rules,
            directive=eval_result.directive,
        ),
    )


# ── 8. IME Futures Catalog (proxy) ────────────────────────────


@router.get(
    "/ime/futures",
    summary="لیست قراردادهای آتی IME (proxy به BrsApi)",
)
async def get_ime_futures(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        rows = await brsapi.get_ime_futures()
    except Exception as exc:
        logger.exception("IME futures fetch failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})
    return ApiResponse[list[dict[str, Any]]](success=True, data=rows)


@router.get(
    "/ime/physical-trades",
    summary="معاملات فیزیکی بورس کالا",
)
async def get_ime_physical_trades(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        rows = await brsapi.get_ime_physical_trades()
    except Exception as exc:
        logger.exception("IME physical trades fetch failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})
    return ApiResponse[list[dict[str, Any]]](success=True, data=rows)
