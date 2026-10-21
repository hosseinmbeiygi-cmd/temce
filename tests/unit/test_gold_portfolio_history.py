"""Unit tests — تاریخچهٔ ارزش پرتفوی، TWR و مقایسه با بنچمارک.

تمرکز روی:
  * توابع خالص (طبقه‌بندی ابزار، انحراف ری‌بالانس، جریان نقدی روزانه، تاریخ شمسی)
  * منطق «هیچ مقدار جعلی» در گزارش کارایی (سری ناکافی → None + دلیل)
  * درست بودن علامت جریان نقدی برای TWR
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.time import now_tehran
from src.gold_desk import portfolio_history as ph
from src.gold_desk.models import GoldPortfolioValueModel
from src.gold_desk.portfolio import PortfolioSummary


def _holding(symbol: str, value: float):
    return SimpleNamespace(symbol=symbol, current_value=value)


def _summary(holdings, total_cost: float = 100.0, unpriced: int = 0) -> PortfolioSummary:
    return PortfolioSummary(
        total_cost=total_cost,
        total_value=sum(h.current_value for h in holdings),
        total_pnl=0.0,
        total_pnl_pct=0.0,
        holdings=holdings,
        by_symbol={},
        unpriced_holdings=unpriced,
    )


def _value_row(day: date, value: float, flow: float = 0.0, cost: float = 100.0, unpriced: int = 0):
    return SimpleNamespace(
        as_of=day,
        total_value_irt=value,
        total_cost_irt=cost,
        net_flow_irt=flow,
        unpriced_holdings=unpriced,
    )


# ── طبقه‌بندی ابزار ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("IR_COIN_EMAMI", "coin"),
        ("coin_bahar", "coin"),
        ("IR_GOLD_MELTED", "melted"),
        ("IR_GOLD_18K", "melted"),
        ("IR_GOLD_1G", "melted"),
        ("عیار", "etf"),
        ("زر", "etf"),
    ],
)
def test_classify_vehicle(symbol: str, expected: str) -> None:
    assert ph.classify_vehicle(symbol) == expected


def test_classify_vehicle_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ph.PORTFOLIO_SYMBOL_VEHICLE_OVERRIDES, "coin_1g", "etf")
    assert ph.classify_vehicle("coin_1g") == "etf"


def test_class_weights_and_drift() -> None:
    holdings = [_holding("IR_GOLD_MELTED", 60.0), _holding("عیار", 40.0)]
    weights = ph.class_weights_from_holdings(holdings)
    assert weights == {"melted": 60.0, "etf": 40.0}

    # هدف پیش‌فرض: etf 40 / melted 40 / coin 20 → انحراف melted = +20
    max_drift, drift = ph.allocation_drift_pct(weights)
    assert drift["melted"] == pytest.approx(20.0)
    assert drift["etf"] == pytest.approx(0.0)
    assert drift["coin"] == pytest.approx(-20.0)
    assert max_drift == pytest.approx(20.0)


def test_drift_none_without_priced_holdings() -> None:
    assert ph.class_weights_from_holdings([_holding("عیار", 0.0)]) == {}
    assert ph.allocation_drift_pct({}) == (None, {})


# ── جریان نقدی روزانه ────────────────────────────────────────────


def test_daily_net_flow_sign_convention() -> None:
    """خرید = واریز (مثبت)، فروش = برداشت (منفی) — هم‌راستا با TWR."""
    day = date(2026, 10, 14)
    buy = SimpleNamespace(traded_at=datetime(2026, 10, 14, 10, 0), action="buy", amount_irt=1_000.0)
    sell = SimpleNamespace(traded_at=datetime(2026, 10, 14, 12, 0), action="sell", amount_irt=400.0)
    other = SimpleNamespace(traded_at=datetime(2026, 10, 13, 12, 0), action="buy", amount_irt=999.0)

    assert ph.daily_net_flow_irt([], [buy], day) == pytest.approx(1_000.0)
    assert ph.daily_net_flow_irt([], [buy, sell], day) == pytest.approx(600.0)
    assert ph.daily_net_flow_irt([], [other], day) == 0.0


def test_daily_net_flow_falls_back_to_holdings() -> None:
    day = date(2026, 10, 14)
    holding = SimpleNamespace(bought_at=datetime(2026, 10, 14, 9, 0), buy_amount_irt=250.0)
    assert ph.daily_net_flow_irt([holding], [], day) == pytest.approx(250.0)


# ── تاریخ شمسی/میلادی بنچمارک ────────────────────────────────────


def test_to_gregorian_handles_shamsi_and_gregorian() -> None:
    # 1405-06-23 شمسی = 2026-09-14 میلادی
    assert ph._to_gregorian("1405-06-23") == date(2026, 9, 14)
    # جداکنندهٔ اسلش (فرمت ردیف‌های تازه‌تر FX)
    assert ph._to_gregorian("1405/05/01") == date(2026, 7, 23)
    # از قبل میلادی
    assert ph._to_gregorian(date(2026, 7, 23)) == date(2026, 7, 23)
    assert ph._to_gregorian(datetime(2026, 7, 23, 5, 0)) == date(2026, 7, 23)
    assert ph._to_gregorian("") is None
    assert ph._to_gregorian(None) is None


# ── بازده بنچمارک ────────────────────────────────────────────────


def test_benchmark_return_pct() -> None:
    series = {date(2026, 7, 1): 100.0, date(2026, 7, 10): 90.0, date(2026, 7, 20): 120.0}
    out = ph.benchmark_return_pct(series)
    assert out == pytest.approx(20.0)
    assert ph.benchmark_return_pct({date(2026, 7, 1): 100.0}) is None
    assert ph.benchmark_return_pct({}) is None


def test_benchmark_return_respects_window() -> None:
    series = {date(2026, 6, 1): 50.0, date(2026, 7, 1): 100.0, date(2026, 7, 31): 150.0}
    out = ph.benchmark_return_pct(
        series, start=date(2026, 7, 1), end=date(2026, 8, 1)
    )
    assert out == pytest.approx(50.0)


# ── ثبت ارزش (persist) ──────────────────────────────────────────


class _ScalarResult:
    def __init__(self, row=None) -> None:
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    def __init__(self, existing=None) -> None:
        self._existing = existing
        self.added: list = []
        self.commits = 0

    async def execute(self, *args, **kwargs):
        return _ScalarResult(self._existing)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj) -> None:
        return None


@pytest.mark.asyncio
async def test_capture_portfolio_value_inserts(monkeypatch: pytest.MonkeyPatch) -> None:
    holdings = [SimpleNamespace(bought_at=datetime(2026, 10, 14), buy_amount_irt=500.0)]
    monkeypatch.setattr(
        ph, "load_holdings_and_trades", lambda *_a, **_k: _async((holdings, []))
    )
    monkeypatch.setattr(
        ph, "get_holdings_grouped", lambda *_a, **_k: _async(_summary([_holding("عیار", 700.0)]))
    )
    session = _FakeSession(existing=None)

    row = await ph.capture_portfolio_value(session, snapshot={}, asof=date(2026, 10, 14))

    assert session.commits == 1 and len(session.added) == 1
    assert row.as_of == date(2026, 10, 14)
    assert row.total_value_irt == pytest.approx(700.0)
    assert row.net_flow_irt == pytest.approx(500.0)  # خرید = واریز مثبت


@pytest.mark.asyncio
async def test_capture_portfolio_value_upserts_same_day(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = GoldPortfolioValueModel(
        as_of=date(2026, 10, 14),
        total_value_irt=1.0,
        total_cost_irt=1.0,
        net_flow_irt=0.0,
        unpriced_holdings=0,
    )
    monkeypatch.setattr(ph, "load_holdings_and_trades", lambda *_a, **_k: _async(([], [])))
    monkeypatch.setattr(
        ph, "get_holdings_grouped", lambda *_a, **_k: _async(_summary([_holding("عیار", 999.0)]))
    )
    session = _FakeSession(existing=existing)

    row = await ph.capture_portfolio_value(session, snapshot={}, asof=date(2026, 10, 14))

    assert session.added == [] and session.commits == 1
    assert row is existing
    assert row.total_value_irt == pytest.approx(999.0)


# ── گزارش کارایی ────────────────────────────────────────────────


def _async(value):
    async def _inner(*_a, **_k):
        return value

    return _inner()


@pytest.mark.asyncio
async def test_performance_report_twr_and_benchmarks(monkeypatch: pytest.MonkeyPatch) -> None:
    today = now_tehran().date()
    days = [today - timedelta(days=4 - i) for i in range(5)]
    # ارزش پایانی هر روز جهش ۱۰٪ دارد و یک واریز ۱۰۰ در روز سوم نباید در TWR اثر کند.
    rows = [
        _value_row(days[0], 1_000.0, 0.0),
        _value_row(days[1], 1_100.0, 0.0),
        _value_row(days[2], 1_310.0, 100.0),
        _value_row(days[3], 1_441.0, 0.0),
        _value_row(days[4], 1_585.1, 0.0),
    ]
    monkeypatch.setattr(ph, "load_value_history", lambda *_a, **_k: _async(rows))
    monkeypatch.setattr(
        ph, "get_holdings_grouped", lambda *_a, **_k: _async(_summary([_holding("عیار", 500.0)]))
    )
    monkeypatch.setattr(
        ph,
        "load_benchmark_series",
        lambda *_a, **_k: _async(dict(zip(days, [100.0, 102.0, 104.0, 106.0, 110.0], strict=True))),
    )

    report = await ph.build_performance_report(_FakeSession(), days=10)
    data = report.as_dict()

    assert data["points"] == 5
    # TWR = 1.1^4 - 1 = 46.41% (واریز ۱۰۰ در روز سوم خنثی می‌شود)
    assert data["twr_pct"] == pytest.approx(46.41, abs=1e-4)
    assert data["simple_return_pct"] == pytest.approx(58.51, abs=1e-6)
    assert data["max_drawdown_pct"] == pytest.approx(0.0)
    # تمرکز: تنها یک دارایی قیمت‌دار → ۱۰۰٪
    assert data["concentration_pct"] == pytest.approx(100.0)
    for key in ("gold", "usd", "tedpix"):
        assert data["benchmarks"][key]["return_pct"] == pytest.approx(10.0)
        assert data["benchmarks"][key]["relative_pct"] == pytest.approx(36.41, abs=1e-4)


@pytest.mark.asyncio
async def test_performance_report_flags_unavailable_without_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ph, "load_value_history", lambda *_a, **_k: _async([_value_row(date(2026, 10, 14), 0.0)])
    )
    monkeypatch.setattr(ph, "get_holdings_grouped", lambda *_a, **_k: _async(_summary([])))
    monkeypatch.setattr(ph, "load_benchmark_series", lambda *_a, **_k: _async({}))

    report = await ph.build_performance_report(_FakeSession(), days=90)
    data = report.as_dict()

    assert data["twr_pct"] is None
    assert data["concentration_pct"] is None
    assert "twr_pct" in data["unavailable"]
    # بنچمارک بدون داده باید دلیل بدهد، نه عدد صفر
    for key in ("gold", "usd", "tedpix"):
        assert data["benchmarks"][key]["return_pct"] is None
        assert data["benchmarks"][key]["relative_pct"] is None
        assert data["benchmarks"][key]["unavailable"]


@pytest.mark.asyncio
async def test_risk_metrics_keys_match_alert_rule_types(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.gold_desk.alert_engine import _PORTFOLIO_METRIC_KEYS

    monkeypatch.setattr(ph, "load_value_history", lambda *_a, **_k: _async([]))
    monkeypatch.setattr(
        ph, "get_holdings_grouped", lambda *_a, **_k: _async(_summary([_holding("IR_GOLD_MELTED", 10.0)]))
    )
    report = await ph.build_performance_report(_FakeSession(), days=30, include_benchmarks=False)

    metrics = report.risk_metrics()
    assert metrics["portfolio_concentration_pct"] == pytest.approx(100.0)
    assert set(metrics) >= set(_PORTFOLIO_METRIC_KEYS.values())
