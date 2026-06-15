from __future__ import annotations

from typing import Any

SAMPLE_PORTFOLIO: dict[str, Any] = {
    "total_value": 1000000000,
    "cash": 200000000,
    "securities": [
        {"symbol": "فولاد", "quantity": 1000, "avg_price": 15000, "last_price": 16000},
        {"symbol": "خودرو", "quantity": 2000, "avg_price": 5000, "last_price": 5200},
    ],
}

SAMPLE_ORDERS: list[dict[str, Any]] = [
    {"id": 1, "symbol": "فولاد", "side": "buy", "quantity": 500, "price": 15500, "status": "filled"},
    {"id": 2, "symbol": "خودرو", "side": "sell", "quantity": 1000, "price": 5300, "status": "pending"},
]
