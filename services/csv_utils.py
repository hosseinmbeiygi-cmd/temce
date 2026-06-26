"""Shared CSV/Excel parsing utilities.

Used by both ``quote_import_service`` and ``codal_import_service``
to avoid code duplication.
"""

from __future__ import annotations

import csv
import io


def _normalise_key(key: str) -> str:
    """Lower-case, strip, remove special chars for flexible matching."""
    return (
        key.strip()
        .lower()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace("<", "")
        .replace(">", "")
    )


def _guess_delimiter(first_line: str) -> str:
    for delim in [",", "\t", ";", "|"]:
        if delim in first_line:
            return delim
    return ","


def parse_csv(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    """Parse a UTF-8 CSV into rows, returning ``(rows, header_keys)``."""
    text = content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    if not lines:
        return [], []

    delimiter = _guess_delimiter(lines[0])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = [dict(row) for row in reader]
    header_keys = list(reader.fieldnames) if reader.fieldnames else []
    return rows, header_keys
