"""Central timeframe enum + evaluation horizons (Layer 0.2).
Single source of truth for model, schema, signal store, UI."""
from __future__ import annotations
from datetime import timedelta
from enum import Enum

class Timeframe(str, Enum):
    M5 = "5m"; M15 = "15m"; H1 = "1h"; H4 = "4h"
    D1 = "1d"; W1 = "1w"
    MO1 = "1mo"; MO3 = "3mo"; MO6 = "6mo"; Y1 = "1y"

SHORT = ["5m","15m","1h","4h","1d","1w"]
MEDIUM = ["1mo","3mo"]
LONG = ["6mo","1y"]
ALL = SHORT + MEDIUM + LONG

def timeframe_group(tf: str) -> str:
    if tf in SHORT: return "short"
    if tf in MEDIUM: return "medium"
    return "long"

# evaluation horizon deltas (calendar fallback; trading-calendar-aware version below)
HORIZONS = {"5m": timedelta(days=1), "15m": timedelta(days=1), "1h": timedelta(days=1),
    "4h": timedelta(days=1), "1d": timedelta(days=1), "1w": timedelta(weeks=1),
    "1mo": timedelta(days=30), "3mo": timedelta(days=90), "6mo": timedelta(days=180),
    "1y": timedelta(days=365)}

def eval_due_at(created, timeframe: str, trading_calendar=None):
    """Compute eval_due_at. Uses trading calendar (trading days) for TSE markets if provided."""
    if trading_calendar is not None and hasattr(trading_calendar, "add_trading_days"):
        n = {"5m":1,"15m":1,"1h":1,"4h":1,"1d":1,"1w":5,"1mo":21,"3mo":63,"6mo":126,"1y":252}.get(timeframe,1)
        try:
            return trading_calendar.add_trading_days(created, n)
        except Exception:
            pass
    return created + HORIZONS[timeframe]
