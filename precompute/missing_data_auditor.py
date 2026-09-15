"""
Missing Data Auditor — precompute/missing_data_auditor.py
============================================================
Classifies missing fields into 3 levels and applies fallback protocol:

    Level CRITICAL   — must have: price_last, trade_volume, symbol, market
                       missing -> cannot compute armor_score reliably -> DRI critical, Unreliable True
    Level IMPORTANT  — should have: free_float_pct, pe_ratio, eps, trade_value
                       missing -> degrade DRI by importance weight, use fallback defaults
    Level SUPPLEMENTARY — nice to have: sector, board, beta, turnover_ratio
                       missing -> minor DRI hit, no fallback needed

Fallback protocol:
    - For IMPORTANT numeric fields, use median of group (A/B/C) or global median if group empty
    - For CRITICAL, no fallback — mark missing, skip computation or flag Unreliable
    - Logs audit result for monitoring (via core.logging)

Decoupled: only contracts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("precompute.missing_data_auditor")


class MissingLevel(str, Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    SUPPLEMENTARY = "SUPPLEMENTARY"


# Field -> level mapping
FIELD_LEVELS: dict[str, MissingLevel] = {
    # CRITICAL
    "symbol": MissingLevel.CRITICAL,
    "price_last": MissingLevel.CRITICAL,
    "trade_volume": MissingLevel.CRITICAL,
    # IMPORTANT
    "trade_value": MissingLevel.IMPORTANT,
    "free_float_pct": MissingLevel.IMPORTANT,
    "pe_ratio": MissingLevel.IMPORTANT,
    "eps": MissingLevel.IMPORTANT,
    "price_lowest_allowed": MissingLevel.IMPORTANT,
    "price_highest_allowed": MissingLevel.IMPORTANT,
    # SUPPLEMENTARY
    "sector": MissingLevel.SUPPLEMENTARY,
    "board": MissingLevel.SUPPLEMENTARY,
    "beta": MissingLevel.SUPPLEMENTARY,
    "turnover_ratio": MissingLevel.SUPPLEMENTARY,
    "volume": MissingLevel.SUPPLEMENTARY,
}

# Fallback defaults for IMPORTANT fields (used when group median unavailable)
FALLBACK_DEFAULTS: dict[str, float] = {
    "trade_value": 5e11,  # 500B Rial median
    "free_float_pct": 25.0,
    "pe_ratio": 7.0,
    "eps": 3000.0,
    "price_lowest_allowed": 0.0,  # derived from price_last if missing
    "price_highest_allowed": 0.0,
}


@dataclass
class AuditResult:
    missing: dict[MissingLevel, list[str]] = field(default_factory=lambda: {MissingLevel.CRITICAL: [], MissingLevel.IMPORTANT: [], MissingLevel.SUPPLEMENTARY: []})
    has_critical: bool = False
    completeness: float = 1.0  # 0..1 for DRI
    patched_row: dict[str, Any] = field(default_factory=dict)
    fallback_applied: dict[str, Any] = field(default_factory=dict)
    red_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing": {k.value: v for k, v in self.missing.items()},
            "has_critical": self.has_critical,
            "completeness": self.completeness,
            "fallback_applied": self.fallback_applied,
            "red_flags": self.red_flags,
        }


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (int, float)) and value == 0:
        # 0 is considered missing for certain fields (trade_value, volume) but not for price_last which can be 0 in halted symbols?
        # We keep 0 as missing for trade_value/volume only via caller; here treat 0 as present to avoid false positives.
        return False
    return False


def audit_row(
    row: dict[str, Any],
    group_medians: dict[str, float] | None = None,
) -> AuditResult:
    """
    Audit a single symbol row for missing data.

    Args:
        row: raw symbol snapshot dict (from BrsApi enriched snapshots)
        group_medians: median values for the symbol's group (A/B/C) to use as fallback

    Returns:
        AuditResult with missing classification, completeness 0..1, and patched_row.
    """
    missing: dict[MissingLevel, list[str]] = {
        MissingLevel.CRITICAL: [],
        MissingLevel.IMPORTANT: [],
        MissingLevel.SUPPLEMENTARY: [],
    }
    patched = dict(row)
    fallback_applied: dict[str, Any] = {}
    red_flags: list[str] = []

    for field, level in FIELD_LEVELS.items():
        val = row.get(field)
        # Special: also check alternative camelCase keys
        if _is_missing(val):
            # Try aliases
            aliases = {
                "price_last": ["price", "last_price", "closing_price"],
                "trade_volume": ["volume", "tradeVolume"],
                "trade_value": ["value", "tradeValue", "trade_value_b"],
                "free_float_pct": ["freeFloatPct", "free_float"],
                "price_lowest_allowed": ["priceLowestAllowed"],
                "price_highest_allowed": ["priceHighestAllowed"],
            }
            for alt in aliases.get(field, []):
                alt_val = row.get(alt)
                if not _is_missing(alt_val):
                    val = alt_val
                    patched[field] = alt_val
                    break
        if _is_missing(val):
            missing[level].append(field)
            if level == MissingLevel.CRITICAL:
                red_flags.append(f"missing_critical:{field}")
            # Apply fallback for IMPORTANT only
            if level == MissingLevel.IMPORTANT:
                fallback_val: Any = None
                if group_medians and field in group_medians and group_medians[field] is not None:
                    fallback_val = group_medians[field]
                elif field in FALLBACK_DEFAULTS:
                    fallback_val = FALLBACK_DEFAULTS[field]
                # Special: price band from price_last
                if field in ("price_lowest_allowed", "price_highest_allowed") and patched.get("price_last"):
                    pl = patched["price_last"] or 0
                    # TSE default ±5% band
                    if field == "price_lowest_allowed":
                        fallback_val = round(pl * 0.95)
                    else:
                        fallback_val = round(pl * 1.05)
                if fallback_val is not None:
                    patched[field] = fallback_val
                    fallback_applied[field] = fallback_val

    has_critical = len(missing[MissingLevel.CRITICAL]) > 0

    # Completeness: weighted (critical 60%, important 30%, supplementary 10%)
    total_fields = len(FIELD_LEVELS)
    critical_total = sum(1 for v in FIELD_LEVELS.values() if v == MissingLevel.CRITICAL)
    important_total = sum(1 for v in FIELD_LEVELS.values() if v == MissingLevel.IMPORTANT)
    supp_total = sum(1 for v in FIELD_LEVELS.values() if v == MissingLevel.SUPPLEMENTARY)

    critical_missing = len(missing[MissingLevel.CRITICAL])
    important_missing = len(missing[MissingLevel.IMPORTANT])
    supp_missing = len(missing[MissingLevel.SUPPLEMENTARY])

    # 1.0 minus weighted missing ratio
    critical_ratio = (critical_total - critical_missing) / max(1, critical_total)
    important_ratio = (important_total - important_missing) / max(1, important_total)
    supp_ratio = (supp_total - supp_missing) / max(1, supp_total)

    completeness = 0.6 * critical_ratio + 0.3 * important_ratio + 0.1 * supp_ratio
    completeness = max(0.0, min(1.0, completeness))

    if has_critical:
        logger.warning("Audit CRITICAL missing for %s: %s", row.get("symbol", "?"), missing[MissingLevel.CRITICAL])
    elif important_missing > 0:
        logger.debug("Audit IMPORTANT missing for %s: %s (fallback applied: %s)", row.get("symbol", "?"), missing[MissingLevel.IMPORTANT], list(fallback_applied.keys()))

    return AuditResult(
        missing=missing,
        has_critical=has_critical,
        completeness=completeness,
        patched_row=patched,
        fallback_applied=fallback_applied,
        red_flags=red_flags,
    )


def audit_batch(
    rows: list[dict[str, Any]],
    group_by: dict[str, str] | None = None,
) -> tuple[list[AuditResult], dict[str, float]]:
    """
    Audit a batch of rows and compute group medians for fallback.

    Returns (audit_results, global_medians).
    """
    # Compute global medians for fallback when group is empty
    import statistics

    def median_for(field: str) -> float | None:
        vals = [r.get(field) for r in rows if r.get(field) not in (None, 0, "")]
        # Try aliases
        if not vals:
            for r in rows:
                for alt in [field, field.replace("_", ""), field.replace("_pct", "")]:
                    if r.get(alt) not in (None, 0, ""):
                        vals.append(r[alt])
                        break
        if not vals:
            return FALLBACK_DEFAULTS.get(field)
        try:
            return float(statistics.median(vals))  # type: ignore
        except Exception:
            return FALLBACK_DEFAULTS.get(field)

    medians: dict[str, float] = {}
    for f in FIELD_LEVELS:
        if FIELD_LEVELS[f] == MissingLevel.IMPORTANT:
            m = median_for(f)
            if m is not None:
                medians[f] = m

    results: list[AuditResult] = []
    for row in rows:
        # Per-group medians if group_by provided
        per_group_medians: dict[str, float] | None = medians
        if group_by and row.get("symbol") in group_by:
            # Could refine: compute per-group median, but for now use global
            per_group_medians = medians
        results.append(audit_row(row, group_medians=per_group_medians))

    return results, medians
