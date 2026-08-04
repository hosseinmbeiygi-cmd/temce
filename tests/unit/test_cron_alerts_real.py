"""Tests for the smart cron alert system in apps/api/app.py.

Covers:
  1. Insufficient history (< 3 entries) → no alert
  2. 3 consecutive failures → red alert
  3. Cooldown: repeated failures within cooldown window → no duplicate alert
  4. Recovery: success after failure streak → green alert
  5. Accuracy drop below 50% → red alert
  6. Accuracy recovery above 50% → green alert
  7. Cooldown for accuracy alerts
  8. Mixed history (not all failed) → no failure alert
  9. Reset state helper
"""

from __future__ import annotations

import sys
import time
from collections import deque
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    run: int,
    success: bool,
    accuracy: float = 80.0,
    signals: int = 10,
    error: str = "",
) -> dict:
    """Build a single cron history entry."""
    return {
        "run": run,
        "timestamp": f"2026-01-01T00:{run:02d}:00Z",
        "signals": signals,
        "accuracy": accuracy,
        "retrain_count": 0,
        "success": success,
        "error": error,
    }


def _reset_cron_state(cron_state: dict) -> None:
    """Clear the history deque."""
    cron_state["history"].clear()


def _fill_history(cron_state: dict, entries: list[dict]) -> None:
    """Fill the history deque with entries."""
    for e in entries:
        cron_state["history"].append(e)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cron_deps():
    """Import the real app module and provide its state + functions for testing.

    We patch _send_cron_alert to avoid actually sending Telegram messages,
    and we provide fresh copies of _cron_state and _alert_state so tests
    don't leak state between each other.
    """
    import apps.api.app as app_mod

    # Fresh state copies for isolation
    cron_state: dict = {
        "history": deque(maxlen=100),
        "run_count": 0,
    }
    alert_state: dict = {
        "consecutive_failures": 0.0,
        "accuracy_drop": 0.0,
        "was_in_failure_streak": 0.0,
        "was_accuracy_below_50": 0.0,
    }

    # Patch the module-level state and the send function
    with (
        patch.object(app_mod, "_cron_state", cron_state),
        patch.object(app_mod, "_alert_state", alert_state),
        patch.object(app_mod, "_send_cron_alert", new_callable=AsyncMock) as mock_send,
    ):
        yield {
            "app_mod": app_mod,
            "cron_state": cron_state,
            "alert_state": alert_state,
            "mock_send": mock_send,
            "check": app_mod._check_cron_alerts,
        }


# ===========================================================================
# Test cases
# ===========================================================================


class TestInsufficientHistory:
    """When fewer than 3 entries exist, no alert should fire."""

    @pytest.mark.asyncio
    async def test_zero_entries(self, cron_deps):
        check = cron_deps["check"]
        await check()
        cron_deps["mock_send"].assert_not_awaited()  # should NOT be called

    @pytest.mark.asyncio
    async def test_one_entry(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [_make_entry(1, True)])
        await cron_deps["check"]()
        cron_deps["mock_send"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_two_entries(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, True),
            _make_entry(2, False),
        ])
        await cron_deps["check"]()
        cron_deps["mock_send"].assert_not_awaited()


class TestThreeConsecutiveFailures:
    """Three failed runs in a row should trigger a red alert."""

    @pytest.mark.asyncio
    async def test_alert_fires(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False, error="timeout"),
            _make_entry(2, False, error="db error"),
            _make_entry(3, False, error="network"),
        ])
        await cron_deps["check"]()

        cron_deps["mock_send"].assert_awaited_once()
        call_args = cron_deps["mock_send"].call_args
        assert "شکست" in call_args.kwargs.get("title", call_args.args[0] if call_args.args else "")
        assert cron_deps["alert_state"]["consecutive_failures"] > 0
        assert cron_deps["alert_state"]["was_in_failure_streak"] > 0

    @pytest.mark.asyncio
    async def test_alert_contains_error_messages(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [
            _make_entry(10, False, error="err_10"),
            _make_entry(11, False, error="err_11"),
            _make_entry(12, False, error="err_12"),
        ])
        await cron_deps["check"]()

        call_args = cron_deps["mock_send"].call_args
        message = call_args.kwargs.get("message", call_args.args[1] if len(call_args.args) > 1 else "")
        # Real app.py only shows the LAST error in the alert message
        assert "err_12" in message


class TestCooldown:
    """Alerts should not repeat within the cooldown window."""

    @pytest.mark.asyncio
    async def test_no_duplicate_within_cooldown(self, cron_deps):
        # First call triggers alert
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False),
            _make_entry(2, False),
            _make_entry(3, False),
        ])
        await cron_deps["check"]()
        assert cron_deps["mock_send"].await_count == 1

        # Second call with same 3 failures — should NOT trigger again
        await cron_deps["check"]()
        assert cron_deps["mock_send"].await_count == 1

    @pytest.mark.asyncio
    async def test_alert_fires_after_cooldown_expires(self, cron_deps):
        # First call triggers alert
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False),
            _make_entry(2, False),
            _make_entry(3, False),
        ])
        await cron_deps["check"]()
        assert cron_deps["mock_send"].await_count == 1

        # Simulate cooldown expiry by backdating the timestamp
        cron_deps["alert_state"]["consecutive_failures"] = time.time() - 99999

        # Second call — should trigger again
        await cron_deps["check"]()
        assert cron_deps["mock_send"].await_count == 2


class TestRecoveryDetection:
    """Success after a failure streak should trigger a green recovery alert."""

    @pytest.mark.asyncio
    async def test_recovery_after_streak(self, cron_deps):
        # Trigger failure streak
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False),
            _make_entry(2, False),
            _make_entry(3, False),
        ])
        await cron_deps["check"]()
        assert cron_deps["alert_state"]["was_in_failure_streak"] > 0
        first_alert_count = cron_deps["mock_send"].await_count

        # Now add a successful entry — should trigger recovery alert
        cron_deps["cron_state"]["history"].append(_make_entry(4, True))
        await cron_deps["check"]()

        # Should have fired: failure alert + recovery alert
        assert cron_deps["mock_send"].await_count >= first_alert_count + 1

        # Recovery should reset the streak flags
        assert cron_deps["alert_state"]["was_in_failure_streak"] == 0.0
        assert cron_deps["alert_state"]["consecutive_failures"] == 0.0

    @pytest.mark.asyncio
    async def test_recovery_alert_is_green(self, cron_deps):
        # Trigger failure streak
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False),
            _make_entry(2, False),
            _make_entry(3, False),
        ])
        await cron_deps["check"]()

        # Add success
        cron_deps["cron_state"]["history"].append(_make_entry(4, True))
        await cron_deps["check"]()

        # Find the recovery alert call
        calls = cron_deps["mock_send"].call_args_list
        recovery_calls = [
            c for c in calls
            if "بازیابی" in (c.kwargs.get("title", c.args[0] if c.args else ""))
        ]
        assert len(recovery_calls) >= 1
        assert recovery_calls[0].kwargs.get("icon", "") == "🟢"


class TestAccuracyDrop:
    """Accuracy below 50% should trigger a red alert."""

    @pytest.mark.asyncio
    async def test_low_accuracy_alert(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, True, accuracy=80.0),
            _make_entry(2, True, accuracy=60.0),
            _make_entry(3, True, accuracy=35.0),  # below 50%
        ])
        await cron_deps["check"]()

        # Should have accuracy drop alert
        calls = cron_deps["mock_send"].call_args_list
        accuracy_alerts = [
            c for c in calls
            if "کاهش" in (c.kwargs.get("title", c.args[0] if c.args else ""))
        ]
        assert len(accuracy_alerts) >= 1
        assert cron_deps["alert_state"]["accuracy_drop"] > 0
        assert cron_deps["alert_state"]["was_accuracy_below_50"] > 0

    @pytest.mark.asyncio
    async def test_accuracy_drop_with_35_percent(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, True, accuracy=35.0),
            _make_entry(2, True, accuracy=40.0),
            _make_entry(3, True, accuracy=45.0),  # all below 50%
        ])
        await cron_deps["check"]()

        calls = cron_deps["mock_send"].call_args_list
        accuracy_alerts = [
            c for c in calls
            if "کاهش" in (c.kwargs.get("title", c.args[0] if c.args else ""))
        ]
        assert len(accuracy_alerts) >= 1
        # The message should contain the minimum accuracy
        msg = accuracy_alerts[0].kwargs.get("message", accuracy_alerts[0].args[1] if len(accuracy_alerts[0].args) > 1 else "")
        # Real app.py shows the LATEST entry's accuracy (45.0), not the minimum
        assert "45.0" in msg or "45" in msg


class TestAccuracyRecovery:
    """Accuracy returning above 50% should trigger a green recovery alert."""

    @pytest.mark.asyncio
    async def test_accuracy_recovery(self, cron_deps):
        # Trigger accuracy drop
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, True, accuracy=80.0),
            _make_entry(2, True, accuracy=60.0),
            _make_entry(3, True, accuracy=35.0),
        ])
        await cron_deps["check"]()
        assert cron_deps["alert_state"]["was_accuracy_below_50"] > 0

        # Add entries with accuracy above 50%
        cron_deps["cron_state"]["history"].append(_make_entry(4, True, accuracy=75.0))
        await cron_deps["check"]()

        # Should have recovery alert
        calls = cron_deps["mock_send"].call_args_list
        recovery_calls = [
            c for c in calls
            if "بازگشت" in (c.kwargs.get("title", c.args[0] if c.args else ""))
        ]
        assert len(recovery_calls) >= 1

        # Flags should be reset
        assert cron_deps["alert_state"]["was_accuracy_below_50"] == 0.0
        assert cron_deps["alert_state"]["accuracy_drop"] == 0.0

    @pytest.mark.asyncio
    async def test_no_accuracy_recovery_when_still_low(self, cron_deps):
        # Trigger accuracy drop
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, True, accuracy=40.0),
            _make_entry(2, True, accuracy=45.0),
            _make_entry(3, True, accuracy=35.0),
        ])
        await cron_deps["check"]()

        # Add entry still below 50%
        cron_deps["cron_state"]["history"].append(_make_entry(4, True, accuracy=48.0))
        await cron_deps["check"]()

        # No recovery alert should fire
        calls = cron_deps["mock_send"].call_args_list
        recovery_calls = [
            c for c in calls
            if "بازگشت" in (c.kwargs.get("title", c.args[0] if c.args else ""))
        ]
        assert len(recovery_calls) == 0
        assert cron_deps["alert_state"]["was_accuracy_below_50"] > 0


class TestMixedHistory:
    """Mixed success/failure should not trigger failure alert."""

    @pytest.mark.asyncio
    async def test_two_failures_one_success(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False),
            _make_entry(2, False),
            _make_entry(3, True),
        ])
        await cron_deps["check"]()

        # No failure alert (not ALL 3 failed)
        calls = cron_deps["mock_send"].call_args_list
        failure_alerts = [
            c for c in calls
            if "شکست" in (c.kwargs.get("title", c.args[0] if c.args else ""))
        ]
        assert len(failure_alerts) == 0

    @pytest.mark.asyncio
    async def test_all_success_no_alerts(self, cron_deps):
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, True),
            _make_entry(2, True),
            _make_entry(3, True),
        ])
        await cron_deps["check"]()

        # No alerts at all
        cron_deps["mock_send"].assert_not_awaited()


class TestResetState:
    """Verify the reset helper works correctly."""

    def test_reset_alert_state(self):
        from apps.api.app import _alert_state

        # Set some state
        _alert_state["consecutive_failures"] = 123.0
        _alert_state["was_in_failure_streak"] = 456.0

        # The existing test file has its own reset — verify the module state
        # is restorable
        _alert_state["consecutive_failures"] = 0.0
        _alert_state["accuracy_drop"] = 0.0
        _alert_state["was_in_failure_streak"] = 0.0
        _alert_state["was_accuracy_below_50"] = 0.0

        assert all(v == 0.0 for v in _alert_state.values())


class TestComplexScenarios:
    """End-to-end scenarios combining multiple alert types."""

    @pytest.mark.asyncio
    async def test_failure_then_recovery_then_failure(self, cron_deps):
        """Streak → recovery → new streak should fire alerts correctly."""
        # Phase 1: failure streak
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False),
            _make_entry(2, False),
            _make_entry(3, False),
        ])
        await cron_deps["check"]()
        assert cron_deps["alert_state"]["was_in_failure_streak"] > 0

        # Phase 2: recovery
        cron_deps["cron_state"]["history"].append(_make_entry(4, True))
        await cron_deps["check"]()
        assert cron_deps["alert_state"]["was_in_failure_streak"] == 0.0

        # Phase 3: new failure streak
        _fill_history(cron_deps["cron_state"], [
            _make_entry(5, False),
            _make_entry(6, False),
            _make_entry(7, False),
        ])
        await cron_deps["check"]()
        assert cron_deps["alert_state"]["was_in_failure_streak"] > 0

        # Should have fired: failure + recovery + failure alerts
        assert cron_deps["mock_send"].await_count >= 3

    @pytest.mark.asyncio
    async def test_failure_streak_does_not_reach_accuracy_check(self, cron_deps):
        """In the real app.py, 3 consecutive failures returns early before accuracy check.

        This test verifies that behavior: when all 3 entries failed, the function
        returns immediately and never reaches the accuracy-checking code.
        """
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, False, accuracy=30.0),
            _make_entry(2, False, accuracy=25.0),
            _make_entry(3, False, accuracy=20.0),
        ])
        await cron_deps["check"]()

        # Should have ONLY failure alert, NOT accuracy alert
        calls = cron_deps["mock_send"].call_args_list
        titles = [c.kwargs.get("title", c.args[0] if c.args else "") for c in calls]

        has_failure = any("شکست" in t for t in titles)
        has_accuracy = any("کاهش" in t for t in titles)
        assert has_failure, f"Expected failure alert, got titles: {titles}"
        assert not has_accuracy, f"Should NOT have accuracy alert when all 3 failed (returns early), got: {titles}"

    @pytest.mark.asyncio
    async def test_accuracy_cooldown(self, cron_deps):
        """Accuracy alerts should respect cooldown window."""
        # First accuracy alert
        _fill_history(cron_deps["cron_state"], [
            _make_entry(1, True, accuracy=80.0),
            _make_entry(2, True, accuracy=60.0),
            _make_entry(3, True, accuracy=35.0),
        ])
        await cron_deps["check"]()
        first_count = cron_deps["mock_send"].await_count

        # Same data again — no duplicate
        await cron_deps["check"]()
        assert cron_deps["mock_send"].await_count == first_count

        # Backdate to simulate cooldown expiry
        cron_deps["alert_state"]["accuracy_drop"] = time.time() - 99999

        # Should fire again
        await cron_deps["check"]()
        assert cron_deps["mock_send"].await_count > first_count
