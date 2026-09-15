"""Kill-switch rules. Spec: 5 exact thresholds, all evaluated independently."""

from __future__ import annotations

from .entities import KillSwitch, MarketSummary

VOLATILITY_LIMIT = 5.0  # abs(daily_usd_change_pct) > 5.0
BUBBLE_LIMIT = 150.0  # dollar_bubble_index > 150
SPREAD_LIMIT = 3.0  # bid_ask_spread_pct > 3.0
TETHER_ARB_LIMIT = 5.0  # abs(tether_arbitrage_pct) > 5.0
HOURLY_LIMIT = 2.0  # abs(hourly_change_pct) > 2.0


def check_kill_switch(
    market: MarketSummary,
    hourly_change_pct: float = 0.0,
) -> KillSwitch:
    """Evaluate all 5 rules. Returns KillSwitch with reasons list.

    Args:
        market: snapshot-derived market summary.
        hourly_change_pct: hour-over-hour move; default 0 means rule never fires.
    """
    reasons: list[str] = []

    if abs(market.daily_volatility) > VOLATILITY_LIMIT:
        reasons.append(f"Daily volatility extreme: {market.daily_volatility:+.1f}%")

    if market.bubble_index > BUBBLE_LIMIT:
        reasons.append(f"Dollar bubble exceeds 150%: {market.bubble_index:.1f}%")

    if market.bid_ask_spread > SPREAD_LIMIT:
        reasons.append(f"Liquidity crisis: spread {market.bid_ask_spread:.1f}%")

    if abs(market.tether_arbitrage) > TETHER_ARB_LIMIT:
        reasons.append(f"Extreme USDT deviation: {market.tether_arbitrage:+.1f}%")

    if abs(hourly_change_pct) > HOURLY_LIMIT:
        reasons.append(f"Hourly shock: {hourly_change_pct:+.1f}%")

    return KillSwitch(
        active=bool(reasons),
        reasons=reasons,
        action="AVOID_NEW_POSITIONS" if reasons else None,
    )
