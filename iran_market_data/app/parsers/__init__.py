from __future__ import annotations

from iran_market_data.app.parsers.excel_parser import read_all_sheets, read_excel_file
from iran_market_data.app.parsers.html_parser import extract_links, parse_tables_with_pandas


def extract_text_from_pdf(file_path: str) -> list[dict[str, str | None]]:
    """Lazy import for pdf_parser to avoid requiring pdfplumber at import time."""
    from iran_market_data.app.parsers.pdf_parser import extract_text_from_pdf as _extract

    return _extract(file_path)


__all__ = [
    "parse_tables_with_pandas",
    "extract_links",
    "read_excel_file",
    "read_all_sheets",
    "extract_text_from_pdf",
]
