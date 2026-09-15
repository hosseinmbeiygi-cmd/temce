from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.mass_scanner_service import get_mass_scanner

logger = get_logger(__name__)

router = APIRouter()


class ScanRequest(BaseModel):
    symbols: list[str] | None = None
    batch_size: int = 20
    max_concurrent: int = 20
    capital: float = 1_000_000_000
    start_date: str | None = None
    end_date: str | None = None
    indicator_ids: list[str] | None = None
    extract_relations: bool = True


@router.post("/scan", summary="Run mass indicator scan on all symbols")
async def start_scan(body: ScanRequest) -> ApiResponse[dict[str, Any]]:
    scanner = get_mass_scanner()
    if scanner.is_running:
        return ApiResponse(
            success=False,
            error={"message": "Mass scan already in progress"},
        )

    start = date.fromisoformat(body.start_date) if body.start_date else None
    end = date.fromisoformat(body.end_date) if body.end_date else None

    # Run in background so the request doesn't timeout
    result_container: dict[str, Any] = {}

    async def _run():
        r = await scanner.scan_all(
            symbols=body.symbols,
            batch_size=body.batch_size,
            max_concurrent=body.max_concurrent,
            capital=body.capital,
            start_date=start,
            end_date=end,
            indicator_ids=body.indicator_ids,
        )
        result_container["result"] = r
        if r.success and body.extract_relations:
            logger.info("Starting relation extraction...")
            rel_result = await scanner.extract_relations()
            result_container["relations"] = rel_result

    asyncio.create_task(_run())

    return ApiResponse(
        success=True,
        data={
            "message": "Mass scan started in background",
            "batch_id": scanner.progress.get("batch_id", ""),
        },
    )


@router.get("/scan/status", summary="Check mass scan progress")
async def scan_status() -> ApiResponse[dict[str, Any]]:
    scanner = get_mass_scanner()
    return ApiResponse(success=True, data=scanner.progress)


@router.get("/scan/results", summary="Get mass scan results")
async def scan_results() -> ApiResponse[dict[str, Any]]:
    scanner = get_mass_scanner()
    if scanner.is_running:
        return ApiResponse(
            success=False,
            error={"message": "Scan still in progress, check /scan/status"},
        )
    return ApiResponse(
        success=True,
        data={
            "batch_id": scanner.progress.get("batch_id", ""),
            "stats": scanner._stats if hasattr(scanner, "_stats") else {},
            "best_per_symbol": {
                sym: {
                    "indicator": r.indicator_id,
                    "params": r.params,
                    "signal": r.signal_config,
                    "score": round(r.score, 2),
                    "metrics": r.metrics,
                }
                for sym, r in scanner._best_per_symbol.items()
            }
            if hasattr(scanner, "_best_per_symbol")
            else {},
        },
    )


@router.post("/scan/extract-relations", summary="Extract symbol relationships")
async def extract_relations() -> ApiResponse[dict[str, Any]]:
    scanner = get_mass_scanner()
    result = await scanner.extract_relations()
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)
