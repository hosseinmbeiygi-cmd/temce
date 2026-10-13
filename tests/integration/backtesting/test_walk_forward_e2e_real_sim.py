"""TD-02 — end-to-end Walk-Forward integration with the *real* engine.

Unlike ``tests/unit/backtesting/test_walk_forward_purged.py`` (which injects a
deterministic fake simulator and monkeypatched collaborators), this module
exercises the un-mocked production path end to end:

    real ORM/Repository  ->  real BacktestSimulator + Broker cost model
                         ->  real WalkForwardOptimizer.optimize()

The market data is seeded into an **isolated in-memory SQLite database** through
the project's own ``QuoteRepository`` / ``QuoteModel`` ORM layer and read back
through the same repository, so no live/production database is ever touched.

Coverage (TD-02):
1. Real data ingestion/retrieval via the Repository & ORM layer.
2. Un-mocked ``BacktestSimulator`` execution with real commission + slippage.
3. Full walk-forward pipeline over 3 folds and a 2-combo grid, asserting the
   aggregate metric contract (``is_sharpes``, ``oos_sharpes``,
   ``walk_forward_efficiency``, ``deflated_sharpe``) and per-fold trade logs.
4. Purge/embargo boundary integrity and complete fixture/engine cleanup.
"""

from __future__ import annotations

import math
from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backtesting.engine.broker import Broker
from backtesting.engine.simulator import BacktestSimulator
from backtesting.optimization.walk_forward import WalkForwardOptimizer
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
from domain.market_data.quote import Quote
from models.quote import QuoteModel
from repositories.quote_repository import QuoteRepository

# ── Scenario constants ───────────────────────────────────────────────────────

SYMBOL = "XAUUSD"
INSTRUMENT_ID = "XAUUSD"
N_BARS = 1500
BASE_PRICE = 2000.0
CAPITAL = 10_000_000.0
SIZING_VALUE = 1_000_000.0

WINDOWS = 3
TRAIN_RATIO = 0.7
EMBARGO_PCT = 0.01
PURGE_PCT = 0.01

WINDOW_SIZE = N_BARS // WINDOWS
SPLIT_INDEX = int(WINDOW_SIZE * TRAIN_RATIO)
PURGE_BARS = max(1, int(N_BARS * PURGE_PCT))
EMBARGO_BARS = max(1, int(N_BARS * EMBARGO_PCT))
EXPECTED_OOS_OBS = WINDOW_SIZE - (SPLIT_INDEX + EMBARGO_BARS) - 1

PARAM_GRID: dict[str, list] = {
    "fast_period": [5],
    "slow_period": [20, 30],
    "instrument_id": [SYMBOL],
    "sizing_value": [SIZING_VALUE],
}
N_COMBOS = math.prod(len(v) for v in PARAM_GRID.values())

START_DATE = date(2024, 1, 1)


# ── Synthetic-but-plausible gold series ──────────────────────────────────────


def _gold_close_series(n: int) -> list[float]:
    """Deterministic gold-like walk: mild uptrend + dominant cycle + micro noise.

    The 40-bar cycle guarantees regular fast/slow MA crossovers, so the real
    simulator produces actual fills rather than a flat equity curve.
    """
    series: list[float] = []
    for i in range(n):
        drift = 0.02 * i
        wave = 25.0 * math.sin(2 * math.pi * i / 40.0)
        micro = 3.0 * math.sin(2 * math.pi * i / 7.0)
        series.append(BASE_PRICE + drift + wave + micro)
    return series


def _make_quote(index: int, price: float, prev_close: float) -> Quote:
    timestamp = datetime.combine(START_DATE, datetime.min.time()) + timedelta(hours=index)
    return Quote(
        id=f"{INSTRUMENT_ID}-{index:05d}",
        instrument_id=INSTRUMENT_ID,
        symbol=SYMBOL,
        price_open=prev_close,
        price_high=max(prev_close, price) + 0.5,
        price_low=min(prev_close, price) - 0.5,
        price_close=price,
        price_last=price,
        ask_price=price + 0.3,
        bid_price=price - 0.3,
        volume=100_000 + (index % 50) * 100,
        time=timestamp.strftime("%H:%M"),
        date=timestamp.date().isoformat(),
        timeframe="1h",
        data_source="test",
    )


def _quotes_to_feed(quotes: list[Quote]) -> list[dict]:
    """Adapt repository domain objects to the simulator's bar-dict contract."""
    feed: list[dict] = []
    for q in quotes:
        feed.append(
            {
                "timestamp": datetime.fromisoformat(f"{q.date}T{q.time}"),
                "instrument_id": q.instrument_id,
                "open": q.price_open,
                "high": q.price_high,
                "low": q.price_low,
                "close": q.price_close,
                "volume": q.volume,
            }
        )
    return feed


# ── Isolated in-memory DB fixture (real ORM + Repository) ────────────────────


@pytest_asyncio.fixture
async def seeded_gold_db() -> AsyncGenerator[tuple[AsyncSession, QuoteRepository, object], None]:
    """Seed N_BARS of gold bars into an isolated in-memory SQLite database.

    Only the ``quotes`` table is created (via the ORM table object) so unrelated
    PostgreSQL-only column types elsewhere in the metadata cannot break SQLite
    compilation.  The repository is the real ``QuoteRepository`` backed by the
    real ``QuoteModel`` ORM mapping.  The engine is disposed on teardown.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: QuoteModel.__table__.create(sync_conn))

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as session:
        repo = QuoteRepository(session=session)
        closes = _gold_close_series(N_BARS)
        prev = closes[0]
        for index, price in enumerate(closes):
            await repo.save(_make_quote(index, price, prev))
            prev = price
        await session.commit()

        yield session, repo, engine

    await engine.dispose()


async def _read_back(repo: QuoteRepository) -> list[Quote]:
    last_day = START_DATE + timedelta(days=N_BARS // 24 + 1)
    result = await repo.get_range(INSTRUMENT_ID, START_DATE, last_day, timeframe="1h")
    assert result.success, result.error
    return result.value


# ── 1 + 2: real ingestion, retrieval, and un-mocked simulator execution ──────


@pytest.mark.asyncio
async def test_repository_round_trip_and_real_simulator_trades(seeded_gold_db):
    """Bars survive the real ORM round-trip and the real engine actually trades."""
    _session, repo, _engine = seeded_gold_db

    quotes = await _read_back(repo)
    assert len(quotes) == N_BARS
    assert all(q.price_close > 0 for q in quotes)
    # OHLC integrity survived the ORM mapping.
    for q in quotes[:5]:
        assert q.price_low <= q.price_close <= q.price_high
        assert q.ask_price > q.bid_price  # non-zero spread seeded

    feed = _quotes_to_feed(quotes)
    assert feed[0]["instrument_id"] == INSTRUMENT_ID

    register_all_strategies()
    cls = get_strategy_registry().get("moving_average_cross")
    assert cls is not None

    # Real Broker with explicit realistic costs (no fake simulator).
    broker = Broker(commission_pct=0.004, slippage_bps=5.0, average_daily_volume=1_000_000)
    simulator = BacktestSimulator(broker=broker)

    smoke = simulator.run(
        cls(fast_period=5, slow_period=20, instrument_id=SYMBOL, sizing_value=SIZING_VALUE),
        initial_capital=CAPITAL,
        data=feed,
    )
    assert smoke.success, smoke.error
    result = smoke.value
    assert result.total_trades > 0, "real simulator produced no fills on the seeded data"
    assert len(result.equity_curve) == N_BARS
    assert all(ep.nav > 0 for ep in result.equity_curve)


# ── 3 + 4: full walk-forward pipeline over the real engine ───────────────────


@pytest.mark.asyncio
async def test_walk_forward_e2e_real_simulator_and_db(seeded_gold_db):
    """Full WalkForwardOptimizer run on the un-mocked simulator + real DB data."""
    _session, repo, _engine = seeded_gold_db

    quotes = await _read_back(repo)
    feed = _quotes_to_feed(quotes)

    register_all_strategies()
    simulator = BacktestSimulator(
        broker=Broker(commission_pct=0.004, slippage_bps=5.0, average_daily_volume=1_000_000)
    )
    optimizer = WalkForwardOptimizer(
        windows=WINDOWS,
        train_ratio=TRAIN_RATIO,
        max_workers=1,
        embargo_pct=EMBARGO_PCT,
        purge_pct=PURGE_PCT,
    )

    out = await optimizer.optimize(
        strategy_name="moving_average_cross",
        param_grid=PARAM_GRID,
        data=feed,
        capital=CAPITAL,
        simulator=simulator,
    )

    assert "error" not in out, out

    # Every configured window produced a real OOS evaluation.
    assert out["n_windows"] == WINDOWS

    # Purge/embargo gap sizing reached the result contract.
    assert out["embargo_bars"] == EMBARGO_BARS
    assert out["purged_bars"] == PURGE_BARS
    assert out["embargo_bars"] >= 1 and out["purged_bars"] >= 1

    # Sharpe vectors: one finite entry per executed window.
    assert isinstance(out["is_sharpes"], list)
    assert isinstance(out["oos_sharpes"], list)
    assert len(out["is_sharpes"]) == WINDOWS
    assert len(out["oos_sharpes"]) == WINDOWS
    for sharpe in out["is_sharpes"] + out["oos_sharpes"]:
        assert isinstance(sharpe, (int, float))
        assert math.isfinite(float(sharpe))

    # Aggregate efficiency is a finite number.
    assert isinstance(out["walk_forward_efficiency"], (int, float))
    assert math.isfinite(float(out["walk_forward_efficiency"]))

    # Deflated Sharpe block (TD-01 guard now permits the single-trial fold).
    dsr = out["deflated_sharpe"]
    assert isinstance(dsr, dict)
    assert N_COMBOS * WINDOWS == dsr["n_trials"]
    assert 0.0 <= dsr["deflated_sharpe"] <= 1.0
    assert 0.0 <= dsr["p_value"] <= 1.0
    assert math.isfinite(dsr["expected_max_sharpe"])

    # Per-fold trade logs + boundary integrity (purge/embargo discarded bars).
    assert out["oos_results"]
    assert len(out["oos_results"]) == WINDOWS
    for index, fold in enumerate(out["oos_results"], start=1):
        assert fold["window"] == index
        assert isinstance(fold["trades"], int)
        assert fold["trades"] >= 0
        assert math.isfinite(fold["sharpe"])
        assert math.isfinite(fold["return_pct"])
        assert fold["n_oos_observations"] == EXPECTED_OOS_OBS
        assert fold["params"]["instrument_id"] == SYMBOL

    # Selection used the OOS Sharpes, so the winner must be one of the grid sets.
    assert out["best_params"]["slow_period"] in (20, 30)


# ── 4: resource & state cleanup ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fixture_teardown_leaves_no_database_leak(seeded_gold_db):
    """The isolated DB is per-test: disposing the engine destroys its contents."""
    session, repo, engine = seeded_gold_db

    count = await session.execute(select(func.count()).select_from(QuoteModel))
    assert count.scalar() == N_BARS

    await session.close()
    await engine.dispose()

    # A brand-new engine for the same DSN must start empty: no leaked
    # connection and no cross-test state.
    fresh = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with fresh.begin() as conn:
        await conn.run_sync(lambda sync_conn: QuoteModel.__table__.create(sync_conn))
    fresh_factory = async_sessionmaker(bind=fresh, expire_on_commit=False)
    async with fresh_factory() as fresh_session:
        fresh_count = await fresh_session.execute(select(func.count()).select_from(QuoteModel))
        assert fresh_count.scalar() == 0
    await fresh.dispose()
