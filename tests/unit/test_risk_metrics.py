"""🛡️ Risk metrics — the maths, and the rule that nothing is reported without a window.

The pure functions are checked against hand-computed values, and the service is driven with a
fake session that returns stored rows, so the assembly (date intersection, thresholds, alerts)
is covered without a database. The most important assertions are the negative ones: a metric
with too few observations must come back ``unknown``, and no metric may ever carry a value
without naming what it was computed from.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from services.risk_metrics import (
    MIN_POINTS,
    PortfolioRiskService,
    beta,
    concentration,
    conditional_var,
    daily_returns,
    daily_volatility,
    drawdown_series,
    historical_var,
    max_drawdown,
    percentile,
)

_DAYS = [date(2026, 1, 1) + timedelta(days=i) for i in range(60)]


# ── pure maths ────────────────────────────────────────────────────────────────────────


def test_percentile_matches_the_linear_definition() -> None:
    assert percentile([1, 2, 3, 4], 0.0) == 1
    assert percentile([1, 2, 3, 4], 1.0) == 4
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([], 0.5) is None
    assert percentile([7], 0.1) == 7, "a single observation is its own quantile"


def test_daily_returns_ignore_a_zero_base() -> None:
    """A zero close is a data defect, not a -100% day: it must not enter the window."""

    assert daily_returns([100, 110, 0, 120]) == [10.0]


def test_var_cvar_and_volatility_refuse_a_short_window() -> None:
    short = [1.0, -2.0, 3.0, -4.0]
    assert len(short) < MIN_POINTS
    assert historical_var(short) is None
    assert conditional_var(short) is None
    assert daily_volatility(short) is None


def test_var_and_cvar_are_read_off_the_observed_tail() -> None:
    returns = [-5.0, -4.0, -3.0, -2.0, -1.0] + [1.0] * 30
    var = historical_var(returns, 0.95)
    assert var is not None and var < 0, "the 5th percentile of this window is a loss"
    cvar = conditional_var(returns, 0.95)
    assert cvar is not None and cvar <= var, "expected shortfall is never better than VaR"


def test_volatility_is_the_sample_stdev_of_daily_returns() -> None:
    returns = [2.0, -2.0] * 20
    vol = daily_volatility(returns)
    assert vol is not None
    assert vol == pytest.approx(2.0 * (len(returns) / (len(returns) - 1)) ** 0.5, rel=1e-9)


def test_drawdown_measures_the_distance_from_the_running_peak() -> None:
    values = [100, 120, 90, 90, 180]
    series = drawdown_series(values)
    assert series[0] == 0.0
    assert series[1] == 0.0
    assert series[2] == pytest.approx(-25.0)  # 90 against the 120 peak, not against 100
    assert series[3] == pytest.approx(-25.0)
    assert series[4] == 0.0
    assert max_drawdown(values) == pytest.approx(-25.0)
    assert max_drawdown([100]) is None, "one point has no drawdown"


def test_beta_of_a_series_against_itself_is_one() -> None:
    returns = [1.5, -0.5, 2.0, -1.0] * 10
    assert beta(returns, returns) == pytest.approx(1.0, abs=1e-9)
    assert beta(returns, [-r for r in returns]) == pytest.approx(-1.0, abs=1e-9)
    assert beta(returns[:5], returns) is None
    assert beta(returns, [1.0] * len(returns)) is None, "a flat benchmark has no variance"


def test_concentration_is_the_largest_weight() -> None:
    assert concentration([12.0, 31.5, 8.0]) == 31.5
    assert concentration([]) is None


# ── the service ───────────────────────────────────────────────────────────────────────


class _Result:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return self._rows


class _Session:
    """Dispatches on the SQL text, mirroring what each query would return."""

    def __init__(self, rows: dict[str, list[tuple]]) -> None:
        self.rows = rows
        self.calls: list[str] = []

    async def execute(self, stmt: object, params: dict | None = None) -> _Result:
        sql = str(stmt)
        self.calls.append(sql)
        for needle, rows in self.rows.items():
            if needle in sql:
                return _Result(rows)
        return _Result([])


def _portfolio_session(*, portfolios: list[tuple], positions: list[tuple], prices: list[tuple]) -> _Session:
    return _Session({
        "FROM portfolios": portfolios,
        "FROM portfolio_positions": positions,
        "FROM brsapi_historical_daily": prices,
        "FROM brsapi_index_values": [],
    })


def _prices(symbols: list[str], start: float, drift: float) -> list[tuple]:
    rows: list[tuple] = []
    for symbol in symbols:
        price = start
        for day in _DAYS:
            rows.append((symbol, day, round(price, 2)))
            price += drift
    return rows


async def test_a_user_without_a_portfolio_gets_declared_gaps_not_numbers() -> None:
    svc = PortfolioRiskService(session=_portfolio_session(portfolios=[], positions=[], prices=[]))  # type: ignore[arg-type]
    payload = await svc.metrics("u-1")

    assert payload["state"] == "NO_PORTFOLIO"
    assert payload["drawdown"] == []
    assert payload["alerts"] == []
    assert all(m["state"] == "unknown" and m["value"] is None for m in payload["metrics"])
    assert all(m["note"] for m in payload["metrics"]), "every gap must say why"
    keys = {m["key"] for m in payload["metrics"]}
    assert "sharpe" in keys, "the ratio is listed so the user knows it was considered and refused"


async def test_a_small_portfolio_computes_only_what_the_window_supports() -> None:
    portfolios = [("p-1", "سبد من", 100_000_000.0, 90_000_000.0, None)]
    positions = [
        ("فولاد", 100, 5000.0, 5500.0, 550_000.0, 61.0),
        ("خودرو", 200, 300.0, 250.0, 50_000.0, 39.0),
    ]
    svc = PortfolioRiskService(
        session=_portfolio_session(
            portfolios=portfolios, positions=positions, prices=_prices(["فولاد", "خودرو"], 5_000.0, 10.0)
        )  # type: ignore[arg-type]
    )
    payload = await svc.metrics("u-1")
    by_key = {m["key"]: m for m in payload["metrics"]}

    assert payload["state"] == "OK"
    assert len(_DAYS) >= MIN_POINTS, "the fixture must be long enough to be a real window"
    assert by_key["var_95"]["state"] != "unknown"
    assert by_key["var_95"]["value"] is not None
    assert by_key["concentration"]["value"] == 61.0  # the stored weight, not a guess
    assert by_key["beta"]["state"] == "unknown", "no index rows were stored"
    assert by_key["sharpe"]["value"] is None
    assert payload["drawdown"], "60 aligned days of prices is a real curve"
    assert payload["drawdown"][0]["date"] == _DAYS[0].isoformat()


async def test_every_computed_metric_names_its_source() -> None:
    """The invariant, stated once: a value without a basis is a fabricated value."""

    portfolios = [("p-1", "سبد", 100.0, 90.0, None)]
    positions = [("فولاد", 1, 5_000.0, 5_500.0, 5_500.0, 100.0)]
    svc = PortfolioRiskService(
        session=_portfolio_session(
            portfolios=portfolios, positions=positions, prices=_prices(["فولاد"], 5_000.0, 5.0)
        )  # type: ignore[arg-type]
    )
    for metric in (await svc.metrics("u-1"))["metrics"]:
        if metric["value"] is not None:
            assert metric["basis"], f"{metric['key']} has a number and no stated source"


async def test_alerts_only_fire_on_a_stored_breach() -> None:
    portfolios = [("p-1", "سبد", 100_000.0, 80_000.0, None)]  # -20%: past the 10% drawdown limit
    positions = [("فولاد", 10, 1_000.0, 900.0, 9_000.0, 30.0)]  # -10%: past the 5% stop loss
    svc = PortfolioRiskService(
        session=_portfolio_session(portfolios=portfolios, positions=positions, prices=[])  # type: ignore[arg-type]
    )
    rules = {a["rule"] for a in (await svc.metrics("u-1"))["alerts"]}

    assert {"stop_loss", "drawdown", "concentration"} <= rules


async def test_positions_of_another_owner_are_never_read() -> None:
    """Ownership is a query filter, so a page view cannot leak someone else's exposures."""

    session = _portfolio_session(portfolios=[], positions=[], prices=[])
    await PortfolioRiskService(session=session).metrics("user-42")  # type: ignore[arg-type]

    portfolio_sql = next(s for s in session.calls if "FROM portfolios" in s)
    assert "owner =" in portfolio_sql
