from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from apps.api.dependencies import get_current_user, get_portfolio_service
from schemas.common.responses import ApiResponse
from services.portfolio_service import PortfolioService
from schemas.api.portfolios import PortfolioCreate, PortfolioResponse, PortfolioListResponse

router = APIRouter()

@router.get("/", summary="List portfolios", response_model=ApiResponse[PortfolioListResponse])
async def list_portfolios(
    service: PortfolioService = Depends(get_portfolio_service),
) -> ApiResponse[PortfolioListResponse]:
    result = await service.list_portfolios()
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
    service: PortfolioService = Depends(get_portfolio_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_portfolio(portfolio_id)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )
