from __future__ import annotations

from typing import Any

async def get_market_metrics(symbol: str) -> dict[str, Any]:
    """Return a lightweight market snapshot for the given symbol.

    This is a wrapper placeholder around the live market pipeline.
    """
    return {
        "symbol": symbol,
        "price": 0.0,
        "changePercent": 0.0,
        "bidAskSummary": {"bid": 0.0, "ask": 0.0},
        "buyerPower": False,
        "spreadHigh": False,
    }
