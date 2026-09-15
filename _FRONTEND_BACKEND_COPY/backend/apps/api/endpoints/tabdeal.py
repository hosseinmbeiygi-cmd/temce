"""
Tabdeal exchange API endpoints.

Provides CRUD and sync operations for orders, trades, account, and markets
via the Tabdeal crypto exchange integration.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.config import settings
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from tabdeal.client import TabdealClient
from tabdeal.service import TabdealService

router = APIRouter()
logger = get_logger(__name__)


def _get_client() -> TabdealClient:
    """Create a Tabdeal client from environment settings."""
    return TabdealClient(
        api_key=getattr(settings, "tabdeal_api_key", ""),
        api_secret=getattr(settings, "tabdeal_api_secret", ""),
    )


def _get_service(session: AsyncSession) -> TabdealService:
    return TabdealService(session=session, client=_get_client())


# ═══════════════════════════════════════════════════════════════
#  PUBLIC — Market Data (no auth required)
# ═══════════════════════════════════════════════════════════════


@router.get("/ping", summary="Tabdeal server ping")
async def tabdeal_ping() -> ApiResponse[dict]:
    client = _get_client()
    try:
        data = await client.ping()
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal ping failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await client.close()


@router.get("/time", summary="Tabdeal server time")
async def tabdeal_time() -> ApiResponse[dict]:
    client = _get_client()
    try:
        data = await client.server_time()
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal server time failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await client.close()


@router.get("/markets", summary="Tabdeal exchange info")
async def tabdeal_markets(
    symbol: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return cached market info from DB. Call /sync/markets first."""
    svc = _get_service(session)
    try:
        data = await svc.get_markets(status="TRADING", is_spot=True)
        if symbol:
            data = [m for m in data if m.get("symbol") == symbol or m.get("tabdeal_symbol") == symbol]
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal markets query failed")
        return ApiResponse(success=False, data=[], error=str(exc))


@router.get("/depth/{symbol}", summary="Tabdeal order book")
async def tabdeal_depth(symbol: str, limit: int = Query(100, ge=1, le=5000)) -> ApiResponse[dict]:
    client = _get_client()
    try:
        data = await client.depth(symbol=symbol, limit=limit)
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal depth query failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await client.close()


@router.get("/trades/{symbol}", summary="Tabdeal public trades")
async def tabdeal_public_trades(symbol: str, limit: int = Query(50, ge=1, le=1000)) -> ApiResponse[list]:
    client = _get_client()
    try:
        data = await client.trades(symbol=symbol, limit=limit)
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal public trades failed")
        return ApiResponse(success=False, data=[], error=str(exc))
    finally:
        await client.close()


# ═══════════════════════════════════════════════════════════════
#  SYNC — Push Tabdeal data into local DB
# ═══════════════════════════════════════════════════════════════


@router.post("/sync/markets", summary="Sync Tabdeal market info to DB")
async def sync_tabdeal_markets(session: AsyncSession = Depends(get_db_session)) -> ApiResponse[dict]:
    svc = _get_service(session)
    try:
        count = await svc.sync_markets()
        return ApiResponse(success=True, data={"synced_markets": count})
    except Exception as exc:
        logger.exception("Tabdeal sync markets failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await svc.client.close()


@router.post("/sync/orders", summary="Sync Tabdeal spot orders to DB")
async def sync_tabdeal_orders(
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    svc = _get_service(session)
    try:
        count = await svc.sync_spot_orders(symbol=symbol, limit=limit)
        return ApiResponse(success=True, data={"synced_orders": count})
    except Exception as exc:
        logger.exception("Tabdeal sync orders failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await svc.client.close()


@router.post("/sync/trades", summary="Sync Tabdeal spot trades to DB")
async def sync_tabdeal_trades(
    symbol: str = Query(...),
    start_time: int | None = Query(None),
    end_time: int | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    svc = _get_service(session)
    try:
        count = await svc.sync_spot_trades(symbol=symbol, start_time=start_time, end_time=end_time)
        return ApiResponse(success=True, data={"synced_trades": count})
    except Exception as exc:
        logger.exception("Tabdeal sync trades failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await svc.client.close()


@router.post("/sync/account", summary="Sync Tabdeal account to DB")
async def sync_tabdeal_account(session: AsyncSession = Depends(get_db_session)) -> ApiResponse[dict]:
    svc = _get_service(session)
    try:
        data = await svc.sync_account()
        return ApiResponse(success=True, data={"status": "synced", "balances": len(data.get("balances", []))})
    except Exception as exc:
        logger.exception("Tabdeal sync account failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await svc.client.close()


@router.post("/sync/fapi-orders", summary="Sync Tabdeal futures orders to DB")
async def sync_tabdeal_fapi_orders(
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    svc = _get_service(session)
    try:
        count = await svc.sync_fapi_orders(symbol=symbol, limit=limit)
        return ApiResponse(success=True, data={"synced_orders": count})
    except Exception as exc:
        logger.exception("Tabdeal sync fapi orders failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await svc.client.close()


# ═══════════════════════════════════════════════════════════════
#  READ — Query local DB
# ═══════════════════════════════════════════════════════════════


@router.get("/orders", summary="Tabdeal orders from DB")
async def get_tabdeal_orders(
    symbol: str | None = Query(None),
    status: str | None = Query(None),
    is_spot: bool = Query(True),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    svc = _get_service(session)
    try:
        data = await svc.get_orders(symbol=symbol, status=status, is_spot=is_spot, limit=limit)
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal get orders failed")
        return ApiResponse(success=False, data=[], error=str(exc))


@router.get("/trades", summary="Tabdeal trades from DB")
async def get_tabdeal_trades(
    symbol: str | None = Query(None),
    is_spot: bool = Query(True),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    svc = _get_service(session)
    try:
        data = await svc.get_trades(symbol=symbol, is_spot=is_spot, limit=limit)
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal get trades failed")
        return ApiResponse(success=False, data=[], error=str(exc))


@router.get("/account", summary="Tabdeal account snapshot from DB")
async def get_tabdeal_account(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any] | None]:
    svc = _get_service(session)
    try:
        data = await svc.get_account_snapshot()
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal get account failed")
        return ApiResponse(success=False, data=None, error=str(exc))


@router.get("/balances", summary="Tabdeal balances from DB")
async def get_tabdeal_balances(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    svc = _get_service(session)
    try:
        data = await svc.get_balances()
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal get balances failed")
        return ApiResponse(success=False, data=[], error=str(exc))


# ═══════════════════════════════════════════════════════════════
#  LIVE — Direct Tabdeal API calls (passthrough)
# ═══════════════════════════════════════════════════════════════


@router.get("/live/account", summary="Live Tabdeal account (passthrough)")
async def live_tabdeal_account() -> ApiResponse[dict]:
    client = _get_client()
    try:
        data = await client.account()
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal live account failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await client.close()


@router.get("/live/open-orders", summary="Live Tabdeal open orders")
async def live_tabdeal_open_orders(
    symbol: str | None = Query(None),
) -> ApiResponse[list]:
    client = _get_client()
    try:
        data = await client.get_open_orders(symbol=symbol)
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal live open orders failed")
        return ApiResponse(success=False, data=[], error=str(exc))
    finally:
        await client.close()


@router.get("/live/my-trades", summary="Live Tabdeal my trades")
async def live_tabdeal_my_trades(
    symbol: str = Query(...),
    start_time: int | None = Query(None),
    end_time: int | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
) -> ApiResponse[list]:
    client = _get_client()
    try:
        data = await client.my_trades(symbol=symbol, start_time=start_time, end_time=end_time, limit=limit)
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal live my trades failed")
        return ApiResponse(success=False, data=[], error=str(exc))
    finally:
        await client.close()


@router.get("/live/fapi/positions", summary="Live Tabdeal futures positions")
async def live_tabdeal_fapi_positions(
    symbol: str | None = Query(None),
) -> ApiResponse[list]:
    client = _get_client()
    try:
        data = await client.fapi_position_risk(symbol=symbol)
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal live fapi positions failed")
        return ApiResponse(success=False, data=[], error=str(exc))
    finally:
        await client.close()


@router.get("/live/fapi/account", summary="Live Tabdeal futures account")
async def live_tabdeal_fapi_account() -> ApiResponse[dict]:
    client = _get_client()
    try:
        data = await client.fapi_account()
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal live fapi account failed")
        return ApiResponse(success=False, data={}, error=str(exc))
    finally:
        await client.close()


@router.get("/live/fapi/balance", summary="Live Tabdeal futures balance")
async def live_tabdeal_fapi_balance() -> ApiResponse[list]:
    client = _get_client()
    try:
        data = await client.fapi_balance()
        return ApiResponse(success=True, data=data)
    except Exception as exc:
        logger.exception("Tabdeal live fapi balance failed")
        return ApiResponse(success=False, data=[], error=str(exc))
    finally:
        await client.close()
