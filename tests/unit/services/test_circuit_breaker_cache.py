"""Tests for the cache layer in :mod:`services.signal_circuit_breaker`.

The cache wraps ``evaluate()`` with a short Redis TTL so the per-request
hot path doesn't repeat the SQL scan. We mock ``core.cache.get_cache``
and verify:

- Cache miss → live eval runs → result is cached.
- Cache hit → live eval does NOT run (the breaker would still hold a
  fresh verdict from a parallel request).
- Redis unavailable → falls through to live eval (no crash).
- ``invalidate_cache`` clears the keys.
- Round-trip via :func:`_state_to_dict` / :func:`_dict_to_state` is
  lossless for the fields an operator would inspect in a log.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from services.signal_circuit_breaker import (
    BreakerState,
    _cache_key,
    _dict_to_state,
    _state_to_dict,
    evaluate_cached,
    invalidate_cache,
)


def _state(**overrides: Any) -> BreakerState:
    base = dict(
        tripped=True,
        accuracy_pct=42.5,
        sample_size=100,
        window_days=3,
        threshold_pct=50.0,
        reason="test reason",
        evaluated_at=datetime(2026, 8, 1, 12, 0, 0),
        per_market={"stock": 50.0, "crypto": 30.0},
    )
    base.update(overrides)
    return BreakerState(**base)


# ── Serialization round-trip ───────────────────────────────────────


def test_state_roundtrip_preserves_fields() -> None:
    """The cache payload must reconstruct the exact same BreakerState."""
    original = _state()
    payload = _state_to_dict(original)
    restored = _dict_to_state(payload)
    assert restored == original


def test_state_roundtrip_handles_empty_per_market() -> None:
    """Cold-start state (no rows) has an empty per_market dict; the
    JSON round-trip must NOT collapse it to ``None``."""
    original = _state(per_market={})
    payload = _state_to_dict(original)
    assert payload["per_market"] == {}
    restored = _dict_to_state(payload)
    assert restored.per_market == {}


# ── Cache key shape ───────────────────────────────────────────────


def test_cache_key_includes_all_parameters() -> None:
    """Different parameter combos must yield different keys so the
    breaker never returns a verdict that was computed under different
    rules.
    """
    k1 = _cache_key(window_days=3, threshold_pct=50.0, min_samples=20)
    k2 = _cache_key(window_days=7, threshold_pct=50.0, min_samples=20)
    k3 = _cache_key(window_days=3, threshold_pct=45.0, min_samples=20)
    k4 = _cache_key(window_days=3, threshold_pct=50.0, min_samples=50)
    assert len({k1, k2, k3, k4}) == 4


# ── evaluate_cached: miss + hit + unavailable ──────────────────────


async def test_evaluate_cached_cache_miss_runs_live_eval() -> None:
    """On miss, evaluate_cached must call the live evaluator and write
    the verdict to the cache for next time.
    """
    fake_state = _state(tripped=False, reason="healthy")
    fake_cache = MagicMock()
    fake_cache.is_connected = True
    fake_cache.get = AsyncMock(return_value=None)
    fake_cache.set = AsyncMock()

    with (
        patch("services.signal_circuit_breaker.get_cache", return_value=fake_cache),
        patch("services.signal_circuit_breaker.evaluate_default", AsyncMock(return_value=fake_state)) as live,
    ):
        result = await evaluate_cached(window_days=3, accuracy_threshold_pct=50.0, min_samples=20, ttl_seconds=60)

    assert result is fake_state
    live.assert_awaited_once()
    fake_cache.set.assert_awaited_once()
    # The set call carries the right TTL and the namespaced key.
    set_args = fake_cache.set.await_args
    assert set_args.args[0].startswith("signal:circuit_breaker:v1:")
    assert set_args.kwargs["ttl"] == 60


async def test_evaluate_cached_cache_hit_skips_live_eval() -> None:
    """A cached verdict must short-circuit the SQL scan entirely."""
    cached_payload = _state_to_dict(_state(tripped=True, reason="cached"))
    fake_cache = MagicMock()
    fake_cache.is_connected = True
    fake_cache.get = AsyncMock(return_value=cached_payload)
    fake_cache.set = AsyncMock()

    with (
        patch("services.signal_circuit_breaker.get_cache", return_value=fake_cache),
        patch("services.signal_circuit_breaker.evaluate_default", AsyncMock()) as live,
    ):
        result = await evaluate_cached()

    live.assert_not_awaited()
    fake_cache.set.assert_not_awaited()
    # Returned state matches the cached one (not a fresh eval).
    assert result.tripped is True
    assert result.reason == "cached"


async def test_evaluate_cached_falls_through_when_redis_unavailable() -> None:
    """If Redis is down, the breaker must still return a verdict.

    The pipeline cannot depend on a side-channel cache; correctness
    comes from the live eval, the cache is a latency optimization.
    """
    fake_state = _state(tripped=False, reason="live")
    fake_cache = MagicMock()
    fake_cache.is_connected = False
    fake_cache.get = AsyncMock()
    fake_cache.set = AsyncMock()

    with (
        patch("services.signal_circuit_breaker.get_cache", return_value=fake_cache),
        patch("services.signal_circuit_breaker.evaluate_default", AsyncMock(return_value=fake_state)) as live,
    ):
        result = await evaluate_cached()

    assert result is fake_state
    live.assert_awaited_once()
    fake_cache.get.assert_not_awaited()
    fake_cache.set.assert_not_awaited()


async def test_evaluate_cached_swallows_cache_read_error() -> None:
    """A cache get() that raises must NOT crash the breaker."""
    fake_state = _state(reason="live-fallback")
    fake_cache = MagicMock()
    fake_cache.is_connected = True
    fake_cache.get = AsyncMock(side_effect=ConnectionError("redis down"))
    fake_cache.set = AsyncMock()

    with (
        patch("services.signal_circuit_breaker.get_cache", return_value=fake_cache),
        patch("services.signal_circuit_breaker.evaluate_default", AsyncMock(return_value=fake_state)) as live,
    ):
        result = await evaluate_cached()

    assert result.reason == "live-fallback"
    live.assert_awaited_once()


# ── invalidate_cache ──────────────────────────────────────────────


async def test_invalidate_cache_noop_when_disconnected() -> None:
    """If Redis is down, invalidate must silently return."""
    fake_cache = MagicMock()
    fake_cache.is_connected = False
    fake_cache.client = MagicMock()
    with patch("services.signal_circuit_breaker.get_cache", return_value=fake_cache):
        await invalidate_cache()
    fake_cache.client.scan_iter.assert_not_called()


async def test_invalidate_cache_scans_and_deletes() -> None:
    """The invalidator must use SCAN, not KEYS, to avoid blocking Redis.

    It must delete every key under the breaker namespace.
    """

    async def fake_scan_iter(match: str, count: int) -> Any:
        for k in ("signal:circuit_breaker:v1:w3:t50:m20", "signal:circuit_breaker:v1:w7:t50:m20"):
            yield k

    fake_cache = MagicMock()
    fake_cache.is_connected = True
    fake_cache.client = MagicMock()
    fake_cache.client.scan_iter = fake_scan_iter
    fake_cache.client.delete = AsyncMock()

    with patch("services.signal_circuit_breaker.get_cache", return_value=fake_cache):
        await invalidate_cache()

    assert fake_cache.client.delete.await_count == 2
    # Both deletes must have used the namespaced keys.
    deleted_keys = [c.args[0] for c in fake_cache.client.delete.await_args_list]
    assert all(k.startswith("signal:circuit_breaker:v1:") for k in deleted_keys)
