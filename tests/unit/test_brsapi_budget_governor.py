"""Unit tests for the BrsApiBudgetGovernor (brsapi/budget.py).

Background
----------
The BrsApi key got blocked because the platform exceeded the plan's real
daily cap (~5,000/day). The in-process ``RateLimiter`` counters reset on every
process restart / replica, so a restarted worker could spend the same budget
again. ``BrsApiBudgetGovernor`` closes that gap with PERSISTENT counters
(Redis INCR / JSON file) plus a post-302 block cooldown.

These tests lock in:
  1. The daily counter survives "restarts" (file backend) and is shared
     across instances (Redis backend).
  2. Fail-fast on the persisted daily budget — no HTTP, no sleep.
  3. HTTP 302 arms a cooldown during which every live call is rejected fast.
  4. The shared 5-min window (Redis) rejects/waits correctly.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import brsapi.client as client_mod
from brsapi.budget import BrsApiBudgetGovernor, BudgetBlockedError, BudgetSoftRejectError
from brsapi.config import EndpointConfig
from brsapi.rate_limiter import RateLimiter, RateLimitExhaustedError


@pytest.fixture(autouse=True)
def _force_live_mode() -> None:
    """The real ``.env`` sets ``BRSAPI_ENABLED=false`` (DB-only mode while the
    key is blocked); client tests that exercise fetch() need live mode."""
    with patch.object(client_mod.brsapi_settings, "enabled", True):
        yield


# ── Fake Redis (subset of redis.asyncio used by the governor) ───────────────


class _FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> Any | None:
        return self._data.get(key)

    async def set(self, key: str, value: Any, **kwargs: Any) -> bool:
        self._data[key] = value
        return True

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def incrby(self, key: str, amount: int) -> int:
        cur = int(self._data.get(key, 0) or 0)
        cur += amount
        self._data[key] = str(cur)
        return cur

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        self._zsets.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def zcard(self, key: str) -> int:
        return len(self._zsets.get(key, {}))

    async def zrange(self, key: str, start: int, stop: int, withscores: bool = False) -> list[Any]:
        items = sorted(self._zsets.get(key, {}).items(), key=lambda kv: kv[1])
        chunk = items[start:] if stop < 0 else items[start : stop + 1]
        if withscores:
            return [(m, s) for m, s in chunk]
        return [m for m, _ in chunk]

    async def zremrangebyscore(self, key: str, mn: float, mx: float) -> int:
        z = self._zsets.get(key, {})
        before = len(z)
        kept = {m: s for m, s in z.items() if not (mn <= s <= mx)}
        self._zsets[key] = kept
        return before - len(kept)


@pytest.fixture
def no_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the file backend: never auto-connect a real Redis."""
    monkeypatch.setattr(BrsApiBudgetGovernor, "_connect_redis", AsyncMock(return_value=None))


def _limiter(daily: int, five_min: int = 500, fail_fast: bool = True) -> RateLimiter:
    return RateLimiter(daily_limit=daily, five_min_limit=five_min, fail_fast=fail_fast)


# ── Persisted daily counter ─────────────────────────────────────────────────


async def test_persisted_daily_survives_restart_file_backend(no_redis, tmp_path) -> None:
    state_file = tmp_path / "budget_state.json"

    # First "process": uses 3/5 of the daily budget.
    g1 = BrsApiBudgetGovernor(rate_limiter=_limiter(5), state_file=state_file)
    await g1.acquire("tsetmc")
    await g1.acquire("tsetmc")
    await g1.acquire("tsetmc")

    # "Restart": a fresh governor + fresh in-memory limiter must NOT get a
    # fresh budget — it sees the persisted 3/5 and only 2 remain.
    g2 = BrsApiBudgetGovernor(rate_limiter=_limiter(5), state_file=state_file)
    assert await g2.available_daily() == 2
    st = await g2.stats()
    assert st["global"]["daily_count"] == 3
    assert st["global"]["daily_remaining"] == 2

    # Using the remaining 2 then a 3rd request must fail fast.
    await g2.acquire("tsetmc")
    await g2.acquire("tsetmc")
    with pytest.raises(RateLimitExhaustedError):
        await g2.acquire("tsetmc")


async def test_redis_daily_counter_shared_across_instances() -> None:
    """Two governor instances sharing one Redis see the same persisted count."""
    fake = _FakeRedis()

    g1 = BrsApiBudgetGovernor(rate_limiter=_limiter(10), redis_client=fake)
    await g1.acquire("tsetmc")
    await g1.acquire("tsetmc")

    g2 = BrsApiBudgetGovernor(rate_limiter=_limiter(10), redis_client=fake)
    assert await g2.available_daily() == 8
    assert (await g2.stats())["global"]["daily_count"] == 2

    # g2's request lands on the SAME counter.
    await g2.acquire("tsetmc")
    assert (await g1.stats())["global"]["daily_count"] == 3


async def test_redis_backend_seeds_limiter_from_persisted_count() -> None:
    """A restarted process's in-memory limiter is seeded from the Redis
    counter, so threshold notifications and the local gate reflect the GLOBAL
    usage (not just this process's)."""
    fake = _FakeRedis()

    g1 = BrsApiBudgetGovernor(rate_limiter=_limiter(10), redis_client=fake)
    await g1.acquire("tsetmc")
    await g1.acquire("tsetmc")

    limiter2 = _limiter(10)
    g2 = BrsApiBudgetGovernor(rate_limiter=limiter2, redis_client=fake)
    await g2.initialize()

    assert limiter2._daily_count == 2, "limiter must be seeded from Redis"
    assert (await g2.stats())["global"]["daily_count"] == 2


async def test_redis_daily_reservation_is_atomic_at_boundary() -> None:
    """INCRBY-first reservation: when another worker takes the last slot, the
    next acquire reserves past the cap and is rejected — no check-then-act
    race that could push past the real plan cap."""
    fake = _FakeRedis()
    g = BrsApiBudgetGovernor(rate_limiter=_limiter(2), redis_client=fake)

    await g.acquire("tsetmc")  # used = 1
    # Another worker concurrently takes the last slot: used = 2
    daily_key = f"brsapi:budget:daily:{BrsApiBudgetGovernor._tehran_today()}"
    await fake.incrby(daily_key, 1)

    with pytest.raises(RateLimitExhaustedError, match="daily budget exhausted"):
        await g.acquire("tsetmc")  # reserve → 3 > 2 → rejected


async def test_daily_exhausted_fail_fast_blocks_before_network(no_redis, tmp_path) -> None:
    state_file = tmp_path / "budget_state.json"
    limiter = _limiter(2)
    g = BrsApiBudgetGovernor(rate_limiter=limiter, state_file=state_file)
    await g.acquire("tsetmc")
    await g.acquire("tsetmc")

    with pytest.raises(RateLimitExhaustedError, match="daily budget exhausted"):
        await g.check_allowed("tsetmc")
    with pytest.raises(RateLimitExhaustedError, match="daily budget exhausted"):
        await g.acquire("tsetmc")


# ── 302 block cooldown ──────────────────────────────────────────────────────


async def test_302_arms_cooldown_and_rejects_all_calls(no_redis, tmp_path) -> None:
    state_file = tmp_path / "budget_state.json"
    g = BrsApiBudgetGovernor(
        rate_limiter=_limiter(1000), state_file=state_file, block_cooldown=900,
    )

    await g.report_302("https://cdn.example/Windows.iso")
    assert await g.is_blocked()
    assert (await g.stats())["block"]["302_count"] == 1

    with pytest.raises(BudgetBlockedError, match="302-cooldown"):
        await g.check_allowed("tsetmc")
    with pytest.raises(BudgetBlockedError, match="302-cooldown"):
        await g.acquire("tsetmc")


async def test_block_clears_after_cooldown_plus_200(no_redis, tmp_path) -> None:
    state_file = tmp_path / "budget_state.json"
    g = BrsApiBudgetGovernor(
        rate_limiter=_limiter(1000), state_file=state_file, block_cooldown=60,
    )
    await g.report_302("heavy-file")

    # Cooldown elapsed + server answers 200 → block cleared.
    g._block.blocked_until = time.time() - 1
    await g.report_ok()

    assert await g.is_blocked() is False
    assert (await g.stats())["block"]["blocked"] is False
    # And the governor works normally again.
    await g.acquire("tsetmc")


async def test_200_during_cooldown_does_not_clear_early(no_redis, tmp_path) -> None:
    state_file = tmp_path / "budget_state.json"
    g = BrsApiBudgetGovernor(
        rate_limiter=_limiter(1000), state_file=state_file, block_cooldown=600,
    )
    await g.report_302("heavy-file")
    g._block.blocked_until = time.time() + 300  # still in cooldown

    await g.report_ok()  # a 200 now must NOT clear the block

    assert await g.is_blocked() is True


# ── Shared 5-min window (Redis) ─────────────────────────────────────────────


async def test_5min_window_redis_fail_fast_when_full() -> None:
    fake = _FakeRedis()
    now = time.time()
    fake._zsets["brsapi:budget:5min"] = {
        "a": now - 10, "b": now - 20, "c": now - 30,
    }
    g = BrsApiBudgetGovernor(
        rate_limiter=_limiter(1000, five_min=3), redis_client=fake, five_min_limit=3,
    )
    with pytest.raises(RateLimitExhaustedError, match="5-min window full"):
        await g.acquire("tsetmc")


async def test_5min_window_redis_waits_then_proceeds(monkeypatch) -> None:
    fake = _FakeRedis()
    now = time.time()
    fake._zsets["brsapi:budget:5min"] = {
        "a": now - 290, "b": now - 280, "c": now - 270,
    }
    g = BrsApiBudgetGovernor(
        rate_limiter=_limiter(1000, five_min=3, fail_fast=False),
        redis_client=fake, five_min_limit=3,
    )

    slept: list[float] = []
    calls = 0

    async def fake_sleep(seconds: float) -> None:
        nonlocal calls
        calls += 1
        slept.append(seconds)
        if calls == 1:
            # Simulate the window sliding: the oldest request ages out.
            fake._zsets["brsapi:budget:5min"].pop("a", None)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    await g.acquire("tsetmc")

    assert len(slept) == 1, "expected exactly one wait for the window to slide"
    # oldest = now-290 → wait ≈ 10s (oldest + 300 - now)
    assert 5.0 <= slept[0] <= 15.0


# ── Backends / stats ────────────────────────────────────────────────────────


async def test_stats_shape_file_backend(no_redis, tmp_path) -> None:
    state_file = tmp_path / "budget_state.json"
    g = BrsApiBudgetGovernor(rate_limiter=_limiter(100, five_min=50), state_file=state_file)

    st = await g.stats()
    assert st["governor"]["backend"] == "file"
    assert st["global"]["daily_limit"] == 100
    assert st["global"]["daily_remaining"] == 100
    assert st["global"]["5min_limit"] == 50
    assert st["block"]["blocked"] is False
    assert st["block"]["cooldown_seconds"] > 0
    assert "limiter" in st and "global" in st["limiter"]


async def test_memory_governor_never_writes(tmp_path) -> None:
    state_file = tmp_path / "budget_state.json"
    g = BrsApiBudgetGovernor(
        rate_limiter=_limiter(5), state_file=state_file, persist=False,
    )
    await g.acquire("tsetmc")
    assert (await g.stats())["governor"]["backend"] == "memory"
    assert not state_file.exists(), "persist=False must not write a state file"


# ── Client integration ──────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, status_code: int, content: bytes = b"{}"):
        self.status_code = status_code
        self.content = content
        self.text = "fake"
        self.headers = {}


class _FakeEndpoint:
    path = "/Test/Endpoint.php"
    category = type("Cat", (), {"value": "tsetmc"})()
    default_params = {}
    critical = False


async def test_client_302_arms_cooldown_second_fetch_rejects_without_http() -> None:
    """A 302 through the client arms the governor; the next fetch is rejected
    BEFORE any HTTP call."""
    from brsapi.client import BrsApiClient

    client = BrsApiClient(
        api_key="test", base_url="http://test.local",
        rate_limiter=_limiter(1000),
    )
    client._client = AsyncMock()
    client._max_retries = 3

    resp = _FakeResp(302)
    resp.headers = {"Location": "https://cdn.example/Windows.iso"}
    client._client.get = AsyncMock(return_value=resp)

    with patch("asyncio.sleep", new=AsyncMock()):
        r1 = await client.fetch(_FakeEndpoint())
    assert r1.success is False
    assert "302" in (r1.error or "")

    # Second fetch: blocked by the governor cooldown — zero HTTP calls.
    client._client.get = AsyncMock(return_value=resp)
    with patch("asyncio.sleep", new=AsyncMock()):
        r2 = await client.fetch(_FakeEndpoint())
    assert r2.success is False
    assert "cooldown" in (r2.error or "").lower()
    client._client.get.assert_not_awaited()


async def test_client_200_clears_block_after_cooldown() -> None:
    from brsapi.client import BrsApiClient

    client = BrsApiClient(
        api_key="test", base_url="http://test.local",
        rate_limiter=_limiter(1000),
    )
    client._client = AsyncMock()
    client._max_retries = 3

    # Arm a block directly on the governor (as a 302 would).
    client._governor._block.blocked_until = time.time() - 1  # cooldown elapsed
    client._governor._block.count = 1

    client._client.get = AsyncMock(return_value=_FakeResp(200, b'{"ok": true}'))
    with patch("asyncio.sleep", new=AsyncMock()):
        r = await client.fetch(_FakeEndpoint())
    assert r.success is True
    assert (await client._governor.stats())["block"]["blocked"] is False


# ── Tiered budget defence: warn at 85%, shed non-critical from 95% ───────────


def _tiered(tmp_path, **kwargs: Any) -> BrsApiBudgetGovernor:
    """Governor over a file backend with a 20-request daily budget."""
    return BrsApiBudgetGovernor(
        rate_limiter=_limiter(100),
        daily_limit=kwargs.pop("daily_limit", 20),
        state_file=tmp_path / "budget_state.json",
        **kwargs,
    )


async def test_budget_warns_once_at_warn_threshold(tmp_path, caplog) -> None:
    """Crossing ``warn_pct`` logs exactly one warning and still allows traffic."""
    caplog.set_level("WARNING", logger="brsapi.budget")
    g = _tiered(tmp_path, warn_pct=85, soft_reject_pct=95)

    for _ in range(16):                       # 80% — below the warning line
        await g.acquire("tsetmc")
    assert not [r for r in caplog.records if "budget at" in r.message]

    await g.acquire("tsetmc")                 # 17/20 = 85%
    await g.acquire("tsetmc")                 # 18/20 = 90%
    warnings = [r for r in caplog.records if "budget at" in r.message]
    assert len(warnings) == 1, "the budget warning must not repeat per request"
    assert "85%" in warnings[0].message


async def test_non_critical_rejected_at_soft_ceiling_but_critical_passes(tmp_path) -> None:
    """Past ``soft_reject_pct`` only critical endpoints may still spend quota."""
    g = _tiered(tmp_path, warn_pct=85, soft_reject_pct=95)
    for _ in range(19):                       # 19/20 = 95%
        await g.acquire("tsetmc", critical=True)

    with pytest.raises(BudgetSoftRejectError, match="non-critical"):
        await g.acquire("tsetmc", endpoint="/Tsetmc/AllSymbols.php")
    with pytest.raises(BudgetSoftRejectError, match="non-critical"):
        await g.check_allowed("tsetmc", "/Tsetmc/AllSymbols.php")

    # The same slot is still open for the same-day market record.
    await g.acquire("tsetmc", endpoint="/Tsetmc/History.php", critical=True)
    assert (await g.stats())["global"]["daily_count"] == 20


async def test_full_budget_still_reports_exhaustion_not_soft_reject(tmp_path) -> None:
    """At 100% the error is the pre-existing exhaustion — criticality is moot."""
    g = _tiered(tmp_path, warn_pct=85, soft_reject_pct=95)
    for _ in range(20):
        await g.acquire("tsetmc", critical=True)

    for call in (lambda: g.check_allowed("tsetmc", critical=True),
                 lambda: g.acquire("tsetmc", critical=True)):
        with pytest.raises(RateLimitExhaustedError, match="daily budget exhausted") as exc:
            await call()
        assert not isinstance(exc.value, BudgetSoftRejectError)


async def test_soft_reject_does_not_consume_budget(tmp_path) -> None:
    """A shed request must not spend quota — that would make the ceiling move."""
    g = _tiered(tmp_path, warn_pct=85, soft_reject_pct=95)
    for _ in range(19):
        await g.acquire("tsetmc", critical=True)

    before = (await g.stats())["global"]["daily_count"]
    for _ in range(5):
        with pytest.raises(BudgetSoftRejectError):
            await g.acquire("tsetmc")
    assert (await g.stats())["global"]["daily_count"] == before


async def test_endpoints_default_to_non_critical_except_the_daily_record() -> None:
    """Only the same-day TSETMC backbone is flagged critical."""
    from brsapi.config import BrsApiEndpoints

    critical = {
        name for name, value in vars(BrsApiEndpoints).items()
        if isinstance(value, EndpointConfig) and value.critical
    }
    assert critical == {
        "SYMBOL_DETAIL", "NAV", "TRANSACTION",
        "HISTORY_PRICE", "HISTORY_REALLEGAL", "CANDLESTICK",
    }
