"""Data normalizer — clean and standardize extracted table data."""

from __future__ import annotations

import re
from typing import Any

from bulk_importer.adapters.base import ExtractedTable


def normalize_table(table: ExtractedTable) -> ExtractedTable:
    """Normalize a single extracted table: clean headers, standardize values."""
    headers = [_normalize_header(h) for h in table.headers]
    rows = [[_normalize_cell(cell) for cell in row] for row in table.rows]
    return ExtractedTable(
        table_index=table.table_index,
        sheet_name=table.sheet_name,
        logical_section=table.logical_section,
        headers=headers,
        rows=rows,
        row_count=len(rows),
        column_count=len(headers),
    )


def normalize_tables(tables: list[ExtractedTable]) -> list[ExtractedTable]:
    """Normalize all tables from a file."""
    return [normalize_table(t) for t in tables]


def detect_logical_sections(tables: list[ExtractedTable]) -> list[ExtractedTable]:
    """Try to identify logical sections based on table content patterns."""
    for table in tables:
        section = _guess_section(table)
        table.logical_section = section
    return tables


def _guess_section(table: ExtractedTable) -> str | None:
    """Guess the logical section from table content."""
    if not table.headers and not table.rows:
        return None

    # Combine headers and first few rows for pattern matching
    text = " ".join(h for h in table.headers if h).lower()
    if table.rows:
        row0 = " ".join(str(c) for c in table.rows[0] if c)
        text += " " + row0.lower() if row0 else ""

    # Balance sheet patterns
    if any(kw in text for kw in ["دارایی", "بدهی", "سرمایه", "assets", "liabilities"]):
        return "balance_sheet"

    # Income statement patterns
    if any(kw in text for kw in ["درآمد", "هزینه", "سود", "زیان", "revenue", "income", "expense"]):
        return "income_statement"

    # Cash flow patterns
    if any(kw in text for kw in ["جریان نقد", "cash flow", "operating", "investing", "financing"]):
        return "cash_flow"

    # Notes / supplementary patterns
    if any(kw in text for kw in ["یادداشت", "note", "supplementary", "پیوست"]):
        return "notes"

    return None


def _normalize_header(h: str) -> str:
    """Normalize a header string."""
    h = h.strip()
    # Collapse multiple spaces
    h = re.sub(r"\s+", " ", h)
    # Remove leading/trailing special chars
    h = h.strip("*#-—:،")
    return h


def _normalize_cell(cell: Any) -> Any:
    """Normalize a cell value."""
    if cell is None:
        return None
    if isinstance(cell, str):
        cell = cell.strip()
        # Collapse whitespace
        cell = re.sub(r"\s+", " ", cell)
        return cell if cell else None
    if isinstance(cell, float):
        # Preserve integers
        if cell == int(cell):
            return int(cell)
    return cell
