"""File format detection using magic bytes and sniffing."""

from __future__ import annotations

import contextlib
from pathlib import Path

OLE_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
MAX_SNIFF_BYTES = 4096


def detect_format(file_path: str | Path) -> str:
    """Detect file format from magic bytes + content sniffing.

    Returns:
        "xlsx_ooxml" — OOXML/XLSX (starts with PK)
        "xls_biff"   — OLE/XLS (starts with D0 CF 11 E0 ...)
        "html"        — HTML export (<html, <!doctype)
        "csv"         — CSV (comma/tab separated text)
        "unknown"     — unrecognized format
    """
    p = Path(file_path)

    try:
        with p.open("rb") as f:
            head = f.read(MAX_SNIFF_BYTES)
    except OSError:
        return "unknown"

    if len(head) == 0:
        return "unknown"

    # ── PK → OOXML/XLSX ──
    if head[:2] == b"PK":
        return "xlsx_ooxml"

    # ── D0 CF 11 E0 → OLE/XLS ──
    if len(head) >= 8 and head[:8] == OLE_MAGIC:
        return "xls_biff"

    # ── HTML sniffing ──
    text_head = head.lstrip(b"\xef\xbb\xbf\xfe\xff\r\n \t")
    text_head_lower = text_head[:512].decode("utf-8", errors="replace").lower()

    if text_head_lower.startswith("<html") or text_head_lower.startswith("<!doctype"):
        return "html"

    # ── CSV heuristic: first 5 lines have consistent delimiters ──
    lines = text_head.split(b"\n")[:5]
    if len(lines) >= 2:
        comma_count = lines[0].count(b",")
        tab_count = lines[0].count(b"\t")
        semicolon_count = lines[0].count(b";")
        delimiter = max((comma_count, tab_count, semicolon_count))
        if delimiter >= 2:
            # Check consistency across first few lines
            consistent = all(
                abs(line.count(b",") - comma_count) <= 1
                for line in lines[1:3] if line.strip()
            )
            if consistent:
                return "csv"

    return "unknown"


def parse_filename_metadata(file_path: str | Path) -> dict[str, str | None]:
    """Extract issuer_symbol, report_type, jalali_date from codal Excel filename.

    Filename pattern: {company}_ن-۱۰_{jalali_year}_{jalali_month}_{jalali_day}.xlsx
    Example: شستا_ن-۱۰_۱۴۰۳_۰۴_۱۰.xlsx
    """
    from bulk_importer.config import REPORT_TYPE_MAP

    p = Path(file_path)
    stem = p.stem  # filename without extension

    result: dict[str, str | None] = {
        "issuer_symbol": None,
        "report_type": None,
        "report_date_jalali": None,
    }

    # Split by underscore
    parts = stem.split("_")
    if len(parts) < 2:
        return result

    # First part is the company symbol
    result["issuer_symbol"] = parts[0]

    # Find report type pattern (ن-XX)
    for i, part in enumerate(parts):
        if part in REPORT_TYPE_MAP:
            result["report_type"] = REPORT_TYPE_MAP[part]
            # Remaining parts after report type are date components
            date_parts = parts[i + 1:]
            if len(date_parts) >= 3:
                with contextlib.suppress(ValueError, IndexError):
                    # Convert Persian digits to English
                    def persian_to_en(s: str) -> str:
                        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
                        return "".join(
                            str(persian_digits.index(c)) if c in persian_digits else c
                            for c in s
                        )

                    y = persian_to_en(date_parts[0])
                    m = persian_to_en(date_parts[1])
                    d = persian_to_en(date_parts[2])
                    result["report_date_jalali"] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            break

    return result
