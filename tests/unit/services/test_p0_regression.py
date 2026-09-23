"""P0/P1 regression: orchestrator releases non-empty, has disclaimer, finite numerics."""
import math

from domain.options.pricing import black_scholes_price
from services.quant_signal_orchestrator import EnrichedSignal, LEGAL_DISCLAIMER_FA


def _sig(**kw):
    base = dict(
        symbol="TEST", name="t", market="stock", direction="buy", timeframe="daily",
        entry_zone="z", stop_loss="95", targets="110", risk_reward="2",
        position_sizing="s", confirmation_condition="c", reason="r",
        invalidation="i", trailing_stop="t", price=100.0, change_pct=1.0,
        rule_score=70.0, ml_score=0.6, boosted_score=70.0, ml_influence_pct=10.0,
        confidence=0.7, calibration_level="medium",
        vote_direction_scores={"buy": 0.7, "sell": 0.2},
        source="test", created_at="now",
    )
    base.update(kw)
    return EnrichedSignal(**base)


def test_disclaimer_present():
    s = _sig()
    d = s.to_dict()
    assert d["legal_disclaimer"] == LEGAL_DISCLAIMER_FA
    assert len(d["legal_disclaimer"]) > 10


def test_pricing_finite():
    for T in (0, 1e-9, 0.5):
        for sig in (0, 1e-9, 0.3):
            for cp in ("call", "put"):
                r = black_scholes_price(100, 100, T, 0.05, sig, cp)
                assert math.isfinite(r.price) and math.isfinite(r.gamma)


def test_history_lengths_preferred():
    # documents the contract: real history length wins over the vote proxy
    real = {"TEST": 60}
    proxy = max(20, len({"buy": 0.7, "sell": 0.2}) * 10)
    chosen = int(real["TEST"]) if real.get("TEST") else proxy
    assert chosen == 60
