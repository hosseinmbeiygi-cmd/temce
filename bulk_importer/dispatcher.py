"""Adapter router — dispatch files to the correct parser."""

from __future__ import annotations

from bulk_importer.adapters.base import BaseAdapter, ParseResult
from bulk_importer.adapters.html_adapter import HtmlAdapter
from bulk_importer.adapters.xls_adapter import XlsAdapter
from bulk_importer.adapters.xlsx_adapter import XlsxAdapter


def get_adapter(detected_format: str) -> BaseAdapter:
    """Return the appropriate adapter for the detected format."""
    adapters = {
        "xlsx_ooxml": XlsxAdapter,
        "xls_biff": XlsAdapter,
        "html": HtmlAdapter,
    }
    cls = adapters.get(detected_format)
    if cls is None:
        raise ValueError(f"Unsupported format: {detected_format}")
    return cls()


def dispatch(file_path: str, detected_format: str) -> ParseResult:
    """Parse a file using the appropriate adapter."""
    adapter = get_adapter(detected_format)
    return adapter.parse(file_path)
