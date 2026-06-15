from __future__ import annotations

from typing import Any

SAMPLE_TSETMC_QUOTE: dict[str, Any] = {
    "insCode": "12345678901234567",
    "symbol": "فولاد",
    "name": "فولاد مبارکه اصفهان",
    "open": 15000,
    "high": 15200,
    "low": 14900,
    "close": 15100,
    "last": 15100,
    "volume": 5000000,
    "value": 75000000000,
    "count": 1200,
    "yesterday": 14900,
    "eps": 2500,
    "pe": 6.04,
}

SAMPLE_TSETMC_ORDERBOOK: dict[str, Any] = {
    "buy_rows": [
        {"price": 15100, "volume": 1000, "count": 5},
        {"price": 15050, "volume": 2000, "count": 8},
    ],
    "sell_rows": [
        {"price": 15150, "volume": 1500, "count": 6},
        {"price": 15200, "volume": 800, "count": 3},
    ],
}

SAMPLE_TSETMC_TRADES: list[dict[str, Any]] = [
    {"price": 15100, "volume": 500, "time": "10:30:15"},
    {"price": 15150, "volume": 300, "time": "10:31:20"},
]
