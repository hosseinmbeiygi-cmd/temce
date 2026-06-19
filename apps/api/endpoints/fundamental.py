from __future__ import annotations

from fastapi import APIRouter, Query

from schemas.common.responses import ApiResponse
from services.fundamental_service import FundamentalService

router = APIRouter()


@router.get("/ratios/{symbol}")
async def get_ratios(symbol: str) -> ApiResponse:
    svc = FundamentalService()
    result = await svc.get_ratios(symbol)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/dcf/{symbol}")
async def get_dcf(symbol: str) -> ApiResponse:
    svc = FundamentalService()
    result = await svc.get_dcf_valuation(symbol)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/score/{symbol}")
async def score_stock(symbol: str) -> ApiResponse:
    svc = FundamentalService()
    result = await svc.score_stock(symbol)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/compare")
async def compare_symbols(symbols: str = Query("فولاد,فملی,شپنا")) -> ApiResponse:
    svc = FundamentalService()
    sym_list = [s.strip() for s in symbols.split(",")]
    result = await svc.compare_symbols(sym_list)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.get("/industry/{industry}")
async def industry_analysis(industry: str) -> ApiResponse:
    svc = FundamentalService()
    result = await svc.industry_analysis(industry)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)
