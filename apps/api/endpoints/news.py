from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_news_service
from services.news_service import NewsService

router = APIRouter()


@router.get("")
async def list_news(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1), service: NewsService = Depends(get_news_service)
):
    result = await service.list_all(page, page_size)
    return {"success": result.success, "data": result.value}


@router.post("")
async def create_news(body: dict[str, Any] = Body(...), service: NewsService = Depends(get_news_service)):
    result = await service.create(title=body.get("title", ""), **{k: v for k, v in body.items() if k != "title"})
    return {"success": result.success, "data": result.value, "error": result.error if not result.success else None}


@router.get("/search")
async def search_news(
    q: str = Query(..., min_length=1), page: int = Query(1, ge=1), service: NewsService = Depends(get_news_service)
):
    result = await service.search(q, page)
    return {"success": result.success, "data": result.value}


@router.get("/symbol/{symbol}")
async def news_by_symbol(symbol: str, page: int = Query(1, ge=1), service: NewsService = Depends(get_news_service)):
    result = await service.get_by_symbol(symbol, page)
    return {"success": result.success, "data": result.value}
