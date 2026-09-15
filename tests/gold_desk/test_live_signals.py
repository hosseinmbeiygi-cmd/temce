"""تست Live Signals — pure functions."""

from __future__ import annotations

from src.gold_desk.live_signals import Signal, detect_signals, detect_spike


def test_detect_spike_up():
    assert detect_spike(100, 102, threshold=1.0) == "spike_up"


def test_detect_spike_down():
    assert detect_spike(100, 98, threshold=1.0) == "spike_down"


def test_detect_spike_no_change():
    assert detect_spike(100, 100, threshold=1.0) is None


def test_detect_spike_below_threshold():
    assert detect_spike(100, 100.5, threshold=1.0) is None


def test_detect_spike_invalid():
    assert detect_spike(0, 100, threshold=1.0) is None
    assert detect_spike(100, 0, threshold=1.0) is None


def test_detect_signals_empty_prev():
    """بدون prev → هیچ signal."""
    snap = {"coins": {}, "score": {}, "references": {}}
    assert detect_signals(None, snap) == []


def test_detect_signals_no_change():
    prev = curr = {
        "coins": {"coin_emami": {"symbol": "IR_COIN_EMAMI", "market_price": 53_000_000, "display_name": "سکه امامی"}},
        "score": {"total": 70},
        "references": {"usd_irt": 68500, "aed_irt": 18650},
    }
    assert detect_signals(prev, curr) == []


def test_detect_signals_coin_spike():
    prev = {
        "coins": {"coin_emami": {"symbol": "X", "market_price": 53_000_000, "display_name": "Y"}},
        "score": {"total": 70},
        "references": {},
    }
    curr = {
        "coins": {"coin_emami": {"symbol": "X", "market_price": 54_000_000, "display_name": "Y"}},
        "score": {"total": 70},
        "references": {},
    }
    sigs = detect_signals(prev, curr)
    assert any(s.signal_type == "spike_up" for s in sigs)
    s = next(s for s in sigs if s.signal_type == "spike_up")
    assert abs(s.change_pct - 1.887) < 0.01
    assert s.severity in ("warn", "critical")


def test_detect_signals_score_change():
    prev = {"coins": {}, "score": {"total": 60}, "references": {}}
    curr = {"coins": {}, "score": {"total": 75}, "references": {}}
    sigs = detect_signals(prev, curr)
    assert any(s.signal_type == "score_change" for s in sigs)


def test_detect_signals_no_score_change_small():
    prev = {"coins": {}, "score": {"total": 60}, "references": {}}
    curr = {"coins": {}, "score": {"total": 65}, "references": {}}
    sigs = detect_signals(prev, curr)
    assert not any(s.signal_type == "score_change" for s in sigs)


def test_detect_signals_usd_spike():
    prev = {"coins": {}, "score": {"total": 60}, "references": {"usd_irt": 68000}}
    curr = {"coins": {}, "score": {"total": 60}, "references": {"usd_irt": 70000}}
    sigs = detect_signals(prev, curr)
    assert any(s.symbol == "USD" and s.signal_type == "spike_up" for s in sigs)


def test_detect_signals_bubble_extreme():
    prev = {
        "coins": {"coin_emami": {"symbol": "X", "market_price": 53_000_000, "display_name": "Y"}},
        "score": {"total": 70},
        "references": {},
    }
    curr = {
        "coins": {"coin_emami": {"symbol": "X", "market_price": 60_000_000, "bubble_pct": 30, "display_name": "Y"}},
        "score": {"total": 70},
        "references": {},
    }
    sigs = detect_signals(prev, curr)
    assert any(s.signal_type == "bubble_extreme" for s in sigs)


def test_signal_to_dict():
    s = Signal(
        symbol="X",
        signal_type="spike_up",
        severity="warn",
        title="t",
        description="d",
        current_value=100,
        threshold=1.5,
        change_pct=2.0,
    )
    d = s.to_dict()
    assert d["symbol"] == "X"
    assert d["ts"] > 0  # auto-filled
