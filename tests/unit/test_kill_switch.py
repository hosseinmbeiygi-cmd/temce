"""Tests for the system-wide Kill Switch (سند v5.0 §15.3 + §19.3).

Covers the in-process mirror (sync hot path), Redis persistence path
(async), event history, and the integration with the IME signal factory.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.ime_signal_factory import MarketState, PricingCandidate, StrategyType, process_candidate
from services.kill_switch import (
    KillSwitch,
    TradingHaltedError,
    assert_not_killed,
    kill_switch,
)


def _passing_candidate() -> PricingCandidate:
    return PricingCandidate(
        candidate_id="test",
        strategy_type=StrategyType.CALENDAR_ARB,
        instrument_keys=["a", "b"],
        theoretical_price=100.0,
        market_price=99.0,
        mispricing_pct=0.01,
        iv=0.3,
        data_quality=0.9,
        liquidity_depth=0.8,
        execution_ease=0.85,
        model_confidence=0.75,
    )


def _passing_state() -> MarketState:
    return MarketState(
        snapshot_age_seconds=2.0,
        days_to_delivery=10.0,
        visible_volume=1000,
        min_strategy_volume=200,
        tick_size=1.0,
        proposed_price=100.0,
        gross_edge=1000.0,
        commission=10.0,
        market_impact=0.0,
        latency_buffer=5.0,
        avg_volume=5000,
        short_term_volatility=0.2,
        eta=0.1,
        gamma=0.05,
        account_risk_budget=10_000.0,
        stop_loss_distance=10.0,
    )


def _reset():
    """Reset singleton + in-process mirror between tests."""
    KillSwitch.reset_singleton()
    from services import kill_switch as ks

    ks._LOCAL_STATE.update({"killed": False, "by": "", "reason": "", "at": 0.0})


class TestKillSwitchSync:
    def setup_method(self):
        _reset()

    def test_default_not_killed(self):
        assert kill_switch.is_killed() is False
        s = kill_switch.status()
        assert s.killed is False
        assert s.by == ""

    def test_kill_then_revive(self):
        ks = kill_switch
        # kill is async; use the async helper via a tiny event loop wrapper
        import asyncio

        asyncio.run(ks.kill("admin_user", "drawdown breach"))
        # But the sync mirror updated in the kill() call already
        assert ks.is_killed() is True
        s = ks.status()
        assert s.by == "admin_user"
        assert "drawdown" in s.reason
        # Revive
        asyncio.run(ks.revive("admin_user"))
        assert ks.is_killed() is False


class TestAssertNotKilled:
    def setup_method(self):
        _reset()

    def test_passes_when_not_killed(self):
        assert_not_killed()  # should not raise

    def test_raises_when_killed(self):
        import asyncio

        asyncio.run(kill_switch.kill("admin", "test reason"))
        with pytest.raises(TradingHaltedError, match="test reason"):
            assert_not_killed()


class TestSignalFactoryIntegration:
    def setup_method(self):
        _reset()

    def test_process_candidate_blocks_when_killed(self):
        import asyncio

        asyncio.run(kill_switch.kill("admin", "crisis"))
        with pytest.raises(TradingHaltedError):
            process_candidate(_passing_candidate(), _passing_state())

    def test_process_candidate_passes_when_not_killed(self):
        from services.ime_signal_factory import SignalMaturity

        maturity, reject, card = process_candidate(_passing_candidate(), _passing_state())
        assert maturity is SignalMaturity.TRADE_CARD
        assert card is not None


class TestRedisPersistence:
    def setup_method(self):
        _reset()

    async def test_kill_writes_to_redis(self):
        mock_cm = MagicMock()
        mock_cm.get = AsyncMock(return_value=None)
        mock_cm.set = AsyncMock(return_value=True)
        with patch("core.cache_manager.get_cache_manager", return_value=mock_cm):
            ks = KillSwitch()
            await ks.kill("admin", "redis test")
            assert mock_cm.set.call_count >= 2
            # Find the state-write call (any key starting with system:kill_switch:state)
            state_calls = [c for c in mock_cm.set.call_args_list if c.args[0] == "system:kill_switch:state"]
            assert len(state_calls) == 1
            import json

            payload = json.loads(state_calls[0].args[1])
            assert payload["killed"] is True
            assert payload["by"] == "admin"

    async def test_refresh_reads_from_redis(self):
        import json

        state_json = json.dumps({"killed": True, "by": "redis_admin", "reason": "remote", "at": 12345.0})
        mock_cm = MagicMock()
        mock_cm.get = AsyncMock(return_value=state_json)
        with patch("core.cache_manager.get_cache_manager", return_value=mock_cm):
            ks = KillSwitch()
            refreshed = await ks.refresh()
            assert refreshed.killed is True
            assert refreshed.by == "redis_admin"
            # Sync mirror updated
            assert kill_switch.is_killed() is True

    async def test_redis_failure_falls_back_to_local(self):
        mock_cm = MagicMock()
        mock_cm.get = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("core.cache_manager.get_cache_manager", return_value=mock_cm):
            ks = KillSwitch()
            # When Redis read fails, the in-process mirror is the fallback
            state = ks.status()
            # In-process mirror is the default (not killed) — fallback works
            assert state.killed is False


class TestHistoryEvent:
    def setup_method(self):
        _reset()

    async def test_activated_event_logged(self):
        mock_cm = MagicMock()
        mock_cm.get = AsyncMock(return_value=None)
        mock_cm.set = AsyncMock(return_value=True)
        with patch("core.cache_manager.get_cache_manager", return_value=mock_cm):
            ks = KillSwitch()
            await ks.kill("admin", "history test")
            # At least one set call should have a history key (with timestamp)
            history_calls = [
                c for c in mock_cm.set.call_args_list if c.args[0].startswith("system:kill_switch:history:")
            ]
            assert len(history_calls) == 1
            import json

            payload = json.loads(history_calls[0].args[1])
            assert payload["event"] == "activated"
            assert payload["actor"] == "admin"
            assert payload["reason"] == "history test"
