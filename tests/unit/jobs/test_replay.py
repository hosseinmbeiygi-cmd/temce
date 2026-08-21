"""Unit tests for the dead-letter replay core (jobs/replay.py).

Covers:
  - ``current_token`` / ``_matches`` / ``_decode`` helpers
  - ``_new_replay_payload`` (attempt reset, token refresh, error strip)
  - ``replay_dead_letter_messages`` in replay / discard / list / dry-run modes
  - ``resolve_since`` window labels
  - ``classify_error`` bucket mapping
  - ``_build_summary`` aggregation (job names, categories, repeated job_ids)
  - ``summarize_dead_letter`` with a fake Redis client
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import pytest

from jobs.replay import (
    DeadLetterSummary,
    ReplayResult,
    _build_summary,
    _decode,
    _matches,
    _new_replay_payload,
    classify_error,
    current_token,
    replay_dead_letter_messages,
    resolve_since,
    summarize_dead_letter,
)

# ── Helpers ───────────────────────────────────────────────────────────────


class FakeRedis:
    """Minimal redis.asyncio fake: lists only (lrange/lpush/lrem/lpop/rpush/llen)."""

    def __init__(self, lists: dict[str, list[str]] | None = None) -> None:
        self._lists: dict[str, list[str]] = {k: list(v) for k, v in (lists or {}).items()}

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return list(self._lists.get(key, []))[start : end + 1 if end >= 0 else None]

    async def lpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, [])
        self._lists[key] = list(values) + self._lists[key]
        return len(values)

    async def lrem(self, key: str, count: int, value: str) -> int:
        lst = self._lists.get(key, [])
        removed = 0
        out: list[str] = []
        for item in lst:
            if count and removed < count and item == value:
                removed += 1
                continue
            out.append(item)
        self._lists[key] = out
        return removed

    async def lpop(self, key: str) -> str | None:
        lst = self._lists.get(key, [])
        return lst.pop(0) if lst else None

    async def rpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))


def _dead_message(job_name: str, job_id: str, attempt: int = 3, error: str | None = None) -> str:
    return json.dumps(
        {
            "type": "job",
            "job_name": job_name,
            "job_id": job_id,
            "token": "t",
            "attempt": attempt,
            "error": error,
            "dead_lettered_at": time.time(),
        },
        ensure_ascii=False,
    )


# ── helpers ───────────────────────────────────────────────────────────────


class TestHelpers:
    def test_current_token_uses_settings_token(self) -> None:
        assert current_token("configured-token") == "configured-token"

    def test_current_token_generates_random_when_missing(self) -> None:
        t1 = current_token()
        t2 = current_token()
        assert t1 and t1 != t2

    def test_matches_filters_by_job_name_and_search(self) -> None:
        payload = {"job_name": "SyncQuotesJob", "symbol": "فولاد"}
        assert _matches(payload, "SyncQuotesJob", None) is True
        assert _matches(payload, "SyncCodalJob", None) is False
        assert _matches(payload, None, "فولاد") is True
        assert _matches(payload, None, "unrelated") is False

    def test_decode_tolerates_malformed(self) -> None:
        assert _decode("not-json")["job_name"] == "<malformed>"
        assert _decode('{"job_name": "X"}')["job_name"] == "X"

    def test_new_replay_payload_resets_attempt_and_token(self) -> None:
        payload = {
            "job_name": "X",
            "attempt": 3,
            "token": "old",
            "error": "boom",
            "dead_lettered_at": 123.0,
        }
        out = json.loads(_new_replay_payload(payload, "new-token"))

        assert out["attempt"] == 1
        assert out["token"] == "new-token"
        assert "error" not in out
        assert "dead_lettered_at" not in out
        assert "replayed_at" in out
        assert "published_at" in out


# ── replay modes ──────────────────────────────────────────────────────────


class TestReplayModes:
    @pytest.mark.asyncio
    async def test_replay_moves_messages_back_to_queue(self) -> None:
        redis = FakeRedis({"job:dead": [_dead_message("A", "1"), _dead_message("B", "2")]})
        result = await replay_dead_letter_messages(
            redis,
            queue_name="job:queue",
            dead_queue="job:dead",
            token="t",
        )

        assert isinstance(result, ReplayResult)
        assert result.mode == "replay"
        assert result.total == 2
        assert result.replayed == 2
        assert result.failed == 0
        assert len(redis._lists["job:queue"]) == 2
        assert redis._lists["job:dead"] == []  # originals removed after LPUSH
        for msg in result.messages:
            assert msg.status == "replayed"
            assert msg.attempt == 1

    @pytest.mark.asyncio
    async def test_replay_respects_job_name_filter(self) -> None:
        redis = FakeRedis(
            {
                "job:dead": [
                    _dead_message("SyncQuotesJob", "1"),
                    _dead_message("SyncCodalJob", "2"),
                ]
            }
        )
        result = await replay_dead_letter_messages(
            redis,
            queue_name="job:queue",
            dead_queue="job:dead",
            token="t",
            job_name="SyncQuotesJob",
        )

        assert result.total == 1
        assert result.replayed == 1
        assert result.messages[0].job_name == "SyncQuotesJob"
        # Unmatched message stays in dead.
        assert len(redis._lists["job:dead"]) == 1

    @pytest.mark.asyncio
    async def test_replay_limit(self) -> None:
        redis = FakeRedis({"job:dead": [_dead_message("A", "1"), _dead_message("A", "2")]})
        result = await replay_dead_letter_messages(
            redis,
            queue_name="job:queue",
            dead_queue="job:dead",
            token="t",
            limit=1,
        )

        assert result.total == 1
        assert result.replayed == 1
        assert len(redis._lists["job:dead"]) == 1  # second message untouched

    @pytest.mark.asyncio
    async def test_failed_push_keeps_message_in_dead(self) -> None:
        class _FailingRedis(FakeRedis):
            async def lpush(self, key: str, *values: str) -> int:
                raise RuntimeError("redis down")

        redis = _FailingRedis({"job:dead": [_dead_message("A", "1")]})
        result = await replay_dead_letter_messages(
            redis,
            queue_name="job:queue",
            dead_queue="job:dead",
            token="t",
        )

        assert result.replayed == 0
        assert result.failed == 1
        assert result.messages[0].status == "failed"
        # No data loss — the original stays in dead.
        assert len(redis._lists["job:dead"]) == 1

    @pytest.mark.asyncio
    async def test_discard_removes_matching_messages(self) -> None:
        redis = FakeRedis({"job:dead": [_dead_message("A", "1"), _dead_message("B", "2")]})
        result = await replay_dead_letter_messages(
            redis,
            queue_name="job:queue",
            dead_queue="job:dead",
            token="t",
            mode="discard",
        )

        assert result.mode == "discard"
        assert result.discarded == 2
        assert redis._lists["job:dead"] == []
        assert all(m.status == "discarded" for m in result.messages)

    @pytest.mark.asyncio
    async def test_list_mode_is_read_only(self) -> None:
        redis = FakeRedis({"job:dead": [_dead_message("A", "1")]})
        result = await replay_dead_letter_messages(
            redis,
            queue_name="job:queue",
            dead_queue="job:dead",
            token="t",
            mode="list",
        )

        assert result.mode == "list"
        assert result.replayed == 0
        assert result.discarded == 0
        assert result.messages[0].status == "listed"
        assert len(redis._lists["job:dead"]) == 1  # untouched
        assert result.queue_size == 0
        assert result.dead_size == 1

    @pytest.mark.asyncio
    async def test_dry_run_reports_without_changes(self) -> None:
        redis = FakeRedis({"job:dead": [_dead_message("A", "1")]})
        result = await replay_dead_letter_messages(
            redis,
            queue_name="job:queue",
            dead_queue="job:dead",
            token="t",
            mode="dry-run",
        )

        assert result.mode == "dry-run"
        assert result.total == 1
        assert redis._lists.get("job:queue", []) == []
        assert len(redis._lists["job:dead"]) == 1


# ── resolve_since / classify_error ────────────────────────────────────────


class TestResolveSince:
    def test_all_and_empty_return_none(self) -> None:
        assert resolve_since("all") is None
        assert resolve_since("") is None

    def test_24h_and_week(self) -> None:
        now = 1_700_000_000.0
        assert resolve_since("24h", now) == now - 24 * 3600
        assert resolve_since("week", now) == now - 7 * 24 * 3600

    def test_today_uses_tehran_midnight(self) -> None:
        from core.time.timezone import localize

        now_dt = localize(datetime(2026, 1, 15, 18, 0), "Asia/Tehran")
        since = resolve_since("today", now_dt.timestamp())
        start = localize(datetime(2026, 1, 15, 0, 0), "Asia/Tehran")
        assert since == start.timestamp()

    def test_unknown_label_raises(self) -> None:
        with pytest.raises(ValueError):
            resolve_since("month")


class TestClassifyError:
    def test_empty_maps_to_no_error(self) -> None:
        assert classify_error(None) == "no_error"
        assert classify_error("") == "no_error"

    def test_known_categories(self) -> None:
        assert classify_error("connection refused to database") == "db_error"
        assert classify_error("json decode failed") == "parse_error"
        assert classify_error("request timed out") == "timeout"
        assert classify_error("rate limit exceeded, 429") == "rate_limit"
        assert classify_error("HTTP 500 status code") == "http_error"
        assert classify_error("401 unauthorized") == "auth"
        assert classify_error("Lock not acquired") == "lock_duplicate"

    def test_unknown_maps_to_other(self) -> None:
        assert classify_error("something weird happened") == "other"


# ── summary ───────────────────────────────────────────────────────────────


class TestSummary:
    def test_build_summary_aggregates_counts(self) -> None:
        raw = [
            _dead_message("SyncQuotesJob", "job-1", error="timeout"),
            _dead_message("SyncQuotesJob", "job-1", error="timeout"),  # repeated
            _dead_message("SyncCodalJob", "job-2", error="db connection refused"),
            "malformed-payload",
        ]
        summary = _build_summary(raw, "job:dead")

        assert isinstance(summary, DeadLetterSummary)
        assert summary.total == 3  # malformed excluded from total
        assert summary.malformed == 1
        assert summary.job_names == [
            {"name": "SyncQuotesJob", "count": 2},
            {"name": "SyncCodalJob", "count": 1},
        ]
        assert summary.error_categories[0]["category"] == "timeout"
        assert summary.error_categories[1]["category"] == "db_error"
        # Same job_id twice → repeated.
        assert summary.repeated_messages == 1
        assert summary.repeated[0]["job_id"] == "job-1"

    def test_build_summary_respects_window(self) -> None:
        raw = [
            json.dumps({"job_name": "A", "job_id": "1", "dead_lettered_at": time.time()}),
            json.dumps(
                {"job_name": "B", "job_id": "2", "dead_lettered_at": time.time() - 10 * 24 * 3600}
            ),
        ]
        since = time.time() - 7 * 24 * 3600
        summary = _build_summary(raw, "job:dead", since=since)

        assert summary.total == 1
        assert summary.job_names[0]["name"] == "A"

    def test_build_summary_empty(self) -> None:
        summary = _build_summary([], "job:dead")
        assert summary.total == 0
        assert summary.job_names == []
        assert summary.error_categories == []

    @pytest.mark.asyncio
    async def test_summarize_dead_letter_reads_from_redis(self) -> None:
        redis = FakeRedis(
            {"job:dead": [_dead_message("SyncQuotesJob", "1", error="timeout")]}
        )
        summary = await summarize_dead_letter(redis, dead_queue="job:dead")

        assert summary.total == 1
        assert summary.queue == "job:dead"
        assert summary.window == "all"
        assert summary.job_names == [{"name": "SyncQuotesJob", "count": 1}]
        assert summary.error_categories == [{"category": "timeout", "count": 1}]
