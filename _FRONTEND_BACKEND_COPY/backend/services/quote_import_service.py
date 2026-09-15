"""Bulk CSV quote import service.

Handles directory scanning, CSV parsing (Persian OR English/Yahoo-style columns),
symbol → instrument resolution, and upsert-by-date for daily market-data files.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.market_data.quote import Quote
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.csv_utils import _normalise_key, parse_csv

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Column maps
# ═══════════════════════════════════════════════════════════════════════════

PERSIAN_COLUMN_MAP: dict[str, str] = {
    "تاریخ": "date",
    "باز": "price_open",
    "بالا": "price_high",
    "پایین": "price_low",
    "بسته": "price_close",
    "آخرین": "price_last",
    "حجم": "volume",
    "ارزش": "value",
    "تعداد": "trade_count",
    "تغییر": "price_change",
    "درصد تغییر": "price_change_pct",
    "قیمت دیروز": "price_yesterday",
    "اولین": "price_first",
    "بالاترین": "price_max",
    "پایین‌ترین": "price_min",
    "فروش": "ask_price",
    "حجم فروش": "ask_volume",
    "خرید": "bid_price",
    "حجم خرید": "bid_volume",
    "زمان": "time",
}

ENGLISH_COLUMN_MAP: dict[str, str] = {
    "ticker": "_symbol",  # special: used for symbol detection
    "dtyyyymmdd": "date",  # Gregorian date YYYYMMDD
    "dt": "date",  # shorter alias
    "date": "date",
    "open": "price_open",
    "high": "price_high",
    "low": "price_low",
    "close": "price_close",
    "price": "price_close",
    "vol": "volume",
    "volume": "volume",
    "openint": "_skip",  # open interest – skip
    "value": "value",
    "trade_count": "trade_count",
    "change": "price_change",
    "change_pct": "price_change_pct",
    "prev_close": "price_yesterday",
    "yesterday": "price_yesterday",
}


def _detect_format(header_keys: list[str]) -> str:
    """Detect whether the CSV uses Persian, English, or unknown column names.

    Returns ``"persian"``, ``"english"``, or ``"raw"`` (no headers / unknown).
    """
    # Check for Persian characters
    persian_chars = set("آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیيك")
    for k in header_keys:
        for ch in k:
            if ch in persian_chars:
                return "persian"

    # Check for known English columns
    eng_headers = {"ticker", "dtyyyymmdd", "open", "high", "low", "close", "vol"}
    normalised = {_normalise_key(k) for k in header_keys}
    if normalised & eng_headers:
        return "english"

    return "raw"


@dataclass
class QuoteImportSummary:
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


# ── Backward-compatible aliases ──────────────────────────────────────────
parse_persian_csv = parse_csv  # renamed in v2; keep alias for CLI


def _clean_raw_row(
    raw: dict[str, str | None],
) -> dict[str, str]:
    """Strip whitespace from keys and values, drop None keys, normalise Arabic->Persian."""
    row: dict[str, str] = {}
    for k, v in raw.items():
        if k is None:
            continue
        key = k.strip().replace("ك", "ک").replace("ي", "ی")
        row[key] = (v or "").strip()
    return row


# ═══════════════════════════════════════════════════════════════════════════
# Row → Quote kwargs (English format)
# ═══════════════════════════════════════════════════════════════════════════


def _parse_int_or_float(val: str) -> tuple[float, str]:
    """Parse a numeric string, return ``(value, type_hint)`` where type_hint is
    ``"int"`` if the value looks integral, ``"float"`` otherwise."""
    cleaned = val.replace(",", "").replace("،", "").strip()
    if not cleaned:
        return 0.0, "float"
    f = float(cleaned)
    if "." in cleaned or "e" in cleaned.lower():
        return f, "float"
    return f, "int"


def row_to_quote_kwargs_persian(
    row: dict[str, str],
    symbol: str,
    instrument_id: str,
    data_source: str = "csv_import",
) -> dict[str, Any] | str:
    """Convert a Persian-column CSV row to Quote kwargs."""
    raw_date = row.get("تاریخ", "")
    if not raw_date:
        return "Missing 'تاریخ' column"

    kwargs: dict[str, Any] = {
        "id": new_id("quote"),
        "instrument_id": instrument_id,
        "symbol": symbol,
        "date": raw_date,
        "timeframe": "1d",
        "data_source": data_source,
    }

    for persian_col, domain_field in PERSIAN_COLUMN_MAP.items():
        raw_value = row.get(persian_col, "")
        if not raw_value:
            continue

        field_type = _infer_field_type(domain_field)
        try:
            if field_type == "int":
                kwargs[domain_field] = int(raw_value.replace(",", "").replace("،", ""))
            elif field_type == "float":
                kwargs[domain_field] = float(raw_value.replace(",", "").replace("،", ""))
            else:
                kwargs[domain_field] = raw_value
        except (ValueError, TypeError):
            pass

    # Fill OHLC defaults
    close_val = kwargs.get("price_close", 0.0)
    if kwargs.get("price_open", 0) == 0 and "باز" not in row:
        kwargs["price_open"] = close_val
    if kwargs.get("price_high", 0) == 0 and "بالا" not in row:
        kwargs["price_high"] = close_val
    if kwargs.get("price_low", 0) == 0 and "پایین" not in row:
        kwargs["price_low"] = close_val

    return kwargs


def row_to_quote_kwargs_english(
    row: dict[str, str],
    default_symbol: str,
    instrument_id: str,
    data_source: str = "csv_import",
) -> dict[str, Any] | str:
    """Convert a Yahoo-style English-column CSV row to Quote kwargs.

    Column names are matched case-insensitively (normalised).
    """
    # Build a normalised lookup
    norm: dict[str, str] = {}
    for k, v in row.items():
        norm[_normalise_key(k)] = v

    # Symbol: prefer TICKER column, fall back to filename-derived
    symbol = norm.get("ticker", default_symbol)
    raw_date = norm.get("dtyyyymmdd") or norm.get("dt") or norm.get("date", "")
    if not raw_date:
        return "Missing date column (DTYYYYMMDD)"

    kwargs: dict[str, Any] = {
        "id": new_id("quote"),
        "instrument_id": instrument_id,
        "symbol": symbol,
        "date": raw_date,
        "timeframe": "1d",
        "data_source": data_source,
    }

    for eng_col, domain_field in ENGLISH_COLUMN_MAP.items():
        if domain_field == "_symbol" or domain_field == "_skip":
            continue
        raw_value = norm.get(eng_col, "")
        if not raw_value:
            continue

        field_type = _infer_field_type(domain_field)
        try:
            if field_type == "int":
                kwargs[domain_field] = int(raw_value.replace(",", "").replace("،", ""))
            elif field_type == "float":
                kwargs[domain_field] = float(raw_value.replace(",", "").replace("،", ""))
            else:
                kwargs[domain_field] = raw_value
        except (ValueError, TypeError):
            pass

    # Fill OHLC defaults
    close_val = kwargs.get("price_close", 0.0)
    if kwargs.get("price_open", 0) == 0 and "open" not in norm:
        kwargs["price_open"] = close_val
    if kwargs.get("price_high", 0) == 0 and "high" not in norm:
        kwargs["price_high"] = close_val
    if kwargs.get("price_low", 0) == 0 and "low" not in norm:
        kwargs["price_low"] = close_val

    return kwargs


def _infer_field_type(field: str) -> str:
    int_fields = {"volume", "trade_count", "ask_volume", "bid_volume"}
    return "int" if field in int_fields else "float"


# ═══════════════════════════════════════════════════════════════════════════
# Main service
# ═══════════════════════════════════════════════════════════════════════════


class QuoteImportService:
    """Import daily quote data from CSV files in bulk.

    Supports both Persian-column (تاریخ, باز, بسته, …) and English Yahoo-style
    (TICKER, DTYYYYMMDD, OPEN, HIGH, LOW, CLOSE, VOL) CSV formats.
    """

    def __init__(
        self,
        quote_repo: QuoteRepository,
        instrument_repo: InstrumentRepository,
    ) -> None:
        self.quote_repo = quote_repo
        self.instrument_repo = instrument_repo

    async def import_directory(
        self,
        directory: str | Path,
        *,
        data_source: str = "csv_import",
        max_concurrent: int = 20,
        symbol_from_filename: bool = True,
    ) -> QuoteImportSummary:
        """Scan a directory for .csv files and import every file concurrently.

        Parameters
        ----------
        symbol_from_filename: bool
            If True (default), the symbol is taken from the file stem (name without .csv).
            If False, the symbol is read from the TICKER column inside the CSV (English format).
        """
        start = time.monotonic()
        summary = QuoteImportSummary()

        dir_path = Path(directory)
        if not dir_path.is_dir():
            summary.errors.append(f"Directory not found: {directory}")
            return summary

        csv_files = sorted(dir_path.glob("*.csv"))
        if not csv_files:
            summary.errors.append(f"No .csv files found in {directory}")
            return summary

        summary.total_files = len(csv_files)
        logger.info("Found %d CSV files in %s", len(csv_files), directory)

        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_one(file: Path) -> None:
            file_symbol = file.stem.strip()
            async with semaphore:
                try:
                    content = file.read_bytes()
                    file_result = await self._import_single_file(
                        symbol=file_symbol,
                        content=content,
                        filename=file.name,
                        data_source=data_source,
                        symbol_from_column=not symbol_from_filename,
                    )
                    summary.per_file[file.name] = {
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
                        summary.errors.extend(f"{file.name}: {e}" for e in file_result["errors"])
                    logger.info(
                        "  %s → %d imported, %d updated, %d errors",
                        file.name,
                        file_result.get("imported", 0),
                        file_result.get("updated", 0),
                        len(file_result.get("errors", [])),
                    )
                except Exception as exc:
                    summary.errors.append(f"{file.name}: {exc}")
                    logger.exception("Failed to process %s", file.name)

        tasks = [process_one(f) for f in csv_files]
        await asyncio.gather(*tasks)

        summary.elapsed_seconds = time.monotonic() - start
        return summary

    async def import_from_bytes(
        self,
        symbol: str,
        content: bytes,
        *,
        filename: str = "",
        data_source: str = "csv_import",
    ) -> Result[dict[str, Any]]:
        file_result = await self._import_single_file(
            symbol=symbol,
            content=content,
            filename=filename,
            data_source=data_source,
        )
        return Result.ok(file_result)

    async def _import_single_file(
        self,
        symbol: str,
        content: bytes,
        filename: str,
        data_source: str,
        symbol_from_column: bool = False,
    ) -> dict[str, Any]:
        """Parse and persist a single CSV file.

        Returns a dict with counts: total_rows, imported, updated, skipped,
        errors, and actual_symbol.
        """
        result: dict[str, Any] = {
            "total_rows": 0,
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "actual_symbol": symbol,
        }

        # 1. Parse CSV and detect format
        try:
            raw_rows, header_keys = parse_csv(content)
        except Exception as exc:
            result["errors"].append(f"CSV parse error: {exc}")
            return result

        result["total_rows"] = len(raw_rows)
        if not raw_rows:
            return result

        fmt = _detect_format(header_keys)
        logger.debug("Detected format '%s' for %s (headers: %s)", fmt, filename, header_keys)

        # 2. Convert rows → Quote kwargs
        kwargs_list: list[dict[str, Any]] = []
        actual_symbol = symbol

        for i, raw in enumerate(raw_rows, start=2):
            row = _clean_raw_row(raw)

            if fmt == "english":
                kw = row_to_quote_kwargs_english(
                    row,
                    default_symbol=symbol,
                    instrument_id="",  # placeholder – resolved below
                    data_source=data_source,
                )
                if isinstance(kw, str):
                    result["errors"].append(f"Row {i}: {kw}")
                    continue
                # Get actual symbol from CSV ticker column (case-insensitive)
                norm_lookup: dict[str, str] = {_normalise_key(k): v for k, v in row.items()}
                csv_ticker = norm_lookup.get("ticker", "")
                if symbol_from_column and csv_ticker:
                    actual_symbol = csv_ticker.strip()
            else:
                # Persian (or raw fallback) – use file-name symbol
                kw = row_to_quote_kwargs_persian(row, symbol=symbol, instrument_id="", data_source=data_source)
                if isinstance(kw, str):
                    result["errors"].append(f"Row {i}: {kw}")
                    continue

            kwargs_list.append(kw)

        result["actual_symbol"] = actual_symbol

        # 3. Resolve symbol → instrument_id
        inst_result = await self.instrument_repo.get_by_symbol(actual_symbol)
        if not inst_result.success:
            result["errors"].append(
                f"Symbol '{actual_symbol}' not found in instruments DB (from filename '{filename}')"
            )
            return result
        instrument = inst_result.value

        # Fill in instrument_id for all rows
        for kw in kwargs_list:
            kw["instrument_id"] = instrument.id

        # 4. Upsert each row
        for kw in kwargs_list:
            q_date = kw.get("date", "")
            existing_result = await self.quote_repo.get_by_date(instrument.id, q_date)
            existing = existing_result.value if existing_result.success else None

            if existing:
                kw["id"] = existing.id
                kw["created_at"] = existing.created_at
                quote = Quote(**kw)
                save_result = await self.quote_repo.save(quote)
                if save_result.success:
                    result["updated"] += 1
                else:
                    result["errors"].append(f"{actual_symbol} {q_date}: {save_result.error}")
            else:
                quote = Quote(**kw)
                save_result = await self.quote_repo.save(quote)
                if save_result.success:
                    result["imported"] += 1
                else:
                    result["errors"].append(f"{actual_symbol} {q_date}: {save_result.error}")

        return result
