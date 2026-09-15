from __future__ import annotations

"""
IME (Iran Mercantile Exchange / بازار کالایی) endpoints.

Aggregates data from all IME sub-markets: futures, options, certificates,
funds, and physical trades — presented as a unified dashboard for the
"بازار کالایی" page.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_brsapi_query_service
from brsapi.services.query_service import BrsApiQueryService
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/dashboard",
    summary="IME market dashboard",
    description="Aggregated overview of all IME sub-markets (futures, options, certificates, funds, physical trades)",
)
async def ime_dashboard(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    """Return a unified snapshot of all IME markets with counts and summary."""
    try:
        futures, options, certs, funds, physical = await _fetch_all_ime_data(service)
        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "futures": {
                    "count": len(futures),
                    "items": futures[:50],
                    "total_open_interest": sum(f.get("open_interest") or 0 for f in futures),
                    "total_trade_value": sum(f.get("trade_value") or 0 for f in futures),
                },
                "options": {
                    "count": len(options),
                    "items": options[:50],
                },
                "certificates": {
                    "count": len(certs),
                    "items": certs[:50],
                },
                "funds": {
                    "count": len(funds),
                    "items": funds[:50],
                },
                "physical_trades": {
                    "count": len(physical),
                    "items": physical[:50],
                    "total_value": sum(p.get("trade_value") or 0 for p in physical),
                },
                "summary": {
                    "total_contracts": len(futures) + len(options) + len(certs) + len(funds) + len(physical),
                    "futures_count": len(futures),
                    "options_count": len(options),
                    "certificates_count": len(certs),
                    "funds_count": len(funds),
                    "physical_count": len(physical),
                },
            },
        )
    except Exception as exc:
        logger.exception("IME dashboard failed")
        return ApiResponse[dict[str, Any]](
            success=False,
            data={
                "futures": {"count": 0, "items": []},
                "options": {"count": 0, "items": []},
                "certificates": {"count": 0, "items": []},
                "funds": {"count": 0, "items": []},
                "physical_trades": {"count": 0, "items": []},
                "summary": {"total_contracts": 0},
            },
            error={"message": str(exc)},
        )


@router.get(
    "/futures",
    summary="IME futures contracts",
    description="All IME futures contracts with pricing, open interest, and order book data",
)
async def ime_futures(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        data = await service.get_ime_futures()
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        logger.exception("IME futures failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/options",
    summary="IME option contracts",
    description="All IME option contracts (اختیار بورس کالا)",
)
async def ime_options(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        data = await service.get_ime_options()
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        logger.exception("IME options failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/certificates",
    summary="IME certificates",
    description="IME certificate/depository receipts (گواهی سپرده کالایی)",
)
async def ime_certificates(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        data = await service.get_ime_certificates()
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        logger.exception("IME certificates failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/funds",
    summary="IME commodity funds",
    description="IME commodity investment funds (صندوق‌های کالایی)",
)
async def ime_funds(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        data = await service.get_ime_funds()
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        logger.exception("IME funds failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/physical-trades",
    summary="IME physical trades",
    description="IME physical commodity trades with pricing, volumes, and settlement details",
)
async def ime_physical_trades(
    date_start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        data = await service.get_ime_physical_trades(
            date_start=date_start, date_end=date_end
        )
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        logger.exception("IME physical trades failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


async def _fetch_all_ime_data(
    service: BrsApiQueryService,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch all IME sub-markets concurrently."""
    import asyncio

    results = await asyncio.gather(
        service.get_ime_futures(),
        service.get_ime_options(),
        service.get_ime_certificates(),
        service.get_ime_funds(),
        service.get_ime_physical_trades(),
        return_exceptions=True,
    )

    def safe(idx: int) -> list[dict[str, Any]]:
        r = results[idx]
        if isinstance(r, Exception):
            logger.warning("IME sub-market fetch failed at index %d: %s", idx, r)
            return []
        return r or []

    return safe(0), safe(1), safe(2), safe(3), safe(4)
