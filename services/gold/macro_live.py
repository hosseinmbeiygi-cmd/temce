"""Gold macro live posture — feeds ``evaluate_gold_macro_posture`` from stored data.

Reads the latest stored 10Y TIPS real yield (FRED DFII10) and broad dollar
index (FRED DTWEXBGS) from ``gold_macro_indicators``, derives ``gold_trend``
from recent XAUUSD snapshots, and runs the existing macro-posture model.

Pure DB → model adapter: nothing here touches the network so posture can be
evaluated from ingested, provenanced data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.gold_macro import GoldMacroIndicatorModel
from providers.macro_sources.tokenized_gold import PREMIUM_INDICATOR_SUFFIX
from services.gold.economic_calendar import is_high_vol_window
from services.gold.macro_indicators import (
    DEFAULT_DXY_MIN_SAMPLES,
    DEFAULT_DXY_PERCENTILE_HIGH,
    DEFAULT_DXY_PERCENTILE_LOW,
    evaluate_gold_macro_posture,
)

logger = get_logger(__name__)

FRED_TIPS_10Y_INDICATOR = "FRED_DFII10"
FRED_DXY_BROAD_INDICATOR = "FRED_DTWEXBGS"
DEFAULT_STALENESS_SECONDS = 7 * 24 * 60 * 60  # 7 days
TREND_CHANGE_THRESHOLD = 0.02  # ±2% → up/down
#: Enough DTWEXBGS history for stable p20/p80 thresholds (daily, ~2 years).
DXY_HISTORY_LIMIT = 2_000


@dataclass
class MacroLiveResult:
    available: bool
    missing: list[str] = field(default_factory=list)
    posture: dict[str, Any] | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    tips_staleness_seconds: float | None = None
    dxy_staleness_seconds: float | None = None
    trend_staleness_seconds: float | None = None
    high_vol_window: bool = False
    error: str | None = None


async def _get_latest_indicator(
    session: AsyncSession, indicator: str
) -> GoldMacroIndicatorModel | None:
    statement = (
        select(GoldMacroIndicatorModel)
        .where(GoldMacroIndicatorModel.indicator == indicator)
        .order_by(desc(GoldMacroIndicatorModel.as_of))
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalars().first()


async def _get_indicator_history(
    session: AsyncSession, indicator: str, limit: int = DXY_HISTORY_LIMIT
) -> list[float]:
    """Stored values of one indicator, newest first, for percentile thresholds."""
    statement = (
        select(GoldMacroIndicatorModel)
        .where(GoldMacroIndicatorModel.indicator == indicator)
        .order_by(desc(GoldMacroIndicatorModel.as_of))
        .limit(limit)
    )
    result = await session.execute(statement)
    values: list[float] = []
    for row in result.scalars().all():
        # Accept both ORM rows (production) and bare floats (test doubles).
        raw = getattr(row, "value", row)
        if raw is None:
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        values.append(number)
    return values


def _dxy_threshold_config() -> tuple[float, float, int]:
    """Percentile thresholds and minimum history from the app config."""
    try:
        from core.config import get_settings

        settings = get_settings()
        return (
            float(settings.gold_dxy_percentile_low),
            float(settings.gold_dxy_percentile_high),
            int(settings.gold_dxy_min_samples),
        )
    except Exception:  # pragma: no cover - config fallback is deliberately safe
        return (
            DEFAULT_DXY_PERCENTILE_LOW,
            DEFAULT_DXY_PERCENTILE_HIGH,
            DEFAULT_DXY_MIN_SAMPLES,
        )


async def _derive_gold_trend(session: AsyncSession) -> tuple[str | None, float | None]:
    """Derive up/down/sideways from the two most recent XAUUSD snapshots."""
    try:
        from src.gold_desk.models import GoldSnapshotModel
    except Exception:  # pragma: no cover - optional surface
        return None, None

    statement = (
        select(GoldSnapshotModel)
        .where(GoldSnapshotModel.xau_usd.isnot(None))
        .order_by(desc(GoldSnapshotModel.snapshot_at))
        .limit(2)
    )
    result = await session.execute(statement)
    rows = list(result.scalars().all())
    if len(rows) < 2:
        latest = rows[0] if rows else None
        return None, (
            latest.snapshot_at.timestamp() if latest and latest.snapshot_at else None
        )
    latest, previous = rows[0], rows[1]
    latest_price = float(latest.xau_usd)
    previous_price = float(previous.xau_usd)
    if previous_price <= 0:
        return None, latest.snapshot_at.timestamp() if latest.snapshot_at else None
    change = (latest_price - previous_price) / previous_price
    if change >= TREND_CHANGE_THRESHOLD:
        trend = "up"
    elif change <= -TREND_CHANGE_THRESHOLD:
        trend = "down"
    else:
        trend = "sideways"
    staleness = (
        (datetime.now(UTC) - latest.snapshot_at).total_seconds()
        if latest.snapshot_at
        else None
    )
    return trend, staleness


async def _resolve_high_vol_window(session: AsyncSession, as_of: date) -> bool:
    """Return True when today sits in a CPI/NFP/FOMC (or Iran manual) window.

    Best-effort: a calendar read failure must not take the posture down, so
    the flag degrades to ``False``.
    """
    try:
        return await is_high_vol_window(as_of, session)
    except Exception:  # noqa: BLE001 - the flag is context, never a blocker
        logger.warning("High-vol window lookup failed", exc_info=True)
        return False


async def _resolve_tokenized_gold_premium(
    session: AsyncSession,
) -> dict[str, float]:
    """Latest stored tokenized-gold premium against spot, per ticker.

    Supplementary context only — a missing premium never blocks the posture.
    """
    premiums: dict[str, float] = {}
    try:
        statement = select(GoldMacroIndicatorModel).where(
            GoldMacroIndicatorModel.indicator.like(f"%{PREMIUM_INDICATOR_SUFFIX}")
        )
        result = await session.execute(statement)
        for row in result.scalars().all():
            ticker = str(row.indicator).removesuffix(PREMIUM_INDICATOR_SUFFIX)
            if ticker and row.value is not None:
                premiums[ticker] = float(row.value)
    except Exception:  # noqa: BLE001 - context only, never a blocker
        logger.warning("Tokenized-gold premium lookup failed", exc_info=True)
    return premiums


async def get_gold_macro_live(session: AsyncSession) -> MacroLiveResult:
    """Evaluate gold macro posture from stored data.

    Returns ``available=False`` with a ``missing`` list when required stored
    inputs are absent or too stale, rather than raising.
    """
    now = datetime.now(UTC)

    tips_row = await _get_latest_indicator(session, FRED_TIPS_10Y_INDICATOR)
    dxy_row = await _get_latest_indicator(session, FRED_DXY_BROAD_INDICATOR)
    trend, trend_staleness = await _derive_gold_trend(session)
    high_vol_window = await _resolve_high_vol_window(session, now.date())
    tokenized_gold_premium = await _resolve_tokenized_gold_premium(session)

    missing: list[str] = []
    tips_staleness = None
    dxy_staleness = None
    inputs: dict[str, Any] = {}

    if tips_row is None:
        missing.append("tips_yield")
    else:
        inputs["tips_yield"] = tips_row.value
        tips_staleness = (now - tips_row.fetched_at).total_seconds() if tips_row.fetched_at else None
        if tips_staleness is not None and tips_staleness > DEFAULT_STALENESS_SECONDS:
            missing.append("tips_yield_stale")

    dxy_history: list[float] = []
    if dxy_row is None:
        missing.append("dxy_index")
    else:
        inputs["dxy_index"] = dxy_row.value
        dxy_staleness = (now - dxy_row.fetched_at).total_seconds() if dxy_row.fetched_at else None
        if dxy_staleness is not None and dxy_staleness > DEFAULT_STALENESS_SECONDS:
            missing.append("dxy_index_stale")
        # DTWEXBGS levels are not on the classic DXY scale; rank the current
        # value against the stored history instead of fixed 95/105 levels.
        dxy_history = await _get_indicator_history(
            session, FRED_DXY_BROAD_INDICATOR
        )
        inputs["dxy_history_samples"] = len(dxy_history)

    if trend is None:
        missing.append("gold_trend")
    else:
        inputs["gold_trend"] = trend

    # Supplementary context — the tokenized-gold premium never gates the
    # posture, it only annotates it.
    if tokenized_gold_premium:
        inputs["tokenized_gold_premium"] = tokenized_gold_premium

    posture: dict[str, Any] | None = None
    error: str | None = None
    if not missing:
        try:
            low, high, min_samples = _dxy_threshold_config()
            posture = evaluate_gold_macro_posture(
                tips_yield=float(inputs["tips_yield"]),
                dxy_index=float(inputs["dxy_index"]),
                gold_trend=str(inputs["gold_trend"]),
                dxy_history=dxy_history,
                dxy_series=FRED_DXY_BROAD_INDICATOR,
                percentile_low=low,
                percentile_high=high,
                min_samples=min_samples,
            )
            if posture.get("posture") == "insufficient_history":
                missing.append("dxy_history")
        except (TypeError, ValueError) as exc:
            error = str(exc)
            missing.append("posture_computation_failed")

    return MacroLiveResult(
        available=(
            posture is not None
            and posture.get("posture") != "insufficient_history"
        ),
        missing=missing,
        posture=posture,
        inputs=inputs,
        tips_staleness_seconds=tips_staleness,
        dxy_staleness_seconds=dxy_staleness,
        trend_staleness_seconds=trend_staleness,
        high_vol_window=high_vol_window,
        error=error,
    )


__all__ = [
    "FRED_DXY_BROAD_INDICATOR",
    "FRED_TIPS_10Y_INDICATOR",
    "DEFAULT_STALENESS_SECONDS",
    "MacroLiveResult",
    "get_gold_macro_live",
]
