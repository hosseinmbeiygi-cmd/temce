from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from models.codal_financial import CodalFinancialStatementModel
from services.codal_accounting_service import (
    CODAL_EXCEL_DIR,
    _parse_filename,
    parse_report,
)

logger = get_logger(__name__)


@dataclass
class CodalFinancialImportSummary:
    total_symbols: int = 0
    total_files: int = 0
    imported: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)
    per_symbol: dict[str, dict[str, Any]] = field(default_factory=dict)
    elapsed_seconds: float = 0.0


class CodalFinancialImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_all(self, batch_id: str | None = None) -> CodalFinancialImportSummary:
        start = time.monotonic()
        summary = CodalFinancialImportSummary()

        if not os.path.isdir(CODAL_EXCEL_DIR):
            summary.errors.append(f"Directory not found: {CODAL_EXCEL_DIR}")
            return summary

        symbols_dirs: list[str] = []
        for entry in os.listdir(CODAL_EXCEL_DIR):
            dir_path = os.path.join(CODAL_EXCEL_DIR, entry)
            if os.path.isdir(dir_path):
                symbols_dirs.append(entry)

        summary.total_symbols = len(symbols_dirs)
        batch_id = batch_id or f"import_{int(start)}"

        for dir_name in symbols_dirs:
            symbol_result = await self._import_symbol_dir(dir_name, batch_id)
            summary.per_symbol[dir_name] = symbol_result
            summary.total_files += symbol_result["total_files"]
            summary.imported += symbol_result["imported"]
            summary.updated += symbol_result["updated"]
            if symbol_result.get("errors"):
                summary.errors.extend(
                    f"{dir_name}: {e}" for e in symbol_result["errors"]
                )

        summary.elapsed_seconds = time.monotonic() - start
        logger.info(
            "Codal financial import complete: %d symbols, %d imported, %d updated in %.1fs",
            summary.total_symbols,
            summary.imported,
            summary.updated,
            summary.elapsed_seconds,
        )
        return summary

    async def _import_symbol_dir(
        self, dir_name: str, batch_id: str
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "symbol": dir_name,
            "total_files": 0,
            "imported": 0,
            "updated": 0,
            "errors": [],
        }

        dir_path = os.path.join(CODAL_EXCEL_DIR, dir_name)
        files = sorted(
            [f for f in os.listdir(dir_path) if f.endswith(".xlsx")]
        )
        result["total_files"] = len(files)

        for filename in files:
            filepath = os.path.join(dir_path, filename)
            try:
                parsed = _parse_filename(filename)
                if not parsed:
                    result["errors"].append(f"{filename}: could not parse filename")
                    continue

                symbol = parsed["symbol"]
                report_type = parsed["report_type"]
                report_date = parsed["date"]

                existing = await self._find_existing(symbol, report_type, report_date)
                if existing:
                    existing.parsed_data = await self._load_parsed_data(filepath)
                    existing.file_path = filepath
                    existing.import_batch = batch_id
                    result["updated"] += 1
                else:
                    parsed_data = await self._load_parsed_data(filepath)
                    if not parsed_data:
                        result["errors"].append(f"{filename}: empty parse result")
                        continue

                    model = CodalFinancialStatementModel(
                        id=new_id("cfs"),
                        symbol=symbol,
                        report_type=report_type,
                        report_date=report_date,
                        filename=filename,
                        file_path=filepath,
                        title=parsed_data.get("title", ""),
                        parsed_data=parsed_data,
                        table_count=parsed_data.get("table_count", 0),
                        row_count=parsed_data.get("raw_rows_count", 0),
                        import_batch=batch_id,
                    )
                    self.session.add(model)
                    result["imported"] += 1
            except Exception as exc:
                result["errors"].append(f"{filename}: {exc}")
                logger.exception("Failed to import %s", filepath)

        return result

    async def _find_existing(
        self, symbol: str, report_type: str | None, report_date: str | None
    ) -> CodalFinancialStatementModel | None:
        stmt = select(CodalFinancialStatementModel).where(
            CodalFinancialStatementModel.symbol == symbol,
            CodalFinancialStatementModel.report_type == report_type,
            CodalFinancialStatementModel.report_date == report_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_parsed_data(self, filepath: str) -> dict[str, Any] | None:
        try:
            parsed = parse_report(filepath)
            if parsed and "error" not in parsed:
                return parsed
            else:
                logger.warning("Failed to parse %s: %s", filepath, parsed.get("error"))
                return None
        except Exception:
            logger.exception("Error parsing %s", filepath)
            return None
