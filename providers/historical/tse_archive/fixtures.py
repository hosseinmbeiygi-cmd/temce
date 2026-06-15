from __future__ import annotations

from typing import Any

SAMPLE_TSE_ARCHIVE_PRICES: list[dict[str, Any]] = [
    {
        "ticker": "12345678901234567",
        "date": "14020101",
        "open": 12000,
        "high": 12300,
        "low": 11900,
        "close": 12200,
        "volume": 3000000,
    },
]

SAMPLE_TSE_CORPORATE_EVENTS: list[dict[str, Any]] = [
    {
        "ticker": "12345678901234567",
        "event": "Capital Increase",
        "date": "14020215",
        "percent": 30,
    },
]
