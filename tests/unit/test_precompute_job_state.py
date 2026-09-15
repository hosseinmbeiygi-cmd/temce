"""
Unit tests — api/job_state.py (precompute job state machine)
=============================================================
Verifies that the worker contract events (contracts/events.md) flowing through
ArmorWsManager drive the job status served by /api/precompute/status.

Runs without Redis: the in-memory fallback path is exercised (CacheService
is not initialized in unit tests, so is_connected is False).
"""
from __future__ import annotations

import pytest

from api import job_state as js
from api.ws_manager import get_armor_ws_manager


@pytest.fixture(autouse=True)
def _reset_state():
    """Isolate in-memory job state between tests."""
    js._mem_status = None
    js._started_at = None
    js._finalizing = False
    js._mem_results.clear()
    yield
    js._mem_status = None
    js._started_at = None
    js._finalizing = False
    js._mem_results.clear()


async def test_reset_job_starts_running() -> None:
    status = await js.reset_job()
    assert status["overall_status"] == "RUNNING"
    assert status["current_group"] == "A"
    assert js.is_job_active() is True


async def test_progress_updates_group_and_overall() -> None:
    await js.reset_job()
    await js.handle_event(
        js.EVENT_PROGRESS,
        {"group": "A", "completed": 3, "total": 10, "percent": 30.0, "current_symbol": "FOLAD"},
    )
    status = await js.load_status()
    assert status["groups"]["A"] == {"total": 10, "completed": 3, "failed": 0, "status": "RUNNING"}
    assert status["total_symbols"] == 10
    assert status["completed_symbols"] == 3
    assert status["current_symbol"] == "FOLAD"
    assert status["progress_percent"] == 30.0


async def test_group_done_finalizes_and_advances() -> None:
    await js.reset_job()
    await js.handle_event(
        js.EVENT_GROUP_COMPLETED,
        {"group": "A", "total_processed": 10, "failed": 1, "timestamp": "t"},
    )
    status = await js.load_status()
    group_a = status["groups"]["A"]
    assert group_a["completed"] == 9
    assert group_a["failed"] == 1
    assert group_a["status"] == "SUCCESS"
    assert status["current_group"] == "B"


async def test_multi_group_accumulation() -> None:
    await js.reset_job()
    await js.handle_event(js.EVENT_GROUP_COMPLETED, {"group": "A", "total_processed": 10, "failed": 0, "timestamp": "t"})
    await js.handle_event(js.EVENT_GROUP_COMPLETED, {"group": "B", "total_processed": 5, "failed": 0, "timestamp": "t"})
    await js.handle_event(js.EVENT_PROGRESS, {"group": "C", "completed": 2, "total": 3, "percent": 66.0, "current_symbol": "X"})
    status = await js.load_status()
    assert status["total_symbols"] == 18
    assert status["completed_symbols"] == 17


async def test_completed_finalizes_job() -> None:
    await js.reset_job()
    await js.handle_event(
        js.EVENT_COMPLETED,
        {"total": 20, "success": 19, "failed": 1, "avg_dri": 80.0, "duration_seconds": 5.0, "timestamp": "t"},
    )
    status = await js.load_status()
    assert status["overall_status"] == "SUCCESS"
    assert status["completed_symbols"] == 19
    assert status["failed_symbols"] == 1
    assert status["progress_percent"] == 100.0
    assert all(m["status"] == "SUCCESS" for m in status["groups"].values())
    assert js.is_job_active() is False


async def test_completed_with_zero_payload_falls_back_to_group_counters() -> None:
    await js.reset_job()
    await js.handle_event(js.EVENT_PROGRESS, {"group": "A", "completed": 7, "total": 7, "percent": 100.0, "current_symbol": "Z"})
    await js.handle_event(
        js.EVENT_COMPLETED,
        {"total": 0, "success": 0, "failed": 0, "avg_dri": 0.0, "duration_seconds": 0.0, "timestamp": "t"},
    )
    status = await js.load_status()
    assert status["total_symbols"] == 7
    assert status["completed_symbols"] == 7
    assert status["overall_status"] == "SUCCESS"


async def test_unknown_group_event_is_ignored() -> None:
    await js.reset_job()
    await js.handle_event(js.EVENT_PROGRESS, {"group": "Z", "completed": 1, "total": 1, "percent": 100.0, "current_symbol": "X"})
    status = await js.load_status()
    assert status["total_symbols"] == 0


async def test_ws_manager_funnel_updates_state() -> None:
    """The real funnel: ArmorWsManager.broadcast_* must feed the state machine."""
    await js.reset_job()
    mgr = get_armor_ws_manager()
    await mgr.broadcast_progress({"group": "B", "completed": 2, "total": 4, "percent": 50.0, "current_symbol": "Y"})
    status = await js.load_status()
    assert status["groups"]["B"]["completed"] == 2
    assert status["completed_symbols"] == 2


class _FakeClient:
    """Minimal WS stand-in that records every frame it is sent."""

    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def accept(self) -> None:  # pragma: no cover - connect() calls it
        return None

    async def send_text(self, raw: str) -> None:
        import json

        self.frames.append(json.loads(raw))


async def test_state_change_pushes_live_snapshot_to_clients() -> None:
    """Every state change must push a PRECOMPUTATION_STATUS_SNAPSHOT with the
    recomputed overall progress to connected dashboard clients."""
    await js.reset_job()
    mgr = get_armor_ws_manager()
    client = _FakeClient()
    await mgr.connect(client)

    await mgr.broadcast_progress(
        {"group": "A", "completed": 5, "total": 10, "percent": 50.0, "current_symbol": "FOLAD"}
    )

    types = [f["type"] for f in client.frames]
    # Frame 0 is the connect-time hydration snapshot. Consumers observe the
    # raw worker event first, then the derived snapshot it triggered.
    assert types[0] == "PRECOMPUTATION_STATUS_SNAPSHOT"
    assert types[1] == "PRECOMPUTATION_PROGRESS"
    assert types[2] == "PRECOMPUTATION_STATUS_SNAPSHOT"
    snapshot = client.frames[2]["payload"]
    assert snapshot["completed_symbols"] == 5
    assert snapshot["progress_percent"] == 50.0
    assert snapshot["groups"]["A"]["completed"] == 5

    await mgr.disconnect(client)


async def test_completion_pushes_final_success_snapshot() -> None:
    """The final COMPLETED event must produce a terminal SUCCESS snapshot so
    the frontend banner (and SoundEffectManager) can react."""
    await js.reset_job()
    mgr = get_armor_ws_manager()
    client = _FakeClient()
    await mgr.connect(client)

    await mgr.broadcast_completed(
        {"total": 20, "success": 19, "failed": 1, "avg_dri": 81.0, "duration_seconds": 9.0, "timestamp": "t"}
    )

    types = [f["type"] for f in client.frames]
    # Frame 0 = hydration snapshot, frame 1 = raw COMPLETED, frame 2 = final snapshot
    assert types[0] == "PRECOMPUTATION_STATUS_SNAPSHOT"
    assert types[1] == "PRECOMPUTATION_COMPLETED"
    assert types[2] == "PRECOMPUTATION_STATUS_SNAPSHOT"
    snapshot = client.frames[2]["payload"]
    assert snapshot["overall_status"] == "SUCCESS"
    assert snapshot["progress_percent"] == 100.0
    assert snapshot["completed_symbols"] == 19

    await mgr.disconnect(client)


async def test_snapshot_events_do_not_reenter_state_machine() -> None:
    """Recursion guard: a PRECOMPUTATION_STATUS_SNAPSHOT fed back through the
    funnel must be ignored (whitelisted state events only)."""
    await js.reset_job()
    before = await js.load_status()

    await js.handle_event(js.EVENT_STATUS_SNAPSHOT, dict(before))
    await js.handle_event("SOME_UNKNOWN_TYPE", {"group": "A"})

    after = await js.load_status()
    assert after == before


async def test_snapshot_broadcast_failure_does_not_break_persistence() -> None:
    """If the WS broadcast blows up, the state must still be persisted."""
    await js.reset_job()
    mgr = get_armor_ws_manager()

    class _Boom:
        async def accept(self) -> None:
            return None

        async def send_text(self, raw: str) -> None:
            raise RuntimeError("boom")

    client = _Boom()
    await mgr.connect(client)

    await js.handle_event(
        js.EVENT_PROGRESS,
        {"group": "A", "completed": 1, "total": 2, "percent": 50.0, "current_symbol": "X"},
    )

    status = await js.load_status()
    assert status["completed_symbols"] == 1
    await mgr.disconnect(client)
