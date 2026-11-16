"""Experimental market-regime classifier (pure — no I/O).

EXPERIMENTAL: the thresholds below are reasoned starting points, not fitted or validated
out of sample. The output is a label with its inputs and reasons — not a probability and
not a score to be read as one. It only sets the *ceiling* on portfolio allocation; it can
never by itself justify an entry.

The label is not taken from the sign of an index. It uses market breadth, the median
move, the share of instruments pinned near their lows/highs, and data quality.
"""

from __future__ import annotations

from typing import Any

MIN_UNIVERSE = 300          # fewer instruments than this ⇒ breadth is not representative
FAVORABLE_BREADTH = 0.60
UNFAVORABLE_BREADTH = 0.35
FAVORABLE_MEDIAN = 0.5      # percent
UNFAVORABLE_MEDIAN = -1.0   # percent
HEAVY_SELLING_SHARE = 0.25  # share of instruments down ≥ 4% on the day
HYSTERESIS = 0.05           # extra breadth needed to *improve* the label


def breadth_from_changes(changes_pct: list[float]) -> dict[str, Any]:
    n = len(changes_pct)
    if n == 0:
        return {"total": 0}
    ordered = sorted(changes_pct)
    return {
        "total": n,
        "advancers_share": sum(c > 0 for c in ordered) / n,
        "decliners_share": sum(c < 0 for c in ordered) / n,
        "median_change_pct": ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2,
        "down_4pct_share": sum(c <= -4 for c in ordered) / n,
        "up_4pct_share": sum(c >= 4 for c in ordered) / n,
    }


def classify(breadth: dict[str, Any] | None, *, data_state: str, previous: str | None = None,
             equal_weight_change_pct: float | None = None) -> dict[str, Any]:
    """``data_state``: "valid" | "last_session" | "stale" | "missing"."""
    base = {"experimental": True, "calibrated": False, "inputs": breadth or {},
            "equal_weight_index_change_pct": equal_weight_change_pct, "data_state": data_state,
            "note": "experimental, unvalidated classifier — sets the allocation ceiling only"}
    if data_state in ("stale", "missing") or not breadth or breadth.get("total", 0) < MIN_UNIVERSE:
        return {**base, "regime": "disrupted",
                "reasons": ["market-wide data is missing, stale or too thin to classify"]}

    adv, med, heavy = breadth["advancers_share"], breadth["median_change_pct"], breadth["down_4pct_share"]
    reasons: list[str] = []
    if adv <= UNFAVORABLE_BREADTH or med <= UNFAVORABLE_MEDIAN or heavy >= HEAVY_SELLING_SHARE:
        regime = "unfavorable"  # deterioration is never delayed by hysteresis
        if adv <= UNFAVORABLE_BREADTH:
            reasons.append(f"only {adv:.0%} of instruments advancing")
        if med <= UNFAVORABLE_MEDIAN:
            reasons.append(f"median move {med:.2f}%")
        if heavy >= HEAVY_SELLING_SHARE:
            reasons.append(f"{heavy:.0%} of instruments down 4% or more")
    else:
        need = FAVORABLE_BREADTH + (HYSTERESIS if previous in ("neutral", "unfavorable", "disrupted") else 0.0)
        if adv >= need and med >= FAVORABLE_MEDIAN:
            regime = "favorable"
            reasons.append(f"{adv:.0%} advancing, median move +{med:.2f}%")
        else:
            regime = "neutral"
            reasons.append(f"{adv:.0%} advancing, median move {med:.2f}% — no clear breadth edge")
            if previous == "unfavorable" and adv < UNFAVORABLE_BREADTH + HYSTERESIS:
                regime = "unfavorable"
                reasons.append("improvement too small to leave the unfavorable label")
    if equal_weight_change_pct is not None and regime == "favorable" and equal_weight_change_pct < 0:
        regime = "neutral"
        reasons.append("equal-weight index is down — breadth signal not corroborated")
    return {**base, "regime": regime, "reasons": reasons, "changed_from": previous if previous != regime else None}
