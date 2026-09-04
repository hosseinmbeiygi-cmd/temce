"""Pure pricing formulas. No I/O, no side effects.

Mirrors the example math in the original spec verbatim so the test cases can
check exact numeric outputs.
"""

from __future__ import annotations

# ---- bubble & arbitrage -----------------------------------------------------


def bubble_index(free_market_usd: float, official_cbi_usd: float) -> float:
    """((free - cbi) / cbi) * 100.

    Spec example: free=615000, cbi=315000 -> 95.238095...
    """
    if official_cbi_usd <= 0:
        raise ValueError("official_cbi_usd must be > 0")
    return ((free_market_usd - official_cbi_usd) / official_cbi_usd) * 100.0


def tether_arbitrage_pct(usdt_irt: float, free_market_usd: float) -> float:
    """((usdt - free) / free) * 100.

    Spec example: usdt=620000, free=615000 -> +0.813008...
    """
    if free_market_usd <= 0:
        raise ValueError("free_market_usd must be > 0")
    return ((usdt_irt - free_market_usd) / free_market_usd) * 100.0


def spread_pct(ask_price: float, bid_price: float) -> float:
    """((ask - bid) / ask) * 100."""
    if ask_price <= 0:
        raise ValueError("ask_price must be > 0")
    return ((ask_price - bid_price) / ask_price) * 100.0


# ---- returns ---------------------------------------------------------------


def daily_volatility_pct(current_price: float, yesterday_close: float) -> float:
    """((current - yesterday) / yesterday) * 100.

    Negative when price dropped, positive when up.
    """
    if yesterday_close <= 0:
        raise ValueError("yesterday_close must be > 0")
    return ((current_price - yesterday_close) / yesterday_close) * 100.0


def simple_return_pct(current_usd: float, entry_usd: float) -> float:
    """((current - entry) / entry) * 100.

    Spec example: current=615000, entry=600000 -> +2.5.
    """
    if entry_usd <= 0:
        raise ValueError("entry_usd must be > 0")
    return ((current_usd - entry_usd) / entry_usd) * 100.0


def position_pnl_toman(current_usd: float, entry_usd: float, volume: float) -> float:
    """(current - entry) * volume."""
    return (current_usd - entry_usd) * volume


# ---- aggregates ------------------------------------------------------------


def classify_sentiment(bubble: float, daily_vol: float) -> str:
    """Cheap sentiment tag from bubble + volatility. Pure.

    - BEARISH: bubble > 100 or daily_vol < -3 (market stressed)
    - BULLISH: bubble < 30 and daily_vol > 0 (stable & rising)
    - NEUTRAL: otherwise
    """
    if bubble > 100.0 or daily_vol < -3.0:
        return "BEARISH"
    if bubble < 30.0 and daily_vol > 0.0:
        return "BULLISH"
    return "NEUTRAL"


def arbitrage_status_for(spread_pct_value: float) -> str:
    """OPPORTUNITY if meaningfully below free market, EXPENSIVE if above, else NORMAL."""
    if spread_pct_value <= -0.5:
        return "OPPORTUNITY"
    if spread_pct_value >= 1.5:
        return "EXPENSIVE"
    return "NORMAL"
