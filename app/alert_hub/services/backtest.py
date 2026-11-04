from __future__ import annotations

from typing import Any


async def get_backtest_summary(symbol: str) -> dict[str, Any]:
    """Return a summary of best backtest results for the symbol.

    Placeholder until the backtest engine/results store is wired in.
    """
    return {
        "symbol": symbol,
        "bestStrategy": "placeholder-strategy",
        "winRate": 55.0,
        "profitFactor": 1.2,
        "maxDrawdown": -8.0,
        "lookback": "1y",
        "notes": "placeholder",
    }
