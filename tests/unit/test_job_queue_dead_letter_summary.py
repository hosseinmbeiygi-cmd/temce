"""Tests for the dead-letter queue summary (GET /jobs/queue/summary).

Covers:
  - The pure ``_build_summary`` aggregation: job_name distribution,
    error-category bucketing, top raw errors, repeated job_ids, malformed
    payload counting, empty-queue shape.
  - ``classify_error`` bucketing for known signatures.
  - The endpoint: wires the analyzer through, Redis-unavailable handling.
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

from jobs.replay import _build_summary, classify_error, resolve_since, summarize_dead_letter


# ---------------------------------------------------------------------------
# classify_error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error,expected",
    [
        ("DBError: SQLAlchemy connection refused", "db_error"),
        ("ParseError: json decode failed", "parse_error"),
        ("boom: connection timeout", "timeout"),
        ("HTTP 429 rate limit exceeded", "rate_limit"),
        ("HTTP 502 from upstream", "http_error"),
        ("invalid auth token", "auth"),
        ("Lock not acquired", "lock_duplicate"),
        ("some weird thing", "other"),
        ("", "no_error"),
        (None, "no_error"),
    ],
)
def test_classify_error_buckets(error, expected):
    assert classify_error(error) == expected


# ---------------------------------------------------------------------------
# _build_summary (pure aggregation)
# ---------------------------------------------------------------------------


def _payload(job_name, job_id, error="boom: connection timeout"):
    return json.dumps(
        {
            "job_name": job_name,
            "job_id": job_id,
            "attempt": 3,
            "error": error,
            "dead_lettered_at": 1767225600.0,
        },
        ensure_ascii=False,
    )


def test_summary_empty_queue_shape():
    summary = _build_summary([], "job:dead")
    assert summary.total == 0
    assert summary.queue == "job:dead"
    assert summary.job_names == []
    assert summary.error_categories == []
    assert summary.top_errors == []
    assert summary.repeated == []
    assert summary.repeated_messages == 0
    assert summary.malformed == 0


def test_summary_job_name_distribution_sorted_desc():
    raw = [
        _payload("SyncQuotesJob", "q1"),
        _payload("SyncQuotesJob", "q2"),
        _payload("SyncCodalJob", "c1"),
    ]
    summary = _build_summary(raw, "job:dead")

    assert summary.total == 3
    assert summary.job_names == [
        {"name": "SyncQuotesJob", "count": 2},
        {"name": "SyncCodalJob", "count": 1},
    ]


def test_summary_error_categories_aggregate():
    raw = [
        _payload("A", "a1", error="DBError: sqlalchemy down"),
        _payload("B", "b1", error="ParseError: bad json"),
        _payload("C", "c1", error="boom: connection timeout"),
    ]
    summary = _build_summary(raw, "job:dead")

    cats = {c["category"]: c["count"] for c in summary.error_categories}
    assert cats == {"db_error": 1, "parse_error": 1, "timeout": 1}


def test_summary_top_errors_truncated_and_sorted():
    raw = [
        _payload("A", "a1", error="timeout x"),
        _payload("A", "a2", error="timeout x"),
        _payload("B", "b1", error="other error"),
    ]
    summary = _build_summary(raw, "job:dead")

    assert summary.top_errors[0] == {"error": "timeout x", "count": 2}
    assert summary.top_errors[1] == {"error": "other error", "count": 1}
    assert all(len(e["error"]) <= 200 for e in summary.top_errors)


def test_summary_repeated_job_ids_detected():
    raw = [
        _payload("SyncQuotesJob", "job-42"),
        _payload("SyncQuotesJob", "job-42"),   # same logical message, dead 2x
        _payload("SyncQuotesJob", "job-43"),
    ]
    summary = _build_summary(raw, "job:dead")

    assert summary.repeated == [
        {"job_name": "SyncQuotesJob", "job_id": "job-42", "count": 2}
    ]
    assert summary.repeated_messages == 1   # 2 copies → 1 extra


def test_summary_malformed_payloads_counted():
    raw = ["not json{{{", _payload("A", "a1")]
    summary = _build_summary(raw, "job:dead")

    # ``total`` counts messages in scope (decodable + in window); malformed
    # payloads are tracked separately so the report never hides corruption.
    assert summary.total == 1
    assert summary.malformed == 1
    # Only the valid message contributes to distributions.
    assert summary.job_names == [{"name": "A", "count": 1}]


def test_summary_missing_job_id_skips_repeat_tracking():
    payload = json.dumps({"job_name": "A", "attempt": 3, "error": "x"})
    summary = _build_summary([payload, payload], "job:dead")

    assert summary.total == 2
    assert summary.repeated == []
    assert summary.repeated_messages == 0


# ---------------------------------------------------------------------------
# resolve_since (window → epoch threshold)
# ---------------------------------------------------------------------------


def test_resolve_since_all_is_none():
    assert resolve_since("all") is None
    assert resolve_since("") is None


def test_resolve_since_week_and_24h():
    now = 1_800_000_000.0
    assert resolve_since("week", now=now) == now - 7 * 24 * 3600
    assert resolve_since("24h", now=now) == now - 24 * 3600


def test_resolve_since_today_is_tehran_midnight():
    # 2027-01-10 12:00 UTC == 2027-01-10 15:30 Tehran (UTC+3:30, no DST in winter)
    now = 1_799_366_400.0
    since = resolve_since("today", now=now)
    assert since is not None
    from datetime import UTC as _UTC, datetime

    dt = datetime.fromtimestamp(since, tz=_UTC)
    # Tehran midnight == previous UTC 20:30 (Iran is UTC+3:30)
    assert dt.hour == 20
    assert dt.minute == 30
    assert dt.second == 0


def test_resolve_since_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        resolve_since("bogus")


# ---------------------------------------------------------------------------
# _build_summary with since window filter
# ---------------------------------------------------------------------------


def _payload_at(job_name, job_id, ts):
    return json.dumps(
        {
            "job_name": job_name,
            "job_id": job_id,
            "attempt": 3,
            "error": "boom",
            "dead_lettered_at": ts,
        },
        ensure_ascii=False,
    )


def test_summary_window_filters_old_messages():
    now = 1_800_000_000.0
    raw = [
        _payload_at("A", "a1", now - 3600),           # recent → included
        _payload_at("A", "a2", now - 3 * 24 * 3600),  # 3 days ago → excluded
        _payload_at("B", "b1", now - 2 * 3600),        # recent → included
    ]
    summary = _build_summary(raw, "job:dead", since=now - 24 * 3600, window="24h")

    assert summary.total == 2
    assert summary.window == "24h"
    assert summary.since == now - 24 * 3600
    assert summary.job_names == [{"name": "A", "count": 1}, {"name": "B", "count": 1}]


def test_summary_window_boundary_inclusive():
    now = 1_800_000_000.0
    raw = [_payload_at("A", "a1", now - 24 * 3600)]  # exactly at boundary
    summary = _build_summary(raw, "job:dead", since=now - 24 * 3600)
    assert summary.total == 1


def test_summary_window_excludes_missing_or_bad_timestamp():
    now = 1_800_000_000.0
    no_ts = json.dumps({"job_name": "A", "job_id": "a0", "attempt": 3, "error": "x"})
    bad_ts = json.dumps({"job_name": "B", "job_id": "b0", "attempt": 3, "error": "x", "dead_lettered_at": "nope"})
    raw = [no_ts, bad_ts, _payload_at("C", "c1", now - 1000)]
    summary = _build_summary(raw, "job:dead", since=now - 24 * 3600)

    assert summary.total == 1
    assert summary.job_names == [{"name": "C", "count": 1}]


def test_summary_window_malformed_still_counted():
    now = 1_800_000_000.0
    raw = ["not json{{{", _payload_at("A", "a1", now - 1000)]
    summary = _build_summary(raw, "job:dead", since=now - 24 * 3600)

    assert summary.malformed == 1
    assert summary.total == 1


@pytest.mark.asyncio
async def test_summarize_dead_letter_passes_window_through():
    class _R:
        def __init__(self):
            self._m = []

        async def lrange(self, *a):
            return self._m

    now = 1_800_000_000.0
    redis = _R()
    redis._m = [_payload_at("A", "a1", now - 1000), _payload_at("B", "b1", now - 5 * 24 * 3600)]

    summary = await summarize_dead_letter(redis, dead_queue="job:dead", window="week", since=None)
    assert summary.total == 2
    assert summary.window == "week"

    summary = await summarize_dead_letter(redis, dead_queue="job:dead", window="all", since=now - 24 * 3600)
    assert summary.total == 1


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class _FakeRedis:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        if end == -1:
            return self._messages[start:]
        return self._messages[start : end + 1]


@pytest.mark.asyncio
async def test_endpoint_returns_summary():
    from apps.api.endpoints import jobs as jobs_mod

    # Two messages for the SAME job so the count-sorted first entry is
    # deterministic (ties break alphabetically).
    redis = _FakeRedis([_payload("SyncQuotesJob", "q1"), _payload("SyncQuotesJob", "q2")])

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch.object(jobs_mod, "_get_queue_redis", return_value=redis),
    ):
        mock_settings.job_queue_dead_letter = "job:dead"

        # Direct function calls do NOT resolve Query defaults — pass every
        # param explicitly (same convention as the replay endpoint tests).
        response = await jobs_mod.dead_letter_summary(window="all", since=None)

    assert response.success is True
    data = response.data
    assert data["total"] == 2
    assert data["queue"] == "job:dead"
    assert data["window"] == "all"
    assert data["since"] is None
    assert data["job_names"][0] == {"name": "SyncQuotesJob", "count": 2}
    assert data["malformed"] == 0
    assert "error_categories" in data
    assert "top_errors" in data
    assert "repeated" in data


@pytest.mark.asyncio
async def test_endpoint_window_filters_messages():
    from apps.api.endpoints import jobs as jobs_mod

    now = 1_800_000_000.0
    redis = _FakeRedis([
        json.dumps({"job_name": "A", "job_id": "a1", "attempt": 3, "error": "x", "dead_lettered_at": now - 1000}),
        json.dumps({"job_name": "B", "job_id": "b1", "attempt": 3, "error": "x", "dead_lettered_at": now - 5 * 24 * 3600}),
    ])

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch.object(jobs_mod, "_get_queue_redis", return_value=redis),
    ):
        mock_settings.job_queue_dead_letter = "job:dead"

        # An explicit ``since`` (epoch) filters deterministically without
        # depending on wall-clock time.
        response = await jobs_mod.dead_letter_summary(window="all", since=now - 24 * 3600)

    assert response.success is True
    data = response.data
    assert data["total"] == 1
    assert data["since"] == now - 24 * 3600
    assert data["job_names"] == [{"name": "A", "count": 1}]


@pytest.mark.asyncio
async def test_endpoint_rejects_invalid_window():
    from apps.api.endpoints import jobs as jobs_mod

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch.object(jobs_mod, "_get_queue_redis", return_value=_FakeRedis([])),
    ):
        mock_settings.job_queue_dead_letter = "job:dead"

        response = await jobs_mod.dead_letter_summary(window="bogus", since=None)

    assert response.success is False
    assert "Invalid window" in (response.error or {}).get("message", "")


@pytest.mark.asyncio
async def test_endpoint_redis_unavailable():
    from apps.api.endpoints import jobs as jobs_mod

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch.object(jobs_mod, "_get_queue_redis", return_value=None),
    ):
        mock_settings.job_queue_dead_letter = "job:dead"

        response = await jobs_mod.dead_letter_summary(window="all", since=None)

    assert response.success is False
    assert "Redis unavailable" in (response.error or {}).get("message", "")
