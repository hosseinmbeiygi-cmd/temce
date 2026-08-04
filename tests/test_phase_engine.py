"""Integration tests for Smart Money Phase Engine.

Tests cover:
- Phase classification from config
- Phase smoothing (hysteresis)
- Phase alerts
- Feature store caching
"""
from __future__ import annotations

import time

from services.smart_money.config_loader import (
    classify_phase_from_config,
    compute_weighted_score,
    load_config,
)
from services.smart_money.feature_store import FeatureStore, FeatureVector
from services.smart_money.phase_alerts import PhaseAlertConfig, PhaseAlertService
from services.smart_money.scoring_engine import ScoringEngine

# ── Phase Classification Tests ──────────────────────────────────────────────


class TestPhaseClassification:
    """Test phase classification from config rules."""

    def test_load_config(self):
        """Config loads successfully with phase rules."""
        cfg = load_config()
        assert len(cfg.phase_rules) > 0
        assert cfg.version == "2.0.0"

    def test_confirmed_smart_money_phase(self):
        """High scores should classify as confirmed_smart_money."""
        cfg = load_config()
        scores = {
            "smc": 0.80,
            "acc": 0.70,
            "abs_final": 0.70,
            "fl": 0.65,
            "br": 0.70,
            "ess": 0.65,
            "rrs": 0.60,
            "rmr_n": 0.55,
            "dps_n": 0.60,
            "rp_n": 0.70,
        }
        phase = classify_phase_from_config(cfg, scores)
        assert phase == "confirmed_smart_money"

    def test_breakout_ready_phase(self):
        """Breakout-ready conditions should classify correctly."""
        cfg = load_config()
        scores = {
            "smc": 0.50,
            "acc": 0.50,
            "abs_final": 0.50,
            "fl": 0.50,
            "br": 0.75,
            "ess": 0.65,
            "rrs": 0.50,
            "rmr_n": 0.50,
            "dps_n": 0.50,
            "rp_n": 0.80,
        }
        phase = classify_phase_from_config(cfg, scores)
        assert phase == "breakout_ready"

    def test_neutral_fallback(self):
        """Low scores should fallback to neutral."""
        cfg = load_config()
        scores = {
            "smc": 0.30,
            "acc": 0.30,
            "abs_final": 0.30,
            "fl": 0.30,
            "br": 0.30,
            "ess": 0.30,
            "rrs": 0.30,
            "rmr_n": 0.30,
            "dps_n": 0.30,
            "rp_n": 0.30,
        }
        phase = classify_phase_from_config(cfg, scores)
        assert phase == "neutral"

    def test_empty_scores(self):
        """Empty scores should return neutral."""
        cfg = load_config()
        phase = classify_phase_from_config(cfg, {})
        assert phase == "neutral"


# ── Phase Smoothing (Hysteresis) Tests ──────────────────────────────────────


class TestPhaseSmoothing:
    """Test phase smoothing with hysteresis."""

    def setup_method(self):
        self.engine = ScoringEngine()

    def test_immediate_downgrade(self):
        """Downgrade should be immediate."""
        symbol = "TEST_DOWNGRADE"
        # First, establish a high phase
        self.engine._phase_history[symbol] = "confirmed_smart_money"
        # Now try to downgrade
        result = self.engine._smooth_phase(symbol, "early_accumulation", 0.5)
        assert result == "early_accumulation"

    def test_upgrade_requires_consecutive_days(self):
        """Upgrade should require 2 consecutive days."""
        symbol = "TEST_UPGRADE"
        # Try to upgrade once - should be blocked
        result1 = self.engine._smooth_phase(symbol, "active_absorption", 0.5)
        assert result1 == "neutral"  # Still neutral

        # Try again - should be allowed
        result2 = self.engine._smooth_phase(symbol, "active_absorption", 0.5)
        assert result2 == "active_absorption"

    def test_phase_change_tracking(self):
        """Phase changes should be tracked in history."""
        symbol = "TEST_TRACKING"
        self.engine._smooth_phase(symbol, "active_absorption", 0.5)
        self.engine._smooth_phase(symbol, "active_absorption", 0.5)
        assert self.engine._phase_history[symbol] == "active_absorption"


# ── Phase Alert Tests ────────────────────────────────────────────────────────


class TestPhaseAlerts:
    """Test phase change alert system."""

    def setup_method(self):
        self.service = PhaseAlertService(config=PhaseAlertConfig(cooldown_seconds=0))  # No cooldown for testing

    def test_first_symbol_no_alert(self):
        """First time seeing a symbol should not trigger alert."""
        event = ("TEST1", "active_absorption", 0.6)
        assert event is None

    def test_phase_change_triggers_alert(self):
        """Phase change should trigger alert."""
        self.service.check_phase_change("TEST2", "neutral", 0.5)
        event = ("TEST2", "active_absorption", 0.7)
        assert event is not None
        assert event.is_upgrade is True
        assert event.old_phase == "neutral"
        assert event.new_phase == "active_absorption"

    def test_same_phase_no_alert(self):
        """Same phase should not trigger alert."""
        self.service.check_phase_change("TEST3", "neutral", 0.5)
        event = self.service.check_phase_change("TEST3", "neutral", 0.5)
        assert event is None

    def test_alert_severity(self):
        """Alert severity should be determined correctly."""
        self.service.check_phase_change("TEST4", "neutral", 0.5)
        event = ("TEST4", "confirmed_smart_money", 0.8)
        assert event is not None
        assert event.severity == "success"

    def test_get_recent_events(self):
        """Should return recent events."""
        self.service.check_phase_change("TEST5", "neutral", 0.5)
        self.service.check_phase_change("TEST5", "active_absorption", 0.7)
        events = self.service.get_recent_events(limit=10)
        assert len(events) == 1

    def test_clear_history(self):
        """Clear history should reset all data."""
        self.service.check_phase_change("TEST6", "neutral", 0.5)
        self.service.check_phase_change("TEST6", "active_absorption", 0.7)
        self.service.clear_history()
        assert len(self.service.get_all_phases()) == 0
        assert len(self.service.get_recent_events()) == 0


# ── Feature Store Tests ─────────────────────────────────────────────────────


class TestFeatureStore:
    """Test feature store caching."""

    def setup_method(self):
        self.store = FeatureStore(ttl=5)

    def test_put_and_get(self):
        """Should cache and retrieve features."""
        fv = FeatureVector(symbol="TEST", timestamp=time.time(), pvs=0.8)
        self.store.put("TEST", fv)
        result = self.store.get("TEST")
        assert result is not None
        assert result.pvs == 0.8

    def test_cache_expiry(self):
        """Cache should expire after TTL."""
        store = FeatureStore(ttl=0)  # Immediate expiry
        fv = FeatureVector(symbol="TEST", timestamp=time.time(), pvs=0.8)
        store.put("TEST", fv)
        time.sleep(0.01)
        result = store.get("TEST")
        assert result is None

    def test_lru_eviction(self):
        """Cache should evict oldest entries when full."""
        store = FeatureStore(ttl=60, max_size=3)
        for i in range(5):
            fv = FeatureVector(symbol=f"SYM{i}", timestamp=time.time(), pvs=float(i))
            store.put(f"SYM{i}", fv)
        assert len(store._cache) == 3
        # Oldest should be evicted
        assert store.get("SYM0") is None
        assert store.get("SYM1") is None

    def test_invalidate(self):
        """Should invalidate specific symbol."""
        fv = FeatureVector(symbol="TEST", timestamp=time.time(), pvs=0.8)
        self.store.put("TEST", fv)
        self.store.invalidate("TEST")
        assert self.store.get("TEST") is None

    def test_stats(self):
        """Should return cache statistics."""
        fv = FeatureVector(symbol="TEST", timestamp=time.time(), pvs=0.8)
        self.store.put("TEST", fv)
        self.store.get("TEST")
        stats = self.store.get_stats()
        assert stats["total_entries"] == 1
        assert stats["hits"] == 1


# ── Weighted Score Tests ────────────────────────────────────────────────────


class TestWeightedScore:
    """Test weighted score computation."""

    def test_basic_weighted_score(self):
        """Basic weighted score should work."""
        cfg = load_config()
        weights = {"a": 0.5, "b": 0.5}
        features = {"a": 0.8, "b": 0.6}
        score = compute_weighted_score(cfg, weights, features)
        assert abs(score - 0.7) < 0.01

    def test_missing_feature(self):
        """Missing feature should use default 0."""
        cfg = load_config()
        weights = {"a": 0.5, "b": 0.5}
        features = {"a": 0.8}
        score = compute_weighted_score(cfg, weights, features)
        assert abs(score - 0.4) < 0.01

    def test_score_bounds(self):
        """Score should be bounded between 0 and 1."""
        cfg = load_config()
        weights = {"a": 1.0}
        features = {"a": 1.5}
        score = compute_weighted_score(cfg, weights, features)
        assert score == 1.0

        features = {"a": -0.5}
        score = compute_weighted_score(cfg, weights, features)
        assert score == 0.0
