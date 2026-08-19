"""Unit tests for the ``JobContext`` / ``JobResult`` data classes.

Covers:
  - ``JobContext`` defaults, param/metadata accessors, ``record_start`` and
    ``to_dict`` serialisation (ISO-8601 for timestamps, ``None`` otherwise)
  - ``JobResult`` constructors (``success_result`` / ``failure``), defaults
    and ``to_dict`` serialisation
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jobs.job_context import JobContext
from jobs.job_result import JobResult


class TestJobContext:
    def test_defaults(self) -> None:
        ctx = JobContext(job_id="j-1", job_name="SyncQuotesJob")
        assert ctx.job_id == "j-1"
        assert ctx.job_name == "SyncQuotesJob"
        assert ctx.scheduled_at is None
        assert ctx.started_at is None
        assert ctx.params == {}
        assert ctx.metadata == {}
        assert ctx.correlation_id == ""
        assert ctx.user_id == ""
        assert ctx.retry_count == 0
        assert ctx.max_retries == 3

    def test_get_param_with_default(self) -> None:
        ctx = JobContext(job_id="j", job_name="n")
        assert ctx.get_param("missing", 42) == 42
        assert ctx.get_param("missing") is None

    def test_get_param_returns_value(self) -> None:
        ctx = JobContext(job_id="j", job_name="n", params={"days": 5})
        assert ctx.get_param("days") == 5
        assert ctx.get_param("days", 99) == 5

    def test_set_and_get_metadata(self) -> None:
        ctx = JobContext(job_id="j", job_name="n")
        ctx.set_metadata("attempt", 1)
        assert ctx.get_metadata("attempt") == 1
        assert ctx.get_metadata("nope", "fallback") == "fallback"
        assert ctx.get_metadata("nope") is None

    def test_record_start_sets_utc_aware_datetime(self) -> None:
        ctx = JobContext(job_id="j", job_name="n")
        assert ctx.started_at is None
        ctx.record_start()
        assert ctx.started_at is not None
        assert ctx.started_at.tzinfo is not None
        assert ctx.started_at.tzinfo == UTC

    def test_to_dict_without_timestamps(self) -> None:
        ctx = JobContext(job_id="j-9", job_name="FundsSyncJob", params={"x": 1})
        d = ctx.to_dict()
        assert d["job_id"] == "j-9"
        assert d["job_name"] == "FundsSyncJob"
        assert d["params"] == {"x": 1}
        assert d["metadata"] == {}
        assert d["scheduled_at"] is None
        assert d["started_at"] is None
        assert d["retry_count"] == 0
        assert d["max_retries"] == 3

    def test_to_dict_serialises_timestamps(self) -> None:
        fixed = datetime(2026, 1, 5, 8, 45, 0, tzinfo=UTC)
        ctx = JobContext(
            job_id="j",
            job_name="n",
            scheduled_at=fixed,
            started_at=fixed,
            correlation_id="c-1",
            user_id="u-1",
            retry_count=2,
            max_retries=5,
        )
        d = ctx.to_dict()
        assert d["scheduled_at"] == fixed.isoformat()
        assert d["started_at"] == fixed.isoformat()
        assert d["correlation_id"] == "c-1"
        assert d["user_id"] == "u-1"
        assert d["retry_count"] == 2
        assert d["max_retries"] == 5


class TestJobResult:
    def test_success_result_defaults(self) -> None:
        res = JobResult.success_result(job_name="SyncQuotesJob")
        assert res.success is True
        assert res.job_name == "SyncQuotesJob"
        assert res.message == "Completed"
        assert res.data == {}
        assert res.error == ""
        assert res.started_at is not None
        assert res.completed_at == res.started_at
        assert res.started_at.tzinfo is not None
        assert res.duration_ms == 0.0

    def test_success_result_with_data_and_message(self) -> None:
        res = JobResult.success_result(
            job_name="FundsSyncJob",
            data={"funds": 12},
            message="12 funds synced",
        )
        assert res.success is True
        assert res.data == {"funds": 12}
        assert res.message == "12 funds synced"

    def test_success_result_message_defaults_when_empty(self) -> None:
        res = JobResult.success_result(job_name="X", message="")
        assert res.message == "Completed"

    def test_failure(self) -> None:
        res = JobResult.failure("db unreachable", job_name="BackfillJob")
        assert res.success is False
        assert res.job_name == "BackfillJob"
        assert res.message == "Failed"
        assert res.error == "db unreachable"
        assert res.data == {}
        assert res.completed_at == res.started_at

    def test_to_dict_success(self) -> None:
        fixed = datetime(2026, 1, 5, 9, 0, 0, tzinfo=UTC)
        res = JobResult(
            success=True,
            job_name="n",
            message="done",
            data={"k": "v"},
            started_at=fixed,
            completed_at=fixed + timedelta(seconds=2),
            duration_ms=2000.0,
        )
        d = res.to_dict()
        assert d["success"] is True
        assert d["job_name"] == "n"
        assert d["message"] == "done"
        assert d["data"] == {"k": "v"}
        assert d["error"] == ""
        assert d["started_at"] == fixed.isoformat()
        assert d["completed_at"] == (fixed + timedelta(seconds=2)).isoformat()
        assert d["duration_ms"] == 2000.0

    def test_to_dict_with_none_timestamps(self) -> None:
        res = JobResult(success=False, error="boom")
        d = res.to_dict()
        assert d["started_at"] is None
        assert d["completed_at"] is None
        assert d["duration_ms"] == 0.0
