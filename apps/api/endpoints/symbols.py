from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from apps.api.dependencies import (
    get_instrument_import_service,
    get_symbol_service,
)
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.instrument_import_service import SUPPORTED_EXTENSIONS, InstrumentImportService
from services.symbol_service import SymbolService

logger = get_logger(__name__)

router = APIRouter()

# Maximum upload size: 10 MB. Files larger than this should be split or imported via the CLI.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# ── Sample CSV template ─────────────────────────────────────────────────────
# 3 pre-filled rows that match the SCHEMA_HINTS displayed in the import page.
# Server is the single source of truth so first-time users get a file that the
# backend will actually accept; if the import schema changes, only this string
# (and the page's SCHEMA_HINTS table) needs to be updated together.
# Notes:
#   * Persian characters stay literal in UTF-8 — import_from_bytes parses
#     UTF-8 with optional BOM, so this round-trips cleanly.
#   * market_type values must match the MarketType enum (bours | ifb | otc |
#     base | energy | …). "bours" is the most common and the safest default.
#   * Numeric columns are written as plain integers so the CSV importer
#     int()/float() transforms work without locale surprises.
SAMPLE_TEMPLATE_CSV = (
    "symbol,name,isin,market_type,sector_code,group_code,tick_size,lot_size,par_value\r\n"
    "فولاد,فولاد مبارکه اصفهان,IRO1FOLD0001,bours,27,27,1,1,1000\r\n"
    "شپنا,پالایش نفت اصفهان,IRO1PNES0001,bours,11,11,1,1,1000\r\n"
    "وبملت,بانک ملت,IRO1BMLT0001,bours,58,58,1,1,1000\r\n"
)


def _validate_upload(file: UploadFile) -> str | None:
    """Returns an error message if *file* is rejected, otherwise None.

    Mirrors the server-side allowlist so the UI can't trick us into parsing
    arbitrary binary content as CSV/JSON/XLSX.
    """
    name = file.filename or ""
    if not name:
        return "Filename is required"
    # Use the suffix defensively (lower-case, allow only one dot).
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if f".{suffix}" not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        return f"Unsupported file extension '.{suffix or '(none)'}'. Allowed: {allowed}"
    return None


@router.post("", summary="Create symbol", description="Create a new trading symbol/instrument")
async def create_symbol(
    body: dict[str, Any] = Body(...),
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    rest = {k: v for k, v in body.items() if k not in ("symbol", "name")}
    result = await service.create(symbol=body.get("symbol", ""), name=body.get("name", ""), **rest)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("", summary="List symbols", description="List all trading symbols with pagination")
async def list_symbols(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=10000),
    market: str | None = Query(None, description="Filter by market type (e.g. BOURS, IFB, OTC)"),
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.list_all(page, page_size, market=market)
    return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)


@router.get("/search", summary="Search symbols", description="Search symbols by name or symbol code")
async def search_symbols(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.search(q, page)
    return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)


@router.get("/{symbol}", summary="Get symbol", description="Get a single symbol by its code")
async def get_symbol(
    symbol: str,
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_by_symbol(symbol)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error or f"Symbol {symbol} not found")
    return ApiResponse[dict[str, Any]](
        success=True,
        data=result.value if result.value else None,
    )


@router.get("/{symbol}/detail", summary="Symbol detail", description="Get detailed information about a symbol")
async def get_symbol_detail(
    symbol: str,
    service: SymbolService = Depends(get_symbol_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_detail(symbol)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.post(
    "/import",
    summary="Import symbols",
    description="Bulk-import instruments from an uploaded CSV, JSON, or XLSX file. "
    "The file must contain a 'symbol' column; common optional columns are listed in "
    "scripts/import_data.py.",
)
async def import_symbols(
    file: UploadFile = File(..., description="CSV, JSON, or XLSX file with a 'symbol' column"),
    importer: InstrumentImportService = Depends(get_instrument_import_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        rejection = _validate_upload(file)
        if rejection:
            return ApiResponse[dict[str, Any]](success=False, error={"message": rejection})

        content = await file.read()
        if not content:
            return ApiResponse[dict[str, Any]](success=False, error={"message": "Uploaded file is empty"})
        if len(content) > MAX_UPLOAD_BYTES:
            return ApiResponse[dict[str, Any]](
                success=False,
                error={"message": f"File too large ({len(content)} bytes). Max is {MAX_UPLOAD_BYTES} bytes."},
            )

        result = await importer.import_from_bytes(file.filename or "", content)
        if not result.success:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result.error or "Import failed"})

        summary = result.value
        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "filename": file.filename,
                "total_rows": summary.total_rows,
                "imported": summary.imported,
                "parse_errors": summary.parse_errors,
                "import_errors": summary.import_errors,
            },
        )
    except Exception as exc:  # noqa: BLE001 - we want a clean JSON error envelope, not a 500 stack
        logger.exception("Instrument import endpoint failed unexpectedly")
        return ApiResponse[dict[str, Any]](success=False, error={"message": f"Server error: {exc}"})


@router.get(
    "/sample",
    summary="Download CSV sample template",
    description="Stream a 3-row UTF-8 CSV template that matches the import page's "
    "SCHEMA_HINTS. Useful for first-time users who want a working file to start from.",
    response_class=StreamingResponse,
)
async def download_sample_template() -> StreamingResponse:
    """Stream the CSV sample so the import page's download button works.

    Returned with ``Content-Disposition: attachment`` so the browser saves it
    rather than rendering it inline. The body is a single UTF-8-encoded string
    kept brief so the streaming overhead (chunked transfer, generator setup)
    stays trivial — there's no measurable win to splitting it into per-line
    chunks for 4 lines of CSV.
    """

    def iter_body() -> Any:
        yield SAMPLE_TEMPLATE_CSV.encode("utf-8")

    return StreamingResponse(
        iter_body(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="instruments-sample.csv"',
            "Cache-Control": "no-cache",
        },
    )



