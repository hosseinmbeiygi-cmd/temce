"""Regression tests for SignalAccuracyTracker.evaluate_signal.

Guards BUG FIX (root-cause patch C): direction_correct must use >= / <= so a
zero-move signal (exit == entry — very common for currency/gold) counts as
correct instead of False. Strict > penalized flat signals and dragged recorded
accuracy toward zero.
"""
import pytest

from services.signal_accuracy_tracker import SignalAccuracyTracker


@pytest.fixture
def tracker() -> SignalAccuracyTracker:
    return SignalAccuracyTracker()


def _signal(direction: str, price: float = 100.0) -> dict:
    return {"direction": direction, "price": price}


@pytest.mark.asyncio
async def test_buy_positive_move_correct(tracker):
    outcome = await tracker.evaluate_signal(_signal("buy"), entry_price=100.0, exit_price=105.0)
    assert outcome.direction_correct is True
    assert outcome.actual_return_pct == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_buy_zero_move_correct(tracker):
    """Regression: exit == entry must be correct (was False with strict >)."""
    outcome = await tracker.evaluate_signal(_signal("buy"), entry_price=100.0, exit_price=100.0)
    assert outcome.direction_correct is True
    assert outcome.actual_return_pct == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_buy_negative_move_incorrect(tracker):
    outcome = await tracker.evaluate_signal(_signal("buy"), entry_price=100.0, exit_price=97.0)
    assert outcome.direction_correct is False
    assert outcome.actual_return_pct == pytest.approx(-3.0)


@pytest.mark.asyncio
async def test_sell_negative_move_correct(tracker):
    outcome = await tracker.evaluate_signal(_signal("sell"), entry_price=100.0, exit_price=95.0)
    assert outcome.direction_correct is True
    assert outcome.actual_return_pct == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_sell_zero_move_correct(tracker):
    """Regression: exit == entry must be correct for sell too."""
    outcome = await tracker.evaluate_signal(_signal("sell"), entry_price=100.0, exit_price=100.0)
    assert outcome.direction_correct is True
    assert outcome.actual_return_pct == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_sell_positive_move_incorrect(tracker):
    outcome = await tracker.evaluate_signal(_signal("sell"), entry_price=100.0, exit_price=103.0)
    assert outcome.direction_correct is False
    assert outcome.actual_return_pct == pytest.approx(-3.0)


@pytest.mark.asyncio
async def test_hold_always_correct(tracker):
    outcome = await tracker.evaluate_signal(_signal("hold"), entry_price=100.0, exit_price=120.0)
    assert outcome.direction_correct is True
    assert outcome.actual_return_pct == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_zero_entry_guard(tracker):
    """Degenerate input (entry_price <= 0) must not raise ZeroDivisionError."""
    outcome = await tracker.evaluate_signal(_signal("buy"), entry_price=0.0, exit_price=100.0)
    assert outcome.actual_return_pct == 0.0
    assert outcome.direction_correct is False

