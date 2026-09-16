"""Unit tests — v5.0 — Tiered Pricing + Signal + Validation."""

from datetime import timedelta

from core.time import utc_now_naive
from domain.decision_engine_v5.models import InstrumentKey, RawTick, TradeCard, TradeLeg
from domain.decision_engine_v5.pricing_tiered import black76_price, cointegration_zscore, cost_of_carry_fair_price, sabr_gate
from domain.decision_engine_v5.trading import check_hard_blocks, compute_net_edge, drawdown_action, fixed_fractional_size, signal_score
from domain.decision_engine_v5.validation import acceptance_gate


def test_instrument_key_str():
    k = InstrumentKey("OPT123", "خودرو", "option", 2500, "2026-09-01")
    assert "خودرو" in str(k)


def test_raw_tick_mid_guard():
    now = utc_now_naive()
    tick = RawTick("k", now, now, best_bid=None, best_ask=100)
    assert tick.mid_price() is None
    tick2 = RawTick("k", now, now, best_bid=100, best_ask=102)
    assert tick2.mid_price() == 101


def test_black76_put_call_parity():
    F, K, T, r, sigma = 100, 100, 0.5, 0.05, 0.3
    c = black76_price(F, K, T, r, sigma, True)
    p = black76_price(F, K, T, r, sigma, False)
    import math

    assert abs((c - p) - (F - K) * math.exp(-r * T)) < 1e-6


def test_hard_blocks():
    assert check_hard_blocks(True, False, True, True, 100, 0.8) is not None  # stale
    assert check_hard_blocks(False, False, True, True, -10, 0.8) is not None  # cost
    assert check_hard_blocks(False, False, True, True, 100, 0.8) is None  # pass


def test_signal_score():
    assert 0.5 <= signal_score(0.9, 0.8, 0.85, 0.75) <= 1.0


def test_fixed_fractional():
    assert fixed_fractional_size(1_000_000, 0.9, 10) > 0
    assert fixed_fractional_size(1_000_000, 0.5, 0) == 0


def test_sabr_gate():
    ok, _ = sabr_gate({"2026-09": [1, 2, 3, 4, 5], "2026-12": [1, 2, 3, 4, 5]}, 0.01, 25)
    assert ok
    ok2, reasons = sabr_gate({"2026-09": [1, 2]}, 0.05, 5)
    assert not ok2 and reasons


def test_acceptance_gate():
    r = acceptance_gate(0.57, 1.6, 1000, -0.08, 1.4, 50)
    assert r.passed
    r2 = acceptance_gate(0.45, 1.6, 1000, -0.08, 1.4, 50)
    assert not r2.passed


def test_drawdown():
    assert drawdown_action(-0.06) == "CAUTION"
    assert drawdown_action(-0.11) == "STOP_ALL"
    assert drawdown_action(-0.16) == "HALVE_SIZE"
