"""STEP 7B — gold features: leakage, real-table sourcing, non-gold stability.

The gold feature block is built by ``services.gold.features`` (pure, no I/O) and
fed by ``services.gold.feature_source.DatabaseGoldFeatureProvider`` (real
tables, ``as_of`` bounded).  These tests pin three contracts:

* every feature value at ``t`` is unchanged when rows after ``t`` are altered,
* a missing source yields ``None``/NaN plus a missing flag — never a number,
* the stock extractor's output is byte-for-byte unchanged by the gold wiring.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from services.gold.features import (
    GOLD_FEATURE_NAMES,
    DatedValue,
    GoldFeatureInputs,
    compute_gold_features,
    normalize_gold_features,
)
from services.signal_feature_pipeline import SignalFeaturePipeline

AS_OF = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def _dv(days_ago: float, value: float) -> DatedValue:
    return DatedValue(as_of=AS_OF - timedelta(days=days_ago), value=value)


def _bubble_series(count: int = 32) -> list[DatedValue]:
    # At least the configured 30 observations, oldest first, so the z-score
    # has a real sample.
    return [_dv(float(count - i), 10.0 + i) for i in range(count)]


def _future(series: list[DatedValue], offset: float = 500.0) -> list[DatedValue]:
    """Copies of ``series`` plus scrambled rows strictly after ``AS_OF``."""
    future = [
        DatedValue(as_of=AS_OF + timedelta(days=1), value=offset),
        DatedValue(as_of=AS_OF + timedelta(days=2), value=-offset),
        DatedValue(as_of=AS_OF + timedelta(days=3), value=offset * 2),
    ]
    return list(series) + future


def _inputs(**kwargs) -> GoldFeatureInputs:
    return GoldFeatureInputs(**kwargs)


@pytest.mark.parametrize(
    ("feature", "kwargs", "expected"),
    [
        (
            "gold_bubble_zscore",
            {"coin_bubble_pct": _bubble_series()},
            15.5 / math.sqrt(85.25),  # n=32, values 10..41, current=41
        ),
        (
            "gold_ime_spread_pct",
            {"ime_spread_pct": [_dv(2, 1.0), _dv(0, 2.5)]},
            2.5,
        ),
        (
            "gold_fund_pnav_pct",
            {"fund_pnav_pct": [_dv(1, -1.5), _dv(0, -2.25)]},
            -2.25,
        ),
        (
            "gold_cot_percentile",
            {"cot_percentile": [_dv(7, 70.0), _dv(0, 85.0)]},
            85.0,
        ),
        (
            "gold_real_yield",
            {"real_yield": [_dv(1, 0.8), _dv(0, 0.9)]},
            0.9,
        ),
        (
            "gold_aed_spread_pct",
            {"aed_spread_pct": [_dv(1, 1.1), _dv(0, 1.4)]},
            1.4,
        ),
        (
            "gold_event_window",
            {
                "high_vol_events": [
                    {
                        "event_date": AS_OF.date().isoformat(),
                        "category": "CPI",
                        "is_high_volatility": True,
                    }
                ]
            },
            1.0,
        ),
    ],
)
def test_feature_value_ignores_data_after_as_of(feature, kwargs, expected) -> None:
    """Each feature is leak-free: post-``t`` rows cannot move the value at ``t``."""
    clean = compute_gold_features(_inputs(**kwargs), AS_OF)
    if feature == "gold_event_window":
        future_events = [
            {
                "event_date": (AS_OF.date() + timedelta(days=days)).isoformat(),
                "category": "FOMC",
                "is_high_volatility": True,
            }
            for days in (1, 2, 3)
        ]
        dirty_inputs = _inputs(high_vol_events=kwargs["high_vol_events"] + future_events)
    else:
        dirty_inputs = _inputs(**{name: _future(rows) for name, rows in kwargs.items()})
    dirty = compute_gold_features(dirty_inputs, AS_OF)

    assert clean.values[feature] == pytest.approx(expected)
    assert dirty.values == clean.values
    assert dirty.missing == clean.missing


def test_event_window_ignores_future_calendar_rows() -> None:
    """A future CPI/FOMC entry is a *later* event and must not flag ``t``."""
    events = [
        {
            "event_date": (AS_OF.date() + timedelta(days=1)).isoformat(),
            "category": "FOMC",
            "is_high_volatility": True,
        }
    ]
    result = compute_gold_features(GoldFeatureInputs(high_vol_events=events), AS_OF)

    assert result.values["gold_event_window"] == 0.0


def test_empty_sources_yield_none_and_missing_flags() -> None:
    result = compute_gold_features(GoldFeatureInputs(), AS_OF)

    assert result.values == dict.fromkeys(GOLD_FEATURE_NAMES)
    assert result.missing == list(GOLD_FEATURE_NAMES)


def test_bubble_zscore_needs_history_and_variance() -> None:
    too_short = compute_gold_features(GoldFeatureInputs(coin_bubble_pct=[_dv(1, 1.0), _dv(0, 2.0)]), AS_OF)
    assert too_short.values["gold_bubble_zscore"] is None
    assert "gold_bubble_zscore" in too_short.missing

    flat = compute_gold_features(
        GoldFeatureInputs(coin_bubble_pct=[_dv(float(30 - i), 4.0) for i in range(30)]),
        AS_OF,
    )
    assert flat.values["gold_bubble_zscore"] is None
    assert "gold_bubble_zscore" in flat.missing


def test_bubble_zscore_requires_thirty_samples_by_default() -> None:
    """A 29-row sample is not enough history: report missing, not a z-score."""
    below = compute_gold_features(
        GoldFeatureInputs(coin_bubble_pct=_bubble_series(count=29)),
        AS_OF,
    )
    enough = compute_gold_features(
        GoldFeatureInputs(coin_bubble_pct=_bubble_series(count=30)),
        AS_OF,
    )

    assert below.values["gold_bubble_zscore"] is None
    assert "gold_bubble_zscore" in below.missing
    assert enough.values["gold_bubble_zscore"] is not None
    assert "gold_bubble_zscore" not in enough.missing


def test_normalize_keeps_missing_as_nan_not_zero() -> None:
    normalized = normalize_gold_features(dict.fromkeys(GOLD_FEATURE_NAMES))

    assert set(normalized) == set(GOLD_FEATURE_NAMES)
    assert all(math.isnan(value) for value in normalized.values())


# ── Extension point: SignalFeaturePipeline._extract_gold_features ──────────


def _price_data() -> dict:
    closes = [100 + i for i in range(21)]
    return {
        "closes": closes,
        "highs": [c + 1.5 for c in closes],
        "lows": [c - 1.5 for c in closes],
        "volumes": [1000 + 10 * i for i in range(21)],
        "values": [c * 1000 for c in closes],
        "last_price": closes[-1],
        "as_of": AS_OF,
    }


class _FakeProvider:
    def __init__(self, inputs: GoldFeatureInputs) -> None:
        self.inputs = inputs
        self.calls: list[datetime] = []
        self.symbols: list[str | None] = []

    async def load(
        self, as_of: datetime, symbol: str | None = None
    ) -> GoldFeatureInputs:
        self.calls.append(as_of)
        self.symbols.append(symbol)
        return self.inputs


@pytest.mark.asyncio
async def test_gold_extractor_appends_features_from_provider() -> None:
    inputs = GoldFeatureInputs(
        coin_bubble_pct=_bubble_series(),
        ime_spread_pct=[_dv(0, 2.5)],
        fund_pnav_pct=[_dv(0, -2.25)],
        cot_percentile=[_dv(0, 85.0)],
        real_yield=[_dv(0, 0.9)],
        aed_spread_pct=[_dv(0, 1.4)],
        high_vol_events=[
            {
                "event_date": AS_OF.date().isoformat(),
                "category": "CPI",
                "is_high_volatility": True,
            }
        ],
    )
    provider = _FakeProvider(inputs)
    pipeline = SignalFeaturePipeline(market="gold", gold_feature_provider=provider)

    features = await pipeline.extract(
        "XAUUSD", "gold", _price_data(), None, {"buy_real_volume": 1, "buy_legal_volume": 1}
    )

    assert provider.calls == [AS_OF]
    assert provider.symbols == ["XAUUSD"]
    assert features.feature_names[-len(GOLD_FEATURE_NAMES) :] == list(GOLD_FEATURE_NAMES)
    gold_values = dict(
        zip(
            GOLD_FEATURE_NAMES,
            features.vector[-len(GOLD_FEATURE_NAMES) :],
            strict=True,
        )
    )
    assert gold_values["gold_ime_spread_pct"] == pytest.approx(0.5)
    assert gold_values["gold_real_yield"] == pytest.approx(0.18)
    assert gold_values["gold_event_window"] == pytest.approx(1.0)
    assert "gold_missing" not in features.metadata


@pytest.mark.asyncio
async def test_gold_extractor_flags_missing_instead_of_fabricating() -> None:
    provider = _FakeProvider(GoldFeatureInputs())
    pipeline = SignalFeaturePipeline(market="gold", gold_feature_provider=provider)

    features = await pipeline.extract("XAUUSD", "gold", _price_data(), None, {})

    gold_values = features.vector[-len(GOLD_FEATURE_NAMES) :]
    assert all(math.isnan(value) for value in gold_values)
    assert features.metadata["gold_missing"] == list(GOLD_FEATURE_NAMES)


@pytest.mark.asyncio
async def test_gold_extractor_degrades_when_provider_raises() -> None:
    class _BrokenProvider:
        async def load(
            self, as_of: datetime, symbol: str | None = None
        ) -> GoldFeatureInputs:
            raise RuntimeError("database down")

    pipeline = SignalFeaturePipeline(market="gold", gold_feature_provider=_BrokenProvider())
    features = await pipeline.extract("XAUUSD", "gold", _price_data(), None, {})

    assert all(math.isnan(value) for value in features.vector[-len(GOLD_FEATURE_NAMES) :])
    assert features.metadata["gold_missing"] == list(GOLD_FEATURE_NAMES)


# ── Real-table provider ────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self):
        return self

    def all(self) -> list:
        return self._rows


class _FakeSession:
    """Answers each provider statement and records the ``as_of`` bound."""

    def __init__(self, rows_by_symbol: dict[str, list]) -> None:
        self.rows_by_symbol = rows_by_symbol
        self.statements: list = []

    async def execute(self, statement):
        self.statements.append(statement)
        params = statement.compile().params
        symbol = params.get("symbol_1")
        return _FakeResult(list(self.rows_by_symbol.get(str(symbol), [])))


def _snapshot_row(*, symbol: str, at: datetime, bubble: float | None, aed_gap: float | None):
    return SimpleNamespace(
        symbol=symbol,
        snapshot_at=at,
        bubble_pct=bubble,
        aed_gap_pct=aed_gap,
        usd_irt=None,
        aed_irt=None,
    )


@pytest.mark.asyncio
async def test_database_provider_reads_real_tables_and_drops_future_rows() -> None:
    from brsapi.models.commodity import GoldCoinPriceModel
    from brsapi.models.ime import ImeCertificateModel
    from models.gold_macro import (
        GoldCotPositionModel,
        GoldEconomicCalendarEventModel,
        GoldIranManualEventModel,
        GoldMacroIndicatorModel,
    )
    from services.gold.feature_source import DatabaseGoldFeatureProvider
    from src.gold_desk.models import GoldFundNAVModel, GoldSnapshotModel

    coin_symbol = "IR_COIN_EMAMI"
    snapshot_rows = [
        _snapshot_row(
            symbol=coin_symbol,
            at=AS_OF - timedelta(hours=32 - i),
            bubble=8.0 + 0.25 * i,
            aed_gap=None,
        )
        for i in range(32)
    ] + [
        _snapshot_row(symbol=coin_symbol, at=AS_OF + timedelta(hours=1), bubble=999.0, aed_gap=None),
    ]
    aed_rows = [
        _snapshot_row(symbol="XAUUSD", at=AS_OF - timedelta(hours=1), bubble=None, aed_gap=1.25),
        _snapshot_row(symbol="XAUUSD", at=AS_OF + timedelta(hours=1), bubble=None, aed_gap=9.99),
    ]
    ime_rows = [
        SimpleNamespace(
            price_last=5_000_000.0,
            contract_size=1,
            contract_size_unit="g",
            contract_code="GOLD-CERT",
            created_at=AS_OF - timedelta(hours=1),
        ),
        SimpleNamespace(
            price_last=99_000_000.0,
            contract_size=1,
            contract_size_unit="g",
            contract_code="GOLD-CERT",
            created_at=AS_OF + timedelta(hours=1),
        ),
    ]
    melted_rows = [
        SimpleNamespace(symbol="IR_GOLD_18K", price=4_000_000.0, created_at=AS_OF - timedelta(hours=1)),
        SimpleNamespace(symbol="IR_GOLD_18K", price=1.0, created_at=AS_OF + timedelta(hours=1)),
    ]
    fund_rows = [
        SimpleNamespace(
            symbol="IR_GOLD_FUND",
            date=AS_OF - timedelta(days=1),
            nav_per_unit=100.0,
            market_price=98.25,
            bubble_pct=-1.75,
        ),
        SimpleNamespace(
            symbol="IR_GOLD_FUND",
            date=AS_OF + timedelta(days=1),
            nav_per_unit=100.0,
            market_price=108.0,
            bubble_pct=8.0,
        ),
    ]
    cot_rows = [
        SimpleNamespace(report_date=(AS_OF - timedelta(days=21)).date(), managed_money_net=500),
        SimpleNamespace(report_date=(AS_OF - timedelta(days=14)).date(), managed_money_net=1500),
        SimpleNamespace(report_date=(AS_OF - timedelta(days=7)).date(), managed_money_net=1000),
        SimpleNamespace(report_date=(AS_OF + timedelta(days=7)).date(), managed_money_net=10**9),
    ]
    macro_rows = [
        SimpleNamespace(indicator="FRED_DFII10", as_of=AS_OF - timedelta(days=1), value=0.9),
        SimpleNamespace(indicator="FRED_DFII10", as_of=AS_OF + timedelta(days=1), value=9.9),
    ]
    calendar_rows = [
        SimpleNamespace(event_date=AS_OF.date(), category="CPI", is_high_volatility=True),
        SimpleNamespace(
            event_date=(AS_OF + timedelta(days=2)).date(),
            category="FOMC",
            is_high_volatility=True,
        ),
    ]

    session = _FakeSession(
        {
            coin_symbol: snapshot_rows,
            "XAUUSD": aed_rows,
            "IR_GOLD_18K": melted_rows,
        }
    )
    provider = DatabaseGoldFeatureProvider(
        session_factory=None,
        session=session,
        fund_symbol="IR_GOLD_FUND",
    )

    # The provider also needs rows for entities without a ``symbol`` param.
    # ``execute`` dispatches on the queried entity, so widen the fake.
    entity_rows = {
        ImeCertificateModel: ime_rows,
        GoldCoinPriceModel: melted_rows,
        GoldFundNAVModel: fund_rows,
        GoldCotPositionModel: cot_rows,
        GoldMacroIndicatorModel: macro_rows,
        GoldSnapshotModel: snapshot_rows,
        GoldEconomicCalendarEventModel: calendar_rows,
        GoldIranManualEventModel: [],
    }

    async def execute(statement):
        session.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        params = statement.compile().params
        symbol = params.get("symbol_1")
        if entity is GoldSnapshotModel and symbol is not None:
            rows = session.rows_by_symbol.get(str(symbol), [])
        elif entity is GoldCoinPriceModel:
            rows = entity_rows[GoldCoinPriceModel]
        else:
            rows = entity_rows.get(entity, [])
        return _FakeResult(list(rows))

    session.execute = execute  # type: ignore[method-assign]

    inputs = await provider.load(AS_OF)
    result = compute_gold_features(inputs, AS_OF)

    assert result.values["gold_bubble_zscore"] is not None
    assert result.values["gold_aed_spread_pct"] == pytest.approx(1.25)
    assert result.values["gold_fund_pnav_pct"] == pytest.approx(-1.75)
    # 1000 against [500, 1000, 1500] → 2 of 3 at or below = 66.67 (2 dp).
    assert result.values["gold_cot_percentile"] == pytest.approx(66.67, abs=0.01)
    assert result.values["gold_real_yield"] == pytest.approx(0.9)
    assert result.values["gold_event_window"] == pytest.approx(1.0)
    assert result.values["gold_ime_spread_pct"] is not None
    assert result.values["gold_ime_spread_pct"] > 0
    assert result.missing == []


def test_post_t_shuffle_leaves_every_feature_unchanged() -> None:
    """Altering/shuffling rows after ``t`` cannot move any of the 7 values."""
    base = GoldFeatureInputs(
        coin_bubble_pct=_bubble_series(),
        ime_spread_pct=[_dv(2, 1.0), _dv(0, 2.5)],
        fund_pnav_pct=[_dv(1, -1.5), _dv(0, -2.25)],
        cot_percentile=[_dv(7, 70.0), _dv(0, 85.0)],
        real_yield=[_dv(1, 0.8), _dv(0, 0.9)],
        aed_spread_pct=[_dv(1, 1.1), _dv(0, 1.4)],
        high_vol_events=[
            {
                "event_date": AS_OF.date().isoformat(),
                "category": "CPI",
                "is_high_volatility": True,
            }
        ],
    )
    shuffled = GoldFeatureInputs(
        coin_bubble_pct=_future(base.coin_bubble_pct, offset=777.0),
        ime_spread_pct=_future(base.ime_spread_pct, offset=313.0),
        fund_pnav_pct=_future(base.fund_pnav_pct, offset=424.0),
        cot_percentile=_future(base.cot_percentile, offset=515.0),
        real_yield=_future(base.real_yield, offset=616.0),
        aed_spread_pct=_future(base.aed_spread_pct, offset=717.0),
        high_vol_events=base.high_vol_events
        + [
            {
                "event_date": (AS_OF.date() + timedelta(days=days)).isoformat(),
                "category": "FOMC",
                "is_high_volatility": True,
            }
            for days in (1, 5, 9)
        ],
    )

    clean = compute_gold_features(base, AS_OF)
    dirty = compute_gold_features(shuffled, AS_OF)

    assert list(clean.values) == list(GOLD_FEATURE_NAMES)
    assert dirty.values == clean.values
    assert dirty.missing == clean.missing


# ── Non-gold stability (before/after) ─────────────────────────────────────

_GOLDEN_STOCK_FEATURES = (
    '{"feature_names": ["return_1d", "return_5d", "return_10d", "return_20d", '
    '"volatility_5d", "volatility_10d", "volatility_20d", "rsi_14", '
    '"ma_cross_5_20", "volume_ratio", "value_change_1d", "real_buy_ratio", '
    '"atr_normalized", "price_position_20d", "trend_strength"], '
    '"metadata": {"closes_count": 21, "last_price": 120}, '
    '"vector": [0.008403361344537815, 0.043478260869565216, 0.09090909090909091, '
    "0.2, 0.00010334116917432025, 0.0002193854334128994, "
    "0.0004838560440609841, 1.0, 0.06787330316742081, 0.21357466063348415, "
    "0.008403361344537815, 0.6, 0.125, 0.9318181818181818, 1.0]}"
)


@pytest.mark.asyncio
async def test_stock_features_are_byte_for_byte_unchanged() -> None:
    pipeline = SignalFeaturePipeline(market="stock")
    features = await pipeline.extract(
        "TEST", "stock", _price_data(), None, {"buy_real_volume": 60, "buy_legal_volume": 40}
    )

    payload = json.dumps(
        {
            "vector": features.vector,
            "feature_names": features.feature_names,
            "metadata": features.metadata,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    assert payload == _GOLDEN_STOCK_FEATURES


# ── STEP 7B-FIX 1 — no cross-fund P/NAV fallback ──────────────────────────


class _EntitySession:
    """Fake session answering per queried entity (SQL bounds NOT applied).

    The provider re-filters every row in Python, so returning rows from
    before *and* after ``as_of`` exercises the point-in-time contract.
    """

    def __init__(self, rows_by_entity: dict[object, list]) -> None:
        self.rows_by_entity = rows_by_entity
        self.statements: list = []

    async def execute(self, statement):
        self.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        return _FakeResult(list(self.rows_by_entity.get(entity, [])))

    def entities(self) -> list[object]:
        return [stmt.column_descriptions[0]["entity"] for stmt in self.statements]


def _provider_rows() -> dict[object, list]:
    from brsapi.models.commodity import GoldCoinPriceModel
    from brsapi.models.ime import ImeCertificateModel
    from models.gold_macro import (
        GoldCotPositionModel,
        GoldEconomicCalendarEventModel,
        GoldIranManualEventModel,
        GoldMacroIndicatorModel,
    )
    from src.gold_desk.models import GoldFundNAVModel, GoldSnapshotModel

    return {
        GoldSnapshotModel: [
            _snapshot_row(
                symbol="IR_COIN_EMAMI",
                at=AS_OF - timedelta(hours=24 - i),
                bubble=8.0 + 0.25 * i,
                aed_gap=None,
            )
            for i in range(24)
        ],
        GoldCoinPriceModel: [
            SimpleNamespace(
                symbol="IR_GOLD_18K",
                price=4_000_000.0,
                created_at=AS_OF - timedelta(hours=1),
            )
        ],
        ImeCertificateModel: [
            SimpleNamespace(
                price_last=5_000_000.0,
                contract_size=1,
                contract_size_unit="g",
                contract_code="GOLD-CERT",
                created_at=AS_OF - timedelta(hours=1),
            )
        ],
        GoldFundNAVModel: [
            SimpleNamespace(
                symbol="IR_GOLD_FUND",
                date=AS_OF - timedelta(days=1),
                nav_per_unit=100.0,
                market_price=98.25,
                bubble_pct=-1.75,
            )
        ],
        GoldCotPositionModel: [
            SimpleNamespace(
                report_date=(AS_OF - timedelta(days=7)).date(), managed_money_net=1000
            )
        ],
        GoldMacroIndicatorModel: [
            SimpleNamespace(
                indicator="FRED_DFII10", as_of=AS_OF - timedelta(days=1), value=0.9
            )
        ],
        GoldEconomicCalendarEventModel: [
            SimpleNamespace(
                event_date=AS_OF.date(),
                category="CPI",
                is_high_volatility=True,
                fetched_at=AS_OF - timedelta(days=5),
                created_at=AS_OF - timedelta(days=5),
            )
        ],
        GoldIranManualEventModel: [],
    }


@pytest.mark.asyncio
async def test_fund_pnav_is_missing_when_no_fund_symbol_is_pinned() -> None:
    """``fund_symbol=None`` must not fall back to the latest row across funds.

    A cross-fund fallback silently mixes different funds' P/NAV series into
    one feature; the contract is an explicit missing flag instead.
    """
    from services.gold.feature_source import DatabaseGoldFeatureProvider
    from src.gold_desk.models import GoldFundNAVModel

    session = _EntitySession(_provider_rows())
    provider = DatabaseGoldFeatureProvider(session=session, fund_symbol=None)

    inputs = await provider.load(AS_OF)
    result = compute_gold_features(inputs, AS_OF)

    assert inputs.fund_pnav_pct == []
    assert result.values["gold_fund_pnav_pct"] is None
    assert "gold_fund_pnav_pct" in result.missing
    # No fund NAV table is even queried without a pinned fund.
    assert GoldFundNAVModel not in session.entities()


@pytest.mark.asyncio
async def test_fund_pnav_reads_only_the_pinned_fund() -> None:
    from services.gold.feature_source import DatabaseGoldFeatureProvider
    from src.gold_desk.models import GoldFundNAVModel

    rows = _provider_rows()
    rows[GoldFundNAVModel] = [
        SimpleNamespace(
            symbol="IR_GOLD_FUND",
            date=AS_OF - timedelta(days=1),
            nav_per_unit=100.0,
            market_price=98.25,
            bubble_pct=-1.75,
        )
    ]
    session = _EntitySession(rows)
    provider = DatabaseGoldFeatureProvider(session=session, fund_symbol="IR_GOLD_FUND")

    inputs = await provider.load(AS_OF)
    result = compute_gold_features(inputs, AS_OF)

    fund_statements = [
        stmt
        for stmt in session.statements
        if stmt.column_descriptions[0]["entity"] is GoldFundNAVModel
    ]
    assert len(fund_statements) == 1
    assert fund_statements[0].compile().params["symbol_1"] == "IR_GOLD_FUND"
    assert result.values["gold_fund_pnav_pct"] == pytest.approx(-1.75)
    assert "gold_fund_pnav_pct" not in result.missing


@pytest.mark.asyncio
async def test_fund_pnav_ignores_default_zero_market_price() -> None:
    """A persisted row with ``market_price=0`` is a missing quote, not 0% P/NAV.

    ``_persist_fund_nav`` used to coerce a missing price to ``0.0`` and a
    missing bubble to ``0.0``, which made every fund look perfectly priced.
    The provider must refuse those rows and report the feature as missing.
    """
    from services.gold.feature_source import DatabaseGoldFeatureProvider
    from src.gold_desk.models import GoldFundNAVModel

    rows = _provider_rows()
    rows[GoldFundNAVModel] = [
        SimpleNamespace(
            symbol="IR_GOLD_FUND",
            date=AS_OF - timedelta(days=1),
            nav_per_unit=1_868_910.0,
            market_price=0.0,
            bubble_pct=0.0,
        )
    ]
    session = _EntitySession(rows)
    provider = DatabaseGoldFeatureProvider(
        session=session, fund_symbol="IR_GOLD_FUND"
    )

    inputs = await provider.load(AS_OF)
    result = compute_gold_features(inputs, AS_OF)

    assert inputs.fund_pnav_pct == []
    assert result.values["gold_fund_pnav_pct"] is None
    assert "gold_fund_pnav_pct" in result.missing


@pytest.mark.asyncio
async def test_fund_pnav_ignores_nav_equals_price_placeholder() -> None:
    """``NAV == price`` with a stored 0 bubble is the default placeholder."""
    from services.gold.feature_source import DatabaseGoldFeatureProvider
    from src.gold_desk.models import GoldFundNAVModel

    rows = _provider_rows()
    rows[GoldFundNAVModel] = [
        SimpleNamespace(
            symbol="IR_GOLD_FUND",
            date=AS_OF - timedelta(days=1),
            nav_per_unit=100.0,
            market_price=100.0,
            bubble_pct=0.0,
        )
    ]
    session = _EntitySession(rows)
    provider = DatabaseGoldFeatureProvider(
        session=session, fund_symbol="IR_GOLD_FUND"
    )

    inputs = await provider.load(AS_OF)
    result = compute_gold_features(inputs, AS_OF)

    assert inputs.fund_pnav_pct == []
    assert result.values["gold_fund_pnav_pct"] is None
    assert "gold_fund_pnav_pct" in result.missing


# ── STEP 7B-FIX 2 — forward-looking event feature ──────────────────────────


def _scheduled_event(
    days_ahead: float,
    *,
    known_days_ago: float | None = 1.0,
    first_seen_days_ago: float | None | str = "same",
    category: str = "CPI",
    high_vol: bool = True,
) -> dict:
    event: dict = {
        "event_date": (AS_OF.date() + timedelta(days=days_ahead)).isoformat(),
        "category": category,
        "is_high_volatility": high_vol,
    }
    if known_days_ago is not None:
        event["known_at"] = AS_OF - timedelta(days=known_days_ago)
    if first_seen_days_ago == "same":
        first_seen_days_ago = known_days_ago
    if first_seen_days_ago is not None:
        event["first_seen_at"] = AS_OF - timedelta(days=first_seen_days_ago)
    return event


def test_forward_event_feature_flags_event_inside_horizon() -> None:
    result = compute_gold_features(
        GoldFeatureInputs(scheduled_events=[_scheduled_event(2)]),
        AS_OF,
        event_horizon_days=7,
    )

    assert result.values["gold_event_in_next_N_days"] == 1.0
    assert "gold_event_in_next_N_days" not in result.missing


def test_forward_event_feature_is_zero_outside_horizon() -> None:
    result = compute_gold_features(
        GoldFeatureInputs(scheduled_events=[_scheduled_event(30)]),
        AS_OF,
        event_horizon_days=7,
    )

    assert result.values["gold_event_in_next_N_days"] == 0.0


def test_forward_event_feature_ignores_low_volatility_events() -> None:
    result = compute_gold_features(
        GoldFeatureInputs(
            scheduled_events=[_scheduled_event(2, category="SPEECH", high_vol=False)]
        ),
        AS_OF,
        event_horizon_days=7,
    )

    assert result.values["gold_event_in_next_N_days"] == 0.0


def test_forward_event_feature_ignores_rows_revealed_after_as_of() -> None:
    """A row first seen after ``t`` cannot move the value at ``t``."""
    clean = compute_gold_features(
        GoldFeatureInputs(scheduled_events=[_scheduled_event(30)]),
        AS_OF,
        event_horizon_days=7,
    )
    dirty = compute_gold_features(
        GoldFeatureInputs(
            scheduled_events=[
                _scheduled_event(30),
                _scheduled_event(2, known_days_ago=-1),  # revealed after t
            ]
        ),
        AS_OF,
        event_horizon_days=7,
    )

    assert clean.values["gold_event_in_next_N_days"] == 0.0
    assert dirty.values["gold_event_in_next_N_days"] == 0.0
    assert dirty.values == clean.values
    assert dirty.missing == clean.missing


def test_forward_event_feature_ignores_event_rescheduled_after_as_of() -> None:
    """A schedule refreshed after ``t`` is not used at ``t``.

    The stored date may have been *changed* after ``t``; the old date is
    unknowable, so the window state at ``t`` is reported as missing instead
    of a fabricated 0/1.
    """
    rescheduled = _scheduled_event(2, known_days_ago=-1, first_seen_days_ago=5)

    result = compute_gold_features(
        GoldFeatureInputs(scheduled_events=[rescheduled]),
        AS_OF,
        event_horizon_days=7,
    )

    assert result.values["gold_event_in_next_N_days"] is None
    assert "gold_event_in_next_N_days" in result.missing


def test_forward_event_feature_is_missing_without_calendar_rows() -> None:
    result = compute_gold_features(GoldFeatureInputs(), AS_OF)

    assert result.values["gold_event_in_next_N_days"] is None
    assert "gold_event_in_next_N_days" in result.missing


def test_past_event_window_ignores_rows_revealed_after_as_of() -> None:
    """An event inserted after ``t`` must not flag the post-print window."""
    revealed_late = {
        "event_date": AS_OF.date().isoformat(),
        "category": "CPI",
        "is_high_volatility": True,
        "known_at": AS_OF + timedelta(days=1),
    }

    result = compute_gold_features(
        GoldFeatureInputs(high_vol_events=[revealed_late]), AS_OF
    )

    assert result.values["gold_event_window"] == 0.0


@pytest.mark.asyncio
async def test_database_provider_marks_scheduled_events_with_known_at() -> None:
    """The provider attaches provenance so the pure layer can police leaks."""
    from models.gold_macro import GoldEconomicCalendarEventModel
    from services.gold.feature_source import DatabaseGoldFeatureProvider

    rows = _provider_rows()
    rows[GoldEconomicCalendarEventModel] = [
        SimpleNamespace(
            event_date=AS_OF.date(),
            category="CPI",
            is_high_volatility=True,
            fetched_at=AS_OF - timedelta(days=5),
            created_at=AS_OF - timedelta(days=5),
        ),
        SimpleNamespace(
            event_date=(AS_OF.date() + timedelta(days=2)),
            category="FOMC",
            is_high_volatility=True,
            fetched_at=AS_OF - timedelta(days=1),
            created_at=AS_OF - timedelta(days=1),
        ),
    ]
    session = _EntitySession(rows)
    provider = DatabaseGoldFeatureProvider(session=session, fund_symbol="IR_GOLD_FUND")

    inputs = await provider.load(AS_OF)
    result = compute_gold_features(inputs, AS_OF, event_horizon_days=7)

    scheduled = inputs.scheduled_events
    assert len(scheduled) == 1
    assert scheduled[0]["event_date"] == (AS_OF.date() + timedelta(days=2)).isoformat()
    assert scheduled[0]["known_at"] is not None
    assert scheduled[0]["first_seen_at"] is not None
    # The past print stays in the post-print window input.
    assert len(inputs.high_vol_events) == 1
    assert result.values["gold_event_window"] == 1.0
    assert result.values["gold_event_in_next_N_days"] == 1.0


# ── STEP 7B-FIX 3 — cache + batched loading ───────────────────────────────


@pytest.mark.asyncio
async def test_provider_cache_serves_repeat_point_without_new_queries() -> None:
    from services.gold.feature_source import DatabaseGoldFeatureProvider

    session = _EntitySession(_provider_rows())
    provider = DatabaseGoldFeatureProvider(session=session, fund_symbol="IR_GOLD_FUND")

    first = await provider.load(AS_OF, "XAUUSD")
    queries_after_first = len(session.statements)
    second = await provider.load(AS_OF, "XAUUSD")

    assert queries_after_first > 0
    assert len(session.statements) == queries_after_first
    assert compute_gold_features(second, AS_OF).values == compute_gold_features(
        first, AS_OF
    ).values


@pytest.mark.asyncio
async def test_provider_cache_is_keyed_by_symbol() -> None:
    from services.gold.feature_source import DatabaseGoldFeatureProvider

    session = _EntitySession(_provider_rows())
    provider = DatabaseGoldFeatureProvider(session=session, fund_symbol="IR_GOLD_FUND")

    await provider.load(AS_OF, "XAUUSD")
    queries = len(session.statements)
    await provider.load(AS_OF, "IR_GOLD_18K")

    assert len(session.statements) > queries


@pytest.mark.asyncio
async def test_provider_load_many_uses_constant_query_count() -> None:
    """A backtest over many points must not issue ~8 queries per point."""
    from services.gold.feature_source import DatabaseGoldFeatureProvider

    points = [AS_OF - timedelta(days=i) for i in range(10)]
    session = _EntitySession(_provider_rows())
    provider = DatabaseGoldFeatureProvider(session=session, fund_symbol="IR_GOLD_FUND")

    results = await provider.load_many(points, "XAUUSD")

    assert len(results) == len(points)
    # One query per source (9 tables) — not 9 per point.
    assert len(session.statements) <= 12


@pytest.mark.asyncio
async def test_provider_load_many_matches_single_loads() -> None:
    """Batched slicing must equal the point-by-point reference result."""
    from services.gold.feature_source import DatabaseGoldFeatureProvider

    points = [AS_OF - timedelta(days=i) for i in range(6)]
    batched = await DatabaseGoldFeatureProvider(
        session=_EntitySession(_provider_rows()), fund_symbol="IR_GOLD_FUND"
    ).load_many(points, "XAUUSD")

    reference_provider = DatabaseGoldFeatureProvider(
        session=_EntitySession(_provider_rows()), fund_symbol="IR_GOLD_FUND"
    )
    for point in points:
        single = await reference_provider.load(point, "XAUUSD")
        assert compute_gold_features(batched[point], point).values == (
            compute_gold_features(single, point).values
        )
