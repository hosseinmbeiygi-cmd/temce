"""Market-microstructure and price-history maths (pure — no I/O).

Inputs are plain dicts/lists shaped like the ``brsapi_symbol_snapshots`` columns. Every
function returns ``None`` (or an explicit ``"unknown"`` state) when its inputs do not
support an answer; nothing here invents a value. A single order-book snapshot shows the
visible queue at one instant — it says nothing about cancellations or hidden intent.
"""

from __future__ import annotations

import math
from typing import Any

BOOK_DEPTH = 5


def _num(value: Any) -> float | None:
    """A finite float, or None. Zero is a legitimate value and is preserved."""
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def book_levels(snap: dict[str, Any], side: str) -> list[dict[str, float]]:
    """Visible price levels on one side ("bid" / "ask") with positive price and volume."""
    out: list[dict[str, float]] = []
    for i in range(1, BOOK_DEPTH + 1):
        price = _num(snap.get(f"{side}_price_{i}"))
        volume = _num(snap.get(f"{side}_volume_{i}"))
        if price is None or volume is None or price <= 0 or volume <= 0:
            continue
        out.append({"price": price, "volume": volume, "count": _num(snap.get(f"{side}_count_{i}")) or 0.0})
    return out


def validate_quote(snap: dict[str, Any]) -> list[str]:
    """Reasons the quote is unusable. Empty list ⇒ structurally valid."""
    problems: list[str] = []
    last = _num(snap.get("price_last"))
    if last is None:
        problems.append("price_last missing")
    elif last <= 0:
        problems.append("price_last is not positive")
    volume = _num(snap.get("trade_volume"))
    if volume is not None and volume < 0:
        problems.append("trade_volume is negative")
    lo, hi = _num(snap.get("price_min")), _num(snap.get("price_max"))
    if lo is not None and hi is not None and lo > 0 and hi > 0:
        if lo > hi:
            problems.append("price_min above price_max")
        elif last is not None and last > 0 and not lo <= last <= hi:
            problems.append("price_last outside the day's min/max")
    return problems


def spread(snap: dict[str, Any]) -> dict[str, Any]:
    bids, asks = book_levels(snap, "bid"), book_levels(snap, "ask")
    if not bids or not asks:
        return {"state": "one_sided" if (bids or asks) else "empty", "bid": None, "ask": None, "pct": None}
    bid, ask = bids[0]["price"], asks[0]["price"]
    if ask < bid:
        return {"state": "crossed", "bid": bid, "ask": ask, "pct": None}
    mid = (bid + ask) / 2
    return {"state": "two_sided", "bid": bid, "ask": ask, "pct": (ask - bid) / mid * 100}


def queue_state(snap: dict[str, Any], low_limit: float | None, high_limit: float | None) -> dict[str, Any]:
    """Locked-queue detection against the instrument's *actual* daily limits.

    Without verified limits the answer is "unknown" — a percentage band is never assumed.
    """
    if not low_limit or not high_limit or low_limit <= 0 or high_limit <= low_limit:
        return {"state": "unknown", "reason": "daily price limits unavailable for this session"}
    bids, asks = book_levels(snap, "bid"), book_levels(snap, "ask")
    best_bid = bids[0] if bids else None
    best_ask = asks[0] if asks else None
    tick = max(1.0, low_limit * 1e-6)
    if best_ask and best_ask["price"] <= low_limit + tick and (not best_bid or best_bid["price"] < low_limit - tick):
        return {"state": "sell_queue", "volume": best_ask["volume"], "orders": best_ask["count"],
                "limit": low_limit, "reason": "best offer sits at the lower limit with no bid at or above it"}
    if best_bid and best_bid["price"] >= high_limit - tick and (not best_ask or best_ask["price"] > high_limit + tick):
        return {"state": "buy_queue", "volume": best_bid["volume"], "orders": best_bid["count"],
                "limit": high_limit, "reason": "best bid sits at the upper limit with no offer at or below it"}
    return {"state": "none", "low_limit": low_limit, "high_limit": high_limit}


def executable_depth(snap: dict[str, Any], side: str, low_limit: float | None = None,
                     high_limit: float | None = None) -> dict[str, float]:
    """Visible volume/value a new order could trade against on ``side`` of the book.

    Levels outside the day's limits cannot trade today and are excluded when limits are known.
    """
    volume = value = 0.0
    for lvl in book_levels(snap, side):
        if low_limit and lvl["price"] < low_limit:
            continue
        if high_limit and lvl["price"] > high_limit:
            continue
        volume += lvl["volume"]
        value += lvl["volume"] * lvl["price"]
    return {"volume": volume, "value_rial": value}


def book_imbalance(snap: dict[str, Any]) -> float | None:
    bid = sum(lvl["volume"] for lvl in book_levels(snap, "bid"))
    ask = sum(lvl["volume"] for lvl in book_levels(snap, "ask"))
    return None if bid + ask <= 0 else (bid - ask) / (bid + ask)


def session_vwap(snap: dict[str, Any]) -> float | None:
    value, volume = _num(snap.get("trade_value")), _num(snap.get("trade_volume"))
    if value is None or volume is None or volume <= 0 or value <= 0:
        return None
    return value / volume


def relative_volume(snap: dict[str, Any], avg_daily_volume: float | None) -> float | None:
    volume = _num(snap.get("trade_volume"))
    if volume is None or not avg_daily_volume or avg_daily_volume <= 0:
        return None
    return volume / avg_daily_volume


def log_returns(closes: list[float]) -> list[float]:
    return [math.log(b / a) for a, b in zip(closes, closes[1:], strict=False) if a > 0 and b > 0]


def daily_volatility_pct(closes: list[float], window: int = 20) -> float | None:
    """Sample stdev of daily log returns over the last ``window`` sessions, in percent."""
    rets = log_returns(closes[-(window + 1):])
    if len(rets) < max(5, window // 2):
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * 100


def horizon_return_pct(closes: list[float], sessions: int) -> float | None:
    if len(closes) <= sessions or closes[-sessions - 1] <= 0:
        return None
    return (closes[-1] / closes[-sessions - 1] - 1) * 100


def discontinuities(closes: list[float], max_abs_return_pct: float = 25.0) -> list[int]:
    """Indices where one session's move exceeds what daily limits normally allow —
    a likely unadjusted corporate action or a bad row. The series is not silently repaired."""
    out = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and abs(closes[i] / closes[i - 1] - 1) * 100 > max_abs_return_pct:
            out.append(i)
    return out


def premium_discount_pct(price: float | None, nav: float | None) -> float | None:
    if price is None or nav is None or nav <= 0 or price <= 0:
        return None
    return (price / nav - 1) * 100


def market_metrics(snap: dict[str, Any], *, low_limit: float | None, high_limit: float | None,
                   avg_daily_volume: float | None, closes: list[float]) -> dict[str, Any]:
    """Everything derivable from one snapshot + the daily close history."""
    last = _num(snap.get("price_last"))
    vwap = session_vwap(snap)
    breaks = discontinuities(closes)
    usable = closes[breaks[-1]:] if breaks else closes  # only the stretch after the last break
    return {
        "price_last": last,
        "price_close": _num(snap.get("price_close")),
        "price_yesterday": _num(snap.get("price_yesterday")),
        "change_pct": _num(snap.get("price_last_change_pct")),
        "session_vwap": vwap,
        "price_vs_vwap_pct": None if not vwap or not last else (last / vwap - 1) * 100,
        "spread": spread(snap),
        "queue": queue_state(snap, low_limit, high_limit),
        "low_limit": low_limit,
        "high_limit": high_limit,
        "bid_depth": executable_depth(snap, "bid", low_limit, high_limit),
        "ask_depth": executable_depth(snap, "ask", low_limit, high_limit),
        "book_imbalance": book_imbalance(snap),
        "trade_volume": _num(snap.get("trade_volume")),
        "trade_value_rial": _num(snap.get("trade_value")),
        "avg_daily_volume": avg_daily_volume,
        "relative_volume": relative_volume(snap, avg_daily_volume),
        "daily_volatility_pct": daily_volatility_pct(usable),
        "return_5d_pct": horizon_return_pct(usable, 5),
        "return_20d_pct": horizon_return_pct(usable, 20),
        "history_sessions": len(closes),
        "history_discontinuities": len(breaks),
        "limitations": [
            "one order-book snapshot: visible queue at one instant, no cancellation/placement history",
            "session VWAP is trade_value/trade_volume for the whole session, not intraday-anchored",
        ],
    }
