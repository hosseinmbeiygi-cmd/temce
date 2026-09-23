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

Polyglot-PK note (core/dbcompat trap #1): ``symbols.id`` is BIGINT so
parameters are passed to asyncpg as int — never str.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Sequence

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
) -> dict[date, float]:
    """Cumulative factor per trade date, deterministic and pure (unit-testable).

    ``actions``: rows ordered by ex_date ASC; each has action_type, ratio,
    dps, ex_date. ``closes_by_date`` supplies close price at each ex-date
    for dividend events. Trade dates with no factor entry get 1.0.
    """
    closes = closes_by_date or {}
    one_day: dict[date, float] = {}
    for a in actions:
        ex = a["ex_date"]
        if isinstance(ex, str):
            ex = date.fromisoformat(ex)
        f = _event_factor(a["action_type"], float(a.get("ratio") or 0), float(a.get("dps") or 0), closes.get(ex))
        one_day[ex] = one_day.get(ex, 1.0) * f

    # cumulative product walking BACKWARDS: factor(t) = product of one-day
    # factors of all events with ex_date > t. Events whose ex-date falls on
    # a non-trading day still fold (pointer walks a separate sorted list —
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

    # close price at each ex-date (for dividend factors)
    close_rows = await session.execute(
        text(
            """
            SELECT trade_date, price_close
            FROM daily_history
            WHERE symbol_id = :sid AND trade_date = ANY(:dates)
            """
        ),
        {"sid": symbol_id, "dates": ex_dates},
    ).all()
    closes = {r[0]: float(r[1]) for r in close_rows if r[1] is not None}

    all_dates = (
        await session.execute(
            text("SELECT trade_date FROM daily_history WHERE symbol_id = :sid"),
            {"sid": symbol_id},
        )
    ).scalars().all()

    factors = compute_cumulative_factors(actions, all_dates, closes)

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
