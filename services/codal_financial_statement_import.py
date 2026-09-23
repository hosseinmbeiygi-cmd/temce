"""Financial-statement extraction for the ACTIVE Codal attachment flow.

Bridge between ``CodalAttachmentDownloadService`` (the scheduler-driven
pipeline) and ``codal_financial_statements``. Previously only the legacy
``CodalDownloadService`` (fed by the unmaintained ``codal_announcements``
table) populated that table, so financials from the active flow were never
extracted (audit finding C1).

Storage contract:
* Files live under ``data/codal_attachments/codal/<symbol>/<code>_excel.xlsx``
  (written by the attachment service). ``import_statement_record`` receives the
  raw bytes and reuses ``parse_report`` through a temp file so the HTML-Excel
  parser keeps working unchanged.
* Dedup/upsert: unique on ``(symbol, report_type, report_date)`` — the same
  constraint the legacy import uses. ``report_type`` is derived from the
  announcement TITLE (C3): ``ن-۱۰``/``ن-۳۰``/``ن-۳۱`` letter codes when
  present, otherwise a classified category, so two different same-day reports
  no longer collapse onto one row.
"""

from __future__ import annotations

import contextlib
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)

# Jalali letter codes Codal uses for periodic reports (also the source of the
# legacy ``report_type`` values, so both flows land on the same taxonomy).
_LETTER_TYPE_RE = re.compile(r"\b(ن-۱۰|ن-۳۰|ن-۳۱|ن-۱۵)\b")

_TITLE_CATEGORY: list[tuple[str, str]] = [
    ("monthly_activity", ["فعالیت ماهانه", "عملکرد ماهانه", "گزارش فعالیت"]),
    ("financial_statements", ["صورت‌های مالی", "ترازنامه", "سود و زیان", "صورت جریان وجوه نقد"]),
    ("dividend", ["سود نقدی", "تقسیم سود", "سود سهام"]),
    ("capital_increase", ["افزایش سرمایه"]),
    ("general_meeting", ["مجمع"]),
    ("nav_disclosure", ["نرخ بازدهی", "صورت وضعیت مالی", "ترکیب دارایی"]),
]


def classify_report_type(title: str) -> str:
    """Derive a stable ``report_type`` from the announcement title (C3)."""
    m = _LETTER_TYPE_RE.search(title or "")
    if m:
        return m.group(1)
    for category, keywords in _TITLE_CATEGORY:
        if any(k in (title or "") for k in keywords):
            return category
    return "codal_download"


async def import_statement_record(
    symbol: str,
    announcement_id: int,
    attachment_id: int,
    title: str,
    content: bytes,
    published_at: datetime | None = None,
) -> bool:
    """Parse Excel/HTML-Excel bytes and upsert into ``codal_financial_statements``.

    Returns True when a row was written/updated. Never raises — callers log.
    """
    if not symbol or not content:
        return False

    from services.codal_accounting_service import parse_report

    with tempfile.TemporaryDirectory(prefix="codal_parse_") as tmp:
        # parse_report() reads from disk; write the bytes to a temp .xlsx so the
        # existing HTML-Excel parser is reused without modification.
        safe_symbol = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", symbol)
        path = Path(tmp) / f"{safe_symbol}_{announcement_id}_{attachment_id}.xlsx"
        path.write_bytes(content)
        try:
            parsed = parse_report(str(path))
        finally:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)

    if not parsed or "error" in parsed:
        logger.debug(
            "Statement parse produced no data: symbol=%s attachment=%s",
            symbol,
            attachment_id,
        )
        return False

    report_type = classify_report_type(title)
    report_date = (published_at or datetime.now()).strftime("%Y-%m-%d")

    from sqlalchemy import select

    from core.database import get_session
    from models.codal_financial import CodalFinancialStatementModel

    async for session in get_session():
        existing = (
            await session.execute(
                select(CodalFinancialStatementModel).where(
                    CodalFinancialStatementModel.symbol == symbol,
                    CodalFinancialStatementModel.report_type == report_type,
                    CodalFinancialStatementModel.report_date == report_date,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.parsed_data = parsed
            existing.title = title[:500] or existing.title
            existing.table_count = parsed.get("table_count", 0)
            existing.row_count = parsed.get("raw_rows_count", 0)
            existing.import_batch = "codal_attachments"
        else:
            session.add(
                CodalFinancialStatementModel(
                    id=new_id("cfs"),
                    symbol=symbol,
                    report_type=report_type,
                    report_date=report_date,
                    filename=f"{announcement_id}_{attachment_id}",
                    file_path="",
                    title=title[:500],
                    parsed_data=parsed,
                    table_count=parsed.get("table_count", 0),
                    row_count=parsed.get("raw_rows_count", 0),
                    import_batch="codal_attachments",
                )
            )
        await session.commit()

    logger.debug(
        "Financial statement stored: %s/%s/%s", symbol, report_type, report_date
    )
    return True
