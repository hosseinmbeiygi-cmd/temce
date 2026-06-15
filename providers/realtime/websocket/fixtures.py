from __future__ import annotations

from typing import Any

SAMPLE_WS_QUOTE_MESSAGE: dict[str, Any] = {
    "type": "quote",
    "symbol": "فولاد",
    "data": {
        "last_price": 15100,
        "change": 200,
        "volume": 5000000,
    },
    "timestamp": "2024-01-15T10:30:00+03:30",
}

SAMPLE_WS_TRADE_MESSAGE: dict[str, Any] = {
    "type": "trade",
    "symbol": "فولاد",
    "data": {
        "price": 15100,
        "volume": 500,
        "time": "10:30:15",
    },
}
