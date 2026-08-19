"""Unit tests for the dead-letter ops cycle script (scripts/dead_letter_ops.py).

Covers the full one-command cycle on a fake redis:
  - default run: seeds (if empty) → reports → replays → verifies
  - ``--no-seed`` uses the existing queue
  - ``--no-replay`` leaves the dead queue untouched
  - seed is skipped when the queue is not empty (unless ``--force-seed``)
  - ``--cleanup`` deletes both queues at the end
  - invalid ``--window`` fails fast
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.dead_letter_ops import main as ops_main
from scripts.dead_letter_report import _demo_raw_messages

DEMO_COUNT = len(_demo_raw_messages())


# ── Fake redis client (list ops the cycle uses + delete) ────────────────


class FakeRedis:
    """Minimal redis.asyncio fake: lrange / lpush / lrem / llen / delete."""

    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}

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

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def delete(self, *keys: str) -> int:
        for key in keys:
            self._lists.pop(key, None)
        return 1


def _settings(token: str = "current-token") -> SimpleNamespace:
    return SimpleNamespace(
        job_queue_name="job:queue",
        job_queue_dead_letter="job:dead",
        job_queue_token=token,
    )


async def _run_main(argv: list[str], redis: FakeRedis, settings: SimpleNamespace) -> None:
    """Run the ops cycle main() with patched argv / redis / settings."""
    with (
        patch("sys.argv", ["dead_letter_ops.py", *argv]),
        patch("scripts.dead_letter_ops._get_redis", return_value=redis),
        patch("scripts.dead_letter_ops.settings", settings),
    ):
        await ops_main()


def _dead_payload(job_name: str = "SyncQuotesJob", error: str = "boom: connection timeout") -> dict:
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


# ── Tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_cycle_seeds_reports_replays_and_verifies(capsys) -> None:
    """Default run on an empty queue: seed → report → replay → verify."""
    redis = FakeRedis()

    await _run_main(["--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "SEED" in out
    assert "گزارش خلاصه" in out
    assert "REPLAY" in out
    assert "VERIFY" in out
    # Everything seeded was replayed to the main queue; dead is drained.
    assert await redis.llen("job:queue") == DEMO_COUNT
    assert await redis.llen("job:dead") == 0


@pytest.mark.asyncio
async def test_no_seed_uses_existing_queue(capsys) -> None:
    """--no-seed replays whatever is already in job:dead without adding more."""
    redis = FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncCodalJob"), ensure_ascii=False))

    await _run_main(["--no-seed", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "SEED" not in out
    assert await redis.llen("job:queue") == 1
    assert await redis.llen("job:dead") == 0


@pytest.mark.asyncio
async def test_seed_skipped_when_queue_not_empty(capsys) -> None:
    """Without --force-seed, a non-empty dead queue is left untouched by seeding."""
    redis = FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncCodalJob"), ensure_ascii=False))

    await _run_main(["--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "seed رد شد" in out
    # Only the pre-existing message was replayed — the demo batch was NOT added.
    assert await redis.llen("job:queue") == 1
    assert await redis.llen("job:dead") == 0


@pytest.mark.asyncio
async def test_force_seed_adds_even_when_queue_not_empty(capsys) -> None:
    """--force-seed pushes the demo batch on top of existing messages."""
    redis = FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncCodalJob"), ensure_ascii=False))

    await _run_main(["--force-seed", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "seed رد شد" not in out
    assert await redis.llen("job:queue") == 1 + DEMO_COUNT
    assert await redis.llen("job:dead") == 0


@pytest.mark.asyncio
async def test_no_replay_keeps_messages_in_dead(capsys) -> None:
    """--no-replay only reports + verifies; the dead queue keeps its messages."""
    redis = FakeRedis()

    await _run_main(["--no-replay", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "REPLAY" not in out
    assert await redis.llen("job:dead") == DEMO_COUNT  # seeded but not replayed
    assert await redis.llen("job:queue") == 0


@pytest.mark.asyncio
async def test_cleanup_deletes_both_queues(capsys) -> None:
    """--cleanup removes job:queue and job:dead after the cycle."""
    redis = FakeRedis()

    await _run_main(["--cleanup", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "CLEANUP" in out
    assert await redis.llen("job:queue") == 0
    assert await redis.llen("job:dead") == 0


@pytest.mark.asyncio
async def test_invalid_window_fails_fast(capsys) -> None:
    """An unknown --window value must exit(1) with a clear message."""
    redis = FakeRedis()

    with pytest.raises(SystemExit):
        await _run_main(["--window", "bogus"], redis, _settings())

    out = capsys.readouterr().out
    assert "بازهٔ نامعتبر" in out
    assert await redis.llen("job:dead") == 0  # nothing was seeded/mutated


@pytest.mark.asyncio
async def test_replay_failure_exits_nonzero(capsys) -> None:
    """A failed replay must exit(1) so automation/cron notices the partial failure."""

    class _BrokenRedis(FakeRedis):
        """lpush fails only for the MAIN queue — seeding job:dead still works."""

        async def lpush(self, key: str, *values: str) -> int:
            if key == "job:queue":
                raise RuntimeError("redis down")
            return await super().lpush(key, *values)

    redis = _BrokenRedis()

    with pytest.raises(SystemExit) as exc:
        await _run_main(["--no-save"], redis, _settings())

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "REPLAY" in out
    # No data loss: failed messages stay in the dead queue.
    assert await redis.llen("job:dead") == DEMO_COUNT
    assert await redis.llen("job:queue") == 0
