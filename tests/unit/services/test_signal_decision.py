"""Tests for the SignalDecisionEngine decision/policy dataclasses.

Tests the pure data-side of the engine: Decision/GateResult helpers, enum
identities, and a small slice of policy enforcement. Integration tests for
the full pipeline belong in tests/integration/.
"""

from __future__ import annotations

from services.signal_decision_engine import (
    Decision,
    FinalVerdict,
    GateResult,
    GateVerdict,
)


def _decision(verdict: FinalVerdict = FinalVerdict.RELEASE) -> Decision:
    return Decision(
        signal_id="s1",
        symbol="BTC-USDT",
        market="crypto",
        direction="long",
        verdict=verdict,
        calibrated_probability=0.6,
        effective_threshold=0.5,
    )


def test_decision_is_releasable_only_for_release_verdict() -> None:
    assert _decision(FinalVerdict.RELEASE).is_releasable() is True
    assert _decision(FinalVerdict.WATCHLIST).is_releasable() is False
    assert _decision(FinalVerdict.REJECT).is_releasable() is False


def test_decision_is_watchlisted_only_for_watchlist() -> None:
    assert _decision(FinalVerdict.WATCHLIST).is_watchlisted() is True
    assert _decision(FinalVerdict.RELEASE).is_watchlisted() is False


def test_all_gates_pass_when_no_blocked() -> None:
    d = _decision()
    d.gate_results = [
        GateResult(gate_name="data_quality", verdict=GateVerdict.PASS, score=0.9),
        GateResult(gate_name="risk", verdict=GateVerdict.WARN, score=0.5, reason="elevated vol"),
    ]
    assert d.all_gates_pass() is True
    assert d.warning_count() == 1
    assert d.blocked_gates() == []


def test_any_blocked_gate_fails_overall() -> None:
    d = _decision()
    d.gate_results = [
        GateResult(gate_name="data_quality", verdict=GateVerdict.PASS, score=0.9),
        GateResult(gate_name="risk", verdict=GateVerdict.BLOCK, score=0.1, reason="fat tail"),
    ]
    assert d.all_gates_pass() is False
    assert d.blocked_gates() == ["risk"]


def test_gate_result_to_dict_is_json_safe() -> None:
    g = GateResult(gate_name="x", verdict=GateVerdict.PASS, score=0.7, reason="ok", details={"k": 1})
    d = g.to_dict()
    assert d["gate"] == "x"
    assert d["verdict"] == "pass"  # enum stringified
    assert d["score"] == 0.7
    assert d["details"] == {"k": 1}


def test_decision_to_dict_includes_core_fields() -> None:
    d = _decision()
    out = d.to_dict()
    assert out["signal_id"] == "s1"
    assert out["symbol"] == "BTC-USDT"
    assert out["verdict"] == "release"
    assert out["calibrated_probability"] == 0.6
    assert out["effective_threshold"] == 0.5


def test_empty_gates_passes() -> None:
    """A decision with no gates evaluated is conservatively 'passing' (not blocked)."""
    d = _decision()
    assert d.all_gates_pass() is True
    assert d.warning_count() == 0
    assert d.blocked_gates() == []


def test_multiple_blocks_are_all_listed() -> None:
    d = _decision()
    d.gate_results = [
        GateResult(gate_name="a", verdict=GateVerdict.BLOCK),
        GateResult(gate_name="b", verdict=GateVerdict.BLOCK),
        GateResult(gate_name="c", verdict=GateVerdict.PASS),
    ]
    assert d.blocked_gates() == ["a", "b"]
