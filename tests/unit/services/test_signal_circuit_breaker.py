"""Tests for the rolling-accuracy circuit breaker.

The breaker is pure async DB code, so we mock the engine with a tiny
in-memory stub. The point is to lock down the *decision logic*, not
the SQL — that's covered by the live dry-run script.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from services.signal_circuit_breaker import evaluate


class _FakeConn:
    """Minimal async-connection stub that returns a fixed result set."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, query: Any, params: dict | None = None) -> _FakeResult:
        return _FakeResult(self._rows)


class _FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


def _engine_for_rows(rows: list[tuple[Any, ...]]) -> MagicMock:
    engine = MagicMock()
    engine.connect = MagicMock(return_value=_FakeConn(rows))
    return engine


# ── Insufficient samples ──────────────────────────────────────────


async def test_evaluate_does_not_trip_with_too_few_samples() -> None:
    """Cold start: fewer than min_samples → not tripped, regardless of acc."""
    rows = [("stock", 5, 0.0), ("crypto", 3, 1.0)]  # total n=8
    state = await evaluate(_engine_for_rows(rows), window_days=3, min_samples=20)
    assert state.tripped is False
    assert state.sample_size == 8
    assert "insufficient_samples" in state.reason


# ── Trip path ─────────────────────────────────────────────────────


async def test_evaluate_trips_when_accuracy_below_threshold() -> None:
    """n >= min_samples AND weighted_acc < threshold → tripped."""
    rows = [
        ("stock", 30, 0.40),  # 40%
        ("crypto", 10, 0.20),  # 20%
    ]
    # weighted: (30*0.4 + 10*0.2) / 40 = (12 + 2) / 40 = 0.35 = 35%
    state = await evaluate(_engine_for_rows(rows), window_days=3, accuracy_threshold_pct=50.0, min_samples=20)
    assert state.tripped is True
    assert state.accuracy_pct == pytest.approx(35.0, abs=0.01)
    assert "35.0%" in state.reason
    assert "weakest market" in state.reason
    # crypto is the weakest at 20%.
    assert state.per_market == {"stock": 40.0, "crypto": 20.0}


async def test_evaluate_healthy_when_above_threshold() -> None:
    """n >= min_samples AND weighted_acc >= threshold → not tripped."""
    rows = [("stock", 100, 0.65), ("crypto", 50, 0.55)]
    # weighted: (100*0.65 + 50*0.55) / 150 = (65 + 27.5) / 150 = 0.617 = 61.7%
    state = await evaluate(_engine_for_rows(rows), window_days=3, accuracy_threshold_pct=50.0, min_samples=20)
    assert state.tripped is False
    assert state.accuracy_pct == pytest.approx(61.67, abs=0.1)
    assert "healthy" in state.reason


# ── Edge cases ────────────────────────────────────────────────────


async def test_evaluate_empty_table_returns_zero_state() -> None:
    """No rows at all → not tripped, accuracy=0, reason mentions insufficient samples."""
    state = await evaluate(_engine_for_rows([]), window_days=3, min_samples=20)
    assert state.tripped is False
    assert state.accuracy_pct == 0.0
    assert state.sample_size == 0
    assert "insufficient_samples" in state.reason


async def test_evaluate_exact_threshold_is_healthy() -> None:
    """A weighted accuracy exactly equal to the threshold is NOT tripped
    (the check is strict ``<``, not ``<=``). This pins the boundary so
    a refactor to ``<=`` is intentional.
    """
    rows = [("stock", 20, 0.50)]  # exactly 50%
    state = await evaluate(_engine_for_rows(rows), window_days=3, accuracy_threshold_pct=50.0, min_samples=20)
    assert state.tripped is False
    assert state.accuracy_pct == 50.0


async def test_evaluate_state_carries_metadata() -> None:
    """The returned state must carry enough metadata for an operator audit log."""
    rows = [("stock", 50, 0.60)]
    state = await evaluate(_engine_for_rows(rows), window_days=7, accuracy_threshold_pct=45.0, min_samples=20)
    assert state.window_days == 7
    assert state.threshold_pct == 45.0
    assert state.sample_size == 50
    # evaluated_at must be a real datetime close to "now".
    assert isinstance(state.evaluated_at, datetime)
    assert (datetime.now(UTC) - state.evaluated_at) < timedelta(minutes=1)


async def test_evaluate_frozen_dataclass() -> None:
    """The state is immutable — operators can pass it to a logger without
    worrying about a later mutation changing the audit trail.
    """
    rows = [("stock", 30, 0.45)]
    state = await evaluate(_engine_for_rows(rows), window_days=3, accuracy_threshold_pct=50.0, min_samples=20)
    with pytest.raises((AttributeError, Exception)):  # FrozenInstanceError is a subclass
        state.tripped = not state.tripped  # type: ignore[misc]
