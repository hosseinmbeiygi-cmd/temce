"""FIN-12: a deeply negative bubble is an anomaly, not a golden opportunity.

``score_bubble`` gave full marks to any bubble below the green ceiling
(including -50%) and ``compute_quick_signal`` returned a high-confidence "buy"
for every negative number. A bubble far below its SMA usually means a broken
price series (or a crash the strategy should not chase), so both now floor it
at ``BUBBLE_ANOMALY_FLOOR_PCT`` and say so.
"""

from __future__ import annotations

from src.gold_desk.constants import BUBBLE_ANOMALY_FLOOR_PCT
from src.gold_desk.hotpath import compute_quick_signal
from src.gold_desk.scorer import SCORE_WEIGHTS, score_bubble


def test_deeply_negative_bubble_scores_zero() -> None:
    component = score_bubble(BUBBLE_ANOMALY_FLOOR_PCT - 20.0)

    assert component.value == 0
    assert "غیرعادی" in component.reason


def test_moderately_negative_bubble_still_scores_full() -> None:
    component = score_bubble(-3.0)

    assert component.value == SCORE_WEIGHTS["bubble"]


def test_quick_signal_does_not_buy_an_anomalous_bubble() -> None:
    signal = compute_quick_signal(BUBBLE_ANOMALY_FLOOR_PCT - 20.0)

    assert signal.action == "wait"
    assert signal.confidence == 0.0
    assert "غیرعادی" in signal.reason


def test_quick_signal_keeps_its_normal_negative_case() -> None:
    signal = compute_quick_signal(-3.0)

    assert signal.action == "buy"
    assert signal.confidence == 0.9
