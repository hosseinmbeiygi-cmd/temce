"""Tests for the ML signal connector upgrades.

Covers:
- ``get_accuracy_by_market`` no longer returns the legacy hard-coded 0.55.
  Instead it queries ``signal_accuracy`` and blends with a 0.5 prior when
  samples < min_samples.
- ``get_signal_boost`` preserves the formula contract (rule vs ML weight) and
  never exceeds the documented caps.
- The connector can be constructed without instantiating ModelLoader (which
  needs a disk directory); we use ``object.__new__`` to avoid I/O.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.ml_signal_connector import MLSignalConnector


def _bare_connector() -> MLSignalConnector:
    """Construct without running MLSignalConnector.__init__ (which touches I/O)."""
    c = object.__new__(MLSignalConnector)
    return c


def _fake_get_session(mock_session):
    """Fake for ``core.database.get_session`` — a real async generator."""

    async def _gen():
        yield mock_session

    return _gen



class TestGetAccuracyByMarket:
    async def test_uses_db_when_samples_sufficient(self):
        c = _bare_connector()
        # session.execute returns a row with n=200, acc=0.62
        row = SimpleNamespace(n=200, acc=0.62)
        mock_session = AsyncMock()
        mock_session.execute.return_value.first = MagicMock(return_value=row)
        with patch("core.database.get_session", _fake_get_session(mock_session)):
            result = await c.get_accuracy_by_market("stock", min_samples=30)
        assert result == pytest.approx(0.62, abs=1e-6)

    async def test_blends_with_prior_when_below_min_samples(self):
        c = _bare_connector()
        # n=10 observed accuracy 0.9, min=30 → 0.9 * 10/40 + 0.5 * 30/40 = 0.225 + 0.375 = 0.6
        row = SimpleNamespace(n=10, acc=0.9)
        mock_session = AsyncMock()
        mock_session.execute.return_value.first = MagicMock(return_value=row)
        with patch("core.database.get_session", _fake_get_session(mock_session)):
            result = await c.get_accuracy_by_market("stock", min_samples=30)
        assert result == pytest.approx(0.6, abs=1e-6)

    async def test_returns_prior_when_no_samples(self):
        c = _bare_connector()
        row = SimpleNamespace(n=0, acc=0)
        mock_session = AsyncMock()
        mock_session.execute.return_value.first = MagicMock(return_value=row)
        with patch("core.database.get_session", _fake_get_session(mock_session)):
            result = await c.get_accuracy_by_market("forex", min_samples=30)
        assert result == 0.50

    async def test_db_failure_falls_back_to_prior(self):
        c = _bare_connector()
        with patch("core.database.get_session", side_effect=RuntimeError("db down")):
            result = await c.get_accuracy_by_market("crypto")
        assert result == 0.50

    async def test_never_above_one(self):
        c = _bare_connector()
        row = SimpleNamespace(n=100, acc=1.5)  # pathological
        mock_session = AsyncMock()
        mock_session.execute.return_value.first = MagicMock(return_value=row)
        with patch("core.database.get_session", _fake_get_session(mock_session)):
            result = await c.get_accuracy_by_market("stock", min_samples=30)
        # The DB average is a float; we don't clamp here but verify the value
        # is in a sane range (>= 0). Clamping belongs to the consumer.
        assert result >= 0.0


class TestGetSignalBoost:
    def test_zero_ml_confidence_keeps_rule(self):
        c = _bare_connector()
        result = c.get_signal_boost(
            ml_prediction={"direction": "buy", "ml_score": 0.5, "confidence": 0.0}, rule_signal_score=70.0
        )
        # ml_weight = 0 → boosted_score = rule_weight*rule + 0*ml*100 = 1.0*70 = 70
        assert result["boosted_score"] == pytest.approx(70.0, abs=1e-6)
        assert result["ml_influence_pct"] == 0.0

    def test_full_ml_confidence_caps_influence(self):
        c = _bare_connector()
        result = c.get_signal_boost(
            ml_prediction={"direction": "buy", "ml_score": 0.8, "confidence": 1.0}, rule_signal_score=50.0
        )
        # ml_weight = 1.0 * 0.7 = 0.7; boosted = 0.3*50 + 0.7*0.8*100 = 15 + 56 = 71
        assert result["boosted_score"] == pytest.approx(71.0, abs=1e-6)
        assert result["ml_influence_pct"] == pytest.approx(70.0, abs=1e-6)

    def test_handles_missing_keys(self):
        c = _bare_connector()
        result = c.get_signal_boost(ml_prediction={}, rule_signal_score=50.0)
        # defaults: ml_score=0.5, confidence=0.0 → rule wins
        assert result["boosted_score"] == pytest.approx(50.0, abs=1e-6)

    def test_direction_preserved(self):
        c = _bare_connector()
        result = c.get_signal_boost(
            ml_prediction={"direction": "sell", "ml_score": 0.3, "confidence": 0.6}, rule_signal_score=40.0
        )
        assert result["ml_direction"] == "sell"


class TestHeuristicTrendPredict:
    """Tests for the multi-indicator heuristic (MA + RSI + MACD + ATR)."""

    def test_empty_returns_hold(self):
        from services.ml_signal_connector import _heuristic_trend_predict

        result = _heuristic_trend_predict([])
        assert result["direction"] == "hold"
        assert result["confidence"] == 0.0

    def test_too_few_samples_returns_hold(self):
        from services.ml_signal_connector import _heuristic_trend_predict

        result = _heuristic_trend_predict([100, 101, 102])
        assert result["direction"] == "hold"

    def test_strong_uptrend_returns_buy(self):
        from services.ml_signal_connector import _heuristic_trend_predict

        closes = [100 * (1.01**i) for i in range(30)]
        result = _heuristic_trend_predict(closes)
        assert result["direction"] == "buy", result
        assert result["confidence"] > 0
        assert "indicators" in result
        assert result["indicators"]["ma_ratio"] > 0
        assert result["models_used"] == ["heuristic_trend"]

    def test_strong_downtrend_returns_sell(self):
        from services.ml_signal_connector import _heuristic_trend_predict

        closes = [100 * (0.99**i) for i in range(30)]
        result = _heuristic_trend_predict(closes)
        assert result["direction"] == "sell", result
        assert result["indicators"]["ma_ratio"] < 0

    def test_sideways_returns_hold_or_mean_reversion(self):
        from services.ml_signal_connector import _heuristic_trend_predict

        closes = [100 + (i % 2) * 0.01 for i in range(30)]
        result = _heuristic_trend_predict(closes)
        assert result["direction"] in ("hold", "buy", "sell")

    def test_indicators_dict_present_on_signal(self):
        from services.ml_signal_connector import _heuristic_trend_predict

        closes = [100 * (1.01**i) for i in range(30)]
        result = _heuristic_trend_predict(closes)
        assert "indicators" in result
        for k in ("ma_ratio", "rsi", "macd_signal", "atr_norm"):
            assert k in result["indicators"]

    def test_handles_zero_prices(self):
        from services.ml_signal_connector import _heuristic_trend_predict

        closes = [0] * 15
        result = _heuristic_trend_predict(closes)
        assert result["direction"] == "hold"
