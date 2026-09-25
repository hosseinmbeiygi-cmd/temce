"""Tests for guarded options signals (Phase 2)."""
from services.options_signals import (
    LiquidityQuote,
    generate_guarded_signals,
    iv_rank,
    route_by_iv,
)


def test_liquidity_guard_blocks_illiquid():
    q = LiquidityQuote(symbol="X", open_interest=0, volume=0, bid=100, ask=130)
    ok, _ = q.passes()
    assert not ok
    q2 = LiquidityQuote(symbol="Y", open_interest=50, volume=20, bid=100, ask=101)
    ok2, _ = q2.passes()
    assert ok2


def test_iv_rank_routing():
    assert route_by_iv(80) == "credit"
    assert route_by_iv(20) == "debit"
    assert route_by_iv(50) == "neutral"
    assert iv_rank(0.5, [0.2, 0.3, 0.4]) == 100.0
    assert iv_rank(0.1, [0.2, 0.3, 0.4]) == 0.0


def test_high_iv_filters_to_credit_only():
    cands = [
        {"id": "long_call", "name": "LC", "market": "bullish", "score": 5,
         "entry": 50, "premium": 50, "max_profit": 200, "max_loss": -50},
        {"id": "covered_call", "name": "CC", "market": "neutral", "score": 5,
         "entry": 50, "premium": 50, "max_profit": 60, "max_loss": -30},
    ]
    out = generate_guarded_signals(cands, iv_rank_value=80.0)
    assert [s["strategy_id"] for s in out] == ["covered_call"]
    s = out[0]
    assert {"entry", "take_profit", "stop_loss", "risk_reward", "confidence"} <= set(s)


def test_unknown_liquidity_fail_closed():
    cands = [{"id": "long_call", "name": "LC", "market": "bullish", "score": 5,
              "entry": 50, "premium": 50, "max_profit": 200, "max_loss": -50}]
    quotes = {"other": LiquidityQuote(symbol="other", open_interest=99, volume=99, bid=1, ask=1)}
    assert generate_guarded_signals(cands, quotes=quotes) == []
