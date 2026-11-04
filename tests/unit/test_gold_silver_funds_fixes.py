"""تست‌های رگرسیون برای یافته‌های GS-06 تا GS-33 (طلا / نقره / صندوق‌ها).

هر تست رفتار «درست» را قفل می‌کند تا باگ‌های ممیزی برنگردند. این فایل بدون
اتصال واقعی به DB اجرا می‌شود (session جعلی).

پوشش:
  GS-07  وضعیت «داده ناموجود» در hard stop
  GS-08  افزودن نقد به total_assets + پوشش بر پایه وزن ارزش
  GS-12  یکسان‌بودن ارزش ذاتی سکه بین Antigravity و pricer
  GS-13  جهت عملگر پیام alert از rule_type
  GS-14  آستانه‌های P/NAV واحد
  GS-17  قیمت ناموجود → «نامعلوم» نه P&L صفر
  GS-19  باند پیش‌بینی کران‌دار + لنگر EMA
  GS-20  رجیستری نماد = نمادهای موجود در منبع
  GS-21  گیت عمر قیمت لایو
  GS-27  کوانتیل واقعی metrics
  GS-28  اسپرد طلا واکنشی به نوسان
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtesting.costs.gold_costs import (  # noqa: E402
    MAX_SPREAD_PCT,
    MIN_SPREAD_PCT,
    GoldCostModel,
)
from services.fund_nav_engine import FundNavEngine, _price_is_stale  # noqa: E402
from src.gold_desk import metrics, pricer  # noqa: E402
from src.gold_desk.alert_engine import _operator_for  # noqa: E402
from src.gold_desk.antigravity.calculations import (  # noqa: E402
    calculate_coin_bubble,
    calculate_nav_premium,
)
from src.gold_desk.constants import COIN_SYMBOLS, GOLD_SYMBOLS  # noqa: E402
from src.gold_desk.forecaster import _forecast_ema_trend, build_forecast  # noqa: E402
from src.gold_desk.hard_stops import check_hard_stops  # noqa: E402
from src.gold_desk.portfolio import fifo_realized, get_holdings_grouped, trades_to_csv  # noqa: E402

# ── session جعلی ────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, rows=(), row=None):
        self._rows = list(rows)
        self._row = row

    def all(self):
        return list(self._rows)

    def fetchall(self):
        return list(self._rows)

    def first(self):
        return self._row

    def scalar(self):
        return self._row[0] if self._row else None

    def scalars(self):
        return self


class _ScriptedSession:
    """session جعلی که بر اساس نام جدول در متن SQL پاسخ می‌دهد."""

    def __init__(self, by_table: dict[str, _FakeResult]):
        self._by_table = by_table

    async def execute(self, stmt, *_args, **_kwargs):
        sql = str(stmt)
        for table, result in self._by_table.items():
            if table in sql:
                return result
        raise AssertionError(f"کوئری پیش‌بینی‌نشده: {sql[:160]}")


# ── GS-07 ───────────────────────────────────────────────────────────────────


def test_hard_stop_without_inputs_is_flagged_not_silent():
    r = check_hard_stops()
    assert r.active is False
    assert r.inputs_missing is True


def test_hard_stop_with_any_input_is_evaluated():
    r = check_hard_stops(usd_irt_daily_change_pct=1.0)
    assert r.inputs_missing is False
    assert r.active is False


# ── GS-08 + GS-22 ───────────────────────────────────────────────────────────


async def test_cash_is_added_to_total_assets():
    valuation_date = date(2026, 9, 20)
    session = _ScriptedSession(
        {
            "fund_holdings": _FakeResult(
                rows=[(valuation_date, "equity", "فولاد", "فولاد", 100, 900_000, 90.0)]
            ),
            "fund_portfolio_reports": _FakeResult(
                row=(valuation_date, 1_000_000, 0.0, 1_000_000, 1000, 100_000)
            ),
            "brsapi_symbol_snapshots": _FakeResult(
                rows=[("فولاد", 10_000.0, datetime.now())]
            ),
        }
    )
    payload = await FundNavEngine(session)._build_payload(  # type: ignore[arg-type]
        "tse:TEST", valuation_date, "STATISTICAL", "SHADOW"
    )
    # position 100×10,000 = 1,000,000 + cash 100,000
    assert payload.total_assets == pytest.approx(1_100_000)
    # پوشش بر پایه وزن ارزش (نه ۱۰۰٪ فرضی): فقط 1,000,000 از 1,100,000 مستقل
    assert payload.coverage_pct == pytest.approx(1_000_000 / 1_100_000 * 100, rel=1e-6)


# ── GS-12 ───────────────────────────────────────────────────────────────────


def test_antigravity_coin_intrinsic_matches_pricer():
    xau, usd = 4000.0, 900_000.0
    b = calculate_coin_bubble(900_000_000, xau, usd)
    assert b.coin_intrinsic == pytest.approx(pricer.fair_coin("IR_COIN_EMAMI", xau, usd))


# ── GS-13 ───────────────────────────────────────────────────────────────────


def test_alert_operator_follows_rule_type_not_threshold_sign():
    assert _operator_for("bubble_below", 3.0) == "<"
    assert _operator_for("bubble_above", 22.0) == ">"
    assert _operator_for("score_below", 20.0) == "<"


# ── GS-14 ───────────────────────────────────────────────────────────────────


def test_nav_premium_uses_single_policy():
    assert calculate_nav_premium(102.5, 100).signal == "NEUTRAL"  # +2.5% ≤ +3
    assert calculate_nav_premium(104.0, 100).signal == "SELL"  # > +3
    assert calculate_nav_premium(98.5, 100).signal == "NEUTRAL"  # −1.5% > −2
    assert calculate_nav_premium(97.0, 100).signal == "BUY"  # < −2


# ── GS-17 ───────────────────────────────────────────────────────────────────


class _HoldingsSession:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, *_a, **_k):
        return _FakeResult(rows=self._rows)


async def test_missing_price_is_unknown_not_false_zero():
    rows = [
        SimpleNamespace(
            symbol="IR_COIN_EMAMI",
            display_name="سکه امامی",
            quantity=2,
            buy_amount_irt=100.0,
            bought_at=datetime(2026, 1, 1),
        )
    ]
    summary = await get_holdings_grouped(_HoldingsSession(rows), {})  # type: ignore[arg-type]
    h = summary.holdings[0]
    assert h.current_price is None
    assert h.current_value is None and h.pnl_irt is None and h.pnl_pct is None
    assert summary.unpriced_holdings == 1


async def test_priced_holding_computes_pnl():
    rows = [
        SimpleNamespace(
            symbol="IR_COIN_EMAMI",
            display_name="سکه امامی",
            quantity=2,
            buy_amount_irt=100.0,
            bought_at=datetime(2026, 1, 1),
        )
    ]
    summary = await get_holdings_grouped(_HoldingsSession(rows), {"IR_COIN_EMAMI": 80.0})  # type: ignore[arg-type]
    h = summary.holdings[0]
    assert h.current_value == pytest.approx(160.0)
    assert h.pnl_irt == pytest.approx(60.0)


# ── GS-19 ───────────────────────────────────────────────────────────────────


def test_forecast_band_is_never_negative_on_volatile_series():
    closes = [100 * (1.25 if i % 2 else 0.75) for i in range(60)]
    result = build_forecast(closes)
    assert result.forecasts
    for p in result.forecasts:
        assert p.lower_band >= 0


def test_ema_trend_is_anchored_on_ema():
    closes = [100 + i for i in range(17)]
    period, horizon = 14, 7
    arr = np.array(closes, dtype=float)
    alpha = 2.0 / (period + 1)
    ema = arr[0]
    for p in arr[1:]:
        ema = p * alpha + ema * (1 - alpha)
    recent = arr[-7:]
    drift = float(np.mean(np.diff(recent) / recent[:-1]))
    expected = float(ema * (1 + drift) ** horizon)
    assert _forecast_ema_trend(closes, horizon, period) == pytest.approx(expected)


# ── GS-20 ───────────────────────────────────────────────────────────────────


def test_symbol_registry_matches_available_source_symbols():
    source = {
        "IR_COIN_1G",
        "IR_COIN_BAHAR",
        "IR_COIN_EMAMI",
        "IR_COIN_HALF",
        "IR_COIN_QUARTER",
        "IR_GOLD_18K",
        "IR_GOLD_24K",
        "IR_GOLD_MELTED",
        "XAUUSD",
    }
    assert set(GOLD_SYMBOLS.values()) <= source
    assert set(COIN_SYMBOLS.values()) <= source
    assert "IR_COIN_1G" in COIN_SYMBOLS.values()


# ── GS-21 ───────────────────────────────────────────────────────────────────


def test_live_price_staleness_gate():
    assert _price_is_stale(datetime(2026, 9, 18, 10, 0), date(2026, 9, 18)) is False
    assert _price_is_stale(datetime(2026, 9, 10, 10, 0), date(2026, 9, 18)) is True
    assert _price_is_stale(None, date(2026, 9, 18)) is False


# ── GS-27 ───────────────────────────────────────────────────────────────────


def test_percentile_is_a_real_quantile():
    assert metrics._percentile([], 0.5) == 0.0
    assert metrics._percentile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)
    assert metrics._percentile([1.0], 0.99) == pytest.approx(1.0)


# ── GS-28 ───────────────────────────────────────────────────────────────────


def test_gold_spread_responds_to_volatility_and_vehicle():
    model = GoldCostModel()
    assert model.effective_spread(1.0) > model.effective_spread(0.0)
    assert model.effective_spread(1.0) <= MAX_SPREAD_PCT
    assert model.effective_spread(-1.0) >= MIN_SPREAD_PCT
    assert model.effective_spread(0.0, "bar") > model.effective_spread(0.0, "coin")


def _trade(action, qty, price, when):
    return SimpleNamespace(action=action, quantity=qty, price=price, traded_at=when, symbol="X",
                           amount_irt=qty * price, fee_irt=0.0, pnl_irt=0.0, note=None)


def test_fifo_realized_pnl_and_open_lots():
    from datetime import datetime as dt

    trades = [
        _trade("buy", 10, 100.0, dt(2026, 1, 1)),
        _trade("buy", 5, 120.0, dt(2026, 1, 2)),
        _trade("sell", 12, 150.0, dt(2026, 1, 3)),
    ]
    out = fifo_realized(trades)
    # ۱۰ لات اول @۱۰۰ و ۲ لات دوم @۱۲۰ فروخته شد
    assert out["realized_pnl_irt"] == pytest.approx((150 - 100) * 10 + (150 - 120) * 2)
    assert out["open_quantity"] == pytest.approx(3)
    assert out["open_cost_basis_irt"] == pytest.approx(3 * 120)


def test_trades_csv_has_header_and_rows():
    from datetime import datetime as dt

    csv_text = trades_to_csv([_trade("buy", 1, 10.0, dt(2026, 1, 1))])
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("traded_at,symbol,action")
    assert "buy" in lines[1]


def test_gold_cost_default_matches_base_spread():
    model = GoldCostModel()
    assert model.compute("buy", 200_000_000) == pytest.approx(200_000_000 * model.effective_spread(0.0) / 2)
    assert model.compute("sell", 200_000_000) == pytest.approx(model.compute("buy", 200_000_000))
