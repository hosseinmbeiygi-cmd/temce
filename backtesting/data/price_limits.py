"""Iran price-limit regime tagging (roadmap v2:72 + v2:32).

Different periods had different daily limits (e.g. 5% -> 2% -> 7%).
Historical bars must be tagged with the rule active at that date,
otherwise backtest is biased.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LimitRule:
    from_date: str  # YYYY-MM-DD inclusive
    to_date: str | None  # None = open ended
    limit_pct: float  # e.g. 0.05 for ±5%
    name: str


# Default Iranian market history (approximate - operator must verify & extend)
IRAN_LIMIT_HISTORY: list[LimitRule] = [
    LimitRule("2000-01-01", "2020-02-08", 0.05, "legacy_5pct"),
    LimitRule("2020-02-09", "2021-01-15", 0.05, "5pct_base_2pct_if_queue"),  # special queue rule
    LimitRule("2021-01-16", "2023-12-31", 0.07, "7pct"),
    LimitRule("2024-01-01", None, 0.03, "3pct_current"),  # example, update with real rule
]


def limit_for_date(gregorian_date: str, history: list[LimitRule] | None = None) -> LimitRule | None:
    """Return the active limit rule for a given date string YYYY-MM-DD."""
    history = history or IRAN_LIMIT_HISTORY
    for rule in history:
        if gregorian_date >= rule.from_date and (rule.to_date is None or gregorian_date <= rule.to_date):
            return rule
    return history[-1] if history else None


def tag_bars(bars: list[dict], history: list[LimitRule] | None = None) -> list[dict]:
    """Add 'price_limit_pct' and 'limit_rule' to each bar based on its date."""
    for bar in bars:
        date = str(bar.get("gregorian_date") or bar.get("date") or bar.get("timestamp") or "")[:10]
        rule = limit_for_date(date, history) if date else None
        bar["price_limit_pct"] = rule.limit_pct if rule else 0.05
        bar["limit_rule"] = rule.name if rule else "unknown"
    return bars
