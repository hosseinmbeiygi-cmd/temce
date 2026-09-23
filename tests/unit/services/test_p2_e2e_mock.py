"""P2-2 E2E (mocked DB): symbol -> history lengths -> decision -> disclaimer, no NaN/inf."""
import asyncio
import math
from unittest.mock import AsyncMock, patch

from services.quant_signal_orchestrator import EnrichedSignal, QuantSignalOrchestrator


def _sig():
    return EnrichedSignal(
        symbol="E2E", name="e2e", market="stock", direction="buy", timeframe="daily",
        entry_zone="z", stop_loss="95", targets="110", risk_reward="2",
        position_sizing="s", confirmation_condition="c", reason="r",
        invalidation="i", trailing_stop="t", price=100.0, change_pct=1.0,
        rule_score=70.0, ml_score=0.6, boosted_score=70.0, ml_influence_pct=10.0,
        confidence=0.7, calibration_level="medium",
        vote_direction_scores={"buy": 0.7, "sell": 0.2},
        source="test", created_at="now",
    )


def test_e2e_decision_with_real_history_lengths():
    orch = QuantSignalOrchestrator(session=None)
    released, rejected = asyncio.run(
        orch._apply_signal_decision([_sig()], history_lengths={"E2E": 60})
    )
    assert len(released) + len(rejected) == 1
    for s in released + rejected:
        d = s.to_dict()
        assert "legal_disclaimer" in d and len(d["legal_disclaimer"]) > 10
        for v in (s.price, s.confidence, s.calibrated_probability, s.net_expectancy_r):
            assert math.isfinite(float(v)), f"non-finite {v}"
