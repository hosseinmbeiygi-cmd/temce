"""لایه ۱: سنجه‌های پایه (۸ شاخص).

- return_1m, return_3m, return_6m, return_1y, return_3y, return_inception
- p_nav_ratio
- aum_btoman
- daily_volume
- bid_ask_spread
"""

from __future__ import annotations

from decimal import Decimal


def compute_layer1(
    *,
    nav_history: list[float] | None,
    nav_redeem: Decimal | float | None,
    market_price: Decimal | float | None,
    aum_btoman: Decimal | float | None,
    daily_volume: Decimal | float | None,
    bid: Decimal | float | None,
    ask: Decimal | float | None,
) -> dict[str, Decimal | float | int | None]:
    """محاسبه لایه ۱.

    همه مقادیر ممکن است None باشند (cold start).
    """
    out: dict[str, Decimal | float | int | None] = {
        "return_1m": None,
        "return_3m": None,
        "return_6m": None,
        "return_1y": None,
        "return_3y": None,
        "return_inception": None,
        "p_nav_ratio": None,
        "aum_btoman": aum_btoman,
        "daily_volume": daily_volume,
        "bid_ask_spread": None,
    }

    if nav_history and len(nav_history) >= 2:
        last = nav_history[-1]
        first = nav_history[0]
        if first > 0:
            out["return_inception"] = (last - first) / first

        def pct_ago(n: int) -> float | None:
            if len(nav_history) <= n:
                return None
            base = nav_history[-n - 1]
            if base <= 0:
                return None
            return (nav_history[-1] - base) / base

        out["return_1m"] = pct_ago(21)
        out["return_3m"] = pct_ago(63)
        out["return_6m"] = pct_ago(126)
        out["return_1y"] = pct_ago(252)
        out["return_3y"] = pct_ago(756)

    if market_price is not None and nav_redeem is not None and nav_redeem > 0:
        out["p_nav_ratio"] = (float(market_price) - float(nav_redeem)) / float(nav_redeem) * 100

    if bid is not None and ask is not None and bid > 0:
        out["bid_ask_spread"] = (float(ask) - float(bid)) / float(bid) * 100

    return out
