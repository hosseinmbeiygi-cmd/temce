"""Symbol search API — lightweight, DB-free symbol lookup for the frontend.

The main ``/instruments`` endpoints query PostgreSQL. This router provides
``GET /symbols/search`` (and ``GET /symbols``) backed by the static
:mod:`services.symbol_catalog` so the frontend can find symbols even when the
database is unreachable, empty, or still seeding.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.symbol_catalog import all_symbols, search, sector_summary

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/search",
    summary="Search symbols",
    description="Search symbols by symbol or name (static catalog — no database required).",
)
async def search_symbols(
    q: str = Query(..., min_length=1, description="Search query (symbol or name)"),
    limit: int = Query(25, ge=1, le=200, description="Maximum number of results"),
) -> ApiResponse[list[dict[str, Any]]]:
    results = search(q, limit=limit)
    return ApiResponse[list[dict[str, Any]]](success=True, data=results)


@router.get(
    "",
    summary="List all symbols (static catalog)",
    description="Return the full static symbol catalog (symbol/name/sector).",
)
async def list_symbols(
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of results"),
) -> ApiResponse[list[dict[str, Any]]]:
    results = all_symbols()[:limit]
    return ApiResponse[list[dict[str, Any]]](success=True, data=results)


@router.get(
    "/sectors",
    summary="List symbol sectors with counts",
    description=(
        "Aggregate the static symbol catalog into the market sectors "
        "(سهام، طلا و سکه، ارز، رمزارز، کامودیتی، بورس کالا، صندوق) with the "
        "number of symbols in each, ordered by count descending."
    ),
)
async def list_sectors() -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse[list[dict[str, Any]]](success=True, data=sector_summary())
