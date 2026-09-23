"""Celery-mode integration tests: the REAL chain against a REAL broker.

What is exercised (and nothing is mocked):

1.  ``precompute.workers.celery_tasks`` builds a real Celery app when the
    ``celery`` package is installed (see requirements.txt) and registers the
    three group tasks plus ``finalize_precompute`` on it.
2.  A real worker subprocess (``_celery_worker_entry.py``, solo pool —
    Windows-safe) consumes ``queue_group_a/b/c`` and runs the chain
    end-to-end through the Redis broker.
3.  ``dispatch_armor_pipeline`` takes the real ``apply_async`` path (not the
    sync fallback) and the chain result is fetched from the Redis result
    backend.
4.  The worker publishes the four contract events from ``contracts/events.md``
    on the ``precompute:events`` Redis channel, and stores per-symbol results
    under ``precompute:result:{symbol}`` — the exact key
    ``api/routers/precompute_router`` reads.

Skipped automatically when the Redis broker is unreachable (CI provisions a
``redis:7-alpine`` service; locally ``redis-server`` must be running).
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import threading
import time

import pytest

import precompute.workers.celery_tasks as ct
import redis
from precompute.config import load_config

pytestmark = [pytest.mark.integration]

_config = load_config()
BROKER_URL = os.getenv("REDIS_URL", _config.redis_url)

WORKER_ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_celery_worker_entry.py")
WORKER_BOOT_TIMEOUT = 60.0
CHAIN_RESULT_TIMEOUT = 120.0


# ── helpers ────────────────────────────────────────────────────────────────
def _broker_reachable() -> bool:
    try:
        probe = redis.Redis.from_url(BROKER_URL, socket_connect_timeout=2, socket_timeout=2)
        ok = bool(probe.ping())
        probe.close()
        return ok
    except Exception:  # noqa: BLE001 — probe must never raise
        return False


def _make_rows(symbols: list[str], group: str) -> list[dict]:
    """Minimal raw-quote rows the pipeline accepts (auditor patches gaps)."""
    return [
        {
            "symbol": sym,
            "group": group,
            "price_last": 10_000.0 + i,
            "trade_value": 5e11 + i * 1e9,
            "trade_volume": 1_000_000 + i,
            "fetched_at": None,
        }
        for i, sym in enumerate(symbols)
    ]


def _wait_until(fn, timeout: float, interval: float = 0.5, what: str = "condition") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fn():
            return
        time.sleep(interval)
    pytest.fail(f"timed out after {timeout}s waiting for {what}")


class EventCapture:
    """Background subscriber on the precompute events channel."""

    def __init__(self, channel: str) -> None:
        self.channel = channel
        self.events: list[dict] = []
        self._stop = threading.Event()
        self._client = redis.Redis.from_url(BROKER_URL, decode_responses=True)
        self._pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        self._pubsub.subscribe(self.channel)
        while not self._stop.is_set():
            msg = self._pubsub.get_message(timeout=0.2)
            if msg and msg.get("type") == "message":
                with contextlib.suppress(TypeError, ValueError):
                    self.events.append(json.loads(msg["data"]))

    def __enter__(self) -> EventCapture:
        self._thread.start()
        time.sleep(0.5)  # let the SUBSCRIBE land before dispatching
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        self._pubsub.close()
        self._client.close()

    def types(self) -> list[str]:
        return [e.get("type") for e in self.events]


# ── fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def real_broker() -> None:
    if not _broker_reachable():
        pytest.skip(f"Redis broker not reachable at {BROKER_URL} — skipping Celery broker integration")


@pytest.fixture(scope="module")
def celery_worker(real_broker):
    """Spawn a real Celery worker subprocess on the three priority queues."""
    log_path = os.path.join(os.environ.get("TEMP", "/tmp"), "celery_it_worker.log")
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [sys.executable, WORKER_ENTRY],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=os.path.dirname(WORKER_ENTRY),
        )
        try:
            def _worker_ready() -> bool:
                if proc.poll() is not None:
                    return False  # crashed during boot
                try:
                    inspector = ct._get_celery_app().control.inspect(timeout=2)
                    pong = inspector.ping()
                except Exception:  # noqa: BLE001
                    return False
                return bool(pong)

            _wait_until(_worker_ready, WORKER_BOOT_TIMEOUT, what="celery worker boot")
            yield proc
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.fixture(autouse=True)
def _clean_redis(real_broker):
    """Flush the broker db around each test for isolation."""
    client = redis.Redis.from_url(BROKER_URL, decode_responses=True)
    client.flushdb()
    yield
    client.flushdb()
    client.close()


# ── tests ──────────────────────────────────────────────────────────────────
def test_celery_app_registers_chain_tasks() -> None:
    """With celery installed, the module must build a real app with all four
    chain tasks registered and routed to the priority queues."""
    app = ct._get_celery_app()
    assert app is not None, "celery is installed — the real app must be built"

    expected = {
        "precompute.workers.celery_tasks.compute_group_a": ct.QUEUE_A,
        "precompute.workers.celery_tasks.compute_group_b": ct.QUEUE_B,
        "precompute.workers.celery_tasks.compute_group_c": ct.QUEUE_C,
        "precompute.workers.celery_tasks.finalize_precompute": ct.QUEUE_A,
    }
    registered = set(app.tasks)
    for name, queue in expected.items():
        assert name in registered, f"{name} not registered on the Celery app"
        # finalize et al. route via per-task options — read the effective queue.
        task_queue = getattr(app.tasks[name], "queue", None)
        assert task_queue == queue, f"{name} must run on {queue}, got {task_queue}"


def test_chain_runs_end_to_end_through_real_broker(celery_worker) -> None:
    """Full pipeline: dispatch → broker → real worker chain → result backend
    → contract events on the channel → per-symbol results in the hot layer."""
    groups = {
        "A": _make_rows(["A1", "A2", "A3", "A4", "A5", "A6"], "A"),
        "B": _make_rows(["B1", "B2", "B3", "B4"], "B"),
        "C": _make_rows(["C1", "C2", "C3"], "C"),
    }
    job_id = "it-celery-full"

    with EventCapture(_config.events_channel) as capture:
        out = ct.dispatch_armor_pipeline(groups, job_id=job_id)

        # dispatch must take the real broker path, not the sync fallback
        assert out["celery"] is True, "dispatch_armor_pipeline must use apply_async with celery installed"
        assert out["job_id"] == job_id
        chain_id = out["chain_id"]
        assert chain_id, "chain id missing"

        app = ct._get_celery_app()
        final = app.AsyncResult(chain_id)
        payload = final.get(timeout=CHAIN_RESULT_TIMEOUT)

    # ── chain result (finalize payload from the result backend) ──
    assert payload["overall_status"] == "SUCCESS"
    assert payload["total"] == 13
    assert payload["success"] == 13
    assert payload["failed"] == 0
    for g, expected_total in (("A", 6), ("B", 4), ("C", 3)):
        summary = payload["groups"][g]
        assert summary["total_processed"] == expected_total
        assert summary["completed"] == expected_total
        assert summary["failed"] == 0

    # ── contract events on the broker channel ──
    types = capture.types()
    assert types.count("SYMBOL_RESULT_UPDATED") == 13
    assert types.count("PRECOMPUTATION_GROUP_COMPLETED") == 3
    assert types.count("PRECOMPUTATION_PROGRESS") >= 3  # ≥1 per non-empty group
    assert types.count("PRECOMPUTATION_COMPLETED") == 1

    # priority order: first A event precedes first B event precedes first C event
    def _first_idx(t: str, group: str | None = None) -> int:
        for i, e in enumerate(capture.events):
            if e.get("type") == t and (group is None or e["payload"].get("group") == group):
                return i
        return -1

    assert 0 < _first_idx("PRECOMPUTATION_GROUP_COMPLETED", "A") < _first_idx("PRECOMPUTATION_GROUP_COMPLETED", "B") < _first_idx("PRECOMPUTATION_GROUP_COMPLETED", "C")

    completed = next(e for e in capture.events if e.get("type") == "PRECOMPUTATION_COMPLETED")
    assert completed["payload"]["job_id"] == job_id
    assert completed["payload"]["total"] == 13

    # ── hot-layer results: the exact key api reads for /symbols/{sym}/summary ──
    hot = redis.Redis.from_url(BROKER_URL, decode_responses=True)
    try:
        for sym in ("A1", "B2", "C3"):
            raw = hot.get(f"precompute:result:{sym}")
            assert raw, f"missing hot-layer result for {sym}"
            result = json.loads(raw)
            assert 0.0 <= result["armor_score"] <= 100.0
            assert 0.0 <= result["data_dri"] <= 100.0
            assert result["group"] == sym[0]
            assert hot.ttl(f"precompute:result:{sym}") > 0  # freshness window set
    finally:
        hot.close()


def test_empty_groups_chain_still_finalizes_completed(celery_worker) -> None:
    """Edge: zero symbols — the chain must still run through the broker and
    emit the terminal PRECOMPUTATION_COMPLETED with total=0."""
    with EventCapture(_config.events_channel) as capture:
        out = ct.dispatch_armor_pipeline({"A": [], "B": [], "C": []}, job_id="it-celery-empty")
        assert out["celery"] is True

        app = ct._get_celery_app()
        payload = app.AsyncResult(out["chain_id"]).get(timeout=CHAIN_RESULT_TIMEOUT)

    assert payload["overall_status"] == "SUCCESS"
    assert payload["total"] == 0
    assert capture.types().count("PRECOMPUTATION_COMPLETED") == 1
    assert capture.types().count("PRECOMPUTATION_GROUP_COMPLETED") == 3


def test_chain_survives_partial_failures_and_reports_them(celery_worker) -> None:
    """A malformed row must be counted as failed (not crash the chain) and the
    finalize event must reflect PARTIAL status."""
    rows = _make_rows(["P1", "P2", "P3"], "A")
    # Malformed but JSON-serializable: a string price breaks float() and the
    # auditor's price-band fallback — the row must be counted, not crash the chain.
    rows.append({"symbol": "BAD", "price_last": "not-a-number", "trade_value": "also-bad"})

    with EventCapture(_config.events_channel):
        out = ct.dispatch_armor_pipeline({"A": rows, "B": [], "C": []}, job_id="it-celery-partial")
        app = ct._get_celery_app()
        payload = app.AsyncResult(out["chain_id"]).get(timeout=CHAIN_RESULT_TIMEOUT)

    assert payload["total"] == 4
    assert payload["success"] == 3
    assert payload["failed"] == 1
    assert payload["overall_status"] == "PARTIAL"
