"""Cumulative price-adjustment factors from corporate actions.

Closes audit gap §2: ``daily_history`` stores raw TSETMC prices, so a
capital increase or DPS silently corrupts every multi-year indicator and
backtest. This service is the **single source of truth** for factor
math — the backfill script and any runtime recomputation both call
``recompute_factors``.

Factor conventions (standard TSE practice):
  capital_increase / bonus → 1 / (1 + ratio)
  dividend                 → (close_at_ex − dps) / close_at_ex

Prices *before* the ex-date are multiplied by the factor; from the
ex-date onward the series stays raw. Factors multiply cumulatively
walking backwards from the newest event.

A recorded event is a *claim*, not a fact: ``corporate_action_events`` is fed
by a scraper and a wrong ratio/DPS used to be applied verbatim, which
manufactured a +40% artificial jump in the adjusted series. ``resolve_event_factor``
checks every claim against the raw price footprint in a ±3-day window
(``load_observed_price_moves``) and returns the factor **plus** a verdict:
``confirmed`` / ``invisible`` (no footprint → factor 1.0) / ``ex_date_snapped``
(footprint one day off → applied where the price moved) / ``price_override``
(footprint disagrees with the claim → the observed multiplier wins) /
``unverified`` (no observation available → the recorded factor stands).

Date axis: factors are keyed on the **true Gregorian trade date**, read from
``vw_daily_history_adjusted`` (migration 0109) so they line up with
``corporate_action_events.ex_date``. ``daily_history.trade_date`` is the
*fetch* date and must not be used here.

Polyglot-PK note (core/dbcompat trap #1): ``symbols.id`` is BIGINT so
parameters are passed to asyncpg as int — never str.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)


def _event_factor(action_type: str, ratio: float, dps: float, close_at_ex: float | None) -> float:
    """One-day factor for a single corporate action."""
    if action_type in ("capital_increase", "bonus"):
        if ratio <= -1:  # nonsensical (e.g. 100% capital reduction)
            raise ValueError(f"invalid ratio {ratio} for {action_type}")
        return 1.0 / (1.0 + ratio)
    if action_type == "dividend":
        if close_at_ex is None or close_at_ex <= 0:
            logger.warning("dividend without close price at ex-date; factor=1 (no adjustment)")
            return 1.0
        if close_at_ex - dps <= 0:
            return 1.0  # DPS >= close: skip rather than flip the series negative
        return (close_at_ex - dps) / close_at_ex
    raise ValueError(f"unknown action_type {action_type!r}")


def compute_cumulative_factors(
    actions: Sequence[dict[str, Any]],
    trade_dates: Iterable[date],
    closes_by_date: dict[date, float] | None = None,
    observed_moves: dict[date, ObservedPriceMove] | None = None,
) -> dict[date, float]:
    """Cumulative factor per trade date, deterministic and pure (unit-testable).

    ``actions``: rows ordered by ex_date ASC; each has action_type, ratio,
    dps, ex_date. ``closes_by_date`` supplies close price at each ex-date
    for dividend events. ``observed_moves`` carries the raw price footprint
    per recorded ex-date (``load_observed_price_moves``) so each claim is
    verified before it can move the series — a claim the price never
    confirmed contributes nothing, and one the price contradicts is replaced
    by the observed multiplier. Trade dates with no factor entry get 1.0.
    """
    closes = closes_by_date or {}
    moves = observed_moves or {}
    one_day: dict[date, float] = {}
    for a in actions:
        ex = a["ex_date"]
        if isinstance(ex, str):
            ex = date.fromisoformat(ex)
        action_type = normalize_action_type(str(a["action_type"]))
        factor, _verdict, apply_on = resolve_event_factor(
            action_type,
            ratio=float(a.get("ratio") or 0),
            dps=float(a.get("dps") or 0),
            close_at_ex=closes.get(ex),
            ex_date=ex,
            observed=moves.get(ex),
        )
        if factor == 1.0:
            continue  # nothing to fold: keeps the cumulative map identical
        one_day[apply_on] = one_day.get(apply_on, 1.0) * factor

    # cumulative product walking BACKWARDS: factor(t) = product of one-day
    # factors of all events applied *after* t (verified apply-on date, which
    # may be a day later than the recorded ex_date). Events whose date falls
    # on a non-trading day still fold (pointer walks a separate sorted list —
    # fixed 2026-09-21: folding keyed on trade dates skipped such events).
    out: dict[date, float] = {}
    events_desc = sorted(one_day.items(), key=lambda kv: kv[0], reverse=True)
    i = 0
    running = 1.0
    for t in sorted(set(trade_dates), reverse=True):
        while i < len(events_desc) and events_desc[i][0] > t:
            running *= events_desc[i][1]
            i += 1
        out[t] = running
    return out


async def recompute_factors(session: AsyncSession, symbol_id: int) -> int:
    """Recompute and upsert daily_adjust_factors for one symbol. Returns row count.

    Reads corporate_action_events + daily_history close at each ex-date, computes
    factors with the pure function above, then upserts with a per-row guard
    (dbcompat trap #3: no implicit commit — caller owns the transaction).
    """
    rows = (
        await session.execute(
            text(
                """
                SELECT ex_date, action_type, ratio, dps
                FROM corporate_action_events
                WHERE symbol_id = :sid
                ORDER BY ex_date ASC
                """
            ),
            {"sid": symbol_id},
        )
    ).mappings().all()
    if not rows:
        return 0

    actions = [
        {"ex_date": r["ex_date"], "action_type": normalize_action_type(r["action_type"]), "ratio": r["ratio"], "dps": r["dps"]}
        for r in rows
    ]
    ex_dates = [a["ex_date"] for a in actions]

    # Factor dates come from vw_daily_history_adjusted, whose ``trade_date``
    # is the TRUE Gregorian trade date derived from the Shamsi column
    # (migration 0109). ``daily_history.trade_date`` is the *fetch* date, so
    # using it here compared real ex-dates against fetch dates and compounded
    # every factor against the wrong day.
    close_rows = await session.execute(
        text(
            """
            SELECT trade_date, price_close
            FROM vw_daily_history_adjusted
            WHERE symbol_id = :sid AND trade_date = ANY(:dates)
            """
        ),
        {"sid": symbol_id, "dates": ex_dates},
    ).all()
    closes = {r[0]: float(r[1]) for r in close_rows if r[1] is not None}

    all_dates = (
        await session.execute(
            text(
                "SELECT trade_date FROM vw_daily_history_adjusted "
                "WHERE symbol_id = :sid AND trade_date IS NOT NULL"
            ),
            {"sid": symbol_id},
        )
    ).scalars().all()

    # The raw series is the witness for every recorded claim (read-only).
    observed = await load_observed_price_moves(session, symbol_id, ex_dates)
    factors = compute_cumulative_factors(actions, all_dates, closes, observed)

    # upsert — per-row ON CONFLICT keeps memory bounded for long histories
    written = 0
    for d, f in factors.items():
        await session.execute(
            text(
                """
                INSERT INTO daily_adjust_factors (symbol_id, trade_date, adj_factor, computed_at)
                VALUES (:sid, :d, :f, now())
                ON CONFLICT (symbol_id, trade_date) DO UPDATE
                SET adj_factor = EXCLUDED.adj_factor, computed_at = now()
                """
            ),
            {"sid": symbol_id, "d": d, "f": f},
        )
        written += 1
    return written


# ── Price verification of a recorded event (audit §2, phase A / step 4) ──

# One day of ordinary trading noise. A claim smaller than this cannot be
# confirmed *or* refuted by one day of price, and a price move smaller than
# this is not a corporate-action footprint at all.
NOISE_DROP = 0.02
# How far the observed one-day multiplier may sit from the recorded factor
# (relatively) and still count as "the claim is what happened". Calibrated on
# the golden symbols: 0.3% for a verified dividend, 40% for the خودرو claim
# that disagreed with its own price footprint.
MULTIPLIER_TOLERANCE = 0.10
# ± days searched for the price footprint of one recorded event.
OBSERVATION_WINDOW_DAYS = 3


@dataclass(frozen=True)
class ObservedPriceMove:
    """What the raw series did around one recorded ex-date.

    ``ex_close`` / ``prev_close`` are the raw closes of the ex-date bar and the
    bar before it. ``max_drop_*`` describe the largest one-day fall inside the
    ±``OBSERVATION_WINDOW_DAYS`` window: the fraction, the day the fall landed
    on, and the observed multiplier ``close / previous_close`` on that day
    (``None`` when it could not be derived).
    """

    ex_close: float
    prev_close: float
    max_drop_in_window: float
    max_drop_date: date | None = None
    max_drop_multiplier: float | None = None


def _agrees(observed_factor: float, recorded_factor: float) -> bool:
    """Is the price-implied multiplier the same one-day move as the claim?"""
    if recorded_factor <= 0 or observed_factor <= 0:
        return False
    return abs(observed_factor - recorded_factor) / recorded_factor <= MULTIPLIER_TOLERANCE


def resolve_event_factor(
    action_type: str,
    *,
    ratio: float,
    dps: float,
    close_at_ex: float | None,
    ex_date: date,
    observed: ObservedPriceMove | None = None,
) -> tuple[float, str, date]:
    """Factor actually applied for one event, plus the verdict behind it.

    ``corporate_action_events`` holds a *claim*; the raw price series is the
    *witness*. Returns ``(factor, verdict, apply_on)``:

      * ``unverified``      — no observation available; the recorded factor stands;
      * ``confirmed``       — the observed move agrees with the claim (or the
                              claim is below the noise floor, so nothing about it
                              can be settled from prices);
      * ``invisible``       — a sizeable claim that left no footprint at all:
                              applying it would invent a jump, so factor 1.0;
      * ``ex_date_snapped`` — the footprint landed one/two days away from the
                              recorded date: keep the factor, apply it on the day
                              the price actually moved;
      * ``price_override``  — the footprint is real but disagrees with the claim:
                              the observed multiplier wins, otherwise the series
                              keeps an artificial jump.
    """
    recorded = _event_factor(action_type, ratio, dps, close_at_ex)
    claimed_drop = 1.0 - recorded

    if observed is None:
        return recorded, "unverified", ex_date

    if claimed_drop <= NOISE_DROP:
        return recorded, "confirmed", ex_date

    if observed.max_drop_in_window <= NOISE_DROP:
        return 1.0, "invisible", ex_date

    observed_factor = observed.max_drop_multiplier
    if observed_factor is None:
        observed_factor = 1.0 - observed.max_drop_in_window

    drop_day = observed.max_drop_date or ex_date
    if drop_day != ex_date and _agrees(observed_factor, recorded):
        return observed_factor, "ex_date_snapped", drop_day

    if _agrees(observed_factor, recorded):
        return recorded, "confirmed", ex_date

    return observed_factor, "price_override", drop_day


_OBSERVED_SERIES_SQL = text(
    """
    SELECT trade_date, price_close
    FROM vw_daily_history_adjusted
    WHERE symbol_id = :sid
      AND trade_date BETWEEN :lo AND :hi
      AND price_close IS NOT NULL AND price_close > 0
    ORDER BY trade_date
    """
)


async def load_observed_price_moves(
    session: AsyncSession,
    symbol_id: int,
    ex_dates: Sequence[date],
    window_days: int = OBSERVATION_WINDOW_DAYS,
) -> dict[date, ObservedPriceMove]:
    """Raw price footprint of every recorded ex-date of one symbol.

    Read-only, one query for the whole batch (padded so the first day of the
    earliest window still has a previous close to compare against). Ex-dates
    with no bar at/just before them, or with nothing inside their window, are
    left out of the result — ``resolve_event_factor`` then says ``unverified``.
    """
    wanted: list[date] = []
    for d in ex_dates:
        wanted.append(d if isinstance(d, date) else date.fromisoformat(str(d)))
    if not wanted:
        return {}

    pad = window_days + 7
    rows = (
        await session.execute(
            _OBSERVED_SERIES_SQL,
            {"sid": symbol_id, "lo": min(wanted) - timedelta(days=pad), "hi": max(wanted) + timedelta(days=pad)},
        )
    ).fetchall()
    if not rows:
        return {}

    series: list[tuple[date, float]] = [(r[0], float(r[1])) for r in rows]

    out: dict[date, ObservedPriceMove] = {}
    for ex in wanted:
        win_lo, win_hi = ex - timedelta(days=window_days), ex + timedelta(days=window_days)

        # The bar at (or just before) the ex-date, plus the bar before *it*.
        idx: int | None = None
        for i, (d, _close) in enumerate(series):
            if d <= ex:
                idx = i
            else:
                break
        if idx is None or idx == 0:
            continue

        best_date: date | None = None
        best_multiplier: float | None = None
        for i in range(1, len(series)):
            day, close = series[i]
            if day < win_lo or day > win_hi:
                continue
            previous = series[i - 1][1]
            if previous <= 0:
                continue
            multiplier = close / previous
            if best_multiplier is None or multiplier < best_multiplier:
                best_multiplier, best_date = multiplier, day
        if best_multiplier is None:
            continue

        out[ex] = ObservedPriceMove(
            ex_close=series[idx][1],
            prev_close=series[idx - 1][1],
            max_drop_in_window=max(0.0, 1.0 - best_multiplier),
            max_drop_date=best_date,
            max_drop_multiplier=best_multiplier,
        )
    return out


def normalize_action_type(action_type: str) -> str:
    """Normalize legacy/whitespace variants of action_type."""
    t = (action_type or "").strip().lower()
    if t in ("capital_increase", "capital increase", "افزایش سرمایه"):
        return "capital_increase"
    if t in ("bonus", "سهام جایزه"):
        return "bonus"
    if t in ("dividend", "DPS", "سود نقدی"):
        return "dividend"
    return t
