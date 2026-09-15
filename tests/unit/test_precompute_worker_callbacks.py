"""
Unit tests — precompute/workers/celery_tasks.py
================================================
Verifies the worker's callbacks into the API layer:

  * chain signatures survive Celery's positional result-prepending
  * group tasks thread context via ``_group_<G>`` keys so finalize sees all
    three group summaries (a chain only prepends the *immediately previous*
    result)
  * contract events (contracts/events.md) published with absolute counters
  * finalize publishes PRECOMPUTATION_COMPLETED (the finalization the old
    Celery path never had)
  * running-loop contexts get events via the api.ws_manager broadcast funnel
    (job_state + WebSocket clients) instead of run_until_complete crashes
  * dispatch_armor_pipeline_async drives the whole pipeline inside a loop and
    finalizes through the funnel

Runs without Redis: in-memory fallback paths are exercised.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from api import job_state as js
from api.routers import precompute_router as pr
from api.ws_manager import get_armor_ws_manager
from precompute.workers import celery_tasks as ct


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Isolate shared state between tests (memory fallback paths only).

    Also forces ``EMIT_MODE=funnel``: these tests simulate the API process,
    where events must traverse the ws_manager broadcast funnel — without
    it, the auto discriminator would route them to the precompute scope's
    own Redis transport (core.cache is not connected under pytest)."""
    monkeypatch.setattr(ct, "EMIT_MODE", "funnel")
    js._mem_status = None
    js._started_at = None
    js._finalizing = False
    js._mem_results.clear()
    pr._mem_lock_until = 0.0
    yield
    js._mem_status = None
    js._started_at = None
    js._finalizing = False
    js._mem_results.clear()
    pr._mem_lock_until = 0.0


class _Capture:
    """Sync record of every emitted (type, payload) pair."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


class _AsyncCapture:
    """Async record of every emitted (type, payload) pair."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


def _task_params(fn) -> list[str]:
    """Signature of the undecorated task function, normalized across the two
    possible wrappings: the no-Celery ``_plain`` fallback (which carries
    ``self`` and ``__wrapped__``) and the real Celery task (whose signature
    reflects the decorated ``run`` without ``self``)."""
    import inspect

    target = getattr(fn, "__wrapped__", None) or getattr(fn, "run", None) or fn
    params = list(inspect.signature(target).parameters)
    if params and params[0] == "self":
        params = params[1:]
    return params


# ═════════════════════════════════ loop-free sync helpers ═══════


def test_chain_links_accept_prepended_result_positionally() -> None:
    """Celery prepends the previous result to the next link's args.  Every
    non-first link must declare prev_result as its FIRST parameter (after
    self) or the real inputs would be clobbered."""
    for fn in (ct.compute_group_b, ct.compute_group_c, ct.finalize_precompute):
        params = _task_params(fn)
        assert params[0] == "prev_result", f"{getattr(fn, '__name__', fn)}: {params}"
    # First link takes the real input directly
    params_a = _task_params(ct.compute_group_a)
    assert params_a[0] == "symbols", params_a


def test_group_tasks_thread_context_via_group_keys() -> None:
    """Each link merges its summary under _group_<G> so finalize (which only
    receives the immediately-previous result) sees all three groups."""
    ra = ct.compute_group_a(symbols=[{"symbol": "A0", "market": "TSE"}], job_id="j")
    rb = ct.compute_group_b(prev_result=ra, symbols=[{"symbol": "B0", "market": "TSE"}], job_id="j")
    rc = ct.compute_group_c(prev_result=rb, symbols=[{"symbol": "C0", "market": "TSE"}], job_id="j")

    assert set(ra) == {"_group_A"} and ra["_group_A"]["group"] == "A"
    assert set(rb) == {"_group_A", "_group_B"}
    assert set(rc) == {"_group_A", "_group_B", "_group_C"}
    assert rc["_group_A"]["total_processed"] == 1
    assert rc["_group_C"]["total_processed"] == 1


def test_group_run_publishes_contract_events() -> None:
    events = _AsyncCapture()
    orig = ct._emit
    ct._emit = events  # type: ignore[assignment]
    try:
        summary = asyncio.run(
            ct._run_group(
                [{"symbol": f"S{i}", "price_last": 100 + i, "market": "TSE"} for i in range(6)],
                "A",
                "j-events",
            )
        )
    finally:
        ct._emit = orig

    assert summary["completed"] == 6 and summary["failed"] == 0
    types = [t for t, _ in events.events]
    assert types.count("SYMBOL_RESULT_UPDATED") == 6
    assert types.count("PRECOMPUTATION_PROGRESS") == 2  # at 5 and at 6
    assert types.count("PRECOMPUTATION_GROUP_COMPLETED") == 1

    # Progress uses absolute counters
    prog = [p for t, p in events.events if t == "PRECOMPUTATION_PROGRESS"]
    assert prog[-1]["completed"] == 6 and prog[-1]["total"] == 6
    assert all(p["group"] == "A" for p in prog)


def test_finalize_publishes_completed_with_real_totals() -> None:
    """finalize aggregates the accumulated chain context."""
    out = ct.finalize_precompute(
        prev_result={
            "_group_A": {"group": "A", "total_processed": 10, "completed": 9, "failed": 1, "duration_seconds": 2.0},
            "_group_B": {"group": "B", "total_processed": 5, "completed": 5, "failed": 0, "duration_seconds": 1.0},
            "_group_C": {"group": "C", "total_processed": 5, "completed": 4, "failed": 1, "duration_seconds": 1.5},
        },
        job_id="j-fin",
    )
    assert out["total"] == 20 and out["success"] == 18 and out["failed"] == 2
    assert out["overall_status"] == "PARTIAL"
    assert set(out["groups"]) == {"A", "B", "C"}


def test_finalize_all_failed_is_failed_status() -> None:
    out = ct.finalize_precompute(
        prev_result={
            "_group_A": {"group": "A", "total_processed": 3, "completed": 0, "failed": 3, "duration_seconds": 1.0},
        },
        job_id="j-fail",
    )
    assert out["overall_status"] == "FAILED"
    assert out["total"] == 3 and out["success"] == 0 and out["failed"] == 3


def test_sync_dispatch_raises_inside_running_loop(monkeypatch) -> None:
    """A running loop + blocking dispatch = crash (run_until_complete inside a
    loop).  Callers inside a loop must use the async dispatch instead.

    With Celery installed the sync dispatch legitimately enqueues via the
    broker (non-blocking), so the guard only governs the no-Celery branch —
    patch the app away to exercise it."""
    monkeypatch.setattr(ct, "_get_celery_app", lambda: None)

    async def _inside_loop() -> None:
        with pytest.raises(RuntimeError, match="dispatch_armor_pipeline_async"):
            ct.dispatch_armor_pipeline({"A": [], "B": [], "C": []}, job_id="j-loop")

    asyncio.run(_inside_loop())


# ═════════════════════════════ async funnel integration ═════════


async def test_emit_inside_loop_feeds_job_state() -> None:
    """With a running loop, _emit must reach the shared state machine through
    ArmorWsManager.broadcast_event (no run_until_complete on a live loop)."""
    await js.reset_job()
    await ct._emit(
        "PRECOMPUTATION_PROGRESS",
        {"group": "A", "completed": 4, "total": 10, "percent": 40.0, "current_symbol": "FOLAD"},
    )
    for _ in range(8):
        await asyncio.sleep(0)
    status = await js.load_status()
    assert status["groups"]["A"]["completed"] == 4
    assert status["completed_symbols"] == 4


async def test_symbol_result_event_seeds_shared_fallback_store() -> None:
    """Full results in SYMBOL_RESULT_UPDATED must land in api/job_state's
    fallback store and be served by the router's load helpers (no Redis)."""
    await js.reset_job()
    result = ct.compute_single_symbol({"symbol": "FOLAD", "price_last": 8500, "market": "TSE"}, "A")
    await ct._emit("SYMBOL_RESULT_UPDATED", result)
    for _ in range(8):
        await asyncio.sleep(0)

    single = await pr._load_single_result("FOLAD")
    assert single is not None and single["armor_score"] == result["armor_score"]
    everything = await pr._load_all_results()
    assert any(r["symbol"] == "FOLAD" for r in everything)


async def test_partial_symbol_update_does_not_degrade_full_record() -> None:
    await js.reset_job()
    full = ct.compute_single_symbol({"symbol": "FOLAD", "price_last": 100, "market": "TSE"}, "A")
    await ct._emit("SYMBOL_RESULT_UPDATED", full)
    for _ in range(8):
        await asyncio.sleep(0)
    # A later partial payload (legacy shape) must merge, not overwrite
    await ct._emit("SYMBOL_RESULT_UPDATED", {"symbol": "FOLAD", "group": "A", "armor_score": 77.7})
    for _ in range(8):
        await asyncio.sleep(0)

    stored = await pr._load_single_result("FOLAD")
    assert stored["armor_score"] == 77.7  # merged update applied
    assert stored.get("expires_at") == full["expires_at"]  # full record preserved


async def test_async_dispatch_runs_pipeline_inside_loop_and_finalizes(monkeypatch) -> None:
    """dispatch_armor_pipeline_async: A->B->C->finalize with every event
    flowing through the funnel — status ends SUCCESS with exact counters.

    Celery is installed in this environment, so the dispatcher would normally
    delegate to the real broker path (that behavior is covered by the broker
    integration suite); patch it away to exercise the inline fallback."""
    monkeypatch.setattr(ct, "_get_celery_app", lambda: None)
    await js.reset_job()
    rows = {
        "A": [{"symbol": f"A{i}", "price_last": 1000 + i, "market": "TSE"} for i in range(7)],
        "B": [{"symbol": f"B{i}", "price_last": 500 + i, "market": "TSE"} for i in range(3)],
        "C": [{"symbol": f"C{i}", "price_last": 100 + i, "market": "TSE"} for i in range(2)],
    }
    out = await ct.dispatch_armor_pipeline_async(rows, job_id="e2e")

    assert out["total"] == 12 and out["success"] == 12 and out["failed"] == 0
    assert out["overall_status"] == "SUCCESS"

    status = await js.load_status()
    assert status["overall_status"] == "SUCCESS"
    assert status["total_symbols"] == 12 and status["completed_symbols"] == 12
    assert status["groups"]["A"]["total"] == 7
    assert status["groups"]["B"]["total"] == 3
    assert status["groups"]["C"]["total"] == 2
    assert status["progress_percent"] == 100.0

    everything = await pr._load_all_results()
    assert len(everything) == 12


async def test_broadcast_event_is_synchronous_api_for_workers() -> None:
    """broadcast_event schedules without awaiting — the worker call site is a
    plain sync function inside a running loop."""
    await js.reset_job()
    mgr = get_armor_ws_manager()
    mgr.broadcast_event("PRECOMPUTATION_PROGRESS", {"group": "C", "completed": 1, "total": 2, "percent": 50.0})
    for _ in range(8):
        await asyncio.sleep(0)
    status = await js.load_status()
    assert status["groups"]["C"]["completed"] == 1


async def test_duplicate_event_id_is_delivered_once_to_clients() -> None:
    """Redis echo protection: the same event_id must not reach a client twice
    nor re-enter the funnel."""
    import json as _json

    await js.reset_job()
    mgr = get_armor_ws_manager()

    class _Client:
        def __init__(self) -> None:
            self.frames: list[dict] = []

        async def accept(self) -> None:
            return None

        async def send_text(self, raw: str) -> None:
            self.frames.append(_json.loads(raw))

    client = _Client()
    await mgr.connect(client)
    n_before = len(client.frames)  # frame 0 = hydration snapshot

    evt = {
        "type": js.EVENT_PROGRESS,
        "payload": {"group": "B", "completed": 3, "total": 5, "percent": 60.0},
        "event_id": "fixed-dup-id",
    }
    await mgr._broadcast(dict(evt))
    await mgr._broadcast(dict(evt))  # echo with the same event_id
    for _ in range(8):
        await asyncio.sleep(0)

    new_types = [f["type"] for f in client.frames[n_before:]]
    # Exactly one raw event delivered (echo dropped) + one derived snapshot.
    assert new_types.count("PRECOMPUTATION_PROGRESS") == 1
    assert new_types.count("PRECOMPUTATION_STATUS_SNAPSHOT") == 1
    await mgr.disconnect(client)


async def test_finalize_event_finalizes_job_state_through_funnel() -> None:
    """Celery-shape COMPLETED event finalizes the shared status (the fix for
    the never-finalizing Celery path)."""
    await js.reset_job()
    payload = ct.finalize_precompute(
        prev_result={
            "_group_A": {"group": "A", "total_processed": 4, "completed": 3, "failed": 1, "duration_seconds": 1.0},
            "_group_B": {"group": "B", "total_processed": 2, "completed": 2, "failed": 0, "duration_seconds": 0.5},
        },
        job_id="celery-sim",
    )
    assert payload["total"] == 6 and payload["failed"] == 1
    await ct._emit("PRECOMPUTATION_COMPLETED", payload)
    for _ in range(8):
        await asyncio.sleep(0)

    status = await js.load_status()
    assert status["overall_status"] == "PARTIAL"
    assert status["completed_symbols"] == 5 and status["failed_symbols"] == 1
    assert status["progress_percent"] == 100.0
    assert js.is_job_active() is False
