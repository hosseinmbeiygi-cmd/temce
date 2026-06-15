from __future__ import annotations

from typing import Any

SAMPLE_TSE_INSTRUMENT: dict[str, Any] = {
    "insCode": "12345678901234567",
    "symbol": "فولاد",
    "name": "فولاد مبارکه اصفهان",
    "market": "بورس",
    "group": "فلزات",
    "eps": 2500,
    "shares": 5000000000,
}

SAMPLE_TSE_SHAREHOLDERS: list[dict[str, Any]] = [
    {"shareholder": "شرکت سرمایه‌گذاری ملی", "percent": 15.5},
    {"shareholder": "شرکت فولاد مبارکه", "percent": 10.2},
]
