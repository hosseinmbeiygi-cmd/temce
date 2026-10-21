"""Gold economic-calendar service layer.

Provides:

* ``is_high_vol_window_from_events(as_of, events, ...)`` — pure function that
  returns ``True`` when ``as_of`` falls within the configured half-window
  (default ±1 calendar day) of a high-volatility CPI / NFP / FOMC event,
* ``is_high_vol_window(as_of, session, ...)`` — async DB-backed version that
  reads stored calendar / Iran-manual events.

Pure function never touches a database; tests inject recorded fixtures.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from core.logging import get_logger
from models.gold_macro import (
    GoldEconomicCalendarEventModel,
    GoldIranManualEventModel,
)
from services.gold.macro_sync import HIGH_VOLATILITY_CATEGORIES

logger = get_logger(__name__)

DEFAULT_HIGH_VOL_WINDOW_DAYS = 1


def is_high_vol_window_from_events(
    as_of: date,
    events: list[dict[str, Any]],
    *,
    window_days: int = DEFAULT_HIGH_VOL_WINDOW_DAYS,
    categories: tuple[str, ...] = HIGH_VOLATILITY_CATEGORIES,
) -> bool:
    """Pure: ``True`` when ``as_of`` is within ±``window_days`` of a high-vol event.

    Each event dict may carry ``event_date`` (date|str) and/or ``category``
    (e.g. CPI/NFP/FOMC) or an explicit ``is_high_volatility`` flag.
    """
    categories_upper = tuple(c.upper() for c in categories)
    target = as_of
    for ev in events:
        raw = ev.get("event_date")
        if raw is None:
            continue
        try:
            event_date = (
                raw if isinstance(raw, date) else date.fromisoformat(str(raw)[:10])
            )
        except (ValueError, TypeError):
            continue
        is_high = bool(ev.get("is_high_volatility")) or str(
            ev.get("category", "")
        ).upper() in categories_upper
        if not is_high:
            continue
        if abs((target - event_date).days) <= window_days:
            return True
    return False


async def is_high_vol_window(
    as_of: date,
    session: Any,
    *,
    window_days: int = DEFAULT_HIGH_VOL_WINDOW_DAYS,
    include_iran_manual: bool = True,
) -> bool:
    """Return ``True`` when ``as_of`` is in a high-volatility window.

    Reads CPI / NFP / FOMC (and optional Iran manual high-vol events) from
    ``gold_economic_calendar_events`` / ``gold_iran_manual_events``.
    """
    start = as_of - timedelta(days=window_days)
    end = as_of + timedelta(days=window_days)

    stmt = select(GoldEconomicCalendarEventModel).where(
        GoldEconomicCalendarEventModel.event_date >= start,
        GoldEconomicCalendarEventModel.event_date <= end,
    )
    result = await session.execute(stmt)
    for row in result.scalars().all():
        if row.is_high_volatility or str(row.category or "").upper() in HIGH_VOLATILITY_CATEGORIES:
            return True

    if include_iran_manual:
        stmt2 = select(GoldIranManualEventModel).where(
            GoldIranManualEventModel.event_date >= start,
            GoldIranManualEventModel.event_date <= end,
        )
        result2 = await session.execute(stmt2)
        for row in result2.scalars().all():
            if row.is_high_volatility or str(row.category or "").upper() in HIGH_VOLATILITY_CATEGORIES:
                return True

    return False


async def add_iran_manual_event(
    session: Any,
    *,
    event_id: str,
    event_date: date,
    event_time: str | None = None,
    title: str | None = None,
    category: str | None = None,
    importance: int | None = None,
    note: str | None = None,
    is_high_volatility: bool = False,
) -> GoldIranManualEventModel:
    """Insert (idempotent by ``event_id``) an Iran-specific manual event.

    Manual entry is the only way Iran events enter the calendar: there is no
    provider feed for them, so they are never auto-ingested.
    """
    existing = await _get_iran_manual_event(session, event_id)
    if existing is not None:
        return existing
    row = GoldIranManualEventModel(
        event_id=event_id,
        event_date=event_date,
        event_time=event_time,
        title=title,
        category=category,
        importance=importance,
        note=note,
        is_high_volatility=is_high_volatility,
    )
    session.add(row)
    await session.commit()
    return row


async def _get_iran_manual_event(
    session: Any, event_id: str
) -> GoldIranManualEventModel | None:
    stmt = select(GoldIranManualEventModel).where(
        GoldIranManualEventModel.event_id == event_id
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def list_economic_calendar(
    session: Any,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
) -> list[GoldEconomicCalendarEventModel]:
    """List stored CPI/NFP/FOMC-style calendar events, newest first."""
    stmt = select(GoldEconomicCalendarEventModel)
    if start is not None:
        stmt = stmt.where(GoldEconomicCalendarEventModel.event_date >= start)
    if end is not None:
        stmt = stmt.where(GoldEconomicCalendarEventModel.event_date <= end)
    stmt = stmt.order_by(
        GoldEconomicCalendarEventModel.event_date.desc()
    ).limit(max(1, min(limit, 500)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_iran_manual_events(
    session: Any,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
) -> list[GoldIranManualEventModel]:
    """List stored Iran manual-entry events, newest first."""
    stmt = select(GoldIranManualEventModel)
    if start is not None:
        stmt = stmt.where(GoldIranManualEventModel.event_date >= start)
    if end is not None:
        stmt = stmt.where(GoldIranManualEventModel.event_date <= end)
    stmt = stmt.order_by(GoldIranManualEventModel.event_date.desc()).limit(
        max(1, min(limit, 500))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


__all__ = [
    "DEFAULT_HIGH_VOL_WINDOW_DAYS",
    "add_iran_manual_event",
    "is_high_vol_window",
    "is_high_vol_window_from_events",
    "list_economic_calendar",
    "list_iran_manual_events",
]
