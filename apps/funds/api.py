"""لایه API صندوق‌یار — endpointهای FastAPI.

مسیرها:
- GET  /funds
- GET  /funds/{symbol}
- GET  /funds/compare
- GET  /screener
- GET  /bubble/live
- GET  /health/sources
- GET  /alerts, POST /alerts
- GET  /backtest/report (internal)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import (
    UserContext,
    get_user_context,
    rate_limit_dependency,
    require_permission,
)
from .constants import TYPE_CODES
from .schemas import (
    AlertCreate,
    AlertItem,
    AlertListResponse,
    BacktestReportResponse,
    BubbleLiveResponse,
    CompareResponse,
    FundListItem,
    FundListResponse,
    FundProfileResponse,
    HealthSourcesResponse,
    ScreenerRequest,
    ScreenerResponse,
)
from .services import FundService

router = APIRouter(prefix="/funds", tags=["Sandooghyar Funds"])


def _dep_service() -> FundService:
    """نمونه سرویس — در حالت واقعی از DI سراسری استفاده می‌شود."""
    return FundService()


_public_deps = [Depends(get_user_context), Depends(rate_limit_dependency)]
_screener_deps = [Depends(require_permission("screener")), Depends(rate_limit_dependency)]
_backtest_deps = [Depends(require_permission("backtest:report")), Depends(rate_limit_dependency)]


def _to_list_item(full: dict) -> FundListItem:
    score = full.get("score", {})
    return FundListItem(
        symbol=full["symbol"],
        name_fa=full["name_fa"],
        type_code=full["type_code"],
        type_label_fa=full["type_label_fa"],
        manager=full.get("manager"),
        aum_btoman=full.get("aum_btoman"),
        p_nav_ratio=full.get("p_nav_ratio"),
        bubble_pct=full.get("bubble_pct"),
        score_total=score.get("score_total"),
        signal=score.get("signal"),
        signal_label_fa=score.get("signal_label_fa"),
        last_updated=full.get("last_updated"),
    )


@router.get("", response_model=FundListResponse, dependencies=_public_deps)
async def list_funds(
    type_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="score_total"),
    service: FundService = Depends(_dep_service),
    _user: UserContext = Depends(get_user_context),
):
    if type_code and type_code not in TYPE_CODES:
        raise HTTPException(status_code=400, detail=f"Invalid type_code: {type_code}")
    result = service.list_funds(type_code=type_code, page=page, page_size=page_size, sort_by=sort_by)
    return FundListResponse(
        items=[_to_list_item(i) for i in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/compare", response_model=CompareResponse, dependencies=_public_deps)
async def compare_funds(
    symbols: str = Query(..., description="comma-separated, 2-5 symbols"),
    service: FundService = Depends(_dep_service),
):
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not (2 <= len(sym_list) <= 5):
        raise HTTPException(
            status_code=400,
            detail="Compare needs 2 to 5 symbols",
        )
    fulls = service.compare(sym_list)
    if not fulls:
        raise HTTPException(status_code=404, detail="No funds found")
    return CompareResponse(funds=[_to_list_item(f) for f in fulls])


@router.get("/{symbol}", response_model=FundProfileResponse, dependencies=_public_deps)
async def fund_profile(
    symbol: str,
    service: FundService = Depends(_dep_service),
):
    full = service.compute_full(symbol)
    if full is None:
        raise HTTPException(status_code=404, detail=f"Fund {symbol} not found")
    score = full["score"]
    metrics = full["metrics"]
    return FundProfileResponse(
        symbol=full["symbol"],
        name_fa=full["name_fa"],
        type_code=full["type_code"],
        type_label_fa=full["type_label_fa"],
        manager=full.get("manager"),
        custodian=full.get("custodian"),
        auditor=full.get("auditor"),
        market_maker=full.get("market_maker"),
        inception_date=full.get("inception_date"),
        is_etf=full.get("is_etf", True),
        recommendation={
            "symbol": full["symbol"],
            "score_total": score.get("score_total"),
            "score_return": score.get("score_return"),
            "score_risk": score.get("score_risk"),
            "score_cost": score.get("score_cost"),
            "score_liquidity": score.get("score_liquidity"),
            "signal": score.get("signal"),
            "signal_label_fa": score.get("signal_label_fa"),
            "reasons": score.get("reasons", []),
            "scoring_version": score.get("scoring_version"),
            "computed_at": metrics.get("computed_at"),
            "is_cold_start_blocked": score.get("is_cold_start_blocked", False),
        },
    )


@router.post("/screener", response_model=ScreenerResponse, dependencies=_screener_deps)
async def screener(
    req: ScreenerRequest,
    service: FundService = Depends(_dep_service),
):
    result = service.screener(
        type_code=req.type_code,
        filters=[f.model_dump() for f in req.filters],
        sort_by=req.sort_by or "score_total",
        page=req.page,
        page_size=req.page_size,
    )
    return ScreenerResponse(
        items=[_to_list_item(i) for i in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/bubble/live", response_model=BubbleLiveResponse, dependencies=_public_deps)
async def bubble_live(
    service: FundService = Depends(_dep_service),
):
    items = service.bubble_snapshot()
    return BubbleLiveResponse(items=items, ts=datetime.utcnow())


@router.get("/health/sources", response_model=HealthSourcesResponse, dependencies=_public_deps)
async def health_sources(
    service: FundService = Depends(_dep_service),
):
    return HealthSourcesResponse(sources=service.adapter_health())


@router.get("/backtest/report", response_model=BacktestReportResponse, dependencies=_backtest_deps)
async def backtest_report(
    service: FundService = Depends(_dep_service),
):
    return service.backtest_report()


@router.get("/alerts", response_model=AlertListResponse, dependencies=_public_deps)
async def list_alerts(
    _user: UserContext = Depends(get_user_context),
):
    # در نسخه DB واقعی: کوئری از جدول alerts برای user.sub
    return AlertListResponse(items=[])


@router.post("/alerts", response_model=AlertItem, dependencies=_public_deps)
async def create_alert(
    req: AlertCreate,
    _user: UserContext = Depends(get_user_context),
):
    # در نسخه DB واقعی: درج در جدول alerts
    return AlertItem(
        id=0,
        user_id=_user.sub,
        symbol=req.symbol,
        event_type=req.event_type,
        payload_json=None,
        created_at=datetime.utcnow(),
    )
