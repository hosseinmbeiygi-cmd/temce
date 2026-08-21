from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile

from apps.api.dependencies import get_quote_service
from schemas.common.responses import ApiResponse
from services.quote_import_service import QuoteImportService
from services.quote_service import QuoteService

router = APIRouter(tags=["quotes"])


@router.post(
    "/{instrument_id}",
    summary="Create quote",
    description="Create a new quote for an instrument",
)
async def create_quote(
    instrument_id: str,
    body: dict[str, Any] = Body(...),
    service: QuoteService = Depends(get_quote_service),
) -> ApiResponse[Any]:

    result = await service.create(instrument_id=instrument_id, **body)

    return ApiResponse[Any](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get(
    "/{instrument_id}/latest",
    summary="Latest quote",
    description="Get the latest quote for an instrument",
)
async def get_latest(
    instrument_id: str,
    service: QuoteService = Depends(get_quote_service),
) -> ApiResponse[Any]:

    result = await service.get_latest(instrument_id)

    return ApiResponse[Any](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get(
    "/{instrument_id}/history",
    summary="Quote history",
    description="Get historical quotes for an instrument",
)
async def get_history(
    instrument_id: str,
    start: str = Query("2024-01-01"),
    end: str = Query("2024-12-31"),
    timeframe: str = Query("1d"),
    service: QuoteService = Depends(get_quote_service),
) -> ApiResponse[Any]:

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return ApiResponse[Any](
            success=False,
            data=None,
            error={"message": "Invalid date format. Use YYYY-MM-DD"},
        )

    result = await service.get_history(
        instrument_id,
        start_date,
        end_date,
        timeframe,
    )

    return ApiResponse[Any](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.post(
    "/import-bulk",
    summary="Bulk import daily quotes",
    description="Upload one or more CSV files (each file name = symbol) "
    "with Persian columns (تاریخ, باز, بالا, پایین, بسته, حجم, ارزش, …). "
    "Files are processed concurrently. Existing records with the same symbol+date are updated.",
)
async def bulk_import_quotes(
    files: list[UploadFile] = File(..., description="CSV files, each named after a symbol (e.g. فولاد.csv)"),
) -> ApiResponse[dict[str, Any]]:
    """Upload multiple daily quote CSV files — one per symbol — and import them all."""
    from core.database import async_session_factory
    from repositories.instrument_repository import InstrumentRepository
    from repositories.quote_repository import QuoteRepository

    # AsyncSession cannot be shared by concurrent coroutines. Build a fresh
    # repository/service graph inside each file worker.
    total_files = len(files)
    per_file: dict[str, dict[str, Any]] = {}
    total_rows = 0
    total_imported = 0
    total_updated = 0
    all_errors: list[str] = []

    async def process_one(file: UploadFile) -> None:
        symbol = (file.filename or "").rsplit(".", 1)[0] if file.filename else ""
        if not symbol:
            all_errors.append(f"{file.filename}: could not determine symbol from filename")
            return

        content = await file.read()
        if not content:
            all_errors.append(f"{file.filename}: empty file")
            return

        if async_session_factory is None:
            all_errors.append(f"{file.filename}: database is not initialized")
            return

        async with async_session_factory() as file_session:
            quote_repo = QuoteRepository(session=file_session)
            instrument_repo = InstrumentRepository(session=file_session)
            service = QuoteImportService(quote_repo=quote_repo, instrument_repo=instrument_repo)
            result = await service.import_from_bytes(
                symbol=symbol,
                content=content,
                filename=file.filename or "",
                data_source="csv_import",
            )
        if not result.success:
            all_errors.append(f"{file.filename}: {result.error}")
            return

        r = result.value
        per_file[file.filename or symbol] = {
            "symbol": symbol,
            "rows": r.get("total_rows", 0),
            "imported": r.get("imported", 0),
            "updated": r.get("updated", 0),
        }
        nonlocal total_rows, total_imported, total_updated
        total_rows += r.get("total_rows", 0)
        total_imported += r.get("imported", 0)
        total_updated += r.get("updated", 0)
        if r.get("errors"):
            all_errors.extend(f"{file.filename}: {e}" for e in r["errors"])

    # Process files concurrently (up to 10 at a time)
    sem = asyncio.Semaphore(10)

    async def limited(file: UploadFile) -> None:
        async with sem:
            await process_one(file)

    results = await asyncio.gather(
        *[limited(f) for f in files],
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            # Keep successful files and report only the failed worker.
            all_errors.append(f"unexpected import error: {result}")

    return ApiResponse[dict[str, Any]](
        success=not all_errors,
        data={
            "total_files": total_files,
            "total_rows": total_rows,
            "imported": total_imported,
            "updated": total_updated,
            "per_file": per_file,
            "errors": all_errors[:50],
        },
    )


@router.get("/test/{instrument_id}")
async def test_quote_direct(instrument_id: str):
    """
    اندپوینت تست مستقل که مستقیماً از SQLite استفاده می‌کند.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from services.quote_service import QuoteService

    engine = create_async_engine("sqlite+aiosqlite:///data/market.db")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        service = QuoteService(session=session)
        result = await service.get_latest(instrument_id)
        if result.success:
            return {"success": True, "price": result.value.price_close}
        return {"success": False, "error": result.error}
