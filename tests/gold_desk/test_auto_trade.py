"""تست auto-trade — pure logic."""

from __future__ import annotations

from src.gold_desk.auto_trade import (
    AutoTradeConfig,
    TradeSignal,
    decide_action,
    default_config,
)


def test_default_config_disabled():
    cfg = default_config()
    assert cfg.enabled is False
    assert cfg.dry_run is True


def test_disabled_returns_hold():
    cfg = default_config()
    action, reason = decide_action(85, cfg, 0)
    assert action == "hold"
    assert "غیرفعال" in reason


def test_green_score_buys():
    cfg = AutoTradeConfig(
        enabled=True,
        dry_run=True,
        max_position_irt=10_000_000,
        min_score_to_buy=80,
        min_score_to_sell=20,
        cooldown_hours=24,
    )
    action, reason = decide_action(85, cfg, 0)
    assert action == "buy"
    assert "85" in reason


def test_red_score_sells():
    cfg = AutoTradeConfig(
        enabled=True,
        dry_run=True,
        max_position_irt=10_000_000,
        min_score_to_buy=80,
        min_score_to_sell=20,
        cooldown_hours=24,
    )
    action, reason = decide_action(15, cfg, 5_000_000)
    assert action == "sell"


def test_yellow_score_holds():
    cfg = AutoTradeConfig(
        enabled=True,
        dry_run=True,
        max_position_irt=10_000_000,
        min_score_to_buy=80,
        min_score_to_sell=20,
        cooldown_hours=24,
    )
    action, reason = decide_action(60, cfg, 0)
    assert action == "hold"


def test_max_position_blocks_buy():
    cfg = AutoTradeConfig(
        enabled=True,
        dry_run=True,
        max_position_irt=10_000_000,
        min_score_to_buy=80,
        min_score_to_sell=20,
        cooldown_hours=24,
    )
    action, reason = decide_action(85, cfg, 25_000_000)
    assert action == "hold"
    assert "position کافی" in reason


def test_no_position_cant_sell():
    cfg = AutoTradeConfig(
        enabled=True,
        dry_run=True,
        max_position_irt=10_000_000,
        min_score_to_buy=80,
        min_score_to_sell=20,
        cooldown_hours=24,
    )
    action, reason = decide_action(15, cfg, 0)
    assert action == "hold"
    assert "position" in reason.lower()


def test_signal_to_dict():
    from datetime import datetime

    sig = TradeSignal(
        action="buy",
        symbol="X",
        amount_irt=1000.0,
        confidence=0.85,
        reason="test",
        dry_run=True,
        ts=datetime(2025, 1, 1),
    )
    d = sig.to_dict()
    assert d["action"] == "buy"
    assert d["dry_run"] is True
    assert "ts" in d
