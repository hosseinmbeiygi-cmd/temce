from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import (
    current_user_id,
    get_current_user,
    get_portfolio_service,
    owned_scope,
)
from core.logging import get_logger
from schemas.api.portfolios import PortfolioCreate, PortfolioListResponse, PortfolioResponse
from schemas.common.responses import ApiResponse
from services.portfolio_service import PortfolioService

logger = get_logger(__name__)

router = APIRouter()

@router.get("/", summary="List portfolios", response_model=ApiResponse[PortfolioListResponse])
async def list_portfolios(
    current_user: dict = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ApiResponse[PortfolioListResponse]:
    result = await service.list_portfolios(owner_id=owned_scope(current_user))
    return ApiResponse[PortfolioListResponse](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )

@router.post("/", summary="Create portfolio", response_model=ApiResponse[PortfolioResponse])
async def create_portfolio(
    body: PortfolioCreate,
    current_user: dict = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ApiResponse[PortfolioResponse]:
    result = await service.create_portfolio(
        name=body.name,
        owner_id=current_user_id(current_user),
        description=body.description,
        initial_capital=body.initial_capital,
        currency=body.currency,
    )
    return ApiResponse[PortfolioResponse](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )

@router.get("/{portfolio_id}", summary="Get portfolio details")
async def get_portfolio(
    portfolio_id: str,
    current_user: dict = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_portfolio(portfolio_id, owner_id=owned_scope(current_user))
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )
