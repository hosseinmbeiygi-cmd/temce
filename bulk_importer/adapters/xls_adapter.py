"""XLS (legacy) adapter using xlrd."""

from __future__ import annotations

import logging
from pathlib import Path

from bulk_importer.adapters.base import BaseAdapter, ExtractedTable, ParseResult
from bulk_importer.config import MAX_ROWS_PER_TABLE, MAX_TABLES_PER_FILE

logger = logging.getLogger(__name__)


class XlsAdapter(BaseAdapter):
    """Parse legacy .xls files using xlrd."""

    def parse(self, file_path: str) -> ParseResult:
        result = ParseResult(file_path=file_path, detected_format="xls_biff")

        try:
            import xlrd
        except ImportError:
            result.errors.append("xlrd not installed: pip install xlrd==1.2.0")
            return result

        p = Path(file_path)
        if not p.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            wb = xlrd.open_workbook(str(p))
        except Exception as e:
            result.errors.append(f"Failed to open workbook: {e}")
            return result

        try:
            for sheet_idx in range(wb.nsheets):
                if sheet_idx >= MAX_TABLES_PER_FILE:
                    break

                ws = wb.sheet_by_index(sheet_idx)
                headers: list[str] = []
                rows: list[list] = []
                row_count = 0

                for row_idx in range(ws.nrows):
                    if row_count >= MAX_ROWS_PER_TABLE:
                        break

                    cells = [self._cell_to_str(ws.cell_value(row_idx, col_idx))
                             for col_idx in range(ws.ncols)]

                    if not any(c for c in cells):
                        continue

                    if not headers:
                        headers = cells
                        continue

                    rows.append(cells)
                    row_count += 1

                if headers or rows:
                    table = ExtractedTable(
                        table_index=sheet_idx,
                        sheet_name=ws.name,
                        headers=headers,
                        rows=rows,
                        row_count=row_count,
                        column_count=len(headers),
                    )
                    result.tables.append(table)
                    result.total_rows += row_count

        except Exception as e:
            result.errors.append(f"Error reading sheets: {e}")

        return result

    @staticmethod
    def _cell_to_str(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        return str(value).strip()
