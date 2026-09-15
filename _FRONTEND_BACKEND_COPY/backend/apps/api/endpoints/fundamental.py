from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_brsapi_query_service
from schemas.common.responses import ApiResponse
from services.fundamental_service import FundamentalService

router = APIRouter()


def _svc(brsapi=Depends(get_brsapi_query_service)) -> FundamentalService:
    return FundamentalService(brsapi_query_service=brsapi)


@router.get("/ratios/{symbol}")
async def get_ratios(symbol: str, svc: FundamentalService = Depends(_svc)) -> ApiResponse:
    result = await svc.get_ratios(symbol)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/dcf/{symbol}")
async def get_dcf(symbol: str, svc: FundamentalService = Depends(_svc)) -> ApiResponse:
    result = await svc.get_dcf_valuation(symbol)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/score/{symbol}")
async def score_stock(symbol: str, svc: FundamentalService = Depends(_svc)) -> ApiResponse:
    result = await svc.score_stock(symbol)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/compare")
async def compare_symbols(
    symbols: str = Query("فولاد,فملی,شپنا"), svc: FundamentalService = Depends(_svc)
) -> ApiResponse:
    sym_list = [s.strip() for s in symbols.split(",")]
    result = await svc.compare_symbols(sym_list)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/industry/{industry}")
async def industry_analysis(industry: str, svc: FundamentalService = Depends(_svc)) -> ApiResponse:
    result = await svc.industry_analysis(industry)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)
