"""
Regression tests — hot-layer-first read order for GET /api/symbols/{symbol}/summary
====================================================================================
Locks in the ordering fix from the live cross-process verification:

A real Celery worker publishes SYMBOL_RESULT_UPDATED events carrying only the
*partial* contract summary (symbol/group/armor_score/data_dri/is_unreliable).
api/job_state seeds its in-memory fallback store from those events.  The
/summary endpoint must ALWAYS prefer the full hot-layer record
(`precompute:result:{symbol}` / `armor:precompute:results` hash) over that
partial in-memory shadow — otherwise the endpoint serves
`last_price: None` and `None` sub-scores even while a complete record exists.

No Redis: the read helpers are driven through a fake cache so the Redis-first
branch is exercised deterministically.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from api import job_state as js
from api.routers import precompute_router as pr


# ── fake cache ────────────────────────────────────────────────────────────
class _FakeCache:
    """Minimal stand-in for core.cache.CacheService backed by a dict.

    is_connected=True forces the Redis-first branch of the read helpers so
    the regression exercises the production ordering, not the fallback.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.calls: list[str] = []

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def client(self) -> _FakeCache:
        # The router awaits cache.client.hget / .get / .scan — the same object
        # provides the async surface.
        return self

    async def hget(self, name: str, key: str) -> str | None:
        self.calls.append(f"hget:{name}:{key}")
        return self.hashes.get(name, {}).get(key)

    async def hgetall(self, name: str) -> dict[str, str]:
        self.calls.append(f"hgetall:{name}")
        return dict(self.hashes.get(name, {}))

    async def get(self, key: str) -> str | None:
        self.calls.append(f"get:{key}")
        return self.store.get(key)

    async def scan(self, cursor: int, match: str = "*", count: int = 100):  # noqa: ANN001
        self.calls.append(f"scan:{match}")
        prefix = match.replace("*", "")
        keys = [k for k in self.store if k.startswith(prefix)]
        return 0, keys


@pytest.fixture()
def fake_cache(monkeypatch):
    cache = _FakeCache()
    monkeypatch.setattr(pr, "get_cache", lambda: cache)
    yield cache


@pytest.fixture(autouse=True)
def _reset_shared_state():
    js._mem_status = None
    js._started_at = None
    js._finalizing = False
    js._mem_results.clear()
    pr._mem_lock_until = 0.0
    pr._mem_results.clear()
    yield
    js._mem_status = None
    js._started_at = None
    js._finalizing = False
    js._mem_results.clear()
    pr._mem_lock_until = 0.0
    pr._mem_results.clear()


FULL_RECORD = {
    "symbol": "FOLAD",
    "group": "A",
    "last_price": 10000.0,
    "closing_price": 9950.0,
    "technical_score": 45.0,
    "liquidity_score": 52.0,
    "money_flow_score": 74.0,
    "armor_score": 54.7,
    "data_dri": 76.0,
    "is_unreliable": False,
    "red_flags": [],
    "calculated_at": "2026-09-13T09:00:00+00:00",
    "expires_at": "2099-01-01T00:00:00+00:00",
    "version": "v4.0",
}

PARTIAL_EVENT_SUMMARY = {
    "symbol": "FOLAD",
    "group": "A",
    "armor_score": 54.7,
    "data_dri": 76.0,
    "is_unreliable": False,
}


# ── 1. /summary prefers the hot layer over the partial in-memory shadow ───
async def test_summary_prefers_full_hot_layer_record_over_partial_event_shadow(fake_cache) -> None:
    """THE regression: the worker's partial SYMBOL_RESULT_UPDATED summary lands
    in the shared in-memory store, while the FULL record lives in the hot
    layer.  /summary must serve the hot layer (real prices + sub-scores),
    never the degraded event payload."""
    # Hot layer: full worker record (layout 2 — precompute:result:{symbol})
    fake_cache.store["precompute:result:FOLAD"] = json.dumps(FULL_RECORD)
    # In-memory: seeded by the partial event payload via the funnel
    js._mem_results["FOLAD"] = dict(PARTIAL_EVENT_SUMMARY)

    resp = await pr.get_symbol_summary("FOLAD")
    data = resp.data

    assert resp.success is True
    assert data["last_price"] == 10000.0  # partial payload would give None/KeyError
    assert data["closing_price"] == 9950.0
    assert data["technical_score"] == 45.0
    assert data["liquidity_score"] == 52.0
    assert data["money_flow_score"] == 74.0
    assert data["armor_score"] == 54.7
    assert data["_cache"] == "redis:hot"


# ── 2. /summary prefers the api-side hash (layout 1) too ─────────────────
async def test_summary_reads_api_hash_before_per_symbol_key(fake_cache) -> None:
    fake_cache.hashes["armor:precompute:results"] = {
        "FOLAD": json.dumps({**FULL_RECORD, "last_price": 11111.0}),
    }
    fake_cache.store["precompute:result:FOLAD"] = json.dumps(FULL_RECORD)

    data = (await pr.get_symbol_summary("FOLAD")).data
    assert data["last_price"] == 11111.0  # layout 1 wins

    # Layout 1 was probed first; because it held the record, the router
    # short-circuits without ever touching the per-symbol key.
    calls = fake_cache.calls
    assert calls[0] == "hget:armor:precompute:results:FOLAD"
    assert "get:precompute:result:FOLAD" not in calls


async def test_summary_falls_through_hash_to_per_symbol_key_in_order(fake_cache) -> None:
    """When the api-side hash has no entry, the per-symbol key is read second."""
    fake_cache.store["precompute:result:FOLAD"] = json.dumps(FULL_RECORD)

    data = (await pr.get_symbol_summary("FOLAD")).data
    assert data["armor_score"] == 54.7

    calls = fake_cache.calls
    assert calls[0] == "hget:armor:precompute:results:FOLAD"
    assert calls[1] == "get:precompute:result:FOLAD"


# ── 3. /dashboard/ready merges both layouts, hot layer authoritative ─────
async def test_dashboard_ready_merges_both_layouts_hot_layer_first(fake_cache) -> None:
    fake_cache.hashes["armor:precompute:results"] = {"FOLAD": json.dumps(FULL_RECORD)}
    # stale per-symbol key must NOT override the hash record
    fake_cache.store["precompute:result:FOLAD"] = json.dumps({**FULL_RECORD, "armor_score": 1.0})

    rows = {r["symbol"]: r for r in (await pr.get_dashboard_ready()).data}
    assert rows["FOLAD"]["armor_score"] == 54.7
    # hash (layout 1) probed before the per-symbol scan (layout 2)
    calls = fake_cache.calls
    assert calls[0] == "hgetall:armor:precompute:results"
    assert any(c.startswith("scan:precompute:result:") for c in calls)


# ── 4. No-Redis fallback still serves the in-memory store ────────────────
async def test_summary_falls_back_to_memory_when_cache_disconnected(monkeypatch) -> None:
    class _Null:
        is_connected = False
        client = None

    monkeypatch.setattr(pr, "get_cache", lambda: _Null())
    js._mem_results["FOLAD"] = dict(PARTIAL_EVENT_SUMMARY)

    resp = await pr.get_symbol_summary("FOLAD")
    assert resp.success is True
    assert resp.data["armor_score"] == 54.7  # memory fallback used


# ── 5. Malformed hot-layer entries never crash the read ──────────────────
async def test_summary_tolerates_corrupt_hot_layer_entry_and_falls_back(fake_cache) -> None:
    fake_cache.store["precompute:result:FOLAD"] = "{not json"
    js._mem_results["FOLAD"] = dict(PARTIAL_EVENT_SUMMARY)

    resp = await pr.get_symbol_summary("FOLAD")
    assert resp.success is True
    assert resp.data["armor_score"] == 54.7


# ── 6. Event-driven seeding still works (funnel integration sanity) ──────
async def test_funnel_seeded_memory_store_serves_summary_without_hot_layer(fake_cache) -> None:
    """The in-memory store must still be populated by real SYMBOL_RESULT_UPDATED
    events through ws_manager — /summary serves it when the hot layer is empty."""
    from precompute.workers import celery_tasks as ct

    monkeypatch_ct_emit = ct.EMIT_MODE  # noqa: F841 — funnel forced via fixture-like patch below
    ct.EMIT_MODE = "funnel"  # type: ignore[misc]
    try:
        await js.reset_job()
        full = ct.compute_single_symbol({"symbol": "HEXAD", "price_last": 8500, "market": "TSE"}, "A")
        await ct._emit("SYMBOL_RESULT_UPDATED", full)
        for _ in range(8):
            await asyncio.sleep(0)
    finally:
        ct.EMIT_MODE = monkeypatch_ct_emit

    resp = await pr.get_symbol_summary("HEXAD")
    assert resp.success is True
    assert resp.data["armor_score"] == full["armor_score"]
    assert resp.data["last_price"] is not None
