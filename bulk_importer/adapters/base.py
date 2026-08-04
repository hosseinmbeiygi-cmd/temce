"""Base adapter interface for file parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedTable:
    """One table extracted from a file."""
    table_index: int
    sheet_name: str | None = None
    logical_section: str | None = None
    headers: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0


@dataclass
class ParseResult:
    """Result of parsing a single file."""
    file_path: str
    detected_format: str
    tables: list[ExtractedTable] = field(default_factory=list)
    total_rows: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.tables) > 0 and len(self.errors) == 0

    @property
    def status(self) -> str:
        if not self.tables:
            return "parse_failed"
        if self.errors:
            return "partial"
        return "parsed"


class BaseAdapter:
    """Base class for file format adapters."""

    def parse(self, file_path: str) -> ParseResult:
        raise NotImplementedError
