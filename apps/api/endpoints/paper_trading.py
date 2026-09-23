"""Paper Trading API — simulated P&L from generated signals.

Endpoints:
  GET  /paper-trading/dashboard           — aggregate P&L stats
  GET  /paper-trading/equity              — daily equity curve
  GET  /paper-trading/trades              — trade ledger (filterable)
  POST /paper-trading/trades              — open a trade from a signal snapshot
  POST /paper-trading/trades/{id}/close   — close a trade (manual price or latest)
  POST /paper-trading/auto-close          — auto-close trades that hit target/stop/max-hold
  GET  /paper-trading/signals             — the signal journal (daily snapshots)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_db_session, get_optional_user
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.paper_trading_service import PaperTradingService

logger = get_logger(__name__)

router = APIRouter()


def _svc(session=Depends(get_db_session)) -> PaperTradingService:
    return PaperTradingService(session=session)


def _user_id(user: dict | None) -> str | None:
    """JWT ``sub`` (the user id) or None for anonymous callers."""
    return str(user.get("sub")) if user and user.get("sub") else None


@router.get("/dashboard", summary="داشبورد سود/زیان صندوق آزمایشی")
async def get_dashboard(
    user: dict | None = Depends(get_optional_user),
    svc: PaperTradingService = Depends(_svc),
) -> ApiResponse[dict[str, Any]]:
    try:
        return ApiResponse(success=True, data=await svc.get_dashboard(user_id=_user_id(user)))
    except Exception as exc:
        logger.exception("Paper dashboard failed")
        return ApiResponse(success=False, data=None, error={"message": "Internal error"})


@router.get("/equity", summary="منحنی سرمایه روزانه")
async def get_equity(
    limit: int = Query(90, ge=1, le=365),
    svc: PaperTradingService = Depends(_svc),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        return ApiResponse(success=True, data=await svc.get_equity_history(limit=limit))
    except Exception as exc:
        logger.exception("Paper equity failed")
        return ApiResponse(success=False, data=[], error={"message": "Internal error"})


@router.get("/trades", summary="دفتر معاملات آزمایشی")
async def list_trades(
    status: str | None = Query(None, description="open / closed"),
    symbol: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict | None = Depends(get_optional_user),
    svc: PaperTradingService = Depends(_svc),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        result = await svc.list_trades(status=status, symbol=symbol, page=page, page_size=page_size, user_id=_user_id(user))
        return ApiResponse(success=result.success, data=result.value)
    except Exception as exc:
        logger.exception("Paper trades list failed")
        return ApiResponse(
            success=False,
            data=PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1),
            error={"message": "Internal error"},
        )


@router.post("/trades", summary="باز کردن معامله از سیگنال ذخیره‌شده")
async def open_trade(
    body: dict[str, Any] = Body(...),
    user: dict | None = Depends(get_optional_user),
    svc: PaperTradingService = Depends(_svc),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await svc.open_trade(
            snapshot_id=str(body.get("snapshot_id") or ""),
            quantity=float(body.get("quantity") or 0),
            capital_allocated=float(body.get("capital_allocated") or 0),
            entry_price=float(body["entry_price"]) if body.get("entry_price") else None,
            entry_notes=body.get("entry_notes"),
            user_id=_user_id(user),
        )
        return ApiResponse(
            success=result.success,
            data=result.value,
            error={"message": result.error} if not result.success else None,
        )
    except Exception as exc:
        logger.exception("Paper open trade failed")
        return ApiResponse(success=False, data=None, error={"message": "Internal error"})


@router.post("/trades/{trade_id}/close", summary="بستن معامله و ثبت سود/زیان")
async def close_trade(
    trade_id: str,
    body: dict[str, Any] | None = Body(default=None),
    user: dict | None = Depends(get_optional_user),
    svc: PaperTradingService = Depends(_svc),
) -> ApiResponse[dict[str, Any]]:
    body = body or {}
    try:
        result = await svc.close_trade(
            trade_id=trade_id,
            exit_price=float(body["exit_price"]) if body.get("exit_price") else None,
            exit_reason=str(body.get("exit_reason") or "manual"),
            exit_notes=body.get("exit_notes"),
            user_id=_user_id(user),
        )
        return ApiResponse(
            success=result.success,
            data=result.value,
            error={"message": result.error} if not result.success else None,
        )
    except Exception as exc:
        logger.exception("Paper close trade failed")
        return ApiResponse(success=False, data=None, error={"message": "Internal error"})


@router.post("/auto-close", summary="بستن خودکار معاملات سررسیدشده")
async def auto_close(svc: PaperTradingService = Depends(_svc)) -> ApiResponse[dict[str, Any]]:
    try:
        result = await svc.auto_close_due_trades()
        return ApiResponse(success=True, data={"closed": result.value})
    except Exception as exc:
        logger.exception("Paper auto-close failed")
        return ApiResponse(success=False, data=None, error={"message": "Internal error"})


@router.get("/signals", summary="ژورنال روزانه سیگنال‌ها")
async def list_signals(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    symbol: str | None = Query(None),
    market: str | None = Query(None),
    direction: str | None = Query(None),
    svc: PaperTradingService = Depends(_svc),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        result = await svc.list_snapshots(
            page=page, page_size=page_size, symbol=symbol, market=market, direction=direction
        )
        return ApiResponse(success=result.success, data=result.value)
    except Exception as exc:
        logger.exception("Paper signals list failed")
        return ApiResponse(
            success=False,
            data=PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1),
            error={"message": "Internal error"},
        )
