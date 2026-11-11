"""تست بازده پورتفوی — اسمی / واقعی / دلاری (pure، بدون DB)."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.gold_desk.portfolio import (
    build_cash_flows,
    cash_flows_from_trades,
    compute_returns,
)

D0 = date(2023, 1, 1)
D1 = date(2024, 1, 1)


def _trade(action, amount, when=datetime(2023, 1, 1)):
    return SimpleNamespace(action=action, amount_irt=amount, traded_at=when)


def _holding(amount, when=datetime(2023, 1, 1)):
    return SimpleNamespace(buy_amount_irt=amount, bought_at=when)


def test_cash_flows_from_trades_signs():
    flows = cash_flows_from_trades([_trade("buy", 100.0), _trade("sell", 250.0, datetime(2024, 1, 1))])
    assert flows == [(D0, -100.0), (D1, 250.0)]


def test_build_cash_flows_prefers_trades_over_holdings():
    holdings = [_holding(999.0)]
    trades = [_trade("buy", 100.0)]
    assert build_cash_flows(holdings=holdings, trades=trades) == [(D0, -100.0)]
    assert build_cash_flows(holdings=holdings) == [(D0, -999.0)]


def test_nominal_returns_and_xirr():
    r = compute_returns([(D0, -100.0)], ending_value=200.0, asof=D1)
    assert r.nominal_pnl_irt == pytest.approx(100.0)
    assert r.nominal_pnl_pct == pytest.approx(100.0)
    assert r.nominal_xirr == pytest.approx(1.0, abs=1e-9)
    assert r.real_xirr is None
    assert r.usd_xirr is None
    assert "real_xirr" in r.unavailable and "usd_xirr" in r.unavailable


def test_usd_return_is_zero_when_fx_doubles():
    r = compute_returns([(D0, -100.0)], ending_value=200.0, asof=D1, fx={D0: 10.0, D1: 20.0})
    assert r.usd_xirr == pytest.approx(0.0, abs=1e-9)
    assert r.usd_basis is None  # basis only set when the caller passes it


def test_real_return_is_zero_when_cpi_doubles():
    r = compute_returns([(D0, -100.0)], ending_value=200.0, asof=D1, cpi={D0: 100.0, D1: 200.0})
    assert r.real_xirr == pytest.approx(0.0, abs=1e-9)


def test_real_return_missing_cpi_date_is_unavailable_not_guessed():
    r = compute_returns([(D0, -100.0)], ending_value=200.0, asof=D1, cpi={D1: 200.0})
    assert r.real_xirr is None
    assert "no value" in r.unavailable["real_xirr"]


def test_no_flows_reports_ending_value_without_irr():
    r = compute_returns([], ending_value=500.0, asof=D1)
    assert r.nominal_pnl_irt == pytest.approx(500.0)
    assert r.nominal_pnl_pct is None
    assert r.nominal_xirr is None
    assert "nominal_xirr" in r.unavailable
