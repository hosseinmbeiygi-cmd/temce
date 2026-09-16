from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import (
    get_codal_financial_import_service,
    get_codal_financial_service,
)
from apps.api.error_handlers import safe_error_message
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.codal_accounting_service import (
    calculate_ratios as fs_calculate_ratios,
)
from services.codal_accounting_service import (
    get_financial_summary as fs_get_financial_summary,
)
from services.codal_accounting_service import (
    list_available_symbols as fs_list_symbols,
)
from services.codal_accounting_service import (
    list_reports as fs_list_reports,
)
from services.codal_accounting_service import (
    parse_report as fs_parse_report,
)
from services.codal_financial_import_service import CodalFinancialImportService
from services.codal_financial_service import CodalFinancialService

logger = get_logger(__name__)

router = APIRouter()


@router.get("/symbols")
async def accounting_symbols(
    svc: CodalFinancialService = Depends(get_codal_financial_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """List all symbols with available Codal accounting data."""
    try:
        symbols = await svc.list_symbols()
        if not symbols:
            symbols = fs_list_symbols()
        return ApiResponse[list[dict[str, Any]]](success=True, data=symbols)
    except Exception as exc:
        logger.exception("Failed to list accounting symbols")
        return ApiResponse[list[dict[str, Any]]](
            success=False,
            data=[],
            error={"message": safe_error_message(exc)},
        )


@router.get("/{symbol}/reports")
async def symbol_reports(
    symbol: str,
    report_type: str | None = Query(None, description="Filter by report type (ن-۱۰, ن-۳۰, ن-۳۱)"),
    svc: CodalFinancialService = Depends(get_codal_financial_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """List available Codal reports for a symbol."""
    try:
        reports = await svc.list_reports(symbol, report_type)
        if not reports:
            reports = fs_list_reports(symbol, report_type)
        return ApiResponse[list[dict[str, Any]]](success=True, data=reports)
    except Exception as exc:
        logger.exception("Failed to list reports for %s", symbol)
        return ApiResponse[list[dict[str, Any]]](
            success=False,
            data=[],
            error={"message": safe_error_message(exc)},
        )


@router.get("/{symbol}/ratios")
async def symbol_ratios(
    symbol: str,
    svc: CodalFinancialService = Depends(get_codal_financial_service),
) -> ApiResponse[dict[str, Any]]:
    """Calculate accounting ratios from latest Codal reports for a symbol."""
    try:
        result = await svc.calculate_ratios(symbol)
        if "error" in result:
            result = fs_calculate_ratios(symbol)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed to calculate ratios for %s", symbol)
        return ApiResponse[dict[str, Any]](
            success=False,
            error={"message": safe_error_message(exc)},
        )


@router.get("/{symbol}/financials")
async def symbol_financials(
    symbol: str,
    svc: CodalFinancialService = Depends(get_codal_financial_service),
) -> ApiResponse[dict[str, Any]]:
    """Get structured financial summary for a symbol from latest Codal reports."""
    try:
        result = await svc.get_financial_summary(symbol)
        if "error" in result:
            result = fs_get_financial_summary(symbol)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed to get financial summary for %s", symbol)
        return ApiResponse[dict[str, Any]](
            success=False,
            error={"message": safe_error_message(exc)},
        )


@router.post("/import", summary="Import all codal financial data from filesystem into DB")
async def import_financial_data(
    service: CodalFinancialImportService = Depends(get_codal_financial_import_service),
    batch_id: str | None = Query(None, description="Optional batch ID for tracking"),
) -> ApiResponse[dict[str, Any]]:
    """Parse all codal Excel files and load them into the database."""
    try:
        summary = await service.import_all(batch_id=batch_id)
        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "total_symbols": summary.total_symbols,
                "total_files": summary.total_files,
                "imported": summary.imported,
                "updated": summary.updated,
                "errors": summary.errors[:20],
                "error_count": len(summary.errors),
                "elapsed_seconds": round(summary.elapsed_seconds, 2),
                "per_symbol": {
                    sym: {
                        "total_files": s["total_files"],
                        "imported": s["imported"],
                        "updated": s["updated"],
                        "errors": s["errors"][:5],
                    }
                    for sym, s in summary.per_symbol.items()
                },
            },
        )
    except Exception as exc:
        logger.exception("Failed to import codal financial data")
        return ApiResponse[dict[str, Any]](
            success=False,
            error={"message": safe_error_message(exc)},
        )


@router.get("/{symbol}/report/{filename:path}")
async def report_detail(
    symbol: str,
    filename: str,
    svc: CodalFinancialService = Depends(get_codal_financial_service),
) -> ApiResponse[dict[str, Any]]:
    """Get parsed data for a specific Codal report."""
    try:
        data = await svc.get_report_data(symbol, filename)
        if not data:
            reports = fs_list_reports(symbol)
            target = None
            for r in reports:
                if r["filename"] == filename:
                    target = r
                    break
            if not target:
                return ApiResponse[dict[str, Any]](
                    success=False,
                    error={"message": "Report not found"},
                )
            parsed = fs_parse_report(target["filepath"])
            parsed.update(
                {
                    "symbol": symbol,
                    "filename": filename,
                    "report_type": target["report_type"],
                    "date": target["date"],
                }
            )
            return ApiResponse[dict[str, Any]](success=True, data=parsed)
        return ApiResponse[dict[str, Any]](success=True, data=data)
    except Exception as exc:
        logger.exception("Failed to parse report: %s", filename)
        return ApiResponse[dict[str, Any]](
            success=False,
            error={"message": safe_error_message(exc)},
        )


@router.get("/{symbol}/db-reports", summary="List all reports in DB for a symbol")
async def symbol_db_reports(
    symbol: str,
    svc: CodalFinancialService = Depends(get_codal_financial_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """List all financial statements stored in DB for a symbol."""
    try:
        reports = await svc.get_all_reports_for_symbol(symbol)
        return ApiResponse[list[dict[str, Any]]](success=True, data=reports)
    except Exception as exc:
        logger.exception("Failed to list DB reports for %s", symbol)
        return ApiResponse[list[dict[str, Any]]](
            success=False,
            data=[],
            error={"message": safe_error_message(exc)},
        )
