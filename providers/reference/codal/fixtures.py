from __future__ import annotations

from typing import Any

SAMPLE_CODAL_REPORT: dict[str, Any] = {
    "id": "12345",
    "symbol": "فولاد",
    "company": "فولاد مبارکه اصفهان",
    "report_type": "تفسیری",
    "period": "12 ماهه",
    "year": "1402",
    "publish_date": "1402/10/15",
    "title": "تفسیری عملکرد 12 ماهه",
}

SAMPLE_CODAL_ATTACHMENT: dict[str, Any] = {
    "id": "67890",
    "report_id": "12345",
    "file_name": "financial_statement.pdf",
    "file_size": 250000,
    "url": "https://codal.ir/attachment/67890",
}
