"""Gold feature source — reads the real gold tables as of a point in time.

This is the I/O half of STEP 7B: every query is bounded by ``<= as_of`` and the
rows are re-filtered in Python as a second line of defence, so a widened SQL
predicate can never leak a future observation into the feature block.

Missing tables/rows return empty lists; ``compute_gold_features`` then emits
``None`` plus a ``missing`` flag instead of inventing a value.

Loading strategy
----------------
Each source is split into a *fetch* (one SQL statement) and a *slice* (pure
Python, point-in-time).  That lets the provider serve

* a single point — ``load(as_of)`` — with tightly bounded queries, and
* a whole backtest — ``load_many(as_of_values)`` — with **one query per
  table** instead of ~8 queries per timestamp.

Both paths share the same slice functions, so a batched result is identical to
the point-by-point result (pinned by a test).

Results are memoised in an in-memory cache keyed by ``(as_of, symbol)``.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.commodity import GoldCoinPriceModel
from brsapi.models.ime import ImeCertificateModel
from core.logging import get_logger
from models.gold_macro import (
    GoldCotPositionModel,
    GoldEconomicCalendarEventModel,
    GoldIranManualEventModel,
    GoldMacroIndicatorModel,
)
from services.gold.features import (
    DEFAULT_EVENT_HORIZON_DAYS,
    DatedValue,
    GoldFeatureInputs,
)
from services.gold.macro_live import FRED_TIPS_10Y_INDICATOR
from services.gold.physical_market import (
    aed_hawala_spread,
    calculate_ime_certificate_spread,
)
from src.gold_desk.models import GoldFundNAVModel, GoldSnapshotModel

logger = get_logger(__name__)

DEFAULT_COIN_SYMBOL = "IR_COIN_EMAMI"
DEFAULT_AED_SYMBOL = "XAUUSD"
DEFAULT_MELTED_SYMBOL = "IR_GOLD_18K"
DEFAULT_FEATURE_SYMBOL = "XAUUSD"
DEFAULT_HISTORY_LIMIT = 240
DEFAULT_COT_HISTORY_LIMIT = 260
DEFAULT_EVENT_LIMIT = 500
DEFAULT_IME_LOOKBACK = 50
#: Row cap of the *batched* loader (one query per table for a whole backtest).
DEFAULT_RAW_ROW_LIMIT = 20_000
#: Number of memoised ``(as_of, symbol)`` feature blocks.
DEFAULT_CACHE_SIZE = 256

_GRAM_UNITS = {"g", "gram", "grams", "گرم"}
_KILOGRAM_UNITS = {"kg", "kilogram", "kilograms", "کیلوگرم"}


class GoldFeatureProvider(Protocol):
    """Point-in-time loader consumed by ``SignalFeaturePipeline``."""

    async def load(
        self, as_of: datetime, symbol: str | None = None
    ) -> GoldFeatureInputs: ...


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _naive_utc(value: datetime) -> datetime:
    """Bind value for ``TIMESTAMP WITHOUT TIME ZONE`` columns (asyncpg rejects
    an aware datetime there) — the stored convention is UTC."""
    return _to_utc(value).replace(tzinfo=None)


def _grams_per_contract(size: Any, unit: Any) -> float | None:
    try:
        numeric = float(size)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    normalized = str(unit or "").strip().lower()
    if normalized in _GRAM_UNITS:
        return numeric
    if normalized in _KILOGRAM_UNITS:
        return numeric * 1_000.0
    return None


def _event_known_at(row: Any) -> datetime | None:
    """When the calendar row's content became known (provenance).

    ``fetched_at`` (provider fetch) and ``created_at`` (row insert) are the
    two stamps the schema offers; the newest one wins.  ``None`` means the row
    carries no provenance at all — such a row can never justify a
    *forward-looking* claim (see ``features._forward_event_window``).
    """
    stamps: list[datetime] = []
    for attribute in ("fetched_at", "created_at", "updated_at"):
        value = getattr(row, attribute, None)
        if isinstance(value, datetime):
            stamps.append(_to_utc(value))
    return max(stamps) if stamps else None


def _event_first_seen_at(row: Any) -> datetime | None:
    """When the calendar row first existed (a row inserted after ``t`` is invisible)."""
    for attribute in ("created_at", "fetched_at"):
        value = getattr(row, attribute, None)
        if isinstance(value, datetime):
            return _to_utc(value)
    return None


def _clone_inputs(inputs: GoldFeatureInputs) -> GoldFeatureInputs:
    """Copy the cached block so a caller cannot mutate the cache."""
    return GoldFeatureInputs(
        coin_bubble_pct=list(inputs.coin_bubble_pct),
        ime_spread_pct=list(inputs.ime_spread_pct),
        fund_pnav_pct=list(inputs.fund_pnav_pct),
        cot_percentile=list(inputs.cot_percentile),
        real_yield=list(inputs.real_yield),
        aed_spread_pct=list(inputs.aed_spread_pct),
        high_vol_events=list(inputs.high_vol_events),
        scheduled_events=list(inputs.scheduled_events),
    )


@dataclass
class _RawSeries:
    """Raw rows of every gold source, fetched once and sliced per ``as_of``."""

    bubble: list[Any] = field(default_factory=list)
    aed: list[Any] = field(default_factory=list)
    ime_certs: list[Any] = field(default_factory=list)
    melted: list[Any] = field(default_factory=list)
    fund_nav: list[Any] = field(default_factory=list)
    cot: list[Any] = field(default_factory=list)
    macro: list[Any] = field(default_factory=list)
    calendar: list[Any] = field(default_factory=list)
    iran: list[Any] = field(default_factory=list)


class DatabaseGoldFeatureProvider:
    """Read gold bubble/spread/P-NAV/COT/yield/AED/calendar from the DB.

    Parameters are injectable so tests can pass a session double; production
    uses ``core.database.get_session`` (one short-lived session per ``load``).

    ``fund_symbol`` pins the gold fund whose P/NAV premium is used.  With
    ``fund_symbol=None`` the P/NAV feature is **not** filled from "the latest
    row across funds" — mixing different funds' series into one feature is
    meaningless — so the feature is reported as missing.
    """

    def __init__(
        self,
        session_factory: Any = None,
        *,
        session: AsyncSession | None = None,
        coin_symbol: str = DEFAULT_COIN_SYMBOL,
        aed_symbol: str = DEFAULT_AED_SYMBOL,
        fund_symbol: str | None = None,
        melted_symbol: str = DEFAULT_MELTED_SYMBOL,
        feature_symbol: str = DEFAULT_FEATURE_SYMBOL,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
        cot_history_limit: int = DEFAULT_COT_HISTORY_LIMIT,
        event_limit: int = DEFAULT_EVENT_LIMIT,
        ime_lookback: int = DEFAULT_IME_LOOKBACK,
        event_horizon_days: int | None = None,
        raw_row_limit: int = DEFAULT_RAW_ROW_LIMIT,
        cache_size: int = DEFAULT_CACHE_SIZE,
    ) -> None:
        if history_limit < 1:
            raise ValueError(f"history_limit must be >= 1, got {history_limit!r}")
        self._session_factory = session_factory
        self._session = session
        self.coin_symbol = coin_symbol
        self.aed_symbol = aed_symbol
        self.fund_symbol = fund_symbol
        self.melted_symbol = melted_symbol
        self.feature_symbol = feature_symbol
        self.history_limit = history_limit
        self.cot_history_limit = cot_history_limit
        self.event_limit = event_limit
        self.ime_lookback = ime_lookback
        self._event_horizon_days = event_horizon_days
        self.raw_row_limit = max(1, raw_row_limit)
        self.cache_size = max(0, cache_size)
        self._cache: OrderedDict[tuple[datetime, str], GoldFeatureInputs] = (
            OrderedDict()
        )

    # ── Configuration helpers ───────────────────────────────────────

    @property
    def event_horizon_days(self) -> int:
        """Forward-looking event horizon in days (config-driven)."""
        if self._event_horizon_days is not None:
            return self._event_horizon_days
        return _configured_event_horizon_days()

    @property
    def _calendar_fetch_limit(self) -> int:
        """Past-event cap plus head-room for the scheduled (future) window."""
        return self.event_limit + max(1, self.event_horizon_days) * 2

    # ── Public API ───────────────────────────────────────────────────

    async def load(
        self, as_of: datetime, symbol: str | None = None
    ) -> GoldFeatureInputs:
        """Point-in-time feature block for one timestamp (memoised)."""
        as_of = _to_utc(as_of)
        key = self._cache_key(as_of, symbol)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        inputs = await self._with_session(
            lambda session: self._load(session, as_of), GoldFeatureInputs()
        )
        self._cache_put(key, inputs)
        return inputs

    async def load_many(
        self,
        as_of_values: Sequence[datetime],
        symbol: str | None = None,
    ) -> dict[datetime, GoldFeatureInputs]:
        """Feature blocks for many timestamps with **one query per table**.

        The raw rows are fetched once (bounded by the newest requested
        ``as_of``) and sliced in Python per point, so a backtest over N
        timestamps costs ~9 queries instead of ~8 * N.
        """
        points = sorted({_to_utc(value) for value in as_of_values})
        if not points:
            return {}

        cache_symbol = symbol or self.feature_symbol
        results: dict[datetime, GoldFeatureInputs] = {}
        pending: list[datetime] = []
        for point in points:
            cached = self._cache_get((point, cache_symbol))
            if cached is not None:
                results[point] = cached
            else:
                pending.append(point)

        if pending:
            max_as_of = pending[-1]
            raw = await self._with_session(
                lambda session: self._fetch_raw_series(session, max_as_of),
                _RawSeries(),
            )
            for point in pending:
                inputs = self._assemble(raw, point)
                self._cache_put((point, cache_symbol), inputs)
                results[point] = inputs
        return results

    def clear_cache(self) -> None:
        """Drop the memoised feature blocks."""
        self._cache.clear()

    def _cache_key(self, as_of: datetime, symbol: str | None) -> tuple[datetime, str]:
        return (as_of, symbol or self.feature_symbol)

    def _cache_get(
        self, key: tuple[datetime, str]
    ) -> GoldFeatureInputs | None:
        if self.cache_size <= 0:
            return None
        item = self._cache.get(key)
        if item is None:
            return None
        self._cache.move_to_end(key)
        return _clone_inputs(item)

    def _cache_put(
        self, key: tuple[datetime, str], inputs: GoldFeatureInputs
    ) -> None:
        if self.cache_size <= 0:
            return
        self._cache[key] = _clone_inputs(inputs)
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    async def _with_session(
        self, fn: Callable[[AsyncSession], Any], default: Any
    ) -> Any:
        """Run ``fn`` with a session from whichever source is configured."""
        if self._session is not None:
            return await fn(self._session)

        if self._session_factory is not None:
            factory = self._session_factory
            if callable(factory):
                result = factory()
                if hasattr(result, "__aiter__"):
                    async for session in result:
                        return await fn(session)
                    return default
                return await fn(result)
            return await fn(factory)

        from core.database import get_session

        async for session in get_session():
            return await fn(session)
        return default

    async def _safe_rows(self, session: AsyncSession, statement, label: str) -> list[Any]:
        """One failing source degrades to empty rows (→ missing flags)."""
        try:
            return list((await session.execute(statement)).scalars().all())
        except Exception as exc:  # noqa: BLE001 - a feature source must not crash extraction
            # Type only: the traceback can contain non-ASCII text that crashes
            # a cp1252 console while logging, taking extraction down with it.
            logger.warning(
                "Gold feature source %s failed: %s", label, type(exc).__name__
            )
            return []

    # ── Fetches (one SQL statement per source) ───────────────────────

    async def _fetch_bubble(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        statement = (
            select(GoldSnapshotModel)
            .where(
                GoldSnapshotModel.symbol == self.coin_symbol,
                GoldSnapshotModel.snapshot_at <= bound,
                GoldSnapshotModel.bubble_pct.isnot(None),
            )
            .order_by(desc(GoldSnapshotModel.snapshot_at))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "bubble")

    async def _fetch_aed(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        statement = (
            select(GoldSnapshotModel)
            .where(
                GoldSnapshotModel.symbol == self.aed_symbol,
                GoldSnapshotModel.snapshot_at <= bound,
            )
            .order_by(desc(GoldSnapshotModel.snapshot_at))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "aed_spread")

    async def _fetch_ime_certs(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        # ``created_at`` on the BrsApi tables is TIMESTAMP WITHOUT TIME ZONE.
        statement = (
            select(ImeCertificateModel)
            .where(
                ImeCertificateModel.created_at <= _naive_utc(bound),
                ImeCertificateModel.price_last.isnot(None),
                ImeCertificateModel.contract_size.isnot(None),
                ImeCertificateModel.contract_size > 0,
            )
            .order_by(desc(ImeCertificateModel.created_at))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "ime_certificates")

    async def _fetch_melted(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        statement = (
            select(GoldCoinPriceModel)
            .where(
                GoldCoinPriceModel.symbol == self.melted_symbol,
                GoldCoinPriceModel.created_at <= _naive_utc(bound),
                GoldCoinPriceModel.price.isnot(None),
            )
            .order_by(desc(GoldCoinPriceModel.created_at))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "ime_melted")

    async def _fetch_fund_nav(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        if not self.fund_symbol:
            # No fund pinned: reading "the latest row across funds" would mix
            # different funds' P/NAV series into one feature.  Skip the table
            # entirely — the feature is reported as missing instead.
            return []
        # ``gold_fund_nav.date`` is TIMESTAMP WITHOUT TIME ZONE.
        statement = (
            select(GoldFundNAVModel)
            .where(
                GoldFundNAVModel.symbol == self.fund_symbol,
                GoldFundNAVModel.date <= _naive_utc(bound),
            )
            .order_by(desc(GoldFundNAVModel.date))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "fund_pnav")

    async def _fetch_cot(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        statement = (
            select(GoldCotPositionModel)
            .where(GoldCotPositionModel.report_date <= bound.date())
            .order_by(desc(GoldCotPositionModel.report_date))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "cot")

    async def _fetch_macro(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        statement = (
            select(GoldMacroIndicatorModel)
            .where(
                GoldMacroIndicatorModel.indicator == FRED_TIPS_10Y_INDICATOR,
                GoldMacroIndicatorModel.as_of <= bound,
                GoldMacroIndicatorModel.value.isnot(None),
            )
            .order_by(desc(GoldMacroIndicatorModel.as_of))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "real_yield")

    async def _fetch_calendar(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        statement = (
            select(GoldEconomicCalendarEventModel)
            .where(
                GoldEconomicCalendarEventModel.event_date
                <= bound.date() + timedelta(days=self.event_horizon_days)
            )
            .order_by(desc(GoldEconomicCalendarEventModel.event_date))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "calendar")

    async def _fetch_iran_calendar(
        self, session: AsyncSession, bound: datetime, limit: int
    ) -> list[Any]:
        statement = (
            select(GoldIranManualEventModel)
            .where(
                GoldIranManualEventModel.event_date
                <= bound.date() + timedelta(days=self.event_horizon_days)
            )
            .order_by(desc(GoldIranManualEventModel.event_date))
            .limit(limit)
        )
        return await self._safe_rows(session, statement, "iran_calendar")

    async def _fetch_raw_series(
        self, session: AsyncSession, bound: datetime
    ) -> _RawSeries:
        """Fetch every source once, bounded by ``bound`` (newest requested point)."""
        limit = self.raw_row_limit
        # One session cannot run statements concurrently — fetch sequentially.
        bubble = await self._fetch_bubble(session, bound, limit)
        aed = await self._fetch_aed(session, bound, limit)
        certs = await self._fetch_ime_certs(session, bound, limit)
        melted = await self._fetch_melted(session, bound, limit)
        fund = await self._fetch_fund_nav(session, bound, limit)
        cot = await self._fetch_cot(session, bound, limit)
        macro = await self._fetch_macro(session, bound, limit)
        calendar = await self._fetch_calendar(session, bound, self._calendar_fetch_limit)
        iran = await self._fetch_iran_calendar(session, bound, self._calendar_fetch_limit)
        return _RawSeries(
            bubble=bubble,
            aed=aed,
            ime_certs=certs,
            melted=melted,
            fund_nav=fund,
            cot=cot,
            macro=macro,
            calendar=calendar,
            iran=iran,
        )

    async def _load(
        self, session: AsyncSession, as_of: datetime
    ) -> GoldFeatureInputs:
        """Point-by-point load: tightly bounded queries, one row set per source."""
        bubble = await self._fetch_bubble(session, as_of, self.history_limit)
        aed = await self._fetch_aed(session, as_of, self.history_limit)
        certs = await self._fetch_ime_certs(session, as_of, self.ime_lookback)
        melted = await self._fetch_melted(session, as_of, 1)
        fund = await self._fetch_fund_nav(session, as_of, self.history_limit)
        cot = await self._fetch_cot(session, as_of, self.cot_history_limit)
        macro = await self._fetch_macro(session, as_of, 1)
        calendar = await self._fetch_calendar(session, as_of, self._calendar_fetch_limit)
        iran = await self._fetch_iran_calendar(session, as_of, self._calendar_fetch_limit)
        return self._assemble(
            _RawSeries(
                bubble=bubble,
                aed=aed,
                ime_certs=certs,
                melted=melted,
                fund_nav=fund,
                cot=cot,
                macro=macro,
                calendar=calendar,
                iran=iran,
            ),
            as_of,
        )

    # ── Slices (pure Python, point-in-time) ──────────────────────────

    def _assemble(self, raw: _RawSeries, as_of: datetime) -> GoldFeatureInputs:
        past_events, scheduled_events = self._slice_events(raw, as_of)
        return GoldFeatureInputs(
            coin_bubble_pct=self._slice_bubble(raw.bubble, as_of),
            ime_spread_pct=self._slice_ime(raw.ime_certs, raw.melted, as_of),
            fund_pnav_pct=self._slice_fund_pnav(raw.fund_nav, as_of),
            cot_percentile=self._slice_cot(raw.cot, as_of),
            real_yield=self._slice_real_yield(raw.macro, as_of),
            aed_spread_pct=self._slice_aed(raw.aed, as_of),
            high_vol_events=past_events,
            scheduled_events=scheduled_events,
        )

    def _slice_bubble(
        self, rows: list[Any], as_of: datetime
    ) -> list[DatedValue]:
        points = [
            DatedValue(
                as_of=_to_utc(row.snapshot_at),
                value=float(row.bubble_pct),
            )
            for row in rows
            if row.snapshot_at is not None
            and row.bubble_pct is not None
            and _to_utc(row.snapshot_at) <= as_of
        ]
        points.sort(key=lambda item: item.as_of)
        return points[-self.history_limit :]

    def _slice_aed(self, rows: list[Any], as_of: datetime) -> list[DatedValue]:
        points: list[DatedValue] = []
        for row in rows:
            if row.snapshot_at is None or _to_utc(row.snapshot_at) > as_of:
                continue
            value = row.aed_gap_pct
            if value is None and row.usd_irt and row.aed_irt:
                try:
                    value = aed_hawala_spread(
                        float(row.usd_irt), float(row.aed_irt)
                    )["spread_pct"]
                except ValueError:
                    value = None
            if value is None:
                continue
            points.append(
                DatedValue(as_of=_to_utc(row.snapshot_at), value=float(value))
            )
        points.sort(key=lambda item: item.as_of)
        return points[-self.history_limit :]

    def _slice_ime(
        self, cert_rows: list[Any], melted_rows: list[Any], as_of: datetime
    ) -> list[DatedValue]:
        melted_candidates = [
            row
            for row in melted_rows
            if row.created_at is not None
            and row.price is not None
            and float(row.price) > 0
            and _to_utc(row.created_at) <= as_of
        ]
        if not melted_candidates:
            return []
        melted_price = float(
            max(melted_candidates, key=lambda row: _to_utc(row.created_at)).price
        )

        certs = [
            row
            for row in cert_rows
            if row.created_at is not None and _to_utc(row.created_at) <= as_of
        ]
        certs.sort(key=lambda row: _to_utc(row.created_at))
        certs = certs[-self.ime_lookback :]

        points: list[DatedValue] = []
        for row in certs:
            grams = _grams_per_contract(row.contract_size, row.contract_size_unit)
            if grams is None or row.price_last is None or row.price_last <= 0:
                continue
            cert_per_gram = float(row.price_last) / grams
            try:
                report = calculate_ime_certificate_spread(
                    cert_per_gram, melted_price
                )
            except ValueError:
                continue
            # Both directions are priced on the same fine-gold basis (the
            # helper applies the 995/750 assay uplift); the feature is the
            # better executable spread after fees, signed.
            spread = max(
                report["buy_melted_sell_cert"]["net_spread_pct"],
                report["buy_cert_sell_melted"]["net_spread_pct"],
            )
            points.append(
                DatedValue(as_of=_to_utc(row.created_at), value=float(spread))
            )
        points.sort(key=lambda item: item.as_of)
        return points[-self.history_limit :]

    def _slice_fund_pnav(
        self, rows: list[Any], as_of: datetime
    ) -> list[DatedValue]:
        if not self.fund_symbol:
            return []
        points: list[DatedValue] = []
        placeholder_rows: list[tuple[Any, ...]] = []
        for row in rows:
            if row.date is None:
                continue
            observed = _to_utc(row.date)
            if observed > as_of:
                continue

            nav_raw = getattr(row, "nav_per_unit", None)
            price_raw = getattr(row, "market_price", None)
            try:
                nav = float(nav_raw) if nav_raw is not None else None
                price = float(price_raw) if price_raw is not None else None
            except (TypeError, ValueError):
                nav = price = None
            if nav is None or price is None or nav <= 0 or price <= 0:
                # A missing quote was historically persisted as 0.0, which
                # would otherwise surface as an exact 0% premium.
                placeholder_rows.append(
                    (row.symbol, nav_raw, price_raw, row.date, row.bubble_pct)
                )
                continue
            if price == nav:
                # ``NAV == price`` with the column default is the placeholder
                # written when the fund had no independent market quote; a
                # genuine 0.00% premium is indistinguishable and is treated as
                # missing rather than as a signal.
                placeholder_rows.append(
                    (row.symbol, nav, price, row.date, row.bubble_pct)
                )
                continue

            # Recompute from the two primary fields instead of trusting a
            # possibly-defaulted ``bubble_pct`` column.
            premium_pct = (price - nav) / nav * 100.0
            points.append(DatedValue(as_of=observed, value=float(premium_pct)))

        if placeholder_rows:
            sample = placeholder_rows[:3]
            logger.debug(
                "fund P/NAV skipped %d placeholder rows (symbol, nav, price, date, bubble): %s",
                len(placeholder_rows),
                sample,
            )
        points.sort(key=lambda item: item.as_of)
        return points[-self.history_limit :]

    def _slice_cot(
        self, rows: list[Any], as_of: datetime
    ) -> list[DatedValue]:
        """Percentile of the current net vs history **as of that report week**.

        The stored ``managed_money_net_percentile`` is computed at sync time and
        may include later reports, so it is not used here; the percentile is
        recomputed from the rows at or before ``as_of``.
        """
        ordered = [
            row
            for row in rows
            if row.report_date is not None and row.report_date <= as_of.date()
        ]
        ordered.sort(key=lambda row: row.report_date)
        ordered = ordered[-self.cot_history_limit :]
        nets = [
            float(row.managed_money_net)
            for row in ordered
            if row.managed_money_net is not None
        ]
        if not nets:
            return []
        current = nets[-1]
        percentile = sum(1 for net in nets if net <= current) / len(nets) * 100.0
        latest_date = ordered[-1].report_date
        observed = (
            datetime.combine(latest_date, datetime.min.time(), tzinfo=UTC)
            if not isinstance(latest_date, datetime)
            else _to_utc(latest_date)
        )
        return [DatedValue(as_of=observed, value=round(percentile, 2))]

    def _slice_real_yield(
        self, rows: list[Any], as_of: datetime
    ) -> list[DatedValue]:
        points: list[DatedValue] = []
        for row in rows:
            if row.as_of is None or row.value is None:
                continue
            observed = _to_utc(row.as_of)
            if observed > as_of:
                continue
            points.append(DatedValue(as_of=observed, value=float(row.value)))
        points.sort(key=lambda item: item.as_of)
        return points[-1:]

    def _slice_events(
        self, raw: _RawSeries, as_of: datetime
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split calendar rows into *past* (post-print window) and *scheduled*.

        Both lists carry ``known_at`` — the provenance stamp that says when the
        schedule became known — so the pure layer can refuse rows revealed or
        rescheduled after ``as_of``.
        """
        target = as_of.date()
        horizon_end = target + timedelta(days=self.event_horizon_days)
        past: list[dict[str, Any]] = []
        scheduled: list[dict[str, Any]] = []

        for rows in (raw.calendar, raw.iran):
            dated: list[tuple[date, dict[str, Any]]] = []
            for row in rows:
                event_date = getattr(row, "event_date", None)
                if not isinstance(event_date, date):
                    continue
                known_at = _event_known_at(row)
                payload = {
                    "event_date": event_date.isoformat(),
                    "category": getattr(row, "category", None),
                    "is_high_volatility": bool(
                        getattr(row, "is_high_volatility", False)
                    ),
                    "known_at": known_at,
                    "first_seen_at": _event_first_seen_at(row),
                }
                dated.append((event_date, payload))
            # Newest first (the SQL order), capped at ``event_limit`` past rows.
            dated.sort(key=lambda item: item[0], reverse=True)
            for event_date, payload in dated[: self.event_limit]:
                if event_date <= target:
                    past.append(payload)
                elif event_date <= horizon_end:
                    scheduled.append(payload)

        return past, scheduled


def _configured_event_horizon_days() -> int:
    """Forward-looking event horizon from the app config (safe fallback)."""
    try:
        from core.config import get_settings

        return int(get_settings().gold_event_horizon_days)
    except Exception:  # pragma: no cover - config fallback is deliberately safe
        return DEFAULT_EVENT_HORIZON_DAYS


__all__ = [
    "DEFAULT_AED_SYMBOL",
    "DEFAULT_COIN_SYMBOL",
    "DEFAULT_FEATURE_SYMBOL",
    "DEFAULT_MELTED_SYMBOL",
    "DatabaseGoldFeatureProvider",
    "GoldFeatureProvider",
]
