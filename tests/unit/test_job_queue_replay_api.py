"""Tests for the ``POST /jobs/queue/replay`` admin endpoint in apps/api/endpoints/jobs.py.

The endpoint delegates to the shared ``jobs.replay.replay_dead_letter_messages``
core (same logic as ``scripts/replay_dead_letter.py``). These tests exercise
the endpoint surface: mode validation, replay/discard/list/dry-run behaviour,
filters, no-data-loss on push failure, and Redis-unavailable handling.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal redis.asyncio fake with the list ops the replay core uses."""

    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}
        self.queue = "job:queue"
        self.dead = "job:dead"

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        lst = self._lists.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    async def lpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, [])
        self._lists[key] = list(values) + self._lists[key]
        return len(self._lists[key])

    async def lrem(self, key: str, count: int, value: str) -> int:
        lst = self._lists.get(key, [])
        removed = 0
        remaining: list[str] = []
        for item in lst:
            if item == value and removed < count:
                removed += 1
                continue
            remaining.append(item)
        self._lists[key] = remaining
        return removed

    async def lpop(self, key: str) -> str | None:
        lst = self._lists.get(key, [])
        return lst.pop(0) if lst else None

    async def rpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))


class _BrokenPushRedis(_FakeRedis):
    """lpush fails for the MAIN queue only — seeding job:dead still works."""

    async def lpush(self, key: str, *values: str) -> int:
        if key == "job:queue":
            raise RuntimeError("redis down")
        return await super().lpush(key, *values)


def _dead_payload(job_name: str = "SyncQuotesJob", error: str = "boom: timeout") -> dict:
    return {
        "type": "job",
        "job_name": job_name,
        "params": {"limit": 100},
        "job_id": f"job-{job_name}",
        "token": "old-token",
        "attempt": 3,
        "published_at": "2026-01-01T00:00:00+00:00",
        "error": error,
        "dead_lettered_at": 1767225600.0,
    }


async def _run_replay(
    redis: _FakeRedis,
    *,
    job_name: str | None = None,
    search: str | None = None,
    limit: int = 0,
    mode: str = "replay",
):
    """Call the endpoint function directly with patched redis + settings."""
    from apps.api.endpoints import jobs as jobs_mod

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch.object(jobs_mod, "_get_queue_redis", return_value=redis),
    ):
        mock_settings.job_queue_name = "job:queue"
        mock_settings.job_queue_dead_letter = "job:dead"
        mock_settings.job_queue_token = "current-token"

        return await jobs_mod.replay_job_queue(
            job_name=job_name,
            search=search,
            limit=limit,
            mode=mode,
        )


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replay_moves_messages_and_resets_attempt():
    """Replay pushes a fresh copy to the main queue + removes from dead."""
    redis = _FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload(), ensure_ascii=False))

    response = await _run_replay(redis)

    assert response.success is True
    data = response.data
    assert data["mode"] == "replay"
    assert data["total"] == 1
    assert data["replayed"] == 1
    assert data["failed"] == 0
    assert data["queue_size"] == 1
    assert data["dead_size"] == 0

    replayed = json.loads(redis._lists["job:queue"][0])
    assert replayed["job_name"] == "SyncQuotesJob"
    assert replayed["attempt"] == 1
    assert replayed["token"] == "current-token"
    assert "error" not in replayed
    assert "dead_lettered_at" not in replayed
    assert "replayed_at" in replayed

    # Per-message detail exposed to the admin panel.
    assert data["messages"][0]["status"] == "replayed"
    assert data["messages"][0]["job_name"] == "SyncQuotesJob"


@pytest.mark.asyncio
async def test_replay_keeps_message_in_dead_when_push_fails():
    """A failed push leaves the message in dead — no data loss."""
    redis = _BrokenPushRedis()
    raw = json.dumps(_dead_payload(), ensure_ascii=False)
    await redis.lpush("job:dead", raw)

    response = await _run_replay(redis)

    assert response.success is True
    data = response.data
    assert data["replayed"] == 0
    assert data["failed"] == 1
    assert data["dead_size"] == 1   # stayed in dead
    assert data["queue_size"] == 0
    assert data["messages"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Read-only / discard modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_mode_is_read_only():
    redis = _FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload(), ensure_ascii=False))

    response = await _run_replay(redis, mode="list")

    assert response.success is True
    assert response.data["total"] == 1
    assert response.data["replayed"] == 0
    assert await redis.llen("job:dead") == 1
    assert await redis.llen("job:queue") == 0
    assert response.data["messages"][0]["status"] == "listed"


@pytest.mark.asyncio
async def test_dry_run_mode_is_read_only():
    redis = _FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload(), ensure_ascii=False))

    response = await _run_replay(redis, mode="dry-run")

    assert response.success is True
    assert response.data["total"] == 1
    assert await redis.llen("job:dead") == 1
    assert await redis.llen("job:queue") == 0


@pytest.mark.asyncio
async def test_discard_deletes_without_replaying():
    redis = _FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload(), ensure_ascii=False))

    response = await _run_replay(redis, mode="discard")

    assert response.success is True
    assert response.data["discarded"] == 1
    assert await redis.llen("job:dead") == 0
    assert await redis.llen("job:queue") == 0


# ---------------------------------------------------------------------------
# Filters & edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_name_filter_only_replays_matching():
    redis = _FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncQuotesJob"), ensure_ascii=False))
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncCodalJob"), ensure_ascii=False))

    response = await _run_replay(redis, job_name="SyncCodalJob")

    assert response.success is True
    assert response.data["total"] == 1
    assert await redis.llen("job:queue") == 1
    assert await redis.llen("job:dead") == 1
    replayed = json.loads(redis._lists["job:queue"][0])
    assert replayed["job_name"] == "SyncCodalJob"


@pytest.mark.asyncio
async def test_search_filter_matches_error_text():
    redis = _FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncQuotesJob"), ensure_ascii=False))
    await redis.lpush(
        "job:dead",
        json.dumps(_dead_payload("SyncNewsJob", error="different failure"), ensure_ascii=False),
    )

    response = await _run_replay(redis, search="timeout")

    assert response.success is True
    assert response.data["total"] == 1
    assert await redis.llen("job:queue") == 1
    replayed = json.loads(redis._lists["job:queue"][0])
    assert replayed["job_name"] == "SyncQuotesJob"


@pytest.mark.asyncio
async def test_limit_caps_replayed_messages():
    redis = _FakeRedis()
    for i in range(3):
        await redis.lpush("job:dead", json.dumps(_dead_payload(f"Job{i}"), ensure_ascii=False))

    response = await _run_replay(redis, limit=2)

    assert response.success is True
    assert response.data["total"] == 2
    assert await redis.llen("job:queue") == 2
    assert await redis.llen("job:dead") == 1


@pytest.mark.asyncio
async def test_empty_dead_queue_is_a_noop():
    redis = _FakeRedis()

    response = await _run_replay(redis)

    assert response.success is True
    assert response.data["total"] == 0
    assert await redis.llen("job:queue") == 0
    assert await redis.llen("job:dead") == 0


@pytest.mark.asyncio
async def test_invalid_mode_returns_error():
    redis = _FakeRedis()

    response = await _run_replay(redis, mode="explode")

    assert response.success is False
    assert "Invalid mode" in (response.error or {}).get("message", "")


@pytest.mark.asyncio
async def test_redis_unavailable_returns_error():
    from apps.api.endpoints import jobs as jobs_mod

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch.object(jobs_mod, "_get_queue_redis", return_value=None),
    ):
        mock_settings.job_queue_name = "job:queue"
        mock_settings.job_queue_dead_letter = "job:dead"

        # Direct function call bypasses FastAPI's Query resolution, so the
        # default Query object is passed as-is — pass the mode explicitly.
        response = await jobs_mod.replay_job_queue(mode="replay")

    assert response.success is False
    assert "Redis unavailable" in (response.error or {}).get("message", "")
