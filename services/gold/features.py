"""Gold signal features — pure, point-in-time (no I/O).

STEP 7B contract
----------------

Every value at ``t`` is computed **only** from observations dated ``<= t``:

* ``gold_bubble_zscore``    — z-score of the latest coin bubble % vs its history
* ``gold_ime_spread_pct``   — IME certificate vs melted-18k net spread %
* ``gold_fund_pnav_pct``    — gold-fund premium/discount to NAV %
* ``gold_cot_percentile``   — managed-money net percentile vs COT history
* ``gold_real_yield``       — latest FRED 10Y TIPS real yield (DFII10)
* ``gold_aed_spread_pct``   — Tehran USD vs AED-hawala-implied USD, %
* ``gold_event_window``    — 1 when ``t`` follows a CPI/NFP/FOMC print within
  the configured window, else 0
* ``gold_event_in_next_N_days`` — 1 when a high-volatility event is *scheduled*
  inside the next ``N`` days (N from config), else 0

A source with no usable rows yields ``None`` **and** a name in ``missing`` —
never a fabricated number.  ``normalize_gold_features`` turns ``None`` into
NaN for the model vector (explicitly flagged in metadata), not into 0.

The event window deliberately uses only events dated ``<= t`` (the post-print
regime).  A forward-scheduled event would let a later calendar edit change the
value at ``t``, which the leakage contract forbids — so the forward-looking
``gold_event_in_next_N_days`` accepts an event only when it carries
provenance proving the schedule was already known at ``t`` (``known_at <= t``).
A row that was first seen, or rescheduled, after ``t`` is dropped for ``t``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from services.gold.physical_market import rolling_zscore_percentile

GOLD_FEATURE_NAMES: tuple[str, ...] = (
    "gold_bubble_zscore",
    "gold_ime_spread_pct",
    "gold_fund_pnav_pct",
    "gold_cot_percentile",
    "gold_real_yield",
    "gold_aed_spread_pct",
    "gold_event_window",
    "gold_event_in_next_N_days",
)

#: ``name -> (scale, clamp)``; the vector value is ``clip(raw / scale, ±clamp)``.
#: A NaN stays NaN (missing), never 0.
GOLD_FEATURE_TRANSFORMS: dict[str, tuple[float, float]] = {
    "gold_bubble_zscore": (3.0, 1.0),
    "gold_ime_spread_pct": (5.0, 1.0),
    "gold_fund_pnav_pct": (10.0, 1.0),
    "gold_cot_percentile": (100.0, 1.0),
    "gold_real_yield": (5.0, 1.0),
    "gold_aed_spread_pct": (5.0, 1.0),
    "gold_event_window": (1.0, 1.0),
    "gold_event_in_next_N_days": (1.0, 1.0),
}

DEFAULT_BUBBLE_WINDOW = 120
DEFAULT_MIN_BUBBLE_OBSERVATIONS = 20
DEFAULT_EVENT_WINDOW_DAYS = 1
#: Forward-looking horizon (days) used when the caller does not pass one.
#: The production value comes from ``settings.gold_event_horizon_days``.
DEFAULT_EVENT_HORIZON_DAYS = 7


@dataclass(frozen=True)
class DatedValue:
    """One observation: the value was known at ``as_of``."""

    as_of: datetime
    value: float | None


@dataclass
class GoldFeatureInputs:
    """Point-in-time inputs assembled by a provider (DB or fixture)."""

    coin_bubble_pct: list[DatedValue] = field(default_factory=list)
    ime_spread_pct: list[DatedValue] = field(default_factory=list)
    fund_pnav_pct: list[DatedValue] = field(default_factory=list)
    cot_percentile: list[DatedValue] = field(default_factory=list)
    real_yield: list[DatedValue] = field(default_factory=list)
    aed_spread_pct: list[DatedValue] = field(default_factory=list)
    high_vol_events: list[dict[str, Any]] = field(default_factory=list)
    #: Calendar rows known at ``as_of`` (past **and** scheduled future dates).
    #: Each row carries ``known_at`` — when the schedule became known — so the
    #: forward-looking feature can refuse rows revealed/rescheduled after ``t``.
    scheduled_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class GoldFeatureSet:
    as_of: datetime
    values: dict[str, float | None]
    missing: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "values": dict(self.values),
            "missing": list(self.missing),
        }


def _to_utc(value: datetime) -> datetime:
    """Treat naive datetimes (SQLite) as UTC so comparisons never raise."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _history(
    series: list[DatedValue],
    as_of: datetime,
    *,
    window: int | None = None,
) -> list[DatedValue]:
    """Rows dated at or before ``as_of``, oldest first; non-finite dropped."""
    usable = [
        item
        for item in series
        if item.value is not None
        and math.isfinite(float(item.value))
        and _to_utc(item.as_of) <= as_of
    ]
    usable.sort(key=lambda item: _to_utc(item.as_of))
    if window is not None and len(usable) > window:
        usable = usable[-window:]
    return usable


def _latest(series: list[DatedValue], as_of: datetime) -> float | None:
    usable = _history(series, as_of)
    return float(usable[-1].value) if usable else None


def _parse_known_at(raw: Any) -> datetime | None:
    """Parse the provenance timestamp of a calendar row (``known_at``)."""
    if isinstance(raw, datetime):
        return _to_utc(raw)
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return _to_utc(parsed)
    return None


def _is_high_vol_event(event: dict[str, Any]) -> bool:
    """High-volatility test: explicit flag or a CPI/NFP/FOMC category."""
    from services.gold.macro_sync import HIGH_VOLATILITY_CATEGORIES

    if bool(event.get("is_high_volatility")):
        return True
    return str(event.get("category", "")).upper() in HIGH_VOLATILITY_CATEGORIES


def _parse_event_date(raw: Any) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


def _event_window(
    events: list[dict[str, Any]],
    as_of: datetime,
    *,
    window_days: int,
) -> float | None:
    """Post-print high-volatility flag using events dated ``<= as_of`` only."""
    if not events:
        return None
    past: list[dict[str, Any]] = []
    for event in events:
        event_date = _parse_event_date(event.get("event_date"))
        if event_date is None or event_date > as_of.date():
            continue
        known_at = _parse_known_at(event.get("known_at"))
        if known_at is not None and known_at > as_of:
            # The row was only revealed (or rescheduled) after ``t`` — it may
            # not have existed yet, so it cannot inform the window at ``t``.
            continue
        past.append({**event, "event_date": event_date})

    from services.gold.economic_calendar import is_high_vol_window_from_events

    return 1.0 if is_high_vol_window_from_events(
        as_of.date(), past, window_days=window_days
    ) else 0.0


def _forward_event_window(
    inputs: GoldFeatureInputs,
    as_of: datetime,
    *,
    horizon_days: int,
) -> float | None:
    """1 when a high-volatility event is scheduled inside the next N days.

    Calendar rows carry two provenance stamps:

    * ``first_seen_at`` — when the row entered the calendar (it did not exist
      at ``t`` when this is after ``t``: such a row is ignored entirely),
    * ``known_at`` — when the row's *content* (its date) last changed.  A row
      whose date was refreshed after ``t`` may have carried a different date
      at ``t``; that date is unknowable, so the window state at ``t`` is
      reported as missing rather than guessed.

    A forward claim additionally needs an explicit ``known_at``: without
    provenance the schedule cannot be shown to have been known in advance.
    """
    rows = list(inputs.scheduled_events) + list(inputs.high_vol_events)
    usable: list[dict[str, Any]] = []
    for event in rows:
        first_seen = _parse_known_at(event.get("first_seen_at"))
        known_at = _parse_known_at(event.get("known_at"))
        if first_seen is not None and first_seen > as_of:
            continue  # the row did not exist at t
        if known_at is not None and known_at > as_of:
            # The row existed at t but its date changed afterwards — the
            # schedule as of t is unknown, so no value can be reported.
            return None
        usable.append(event)

    if not usable:
        # The calendar source produced nothing known at t — missing, not 0.
        return None

    target = as_of.date()
    horizon_end = target + timedelta(days=horizon_days)
    for event in usable:
        known_at = _parse_known_at(event.get("known_at"))
        if known_at is None:
            # Cannot prove the schedule was known at t — never use it.
            continue
        event_date = _parse_event_date(event.get("event_date"))
        if event_date is None or not (target < event_date <= horizon_end):
            continue
        if not _is_high_vol_event(event):
            continue
        return 1.0
    return 0.0


def compute_gold_features(
    inputs: GoldFeatureInputs,
    as_of: datetime,
    *,
    bubble_window: int = DEFAULT_BUBBLE_WINDOW,
    min_bubble_observations: int = DEFAULT_MIN_BUBBLE_OBSERVATIONS,
    event_window_days: int = DEFAULT_EVENT_WINDOW_DAYS,
    event_horizon_days: int = DEFAULT_EVENT_HORIZON_DAYS,
) -> GoldFeatureSet:
    """Build the gold feature block at ``as_of`` (leak-free, explicit missing)."""
    if bubble_window < 2:
        raise ValueError(f"bubble_window must be >= 2, got {bubble_window!r}")
    if min_bubble_observations < 2:
        raise ValueError(
            "min_bubble_observations must be >= 2, "
            f"got {min_bubble_observations!r}"
        )
    if event_window_days < 0:
        raise ValueError(
            f"event_window_days must be non-negative, got {event_window_days!r}"
        )
    if event_horizon_days < 0:
        raise ValueError(
            f"event_horizon_days must be non-negative, got {event_horizon_days!r}"
        )
    as_of = _to_utc(as_of)

    values: dict[str, float | None] = {}
    missing: list[str] = []

    bubble_history = _history(inputs.coin_bubble_pct, as_of, window=bubble_window)
    if len(bubble_history) < min_bubble_observations:
        values["gold_bubble_zscore"] = None
    else:
        sample = [float(item.value) for item in bubble_history]
        values["gold_bubble_zscore"] = rolling_zscore_percentile(
            sample, sample[-1]
        )["z_score"]

    values["gold_ime_spread_pct"] = _latest(inputs.ime_spread_pct, as_of)
    values["gold_fund_pnav_pct"] = _latest(inputs.fund_pnav_pct, as_of)
    values["gold_cot_percentile"] = _latest(inputs.cot_percentile, as_of)
    values["gold_real_yield"] = _latest(inputs.real_yield, as_of)
    values["gold_aed_spread_pct"] = _latest(inputs.aed_spread_pct, as_of)
    values["gold_event_window"] = _event_window(
        inputs.high_vol_events, as_of, window_days=event_window_days
    )
    values["gold_event_in_next_N_days"] = _forward_event_window(
        inputs, as_of, horizon_days=event_horizon_days
    )

    for name in GOLD_FEATURE_NAMES:
        if values.get(name) is None:
            missing.append(name)

    return GoldFeatureSet(as_of=as_of, values=values, missing=missing)


def normalize_gold_features(
    values: dict[str, float | None],
) -> dict[str, float]:
    """Scale raw values for the model vector; missing stays NaN, never 0."""
    normalized: dict[str, float] = {}
    for name in GOLD_FEATURE_NAMES:
        scale, clamp = GOLD_FEATURE_TRANSFORMS[name]
        raw = values.get(name)
        if raw is None or not math.isfinite(float(raw)):
            normalized[name] = math.nan
            continue
        scaled = float(raw) / scale
        normalized[name] = max(-clamp, min(clamp, scaled))
    return normalized


__all__ = [
    "DEFAULT_BUBBLE_WINDOW",
    "DEFAULT_EVENT_HORIZON_DAYS",
    "DEFAULT_EVENT_WINDOW_DAYS",
    "DEFAULT_MIN_BUBBLE_OBSERVATIONS",
    "GOLD_FEATURE_NAMES",
    "GOLD_FEATURE_TRANSFORMS",
    "DatedValue",
    "GoldFeatureInputs",
    "GoldFeatureSet",
    "compute_gold_features",
    "normalize_gold_features",
]
