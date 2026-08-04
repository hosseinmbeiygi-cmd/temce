"""Pre-Test Filter: eliminates ~90% of invalid/non-logical strategy combinations BEFORE backtesting.

This is the key performance optimization - instead of running millions of backtests,
we first remove structurally flawed combinations.
"""
from __future__ import annotations

from typing import Any

from backtesting.composer.strategy_composer import StrategyBlueprint

# ── Compatibility Matrix: which indicators conflict with each other ────────────────

# If entry = X and exit = Y, this set is ALWAYS invalid (contradictory signals)
CONTRADICTORY_PAIRS: set[tuple[str, str, str, str]] = {
    # (entry_ind, entry_cond, exit_ind, exit_cond)
    ("rsi", "oversold", "macd", "bearish_cross"),      # RSI oversold = buy, MACD bearish = sell
    ("rsi", "overbought", "macd", "bullish_cross"),     # RSI overbought = sell, MACD bullish = buy
    ("stochastic", "oversold", "williams_r", "overbought"),
    ("stochastic", "overbought", "williams_r", "oversold"),
    ("ema_crossover", "golden_cross", "ema_crossover", "golden_cross"),  # Same signal entry/exit
    ("ema_crossover", "death_cross", "ema_crossover", "death_cross"),
    ("half_trend", "buy_signal", "parabolic_sar", "sell_signal"),
    ("half_trend", "sell_signal", "parabolic_sar", "buy_signal"),
    ("ichimoku", "bullish_cloud", "ichimoku", "bearish_cloud"),
    ("support_resistance", "break_up", "support_resistance", "break_down"),
    ("obv", "obv_rising", "obv", "obv_falling"),
    ("vwap", "above_vwap", "vwap", "below_vwap"),
    ("squeeze_momentum", "squeeze_release", "squeeze_momentum", "squeeze_release"),
}

# Indicator groups that are redundant when used together as entry+exit
REDUNDANT_GROUPS = {
    ("momentum", "momentum"),  # Two momentum indicators = same signal type
    ("volume", "volume"),      # Two volume indicators = same signal type
}

# Indicators that don't work well as exit (structural limitation)
BAD_EXIT_INDICATORS = {"adx", "relative_strength", "supply_absorption", "buyer_power", "net_real_flow"}

# Indicators that don't work well as standalone entry (need confirmation)
WEAK_ENTRY_INDICATORS = {"clv", "recovery_ratio", "compression_ratio", "supply_dryness"}


class PreTestFilter:
    """Filters StrategyBlueprints before backtesting.

    Goal: eliminate ~90% of invalid/non-logical combinations.
    """

    def __init__(self) -> None:
        self.stats = {
            "total": 0,
            "passed": 0,
            "rejected_same_entry_exit": 0,
            "rejected_contradictory": 0,
            "rejected_redundant_group": 0,
            "rejected_bad_exit": 0,
            "rejected_bad_params": 0,
            "rejected_filter_conflict": 0,
        }

    def should_test(self, blueprint: StrategyBlueprint) -> tuple[bool, str]:
        """Check if a blueprint should be backtested.

        Returns (should_test, reason).
        """
        self.stats["total"] += 1

        # ── Rule 1: Entry and Exit cannot be identical indicator + condition ──
        if (blueprint.entry_indicator == blueprint.exit_indicator and
                blueprint.entry_condition == blueprint.exit_condition):
            self.stats["rejected_same_entry_exit"] += 1
            return False, "same_entry_exit"

        # ── Rule 2: Contradictory signal pairs ──
        pair = (
            blueprint.entry_indicator, blueprint.entry_condition,
            blueprint.exit_indicator, blueprint.exit_condition,
        )
        if pair in CONTRADICTORY_PAIRS:
            self.stats["rejected_contradictory"] += 1
            return False, "contradictory_signals"

        # ── Rule 3: Redundant indicator groups ──
        entry_spec = _get_spec(blueprint.entry_indicator)
        exit_spec = _get_spec(blueprint.exit_indicator)
        if entry_spec and exit_spec:
            group_pair = tuple(sorted([entry_spec.group, exit_spec.group]))
            if group_pair in REDUNDANT_GROUPS:
                # Allow if they have different condition types
                if not _conditions_complementary(blueprint.entry_condition, blueprint.exit_condition):
                    self.stats["rejected_redundant_group"] += 1
                    return False, "redundant_group"

        # ── Rule 4: Bad exit indicators ──
        if blueprint.exit_indicator in BAD_EXIT_INDICATORS:
            self.stats["rejected_bad_exit"] += 1
            return False, "bad_exit_indicator"

        # ── Rule 5: Invalid parameter combinations ──
        if not _valid_params(blueprint):
            self.stats["rejected_bad_params"] += 1
            return False, "invalid_params"

        # ── Rule 6: Filter conflicts ──
        if blueprint.filter1_indicator:
            if blueprint.filter1_indicator == blueprint.entry_indicator:
                self.stats["rejected_filter_conflict"] += 1
                return False, "filter_same_as_entry"
            if blueprint.filter1_indicator == blueprint.exit_indicator:
                self.stats["rejected_filter_conflict"] += 1
                return False, "filter_same_as_exit"

        # ── Rule 7: Risk management logic ──
        if blueprint.stop_loss_pct is not None and blueprint.take_profit_pct is not None:
            if blueprint.stop_loss_pct >= blueprint.take_profit_pct:
                self.stats["rejected_bad_params"] += 1
                return False, "sl_ge_tp"

        self.stats["passed"] += 1
        return True, ""

    def filter_batch(self, blueprints: list[StrategyBlueprint]) -> list[StrategyBlueprint]:
        """Filter a batch of blueprints, returning only valid ones."""
        return [bp for bp in blueprints if self.should_test(bp)[0]]

    def get_stats(self) -> dict[str, Any]:
        """Return filter statistics."""
        total = self.stats["total"]
        passed = self.stats["passed"]
        return {
            **self.stats,
            "rejection_rate": round((1 - passed / total) * 100, 1) if total > 0 else 0,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        }

    def reset_stats(self) -> None:
        for k in self.stats:
            self.stats[k] = 0


# ── Helper functions ──────────────────────────────────────────────────────────────

def _get_spec(indicator_id: str):
    from backtesting.composer.indicator_registry import get_indicator
    return get_indicator(indicator_id)


def _conditions_complementary(cond1: str, cond2: str) -> bool:
    """Check if two conditions are complementary (not redundant)."""
    complementary_pairs = {
        ("oversold", "overbought"),
        ("bullish_cross", "bearish_cross"),
        ("golden_cross", "death_cross"),
        ("buy_signal", "sell_signal"),
        ("above_vwap", "below_vwap"),
        ("obv_rising", "obv_falling"),
        ("above_upper", "below_lower"),
        ("inflow", "outflow"),
        ("strong_buyers", "strong_sellers"),
        ("break_up", "break_down"),
    }
    return (cond1, cond2) in complementary_pairs or (cond2, cond1) in complementary_pairs


def _valid_params(bp: StrategyBlueprint) -> bool:
    """Check if parameter combinations are logically valid."""
    # EMA: fast must be < slow
    if bp.entry_indicator == "ema_crossover":
        fast = bp.entry_params.get("fast", 10)
        slow = bp.entry_params.get("slow", 30)
        if fast >= slow:
            return False
    if bp.exit_indicator == "ema_crossover":
        fast = bp.exit_params.get("fast", 10)
        slow = bp.exit_params.get("slow", 30)
        if fast >= slow:
            return False

    # RSI: oversold < overbought (for entry conditions)
    # Stochastic: k_period should be reasonable
    if bp.entry_indicator == "stochastic":
        k = bp.entry_params.get("k_period", 14)
        if k < 5 or k > 50:
            return False

    # ADX: period should be reasonable
    if bp.entry_indicator == "adx":
        p = bp.entry_params.get("period", 14)
        if p < 7 or p > 50:
            return False

    return True
