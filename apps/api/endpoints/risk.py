"""🛡️ Portfolio risk API — derived from the user's own stored positions.

Mounted at ``/api/v1/risk``. Every figure comes through
:class:`services.risk_metrics.PortfolioRiskService`, which either computes from
``portfolio_positions`` × ``brsapi_historical_daily`` or answers ``unknown`` with the reason.
This used to return a hardcoded list of eight metrics for a page whose endpoints did not even
exist, so nothing here is a stored fact about anybody's money any more.

Scoping is the platform's convention: portfolios are read with ``owner = current_user["sub"]``,
so one user never sees another's exposures.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db_session
from schemas.common.responses import ApiResponse
from services.risk_metrics import PortfolioRiskService

router = APIRouter()

router_tag = "Risk"


async def _payload(session: AsyncSession, user_id: str) -> dict[str, Any]:
    return await PortfolioRiskService(session=session).metrics(user_id)


@router.get(
    "/",
    response_model=ApiResponse[dict[str, Any]],
    summary="جمع ریسک پرتفوی کاربر (همان /metrics)",
)
async def get_risk_overview(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse[dict[str, Any]](success=True, data=await _payload(session, current_user["sub"]))


@router.get(
    "/metrics",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="شاخص‌های ریسک محاسبه‌شده از قیمت‌های واقعی",
)
async def get_risk_metrics(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[list[dict[str, Any]]]:
    payload = await _payload(session, current_user["sub"])
    return ApiResponse[list[dict[str, Any]]](success=True, data=payload["metrics"])


@router.get(
    "/drawdown",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="منحنی افت از ارزش روزانهٔ پرتفوی",
)
async def get_drawdown(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[list[dict[str, Any]]]:
    payload = await _payload(session, current_user["sub"])
    return ApiResponse[list[dict[str, Any]]](success=True, data=payload["drawdown"])


@router.get(
    "/limits",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="حد ریسک تنظیم‌شده در برابر مقدار اندازه‌گرفته‌شده",
)
async def get_limits(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[list[dict[str, Any]]]:
    payload = await _payload(session, current_user["sub"])
    return ApiResponse[list[dict[str, Any]]](success=True, data=payload["limits"])


@router.get(
    "/alerts",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="عبورهای فعلی از حد ریسک (فقط خواندنی، بدون ارسال اعلان)",
)
async def get_alerts(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[list[dict[str, Any]]]:
    """Read-only by intent: `LiveRiskMonitorService` pushes Telegram messages, so the page
    must not call it just to render a table."""

    payload = await _payload(session, current_user["sub"])
    return ApiResponse[list[dict[str, Any]]](success=True, data=payload["alerts"])
