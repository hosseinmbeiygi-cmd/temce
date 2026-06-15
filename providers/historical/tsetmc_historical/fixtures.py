from __future__ import annotations

from typing import Any

SAMPLE_INSTRUMENT_HISTORY: list[dict[str, Any]] = [
    {
        "insCode": "12345678901234567",
        "date": "20240101",
        "open": 15000,
        "high": 15200,
        "low": 14900,
        "close": 15100,
        "volume": 5000000,
        "value": 75000000000,
        "count": 1200,
    },
]


SAMPLE_CORPORATE_EVENTS: list[dict[str, Any]] = [
    {
        "insCode": "12345678901234567",
        "eventType": "capital_increase",
        "eventDate": "20240115",
        "description": "30% capital increase from cash and receivables",
    },
]
