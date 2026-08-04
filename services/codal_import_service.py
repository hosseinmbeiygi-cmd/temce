"""Bulk Codal disclosure import service.

Handles Excel (.xlsx) and CSV parsing, symbol → instrument resolution,
and upsert-by-unique-key (symbol + report_type + fiscal_year + period) for
Codal/کدال disclosure filings.
"""

from __future__ import annotations

import asyncio
import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.codal.disclosure import Disclosure
from repositories.codal_repository import CodalRepository
from repositories.instrument_repository import InstrumentRepository
from services.csv_utils import _normalise_key, parse_csv

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Persian ↔ English column mapping for Codal disclosures
# ═══════════════════════════════════════════════════════════════════════════

PERSIAN_COLUMN_MAP: dict[str, str] = {
    "نماد": "symbol",
    "نام شرکت": "company_name",
    "نوع گزارش": "disclosure_type",
    "سال مالی": "fiscal_year",
    "دوره": "period",
    "تاریخ انتشار": "publish_date",
    "خلاصه": "summary",
    "لینک": "url",
    "دسته": "category",
    "منبع": "data_source",
    "شناسه": "tracking_no",
}

ENGLISH_COLUMN_MAP: dict[str, str] = {
    "symbol": "symbol",
    "ticker": "symbol",
    "company": "company_name",
    "company_name": "company_name",
    "report_type": "disclosure_type",
    "type": "disclosure_type",
    "fiscal_year": "fiscal_year",
    "year": "fiscal_year",
    "period": "period",
    "publish_date": "publish_date",
    "date": "publish_date",
    "summary": "summary",
    "url": "url",
    "link": "url",
    "category": "category",
    "source": "data_source",
    "tracking_no": "tracking_no",
}


def _detect_format(header_keys: list[str]) -> str:
    """Detect whether headers use Persian, English, or unknown column names."""
    persian_chars = set("آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیيك")
    for k in header_keys:
        for ch in k:
            if ch in persian_chars:
                return "persian"

    eng_headers = {"symbol", "ticker", "report_type", "type", "fiscal_year"}
    normalised = {_normalise_key(k) for k in header_keys}
    if normalised & eng_headers:
        return "english"

    return "raw"


@dataclass
class CodalImportSummary:
    total_files: int = 0
    total_rows: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    per_file: dict[str, dict[str, Any]] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.imported + self.updated + self.skipped
        return (total / self.total_rows * 100.0) if self.total_rows else 100.0


# ═══════════════════════════════════════════════════════════════════════════
# File parsing
# ═══════════════════════════════════════════════════════════════════════════

def parse_xlsx(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    """Parse an Excel (.xlsx) file. Returns ``(rows, header_keys)``.

    Reads the first sheet. First row is treated as the header.
    """
    try:
        import openpyxl
    except ImportError:
        return [], []

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return [], []

    raw_rows: list[list[Any]] = []
    for row in ws.iter_rows(values_only=True):
        raw_rows.append(list(row))

    wb.close()

    if not raw_rows:
        return [], []

    header_keys = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(raw_rows[0])]
    rows: list[dict[str, str]] = []
    for raw in raw_rows[1:]:
        row: dict[str, str] = {}
        for i, val in enumerate(raw):
            if i < len(header_keys):
                row[header_keys[i]] = str(val) if val is not None else ""
        rows.append(row)

    return rows, header_keys


def row_to_disclosure_kwargs(
    row: dict[str, str],
    default_symbol: str,
    instrument_id: str,
    fmt: str = "english",
) -> dict[str, Any] | str:
    """Convert a CSV/Excel row to Codal ``Disclosure`` kwargs.

    Maps Persian or English columns via the column maps above.
    """
    col_map = PERSIAN_COLUMN_MAP if fmt == "persian" else ENGLISH_COLUMN_MAP

    # Build normalised lookup for flexible column matching
    norm_lookup: dict[str, str] = {}
    for k, v in row.items():
        norm_lookup[_normalise_key(k)] = v
        # Also add the original key for Persian matching
        norm_lookup[k.strip()] = v

    kwargs: dict[str, Any] = {
        "id": new_id("cod"),
        "instrument_id": instrument_id,
        "data_source": "manual_import",
    }

    # Map columns
    for col, target_field in col_map.items():
        # Try normalised key first, then raw cleaned key
        val = norm_lookup.get(_normalise_key(col), "") or norm_lookup.get(col, "")
        if not val:
            continue
        kwargs[target_field] = val

    # Symbol: prefer mapped symbol, fall back to default
    if not kwargs.get("symbol"):
        kwargs["symbol"] = default_symbol

    # Title
    kwargs.setdefault("title", "")

    # Check we have at least symbol + some content
    if not kwargs.get("symbol"):
        return "Missing symbol column"

    # Parse publish_date from various formats
    if kwargs.get("publish_date"):
        kwargs["publish_date"] = kwargs["publish_date"].strip()

    return kwargs


# ═══════════════════════════════════════════════════════════════════════════
# Main service
# ═══════════════════════════════════════════════════════════════════════════


class CodalImportService:
    """Import Codal disclosures from Excel or CSV files.

    Supports Persian and English column headers.  Upserts by
    (symbol, report_type, fiscal_year, period) — if an existing disclosure
    with the same key exists, it updates it; otherwise inserts a new one.
    """

    def __init__(
        self,
        codal_repo: CodalRepository,
        instrument_repo: InstrumentRepository,
    ) -> None:
        self.codal_repo = codal_repo
        self.instrument_repo = instrument_repo

    async def import_directory(
        self,
        directory: str | Path,
        *,
        data_source: str = "manual_import",
        max_concurrent: int = 10,
    ) -> CodalImportSummary:
        """Scan a directory for .xlsx + .csv files and import them concurrently."""
        start = time.monotonic()
        summary = CodalImportSummary()

        dir_path = Path(directory)
        if not dir_path.is_dir():
            summary.errors.append(f"Directory not found: {directory}")
            return summary

        files = sorted(list(dir_path.glob("*.xlsx")) + list(dir_path.glob("*.csv")))
        if not files:
            summary.errors.append(f"No .xlsx or .csv files found in {directory}")
            return summary

        summary.total_files = len(files)
        logger.info("Found %d files in %s", len(files), directory)

        sem = asyncio.Semaphore(max_concurrent)

        async def process_one(fp: Path) -> None:
            file_symbol = fp.stem.strip()
            async with sem:
                try:
                    content = fp.read_bytes()
                    file_result = await self._import_single_file(
                        symbol=file_symbol,
                        content=content,
                        filename=fp.name,
                        data_source=data_source,
                    )
                    summary.per_file[fp.name] = {
                        "symbol": file_result.get("actual_symbol", file_symbol),
                        "rows": file_result.get("total_rows", 0),
                        "imported": file_result.get("imported", 0),
                        "updated": file_result.get("updated", 0),
                        "errors": file_result.get("errors", []),
                    }
                    summary.total_rows += file_result.get("total_rows", 0)
                    summary.imported += file_result.get("imported", 0)
                    summary.updated += file_result.get("updated", 0)
                    summary.skipped += file_result.get("skipped", 0)
                    if file_result.get("errors"):
                        summary.errors.extend(
                            f"{fp.name}: {e}" for e in file_result["errors"]
                        )
                except Exception as exc:
                    summary.errors.append(f"{fp.name}: {exc}")
                    logger.exception("Failed to process %s", fp.name)

        await asyncio.gather(*[process_one(f) for f in files])

        summary.elapsed_seconds = time.monotonic() - start
        return summary

    async def import_from_bytes(
        self,
        symbol: str,
        content: bytes,
        *,
        filename: str = "",
        data_source: str = "manual_import",
    ) -> Result[dict[str, Any]]:
        file_result = await self._import_single_file(
            symbol=symbol, content=content, filename=filename, data_source=data_source
        )
        return Result.ok(file_result)

    async def _import_single_file(
        self,
        symbol: str,
        content: bytes,
        filename: str,
        data_source: str,
    ) -> dict[str, Any]:
        """Parse and persist a single Excel/CSV file."""
        result: dict[str, Any] = {
            "total_rows": 0,
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "actual_symbol": symbol,
        }

        # 1. Parse file (XLSX or CSV)
        try:
            if filename.lower().endswith(".xlsx"):
                raw_rows, header_keys = parse_xlsx(content)
            else:
                raw_rows, header_keys = parse_csv(content)
        except Exception as exc:
            result["errors"].append(f"Parse error: {exc}")
            return result

        result["total_rows"] = len(raw_rows)
        if not raw_rows:
            return result

        fmt = _detect_format(header_keys)
        logger.debug("Detected format '%s' for %s", fmt, filename)

        # 2. Resolve instrument_id from first row's symbol (or filename)
        actual_symbol = symbol

        # Try to read symbol from first row
        first_row = raw_rows[0]
        if fmt == "persian":
            actual_symbol = first_row.get("نماد", symbol)
        else:
            nl: dict[str, str] = {_normalise_key(k): v for k, v in first_row.items()}
            actual_symbol = nl.get("symbol", "") or nl.get("ticker", "") or symbol

        inst_result = await self.instrument_repo.get_by_symbol(actual_symbol)
        if not inst_result.success:
            result["errors"].append(
                f"Symbol '{actual_symbol}' not found in instruments DB"
            )
            return result
        instrument_id = inst_result.value.id
        result["actual_symbol"] = actual_symbol

        # 3. Convert rows → Disclosure kwargs
        kwargs_list: list[dict[str, Any]] = []
        for i, raw in enumerate(raw_rows, start=2):
            row: dict[str, str] = {
                k.strip().replace("ك", "ک").replace("ي", "ی"): (v or "").strip()
                for k, v in raw.items()
                if k is not None
            }

            kw = row_to_disclosure_kwargs(
                row,
                default_symbol=actual_symbol,
                instrument_id=instrument_id,
                fmt=fmt,
            )
            if isinstance(kw, str):
                result["errors"].append(f"Row {i}: {kw}")
                continue
            kwargs_list.append(kw)

        # 4. Upsert by unique key
        for kw in kwargs_list:
            sym = kw.get("symbol", "")
            rtype = kw.get("disclosure_type", "")
            fyear = kw.get("fiscal_year", "")
            period = kw.get("period", "")

            # Find existing disclosure with same key
            existing = await self._find_existing(sym, rtype, fyear, period)
            if existing:
                kw["id"] = existing.id
                kw["created_at"] = existing.created_at
                disclosure = Disclosure(**kw)
                save_result = await self.codal_repo.save(disclosure)
                if save_result.success:
                    result["updated"] += 1
                else:
                    result["errors"].append(f"{sym} {rtype} {fyear}: {save_result.error}")
            else:
                disclosure = Disclosure(**kw)
                save_result = await self.codal_repo.save(disclosure)
                if save_result.success:
                    result["imported"] += 1
                else:
                    result["errors"].append(f"{sym} {rtype} {fyear}: {save_result.error}")

        return result

    async def _find_existing(
        self,
        symbol: str,
        report_type: str,
        fiscal_year: str,
        period: str,
    ) -> Disclosure | None:
        """Find an existing disclosure matching the unique key (O(1) targeted query)."""
        result = await self.codal_repo.get_by_key(symbol, report_type, fiscal_year, period)
        if result.success and result.value:
            return result.value
        return None
