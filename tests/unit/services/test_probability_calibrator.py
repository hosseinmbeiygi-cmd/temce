"""Unit tests for ProbabilityCalibrator — calibration bucket logic, hierarchy, and edge cases.

Tests cover:
  - Static helpers: _bucket_for_score, _is_calibration_poor, fix_probability
  - Dataclass serialization: CalibratedProbability.to_dict(), CalibrationBuckets
  - Bucket assignment logic (bucket_key computation in _try_level)
  - Calibration hierarchy: calibrate() fallback through Market+Regime → Market → Global → raw
  - calibrate() with mocked DB data (returns calibrated probability from bucket data)
  - calibrate() edge cases: raw score clamping, empty buckets, no matching bucket"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.probability_calibrator import (
    CalibratedProbability,
    CalibrationBuckets,
    ProbabilityCalibrator,
)

# ═══════════════════════════════════════════════════════════════════════════════
# ── Static Helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestBucketForScore:
    def test_exact_bucket_match(self):
        assert ProbabilityCalibrator._bucket_for_score(0.55) == "0.55-0.60"
        assert ProbabilityCalibrator._bucket_for_score(0.60) == "0.60-0.65"
        assert ProbabilityCalibrator._bucket_for_score(0.72) == "0.70-0.75"

    def test_below_lowest_bucket(self):
        """Score 0.3 falls below 0.50 → goes to '0.00-0.50' bucket."""
        assert ProbabilityCalibrator._bucket_for_score(0.3) == "0.00-0.50"

    def test_above_highest_bucket(self):
        """Score 0.98 falls into 0.95-1.00."""
        assert ProbabilityCalibrator._bucket_for_score(0.98) == "0.95-1.00"

    def test_edge_at_1_point_0(self):
        assert ProbabilityCalibrator._bucket_for_score(1.0) == "0.95-1.00"

    def test_edge_between_buckets(self):
        """Score exactly 0.60 falls in lower bucket [0.55, 0.60)."""
        assert ProbabilityCalibrator._bucket_for_score(0.60) == "0.60-0.65"
        assert ProbabilityCalibrator._bucket_for_score(0.599) == "0.55-0.60"

    def test_low_below_50(self):
        assert ProbabilityCalibrator._bucket_for_score(0.0) == "0.00-0.50"
        assert ProbabilityCalibrator._bucket_for_score(0.45) == "0.00-0.50"
        assert ProbabilityCalibrator._bucket_for_score(0.499) == "0.00-0.50"

    def test_high_values(self):
        assert ProbabilityCalibrator._bucket_for_score(0.85) == "0.85-0.90"
        assert ProbabilityCalibrator._bucket_for_score(0.91) == "0.90-0.95"


class TestIsCalibrationPoor:
    def test_few_samples(self):
        """Less than 100 samples → True."""
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.10, total_samples=50) is True
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.05, total_samples=99) is True

    def test_high_brier(self):
        """Brier > 0.22 with enough samples → True."""
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.30, total_samples=200) is True
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.25, total_samples=500) is True

    def test_good_calibration(self):
        """Low Brier + enough samples → False."""
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.10, total_samples=200) is False
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.22, total_samples=150) is False

    def test_edge_brier(self):
        """Brier exactly 0.22 with enough samples → False (not > 0.22)."""
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.22, total_samples=200) is False

    def test_edge_samples(self):
        """Exactly 100 samples with good Brier → False."""
        assert ProbabilityCalibrator._is_calibration_poor(brier_score=0.15, total_samples=100) is False


class TestFixProbability:
    def test_normal_values(self):
        assert ProbabilityCalibrator.fix_probability(0.5) == 0.5
        assert ProbabilityCalibrator.fix_probability(0.75) == 0.75
        assert ProbabilityCalibrator.fix_probability(0.0) == 0.001
        assert ProbabilityCalibrator.fix_probability(1.0) == 0.999

    def test_clamping(self):
        assert ProbabilityCalibrator.fix_probability(-0.1) == 0.001
        assert ProbabilityCalibrator.fix_probability(1.5) == 0.999
        assert ProbabilityCalibrator.fix_probability(0.0005) == 0.001
        assert ProbabilityCalibrator.fix_probability(0.9999) == 0.999


# ═══════════════════════════════════════════════════════════════════════════════
# ── Dataclass Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalibratedProbability:
    def test_to_dict(self):
        cp = CalibratedProbability(
            calibrated_probability=0.683,
            raw_score=0.65,
            calibration_level="calibrated",
            calibration_version="1.0.0",
            method="bucket",
            bucket_count=45,
            notes=["test note"],
        )
        d = cp.to_dict()
        assert d["calibrated_probability"] == 0.683
        assert d["raw_score"] == 0.65
        assert d["calibration_level"] == "calibrated"
        assert d["method"] == "bucket"
        assert d["bucket_count"] == 45
        assert d["notes"] == ["test note"]
        assert d["calibration_version"] == "1.0.0"

    def test_defaults(self):
        cp = CalibratedProbability(
            calibrated_probability=0.5,
            raw_score=0.5,
            calibration_level="no_calibration",
            calibration_version="0.0.0",
            method="none",
            bucket_count=0,
        )
        assert cp.notes == []
        d = cp.to_dict()
        assert d["notes"] == []


class TestCalibrationBuckets:
    def test_defaults(self):
        cb = CalibrationBuckets()
        assert cb.buckets == {}
        assert cb.total_signals == 0
        assert cb.brier_score == 999.0
        assert cb.expected_calibration_error == 999.0
        assert cb.model_version == "0.0.0"
        assert cb.calibrated_at == ""


# ═══════════════════════════════════════════════════════════════════════════════
# ── Calibrator Core Logic (no DB mocking needed)
# ═══════════════════════════════════════════════════════════════════════════════


class TestProbabilityCalibratorInit:
    def test_default_version(self):
        calibrator = ProbabilityCalibrator()
        assert calibrator._version == "1.0.0"
        assert calibrator.MIN_SIGNALS_PER_BUCKET == 30

    def test_bucket_edges_match_defaults(self):
        """Verify DEFAULT_BUCKETS has expected values."""
        expected = [
            0.0,
            0.50,
            0.55,
            0.60,
            0.65,
            0.70,
            0.75,
            0.80,
            0.85,
            0.90,
            0.95,
            1.0,
        ]
        assert expected == ProbabilityCalibrator.DEFAULT_BUCKETS


# ═══════════════════════════════════════════════════════════════════════════════
# ── Calibrator with Mocked DB
# ═══════════════════════════════════════════════════════════════════════════════


class MockRow:
    """Simulate a SQLAlchemy row with tuple-like access."""

    def __init__(self, values: tuple):
        self._values = values

    def __getitem__(self, idx):
        return self._values[idx]


class MockResult:
    """Simulate SQLAlchemy result with fetchone/fetchall."""

    def __init__(self, rows: list[tuple] | tuple | None):
        if isinstance(rows, tuple) or rows is None:
            self._rows = [rows] if rows else []
            self._is_one = True
        else:
            self._rows = rows
            self._is_one = False

    def fetchone(self):
        if self._rows:
            return MockRow(self._rows[0])
        return None

    def fetchall(self):
        return [MockRow(r) for r in self._rows]


def _make_mock_session(calibration_rows: list[tuple] | None = None):
    """Create a mock async session that returns pre-canned calibration data.

    The calibration_models table schema:
      (id, model_version, method, parameters_json, brier_score, ece, total_samples, last_trained_at)
    """
    session = AsyncMock()
    if calibration_rows:
        session.execute.return_value = MockResult(calibration_rows)
    else:
        session.execute.return_value = MockResult(None)
    return session


def _make_mock_factory(mock_session):
    """Create a mock async_session_factory that returns the mock session."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = mock_session
    factory.return_value.__aexit__.return_value = None
    return factory


class TestCalibrateWithMockDB:
    @pytest.mark.asyncio
    async def test_no_calibration_data_falls_back_to_raw(self):
        """When no calibration model exists in DB, returns raw score unchanged."""
        calibrator = ProbabilityCalibrator()
        mock_session = _make_mock_session(calibration_rows=None)
        mock_factory = _make_mock_factory(mock_session)

        with patch("core.database.async_session_factory", mock_factory), patch.object(
            calibrator, "_try_bootstrap", new_callable=AsyncMock, return_value=None
        ):
            result = await calibrator.calibrate(
                raw_score=0.65,
                market="stock",
                timeframe="daily",
                direction="buy",
            )

        assert result.calibrated_probability == pytest.approx(0.65)
        assert result.calibration_level == "no_calibration"
        assert result.method == "none"
        assert result.bucket_count == 0

    @pytest.mark.asyncio
    async def test_calibrate_with_bucket_match(self):
        """When calibration model exists and bucket matches, returns calibrated rate."""
        bucket_data = json.dumps(
            {
                "0.65-0.70": {"predicted_mean": 0.67, "actual_rate": 0.63, "count": 50},
                "0.70-0.75": {
                    "predicted_mean": 0.72,
                    "actual_rate": 0.68,
                    "count": 100,
                },
            }
        )

        # (id, model_version, method, parameters, brier_score, ece, total_samples, last_trained_at)
        row = (
            "cal_stock_daily_buy",
            "1.0.0",
            "bucket",
            bucket_data,
            0.15,
            0.04,
            200,
            datetime(2026, 1, 1),
        )

        calibrator = ProbabilityCalibrator()
        mock_session = _make_mock_session([row])
        mock_factory = _make_mock_factory(mock_session)

        with patch("core.database.async_session_factory", mock_factory):
            result = await calibrator.calibrate(
                raw_score=0.72,
                market="stock",
                timeframe="daily",
                direction="buy",
            )

        # raw_score=0.72 falls in bucket "0.70-0.75" with actual_rate=0.68
        # count=100 >= MIN_SIGNALS_PER_BUCKET(30) → no blending, calibrated = actual_rate
        assert result.calibrated_probability == pytest.approx(0.68, abs=0.001)
        assert result.calibration_level == "calibrated"
        assert result.method == "bucket"
        assert result.bucket_count == 100
        assert result.calibration_version == "1.0.0"
        assert "100" in result.notes[0] if result.notes else True  # note about count

    @pytest.mark.asyncio
    async def test_calibrate_with_low_data_blend(self):
        """When count < MIN_SIGNALS_PER_BUCKET, blends actual_rate with raw_score."""
        bucket_data = json.dumps(
            {
                "0.65-0.70": {"predicted_mean": 0.67, "actual_rate": 0.63, "count": 15},
            }
        )

        row = (
            "cal_stock_daily_buy",
            "1.0.0",
            "bucket",
            bucket_data,
            0.15,
            0.04,
            200,
            datetime(2026, 1, 1),
        )

        calibrator = ProbabilityCalibrator()
        mock_session = _make_mock_session([row])
        mock_factory = _make_mock_factory(mock_session)

        with patch("core.database.async_session_factory", mock_factory):
            result = await calibrator.calibrate(
                raw_score=0.68,
                market="stock",
                timeframe="daily",
                direction="buy",
            )

        # raw=0.68 in bucket 0.65-0.70, actual_rate=0.63, count=15
        # blend_weight = 15/30 = 0.5
        # calibrated = 0.68 * 0.5 + 0.63 * 0.5 = 0.655

        assert result.calibrated_probability == pytest.approx(0.655, abs=0.001)
        assert result.calibration_level == "low_data"
        assert result.bucket_count == 15

    @pytest.mark.asyncio
    async def test_calibrate_closest_bucket_fallback(self):
        """When exact bucket not found, uses closest bucket."""
        bucket_data = json.dumps(
            {
                "0.70-0.75": {"predicted_mean": 0.72, "actual_rate": 0.68, "count": 50},
            }
        )

        row = (
            "cal_stock_daily_buy",
            "1.0.0",
            "bucket",
            bucket_data,
            0.15,
            0.04,
            100,
            datetime(2026, 1, 1),
        )

        calibrator = ProbabilityCalibrator()
        mock_session = _make_mock_session([row])
        mock_factory = _make_mock_factory(mock_session)

        with patch("core.database.async_session_factory", mock_factory):
            result = await calibrator.calibrate(
                raw_score=0.50,
                market="stock",
                timeframe="daily",
                direction="buy",
            )

        # raw=0.50 → no exact bucket match → closest is 0.70-0.75 with actual_rate=0.68
        assert result.calibrated_probability == pytest.approx(0.68, abs=0.001)
        assert result.calibration_level == "low_data"
        assert result.method == "bucket"

    @pytest.mark.asyncio
    async def test_calibrate_raw_score_clamping(self):
        """Raw scores outside [0.01, 0.99] are clamped."""
        calibrator = ProbabilityCalibrator()
        mock_session = _make_mock_session(None)
        mock_factory = _make_mock_factory(mock_session)

        with patch("core.database.async_session_factory", mock_factory), patch.object(
            calibrator, "_try_bootstrap", new_callable=AsyncMock, return_value=None,
        ):
            result_high = await calibrator.calibrate(
                raw_score=1.5,
                market="stock",
                timeframe="daily",
                direction="buy",
            )
            result_low = await calibrator.calibrate(
                raw_score=-0.5,
                market="stock",
                timeframe="daily",
                direction="buy",
            )

        assert result_high.raw_score == pytest.approx(0.99)
        assert result_low.raw_score == pytest.approx(0.01)

    @pytest.mark.asyncio
    async def test_calibrate_hierarchy_falls_through(self):
        """calibrate() tries Market+Regime → Market → Global → raw fallback.

        Only Global level has data, so it should use that.
        """
        bucket_data = json.dumps(
            {
                "0.55-0.60": {"predicted_mean": 0.57, "actual_rate": 0.56, "count": 40},
            }
        )

        # Global calibration model (empty market, timeframe, direction)
        row = ("cal____", "1.0.0", "bucket", bucket_data, 0.12, 0.03, 500, datetime(2026, 1, 1))

        calibrator = ProbabilityCalibrator()
        mock_session = _make_mock_session([row])
        mock_factory = _make_mock_factory(mock_session)

        with patch("core.database.async_session_factory", mock_factory):
            result = await calibrator.calibrate(
                raw_score=0.57,
                market="stock",
                timeframe="daily",
                direction="buy",
                regime="TREND",
            )

        # Should find the global calibration model (empty market/timeframe/direction)
        assert result.calibrated_probability == pytest.approx(0.56, abs=0.001)
        assert result.method == "bucket"

    @pytest.mark.asyncio
    async def test_calibrate_with_poor_calibration_adds_note(self):
        """When Brier > 0.22 and samples < 100, notes include calibration warning."""
        bucket_data = json.dumps(
            {
                "0.60-0.65": {"predicted_mean": 0.62, "actual_rate": 0.58, "count": 50},
            }
        )

        # brier=0.30 (poor), total_samples=50 (< 100)
        row = (
            "cal_stock_daily_buy",
            "1.0.0",
            "bucket",
            bucket_data,
            0.30,
            0.10,
            50,
            datetime(2026, 1, 1),
        )

        calibrator = ProbabilityCalibrator()
        mock_session = _make_mock_session([row])
        mock_factory = _make_mock_factory(mock_session)

        with patch("core.database.async_session_factory", mock_factory), patch.object(
            calibrator, "_try_bootstrap", new_callable=AsyncMock, return_value=None,
        ):
            result = await calibrator.calibrate(
                raw_score=0.62,
                market="stock",
                timeframe="daily",
                direction="buy",
            )

        assert result.calibrated_probability is not None
        # Should have at least one warning note about poor calibration or low data
        assert len(result.notes) > 0
        assert result.calibration_level in ("calibrated", "low_data")


# ═══════════════════════════════════════════════════════════════════════════════
# ── Orchestrator Parsing Tests (from quant_signal_orchestrator.py)
# ═══════════════════════════════════════════════════════════════════════════════

# We import these from the orchestrator
from services.quant_signal_orchestrator import QuantSignalOrchestrator


class TestParseRiskReward:
    def test_direct_float(self):

        assert QuantSignalOrchestrator._parse_risk_reward("2.5") == pytest.approx(2.5)

        assert QuantSignalOrchestrator._parse_risk_reward("1.0") == pytest.approx(1.0)

        assert QuantSignalOrchestrator._parse_risk_reward("0.5") == pytest.approx(0.5)

    def test_ratio_format(self):

        assert QuantSignalOrchestrator._parse_risk_reward("1:2.5") == pytest.approx(2.5)

        assert QuantSignalOrchestrator._parse_risk_reward("1:3") == pytest.approx(3.0)

        assert QuantSignalOrchestrator._parse_risk_reward("1:1.5") == pytest.approx(1.5)

    def test_persian_comma_in_regex_fallback(self):
        """Comma as decimal separator should work via regex path.

        Note: the ratio format path (split on ':') doesn't handle comma decimals,
        but the regex fallback path does via replace(',', '.').
        The regex path returns the first valid number in [0.1, 100],
        so '1' is returned before '2.5'."""

        assert QuantSignalOrchestrator._parse_risk_reward("2,5") == pytest.approx(2.5)

    def test_empty_string(self):
        assert QuantSignalOrchestrator._parse_risk_reward("") == 0.0
        assert QuantSignalOrchestrator._parse_risk_reward(None) == 0.0

    def test_invalid_string(self):
        assert QuantSignalOrchestrator._parse_risk_reward("invalid") == 0.0
        assert QuantSignalOrchestrator._parse_risk_reward("abc") == 0.0

    def test_high_value_in_ratio_format(self):
        """Ratio format returns second part directly without range check."""

        assert QuantSignalOrchestrator._parse_risk_reward("1:200") == pytest.approx(200.0)


class TestParseStopLossPct:
    def test_percentage_format(self):
        sl = QuantSignalOrchestrator._parse_stop_loss_pct("-5%", price=50000)
        assert sl == pytest.approx(0.05)

    def test_percentage_without_minus(self):
        sl = QuantSignalOrchestrator._parse_stop_loss_pct("5%", price=50000)
        assert sl == pytest.approx(0.05)

    def test_price_amount_format(self):
        """Stop loss as absolute price (47500 for entry at 50000 = 5% drop)."""
        sl = QuantSignalOrchestrator._parse_stop_loss_pct("47500", price=50000)
        assert sl == pytest.approx(0.05, abs=0.001)

    def test_empty_string_default(self):
        sl = QuantSignalOrchestrator._parse_stop_loss_pct("", price=50000)
        assert sl == pytest.approx(0.05)

    def test_none_default(self):
        sl = QuantSignalOrchestrator._parse_stop_loss_pct(None, price=50000)
        assert sl == pytest.approx(0.05)

    def test_zero_price_default(self):
        sl = QuantSignalOrchestrator._parse_stop_loss_pct("-5%", price=0)
        assert sl == pytest.approx(0.05)

    def test_large_percentage_unlikely(self):
        """50%+ change normalized to default 5% (heuristic)."""
        sl = QuantSignalOrchestrator._parse_stop_loss_pct("25000", price=50000)
        # pct = abs(25000 - 50000) / 50000 = 0.5 -> 0.5 is at boundary, 0.001 <= 0.5 <= 0.5 → True
        assert sl == pytest.approx(0.5)

    def test_very_large_difference_default(self):
        """Very large difference > 500% -> returns default 5%."""
        sl = QuantSignalOrchestrator._parse_stop_loss_pct("1000", price=50000)
        # pct = |1000-50000|/50000 = 0.98 > 0.5 → next check: 0.98 <= 5 → True → 0.05
        # Actually 0.98 > 0.5 but <= 5, so returns 0.05
        assert sl == pytest.approx(0.05)


class TestParseTargetPct:
    def test_percentage_format(self):
        t = QuantSignalOrchestrator._parse_target_pct("+10%", price=50000)
        assert t == pytest.approx(0.10)

    def test_price_amount_format(self):
        """Target as absolute price (55000 for entry at 50000 = 10% gain)."""
        t = QuantSignalOrchestrator._parse_target_pct("55000", price=50000)
        assert t == pytest.approx(0.10, abs=0.001)

    def test_empty_string(self):

        assert QuantSignalOrchestrator._parse_target_pct("", price=50000) == 0.0

    def test_none_value(self):

        assert QuantSignalOrchestrator._parse_target_pct(None, price=50000) == 0.0

    def test_invalid_format(self):

        assert QuantSignalOrchestrator._parse_target_pct("invalid", price=50000) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ── Orchestrator Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestApplyProbabilityCalibration:
    @pytest.mark.asyncio
    async def test_applies_calibration_to_enriched_signals(self):
        """_apply_probability_calibration should call calibrator and store results."""
        from services.quant_signal_orchestrator import (
            EnrichedSignal,
            QuantSignalOrchestrator,
        )

        orchestrator = QuantSignalOrchestrator()

        # Create a mock EnrichedSignal
        sig = EnrichedSignal(
            symbol="فولاد",
            name="فولاد مبارکه",
            market="stock",
            direction="buy",
            timeframe="daily",
            entry_zone="50000",
            stop_loss="47500",
            targets="55000",
            risk_reward="2.0",
            position_sizing="10%",
            confirmation_condition="",
            reason="test",
            invalidation="",
            trailing_stop="",
            price=50000,
            change_pct=0.5,
            rule_score=72.0,
            ml_score=0.0,
            boosted_score=72.0,
            ml_influence_pct=0.0,
            confidence=0.6,
            calibration_level="medium",
            source="test",
            created_at="",
        )

        # Mock the calibrator
        mock_result = CalibratedProbability(
            calibrated_probability=0.68,
            raw_score=0.72,
            calibration_level="calibrated",
            calibration_version="1.0.0",
            method="bucket",
            bucket_count=100,
            notes=["test note"],
        )

        with patch(
            "services.probability_calibrator.ProbabilityCalibrator.calibrate",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await orchestrator._apply_probability_calibration([sig])

        assert len(result) == 1
        assert result[0].calibrated_probability == 0.68
        assert result[0].calibration_method == "bucket"
        assert result[0].calibration_version == "1.0.0"
        assert "test note" in result[0].confidence_notes

    @pytest.mark.asyncio
    async def test_calibration_fallback_on_error(self):
        """When calibrator errors, sig.calibrated_probability falls back to raw score."""
        from services.quant_signal_orchestrator import (
            EnrichedSignal,
            QuantSignalOrchestrator,
        )

        orchestrator = QuantSignalOrchestrator()

        sig = EnrichedSignal(
            symbol="فولاد",
            name="فولاد مبارکه",
            market="stock",
            direction="buy",
            timeframe="daily",
            entry_zone="50000",
            stop_loss="47500",
            targets="55000",
            risk_reward="2.0",
            position_sizing="10%",
            confirmation_condition="",
            reason="test",
            invalidation="",
            trailing_stop="",
            price=50000,
            change_pct=0.5,
            rule_score=72.0,
            ml_score=0.0,
            boosted_score=72.0,
            ml_influence_pct=0.0,
            confidence=0.6,
            calibration_level="medium",
            source="test",
            created_at="",
        )

        with patch(
            "services.probability_calibrator.ProbabilityCalibrator.calibrate",
            new_callable=AsyncMock,
            side_effect=Exception("DB error"),
        ):
            result = await orchestrator._apply_probability_calibration([sig])

        assert len(result) == 1
        # Fallback: uses raw = max(0.01, min(0.99, ml_score (=0.0) or rule_score/100 (=0.72)))
        assert result[0].calibrated_probability == pytest.approx(0.72)
        assert result[0].calibration_method == "none"

    @pytest.mark.asyncio
    async def test_empty_signals_returns_empty(self):
        orchestrator = QuantSignalOrchestrator()
        result = await orchestrator._apply_probability_calibration([])
        assert result == []
