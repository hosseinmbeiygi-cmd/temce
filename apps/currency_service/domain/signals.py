"""Signal generator. Heuristic, deterministic, pure.

Two rules today (see plan; spec does not require ML):
  1. CASH_USD BUY MEDIUM if bubble < 30 AND daily_vol < 2.0
  2. USDT SELL LOW if tether_arbitrage > +2.0

No signal otherwise.
"""

from __future__ import annotations

from .entities import MarketSummary, Signal


def _entry_range(mid: float, bubble: float, vol: float) -> tuple[int, int]:
    """Tight ±0.4% band around mid, rounded to 1000 toman."""
    lo = int(round(mid * 0.996 / 1000.0)) * 1000
    hi = int(round(mid * 1.004 / 1000.0)) * 1000
    return lo, hi


def generate_signals(market: MarketSummary) -> list[Signal]:
    """Return 0..2 signals. No mutation, no I/O."""
    signals: list[Signal] = []
    mid_free = (market.free_market_usd + market.usdt_irt) / 2.0

    # Rule 1: CASH_USD BUY when market stable & not over-inflated.
    if market.bubble_index < 30.0 and abs(market.daily_volatility) < 2.0:
        lo, hi = _entry_range(mid_free, market.bubble_index, market.daily_volatility)
        target = int(round(hi * 1.017 / 1000.0)) * 1000  # +1.7% target
        stop = int(round(lo * 0.987 / 1000.0)) * 1000  # -1.3% stop
        signals.append(
            Signal(
                asset_type="CASH_USD",
                signal_type="BUY",
                confidence="MEDIUM",
                entry_range=(lo, hi),
                target_price=target,
                stop_loss=stop,
                holding_period="3-7 days",
                reason=(f"Bubble {market.bubble_index:.1f}%, daily vol {market.daily_volatility:+.1f}%, stable"),
                risk_level="MEDIUM",
            )
        )

    # Rule 2: USDT SELL when tether premium stretched above +2%.
    if market.tether_arbitrage > 2.0:
        signals.append(
            Signal(
                asset_type="USDT",
                signal_type="SELL",
                confidence="LOW",
                reason=(f"Tether premium {market.tether_arbitrage:+.1f}% vs free, possible mean reversion"),
                risk_level="MEDIUM",
            )
        )

    return signals
