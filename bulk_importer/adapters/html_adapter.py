"""HTML adapter — parse HTML table exports from Codal."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bulk_importer.adapters.base import BaseAdapter, ExtractedTable, ParseResult
from bulk_importer.config import MAX_ROWS_PER_TABLE, MAX_TABLES_PER_FILE

logger = logging.getLogger(__name__)


class HtmlAdapter(BaseAdapter):
    """Parse HTML files containing financial tables."""

    def parse(self, file_path: str) -> ParseResult:
        result = ParseResult(file_path=file_path, detected_format="html")

        p = Path(file_path)
        if not p.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            content = p.read_bytes()
        except OSError as e:
            result.errors.append(f"Cannot read file: {e}")
            return result

        # Try lxml first (fast), fallback to regex-based parsing
        tables = self._parse_with_lxml(content)
        if not tables:
            tables = self._parse_with_regex(content)

        if not tables:
            result.errors.append("No tables found in HTML file")
            return result

        for idx, (headers, rows) in enumerate(tables[:MAX_TABLES_PER_FILE]):
            limited_rows = rows[:MAX_ROWS_PER_TABLE]
            table = ExtractedTable(
                table_index=idx,
                headers=headers,
                rows=limited_rows,
                row_count=len(limited_rows),
                column_count=len(headers),
            )
            result.tables.append(table)
            result.total_rows += len(limited_rows)

        return result

    def _parse_with_lxml(self, content: bytes) -> list[tuple[list[str], list[list[str]]]]:
        """Parse HTML tables using lxml (fast)."""
        try:
            from lxml import html
        except ImportError:
            return []

        try:
            doc = html.fromstring(content)
        except Exception:
            return []

        tables = []
        for tbl in doc.xpath("//table"):
            headers, rows = self._extract_table(tbl)
            if headers or rows:
                tables.append((headers, rows))
        return tables

    def _parse_with_regex(self, content: bytes) -> list[tuple[list[str], list[list[str]]]]:
        """Fallback: regex-based HTML table extraction."""
        text = content.decode("utf-8", errors="replace")
        tables = []

        # Find all <table>...</table> blocks
        table_pattern = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL | re.IGNORECASE)
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
        cell_pattern = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.DOTALL | re.IGNORECASE)

        for table_match in table_pattern.finditer(text):
            table_html = table_match.group(1)
            all_rows = []

            for row_match in row_pattern.finditer(table_html):
                cells = [
                    re.sub(r"<[^>]+>", "", cell_match.group(1)).strip()
                    for cell_match in cell_pattern.finditer(row_match.group(1))
                ]
                if cells:
                    all_rows.append(cells)

            if all_rows:
                headers = all_rows[0] if all_rows else []
                rows = all_rows[1:] if len(all_rows) > 1 else []
                tables.append((headers, rows))

        return tables

    def _extract_table(self, tbl) -> tuple[list[str], list[list[str]]]:
        """Extract headers and rows from an lxml table element."""
        headers: list[str] = []
        rows: list[list[str]] = []

        for tr in tbl.xpath(".//tr"):
            cells = [
                self._clean_text(c.text_content())
                for c in tr.xpath("./th|./td")
            ]
            if not cells:
                continue

            # Check if this is a header row (contains <th>)
            has_th = len(tr.xpath("./th")) > 0
            if has_th and not headers:
                headers = cells
            else:
                rows.append(cells)

        return headers, rows

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean text content: normalize whitespace, strip tags."""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
