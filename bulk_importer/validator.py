"""Validator — verify extracted data quality before persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from bulk_importer.adapters.base import ExtractedTable, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a file's extracted data."""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tables_valid: int = 0
    tables_total: int = 0


def validate_parse_result(result: ParseResult) -> ValidationResult:
    """Validate a complete parse result before persistence."""
    vr = ValidationResult()
    vr.tables_total = len(result.tables)

    if not result.tables:
        vr.is_valid = False
        vr.errors.append("No tables extracted")
        return vr

    for table in result.tables:
        ok = validate_table(table, vr)
        if ok:
            vr.tables_valid += 1

    if vr.tables_valid == 0:
        vr.is_valid = False
        vr.errors.append("No valid tables after validation")

    return vr


def validate_table(table: ExtractedTable, vr: ValidationResult) -> bool:
    """Validate a single extracted table. Returns True if valid."""
    valid = True

    # Check minimum rows
    if table.row_count == 0:
        vr.warnings.append(f"Table {table.table_index}: empty (0 rows)")
        return False

    # Check headers exist
    if not table.headers:
        vr.warnings.append(f"Table {table.table_index}: no headers detected")
        # Still valid if rows exist

    # Check column count consistency
    expected_cols = table.column_count or len(table.headers)
    if expected_cols > 0:
        inconsistent = sum(
            1 for row in table.rows
            if len(row) != expected_cols
        )
        if inconsistent > 0:
            pct = inconsistent / len(table.rows) * 100
            if pct > 50:
                vr.errors.append(
                    f"Table {table.table_index}: {pct:.0f}% rows have inconsistent column count"
                )
                valid = False
            else:
                vr.warnings.append(
                    f"Table {table.table_index}: {inconsistent} rows with wrong column count"
                )

    # Check for all-None rows
    all_none_count = sum(
        1 for row in table.rows
        if all(c is None for c in row)
    )
    if all_none_count > 0:
        vr.warnings.append(f"Table {table.table_index}: {all_none_count} all-null rows")

    # Check for duplicate rows
    if table.rows:
        unique_rows = {tuple(str(c) for c in row) for row in table.rows}
        dup_count = len(table.rows) - len(unique_rows)
        if dup_count > 0:
            vr.warnings.append(f"Table {table.table_index}: {dup_count} duplicate rows")

    return valid
