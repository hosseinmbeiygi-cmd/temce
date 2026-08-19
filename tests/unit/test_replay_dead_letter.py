"""Unit tests for the dead-letter replay script (scripts/replay_dead_letter.py).

Covers:
  - Replay: moves messages job:dead → job:queue, resets attempt, refreshes
    token, strips error/dead_lettered_at, removes from dead only on success.
  - ``--list`` and ``--dry-run`` are read-only.
  - ``--discard`` deletes without replaying.
  - Filters (--job-name / --search / --limit) and the empty-queue path.

Uses a fake ``redis.asyncio`` client — no real Redis needed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.replay_dead_letter import main as replay_main

# ── Fake redis client (lrange / lpush / lrem / llen) ────────────────────


class FakeRedis:
    """Minimal redis.asyncio fake with the list ops the replay script uses."""

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


def _dead_payload(
    job_name: str = "SyncQuotesJob",
    attempt: int = 3,
    error: str = "boom: connection timeout",
) -> dict:
    return {
        "type": "job",
        "job_name": job_name,
        "params": {"limit": 100},
        "job_id": f"job-{job_name}",
        "token": "old-token",
        "attempt": attempt,
        "published_at": "2026-01-01T00:00:00+00:00",
        "error": error,
        "dead_lettered_at": 1767225600.0,
    }


def _settings(token: str = "current-token") -> SimpleNamespace:
    return SimpleNamespace(
        job_queue_name="job:queue",
        job_queue_dead_letter="job:dead",
        job_queue_token=token,
    )


async def _run_main(argv: list[str], redis: FakeRedis, settings: SimpleNamespace) -> None:
    """Run the replay script's main() with patched argv / redis / settings."""
    with (
        patch("sys.argv", ["replay_dead_letter.py", *argv]),
        patch("scripts.replay_dead_letter._get_redis", return_value=redis),
        patch("scripts.replay_dead_letter.settings", settings),
    ):
        await replay_main()


# ── Replay ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_moves_messages_and_resets_attempt() -> None:
    redis = FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload(), ensure_ascii=False))

    await _run_main([], redis, _settings())

    # Message moved to the main queue with a fresh retry budget + current token.
    assert await redis.llen("job:queue") == 1
    assert await redis.llen("job:dead") == 0
    replayed = json.loads(redis._lists["job:queue"][0])
    assert replayed["job_name"] == "SyncQuotesJob"
    assert replayed["attempt"] == 1
    assert replayed["token"] == "current-token"
    assert "error" not in replayed
    assert "dead_lettered_at" not in replayed
    assert "replayed_at" in replayed


@pytest.mark.asyncio
async def test_replay_keeps_message_in_dead_when_push_fails() -> None:
    class _BrokenRedis(FakeRedis):
        """lpush fails only for the MAIN queue — seeding job:dead still works."""

        async def lpush(self, key: str, *values: str) -> int:
            if key == "job:queue":
                raise RuntimeError("redis down")
            return await super().lpush(key, *values)

    redis = _BrokenRedis()
    raw = json.dumps(_dead_payload(), ensure_ascii=False)
    await redis.lpush("job:dead", raw)

    with pytest.raises(SystemExit):
        await _run_main([], redis, _settings())

    # Data loss is impossible: the message stays in job:dead.
    assert await redis.llen("job:dead") == 1
    assert await redis.llen("job:queue") == 0


# ── Read-only modes ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_mode_does_not_modify_anything() -> None:
    redis = FakeRedis()
    raw = json.dumps(_dead_payload(), ensure_ascii=False)
    await redis.lpush("job:dead", raw)

    await _run_main(["--list"], redis, _settings())

    assert await redis.llen("job:dead") == 1
    assert await redis.llen("job:queue") == 0


@pytest.mark.asyncio
async def test_dry_run_does_not_modify_anything() -> None:
    redis = FakeRedis()
    raw = json.dumps(_dead_payload(), ensure_ascii=False)
    await redis.lpush("job:dead", raw)

    await _run_main(["--dry-run"], redis, _settings())

    assert await redis.llen("job:dead") == 1
    assert await redis.llen("job:queue") == 0


# ── Discard ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discard_deletes_without_replaying() -> None:
    redis = FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload(), ensure_ascii=False))

    await _run_main(["--discard"], redis, _settings())

    assert await redis.llen("job:dead") == 0
    assert await redis.llen("job:queue") == 0


# ── Filters & empty queue ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_name_filter_only_replays_matching() -> None:
    redis = FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncQuotesJob"), ensure_ascii=False))
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncCodalJob"), ensure_ascii=False))

    await _run_main(["--job-name", "SyncCodalJob"], redis, _settings())

    assert await redis.llen("job:queue") == 1
    assert await redis.llen("job:dead") == 1
    replayed = json.loads(redis._lists["job:queue"][0])
    assert replayed["job_name"] == "SyncCodalJob"


@pytest.mark.asyncio
async def test_search_filter_matches_error_text() -> None:
    redis = FakeRedis()
    await redis.lpush("job:dead", json.dumps(_dead_payload("SyncQuotesJob"), ensure_ascii=False))
    await redis.lpush(
        "job:dead",
        json.dumps(_dead_payload("SyncNewsJob", error="different failure"), ensure_ascii=False),
    )

    await _run_main(["--search", "timeout"], redis, _settings())

    # Only SyncQuotesJob carries "connection timeout" in its error field.
    assert await redis.llen("job:queue") == 1
    assert await redis.llen("job:dead") == 1
    replayed = json.loads(redis._lists["job:queue"][0])
    assert replayed["job_name"] == "SyncQuotesJob"


@pytest.mark.asyncio
async def test_limit_caps_the_number_of_replayed_messages() -> None:
    redis = FakeRedis()
    for i in range(3):
        payload = _dead_payload(f"Job{i}")
        await redis.lpush("job:dead", json.dumps(payload, ensure_ascii=False))

    await _run_main(["--limit", "2"], redis, _settings())

    assert await redis.llen("job:queue") == 2
    assert await redis.llen("job:dead") == 1


@pytest.mark.asyncio
async def test_empty_dead_queue_is_a_noop() -> None:
    redis = FakeRedis()

    await _run_main([], redis, _settings())

    assert await redis.llen("job:queue") == 0
    assert await redis.llen("job:dead") == 0


# ── --summary (read-only dead-letter report) ───────────────────────────


@pytest.mark.asyncio
async def test_summary_mode_prints_report_without_touching_the_queue(capsys) -> None:
    """--summary prints the same report as dead_letter_report.py and is read-only."""
    redis = FakeRedis()
    await redis.lpush(
        "job:dead",
        json.dumps(_dead_payload("SyncQuotesJob", error="DBError: connection refused"), ensure_ascii=False),
    )
    await redis.lpush(
        "job:dead",
        json.dumps(_dead_payload("SyncCodalJob", error="TimeoutError: timed out"), ensure_ascii=False),
    )

    await _run_main(["--summary", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "گزارش خلاصه" in out
    assert "SyncQuotesJob" in out
    assert "SyncCodalJob" in out
    assert "db_error" in out
    assert "timeout" in out
    # Read-only: nothing moved, nothing deleted.
    assert await redis.llen("job:dead") == 2
    assert await redis.llen("job:queue") == 0


@pytest.mark.asyncio
async def test_summary_mode_window_filters_old_messages(capsys) -> None:
    """--summary --window today excludes messages dead-lettered before today."""
    redis = FakeRedis()
    now = __import__("time").time()
    today_payload = {**_dead_payload("TodayJob", error="TimeoutError: x"), "dead_lettered_at": now - 3600}
    old_payload = {**_dead_payload("OldJob", error="DBError: x"), "dead_lettered_at": now - 10 * 24 * 3600}
    await redis.lpush("job:dead", json.dumps(old_payload, ensure_ascii=False))
    await redis.lpush("job:dead", json.dumps(today_payload, ensure_ascii=False))

    await _run_main(["--summary", "--window", "today", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "TodayJob" in out
    assert "OldJob" not in out
    assert await redis.llen("job:dead") == 2  # still read-only


@pytest.mark.asyncio
async def test_summary_mode_saves_report_files_by_default(tmp_path) -> None:
    """Without --no-save the report JSON/Markdown are written like the report script."""
    redis = FakeRedis()
    await redis.lpush(
        "job:dead",
        json.dumps(_dead_payload("SyncQuotesJob", error="DBError: boom"), ensure_ascii=False),
    )

    with patch("scripts.dead_letter_report.REPORT_DIR", tmp_path):
        await _run_main(["--summary"], redis, _settings())

    assert (tmp_path / "dead_letter_report.json").exists()
    assert (tmp_path / "dead_letter_report.md").exists()
    saved = json.loads((tmp_path / "dead_letter_report.json").read_text(encoding="utf-8"))
    assert saved["source"] == "replay-cli"
    assert saved["total"] == 1
    # Queue untouched — summary mode is read-only.
    assert await redis.llen("job:dead") == 1
    assert await redis.llen("job:queue") == 0


@pytest.mark.asyncio
async def test_summary_mode_empty_queue_is_a_noop(capsys) -> None:
    """Empty dead queue → friendly message, exit 0, nothing written."""
    redis = FakeRedis()

    await _run_main(["--summary", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "خالی است" in out
    assert await redis.llen("job:dead") == 0
    assert await redis.llen("job:queue") == 0


@pytest.mark.asyncio
async def test_summary_mode_rejects_invalid_window(capsys) -> None:
    """An unknown --window value must fail fast with a clear message."""
    redis = FakeRedis()
    await redis.lpush(
        "job:dead",
        json.dumps(_dead_payload("SyncQuotesJob"), ensure_ascii=False),
    )

    with pytest.raises(SystemExit):
        await _run_main(["--summary", "--window", "bogus", "--no-save"], redis, _settings())

    out = capsys.readouterr().out
    assert "بازهٔ نامعتبر" in out
    # Read-only even on validation failure.
    assert await redis.llen("job:dead") == 1
