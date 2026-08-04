"""Reusable service for importing instruments from CSV / JSON / XLSX files.

Both the FastAPI endpoint ``apps/api/endpoints/symbols.py::import_symbols`` and the
CLI script ``scripts/import_data.py`` use this service so they stay in sync.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.common.enum_types import AssetClass, MarketType
from domain.instruments.instrument import Instrument
from repositories.instrument_repository import InstrumentRepository

logger = get_logger(__name__)


# Column -> Instrument kwarg mapping
# Tuple format: (column_name, instrument_arg, transform_fn, required)
COLUMN_MAP: list[tuple[str, str, Any | None, bool]] = [
    ("symbol", "symbol", None, True),
    ("name", "name", None, False),
    ("isin", "isin", None, False),
    ("ins_code", "ins_code", None, False),
    ("industry_code", "industry_code", None, False),
    ("market_type", "market_type", None, False),
    ("asset_class", "asset_class", None, False),
    ("sector_code", "sector_code", None, False),
    ("group_code", "group_code", None, False),
    ("sub_group_code", "sub_group_code", None, False),
    ("tick_size", "tick_size", float, False),
    ("lot_size", "lot_size", int, False),
    ("par_value", "par_value", int, False),
    ("eps", "eps", float, False),
    ("shares_count", "shares_count", int, False),
    ("base_volume", "base_volume", int, False),
    ("exchange_code", "exchange_code", None, False),
    ("board_code", "board_code", None, False),
]


SUPPORTED_EXTENSIONS = {".csv", ".json", ".xlsx"}


@dataclass
class ImportSummary:
    total_rows: int = 0
    imported: int = 0
    parse_errors: list[str] = field(default_factory=list)
    import_errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return (self.imported / self.total_rows * 100.0) if self.total_rows else 0.0


def parse_csv_bytes(content: bytes) -> list[dict[str, Any]]:
    """Parse CSV bytes, UTF-8 with optional BOM, into a list of row dictionaries."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def parse_json_bytes(content: bytes) -> list[dict[str, Any]]:
    """Parse JSON bytes.

    Accepted formats:

    1. Top-level list:

        [
            {"symbol": "فولاد"},
            {"symbol": "فملی"}
        ]

    2. Wrapped object:

        {
            "data": [...]
        }

    Supported wrapper keys:
    data, items, records, symbols
    """
    data = json.loads(content.decode("utf-8"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "items", "records", "symbols"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]

    return []


def parse_xlsx_bytes(content: bytes) -> list[dict[str, Any]]:
    """Parse XLSX bytes.

    Requires openpyxl:

        pip install openpyxl
    """
    try:
        import openpyxl  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl is required for Excel import. Install with: pip install openpyxl"
        ) from exc

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)

    try:
        ws = wb.active
        rows: list[dict[str, Any]] = []
        headers: list[str] = []

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [
                    str(cell).strip() if cell is not None else f"col_{j}"
                    for j, cell in enumerate(row)
                ]
                continue

            row_dict = {
                headers[j]: cell
                for j, cell in enumerate(row)
                if j < len(headers)
            }
            rows.append(row_dict)

        return rows

    finally:
        wb.close()


def row_to_instrument_kwargs(row: dict[str, Any], row_num: int) -> dict[str, Any] | str:
    """Convert a row dictionary to Instrument kwargs.

    Returns:
        dict[str, Any]: valid kwargs for Instrument
        str: error message if row is invalid
    """
    symbol = str(row.get("symbol", "")).strip()

    if not symbol:
        return f"Row {row_num}: 'symbol' is required"

    raw_id = str(row.get("id", "")).strip() if "id" in row else ""

    kwargs: dict[str, Any] = {
        "id": raw_id or new_id("inst"),
        "symbol": symbol,
    }

    for col_name, arg_name, transform, required in COLUMN_MAP:
        if col_name == "symbol":
            continue

        value = row.get(col_name)

        if value is None:
            if required:
                return f"Row {row_num} ({symbol}): '{col_name}' is required"
            continue

        s = str(value).strip()

        if not s:
            if required:
                return f"Row {row_num} ({symbol}): '{col_name}' is required"
            continue

        try:
            kwargs[arg_name] = transform(s) if transform else s
        except (ValueError, TypeError) as exc:
            return (
                f"Row {row_num} ({symbol}): "
                f"failed to parse '{col_name}'='{s}': {exc}"
            )

    return kwargs


async def parse_file_bytes_async(filename: str, content: bytes) -> list[dict[str, Any]]:
    """Detect file format by extension and parse content."""
    ext = (Path(filename or "").suffix or "").lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".csv":
        return await asyncio.to_thread(parse_csv_bytes, content)

    if ext == ".json":
        return parse_json_bytes(content)

    return await asyncio.to_thread(parse_xlsx_bytes, content)


class InstrumentImportService:
    """Stateless service that parses uploaded files and persists instruments."""

    def __init__(self, repo: InstrumentRepository | None = None) -> None:
        self.repo = repo or InstrumentRepository()

    async def import_from_bytes(
        self,
        filename: str,
        content: bytes,
        *,
        max_errors: int = 50,
    ) -> Result[ImportSummary]:
        """Parse file content by extension and persist every valid row."""
        try:
            rows = await parse_file_bytes_async(filename, content)
        except RuntimeError as exc:
            return Result.fail(str(exc))
        except ValueError as exc:
            return Result.fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            return Result.fail(f"Failed to parse file: {exc}")

        summary = ImportSummary(total_rows=len(rows))

        if not rows:
            return Result.ok(summary)

        if isinstance(rows[0], dict) and "symbol" not in rows[0]:
            return Result.fail(
                "File must have a 'symbol' column. Found columns: "
                + ", ".join(sorted(str(k) for k in rows[0]))
            )

        kwargs_list: list[dict[str, Any]] = []

        # Phase 1: validate and normalize rows
        for i, row in enumerate(rows, start=2):
            if not isinstance(row, dict):
                if len(summary.parse_errors) < max_errors:
                    summary.parse_errors.append(f"Row {i}: row is not an object/dict")
                continue

            result = row_to_instrument_kwargs(row, i)

            if isinstance(result, str):
                if len(summary.parse_errors) < max_errors:
                    summary.parse_errors.append(result)
            else:
                kwargs_list.append(result)

        # Phase 2: persist instruments
        for kwargs in kwargs_list:
            symbol = kwargs.get("symbol", "?")

            try:
                if isinstance(kwargs.get("market_type"), str):
                    kwargs["market_type"] = MarketType(kwargs["market_type"])

                if isinstance(kwargs.get("asset_class"), str):
                    kwargs["asset_class"] = AssetClass(kwargs["asset_class"])

                instrument = Instrument(**kwargs)
                save = await self.repo.save(instrument)

                if save.success:
                    summary.imported += 1
                else:
                    if len(summary.import_errors) < max_errors:
                        summary.import_errors.append(f"{symbol}: {save.error}")

            except Exception as exc:  # noqa: BLE001
                if len(summary.import_errors) < max_errors:
                    summary.import_errors.append(f"{symbol}: {exc}")

        logger.info(
            "Instrument import: %d/%d rows committed, %d parse errors, %d import errors",
            summary.imported,
            summary.total_rows,
            len(summary.parse_errors),
            len(summary.import_errors),
        )

        return Result.ok(summary)
