"""
DRI Engine — precompute/dri_engine.py
======================================
Data Reliability Index (0..100) + Unreliable flag.

Inputs are the missing-data audit result + data quality signals:
    - completeness (how many critical fields are present)
    - freshness (age of snapshot)
    - consistency (price within allowed band, volume vs value coherence)
    - coverage (number of independent sources agreeing)

Formula:
    DRI = 0.40*completeness + 0.25*freshness + 0.20*consistency + 0.15*coverage
    Unreliable = DRI < 40  OR  critical field missing  OR  freshness > 30 min during market

Decoupled: only contracts/schemas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class DRISignals:
    # Completeness 0..1 (from auditor)
    completeness: float = 0.0  # 1.0 = all critical + important present
    # Freshness 0..1 (1.0 = just now)
    age_seconds: float | None = None
    is_market_open: bool = False
    # Consistency 0..1
    price_in_band: bool | None = None
    volume_value_coherent: bool | None = None
    # Coverage 0..1 (how many sources)
    source_count: int = 0
    max_sources: int = 3

    # Critical missing flag from auditor (overrides)
    has_critical_missing: bool = False


@dataclass
class DRIResult:
    dri: float  # 0..100
    is_unreliable: bool
    red_flags: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)


def _freshness_score(age_seconds: float | None, is_market_open: bool) -> float:
    if age_seconds is None:
        return 0.0
    if age_seconds < 0:
        age_seconds = 0
    # During market: 0s -> 1.0, 60s -> 0.9, 300s -> 0.5, 1800s -> 0.1
    # Outside market: more lenient
    if is_market_open:
        if age_seconds <= 60:
            return 1.0 - (age_seconds / 600)  # 60s -> 0.9
        elif age_seconds <= 300:
            return 0.9 - ((age_seconds - 60) / 240) * 0.4  # 300s -> 0.5
        elif age_seconds <= 1800:
            return 0.5 - ((age_seconds - 300) / 1500) * 0.4  # 1800s -> 0.1
        else:
            return max(0.0, 0.1 - (age_seconds - 1800) / 3600 * 0.1)
    else:
        # Outside market: snapshot from today is fine
        if age_seconds <= 3600:
            return 1.0
        elif age_seconds <= 86400:
            return 0.8
        else:
            return max(0.0, 0.8 - (age_seconds - 86400) / 86400 * 0.5)


def _consistency_score(price_in_band: bool | None, volume_value_coherent: bool | None) -> float:
    if price_in_band is None and volume_value_coherent is None:
        return 0.5  # unknown -> neutral
    scores: list[float] = []
    if price_in_band is not None:
        scores.append(1.0 if price_in_band else 0.0)
    if volume_value_coherent is not None:
        scores.append(1.0 if volume_value_coherent else 0.2)
    return sum(scores) / len(scores) if scores else 0.5


def _coverage_score(source_count: int, max_sources: int = 3) -> float:
    if max_sources <= 0:
        return 0.0
    return max(0.0, min(1.0, source_count / max_sources))


def compute_dri(signals: DRISignals) -> DRIResult:
    """
    Compute DRI 0..100 and unreliable flag.

    Red flags are human-readable codes for api/frontend display.
    """
    freshness = _freshness_score(signals.age_seconds, signals.is_market_open)
    consistency = _consistency_score(signals.price_in_band, signals.volume_value_coherent)
    coverage = _coverage_score(signals.source_count, signals.max_sources)
    completeness = max(0.0, min(1.0, signals.completeness))

    dri_01 = 0.40 * completeness + 0.25 * freshness + 0.20 * consistency + 0.15 * coverage
    dri = round(dri_01 * 100, 1)
    dri = max(0.0, min(100.0, dri))

    red_flags: list[str] = []
    if signals.has_critical_missing:
        red_flags.append("critical_missing")
    if signals.age_seconds is not None and signals.age_seconds > 1800 and signals.is_market_open:
        red_flags.append("stale_during_market")
    if signals.price_in_band is False:
        red_flags.append("price_out_of_band")
    if signals.volume_value_coherent is False:
        red_flags.append("volume_value_incoherent")
    if completeness < 0.5:
        red_flags.append("low_completeness")
    if coverage < 0.33:
        red_flags.append("single_source")

    is_unreliable = False
    if dri < 40:
        is_unreliable = True
        if "low_dri" not in red_flags:
            red_flags.append("low_dri")
    if signals.has_critical_missing:
        is_unreliable = True
    # Freshness override: stale during market makes it unreliable regardless of dri
    if signals.is_market_open and signals.age_seconds is not None and signals.age_seconds > 1800:
        is_unreliable = True

    breakdown = {
        "completeness": round(completeness * 100, 1),
        "freshness": round(freshness * 100, 1),
        "consistency": round(consistency * 100, 1),
        "coverage": round(coverage * 100, 1),
    }

    return DRIResult(dri=dri, is_unreliable=is_unreliable, red_flags=red_flags, breakdown=breakdown)


# Convenience: age from ISO timestamp
def age_from_iso(iso_str: str | None) -> float | None:
    if not iso_str:
        return None
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return (datetime.now(UTC) - dt).total_seconds()
    except Exception:
        return None
