"""Unit tests for the ``JobDeduplicator`` and ``JobRegistry`` helpers.

Covers:
  - ``JobDeduplicator``: mark/duplicate detection, TTL expiry (via a patched
    ``time.monotonic``), remove and clear
  - ``JobRegistry``: register/get/create/list/unregister and module discovery
"""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

from jobs.base_job import BaseJob
from jobs.deduplication import JobDeduplicator
from jobs.job_context import JobContext
from jobs.job_registry import JobRegistry
from jobs.job_result import JobResult


class _DummyJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        return JobResult.success_result(job_name=self.name)


class _OtherDummyJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        return JobResult.success_result(job_name=self.name)


class _NotAJob:
    """Plain class that must NOT be discovered by ``register_module``."""


# ──────────────────────────────────────────────
#  JobDeduplicator
# ──────────────────────────────────────────────


class TestJobDeduplicator:
    async def test_not_duplicate_initially(self) -> None:
        dedup = JobDeduplicator()
        assert await dedup.is_duplicate("job:quotes") is False

    async def test_mark_then_duplicate(self) -> None:
        dedup = JobDeduplicator()
        await dedup.mark("job:quotes")
        assert await dedup.is_duplicate("job:quotes") is True

    async def test_different_keys_are_independent(self) -> None:
        dedup = JobDeduplicator()
        await dedup.mark("job:a")
        assert await dedup.is_duplicate("job:b") is False
        assert await dedup.is_duplicate("job:a") is True

    async def test_remove(self) -> None:
        dedup = JobDeduplicator()
        await dedup.mark("job:a")
        await dedup.remove("job:a")
        assert await dedup.is_duplicate("job:a") is False

    async def test_remove_missing_key_is_noop(self) -> None:
        dedup = JobDeduplicator()
        await dedup.remove("never-marked")
        assert await dedup.is_duplicate("never-marked") is False

    async def test_clear(self) -> None:
        dedup = JobDeduplicator()
        await dedup.mark("job:a")
        await dedup.mark("job:b")
        await dedup.clear()
        assert await dedup.is_duplicate("job:a") is False
        assert await dedup.is_duplicate("job:b") is False

    async def test_ttl_expiry_drops_key(self) -> None:
        dedup = JobDeduplicator(ttl=10.0)
        with patch("jobs.deduplication.time.monotonic", return_value=100.0):
            await dedup.mark("job:a")
        # Advance past the TTL → key must be gone on the next check.
        with patch("jobs.deduplication.time.monotonic", return_value=111.0):
            assert await dedup.is_duplicate("job:a") is False

    async def test_mark_within_ttl_still_duplicate(self) -> None:
        dedup = JobDeduplicator(ttl=10.0)
        with patch("jobs.deduplication.time.monotonic", return_value=100.0):
            await dedup.mark("job:a")
        with patch("jobs.deduplication.time.monotonic", return_value=109.99):
            assert await dedup.is_duplicate("job:a") is True

    async def test_ttl_expires_exactly_at_boundary(self) -> None:
        """Expiry is ``now >= expires`` — at the exact boundary the key is gone."""
        dedup = JobDeduplicator(ttl=10.0)
        with patch("jobs.deduplication.time.monotonic", return_value=100.0):
            await dedup.mark("job:a")
        with patch("jobs.deduplication.time.monotonic", return_value=110.0):
            assert await dedup.is_duplicate("job:a") is False

    async def test_custom_ttl_overrides_default(self) -> None:
        dedup = JobDeduplicator(ttl=1000.0)
        with patch("jobs.deduplication.time.monotonic", return_value=100.0):
            await dedup.mark("job:short", ttl=5.0)
        with patch("jobs.deduplication.time.monotonic", return_value=104.9):
            assert await dedup.is_duplicate("job:short") is True
        with patch("jobs.deduplication.time.monotonic", return_value=105.1):
            assert await dedup.is_duplicate("job:short") is False


# ──────────────────────────────────────────────
#  JobRegistry
# ──────────────────────────────────────────────


class TestJobRegistry:
    async def test_register_and_get(self) -> None:
        reg = JobRegistry()
        reg.register(_DummyJob)
        assert reg.get("_DummyJob") is _DummyJob

    def test_get_unknown_returns_none(self) -> None:
        reg = JobRegistry()
        assert reg.get("NoSuchJob") is None

    async def test_create_instantiates_with_name(self) -> None:
        reg = JobRegistry()
        reg.register(_DummyJob)
        job = reg.create("_DummyJob")
        assert job is not None
        assert isinstance(job, _DummyJob)
        assert job.name == "_DummyJob"

    def test_create_unknown_returns_none(self) -> None:
        reg = JobRegistry()
        assert reg.create("NoSuchJob") is None

    async def test_create_runs_execute(self) -> None:
        reg = JobRegistry()
        reg.register(_DummyJob)
        job = reg.create("_DummyJob")
        ctx = JobContext(job_id="j-1", job_name="_DummyJob")
        result = await job.execute(ctx)
        assert result.success is True
        assert result.job_name == "_DummyJob"

    def test_list_names_and_get_all(self) -> None:
        reg = JobRegistry()
        reg.register(_DummyJob)
        reg.register(_OtherDummyJob)
        assert set(reg.list_names()) == {"_DummyJob", "_OtherDummyJob"}
        all_jobs = reg.get_all()
        assert all_jobs["_DummyJob"] is _DummyJob
        # get_all must return a copy, not the internal dict.
        all_jobs["_DummyJob"] = _OtherDummyJob
        assert reg.get("_DummyJob") is _DummyJob

    def test_unregister(self) -> None:
        reg = JobRegistry()
        reg.register(_DummyJob)
        reg.unregister("_DummyJob")
        assert reg.get("_DummyJob") is None
        # Unregistering an unknown name must be a no-op.
        reg.unregister("_DummyJob")

    def test_register_module_discovers_subclasses(self) -> None:
        module = types.ModuleType("fake_jobs")
        module.DummyJob = _DummyJob
        module.OtherDummyJob = _OtherDummyJob
        module.NotAJob = _NotAJob
        module.BaseJob = BaseJob  # must be excluded (abstract base)
        sys.modules["fake_jobs"] = module
        try:
            reg = JobRegistry()
            reg.register_module(module)
            assert set(reg.list_names()) == {"_DummyJob", "_OtherDummyJob"}
        finally:
            del sys.modules["fake_jobs"]

    def test_register_module_ignores_plain_classes_and_base(self) -> None:
        module = types.ModuleType("fake_jobs_empty")
        module.NotAJob = _NotAJob
        module.BaseJob = BaseJob
        sys.modules["fake_jobs_empty"] = module
        try:
            reg = JobRegistry()
            reg.register_module(module)
            assert reg.list_names() == []
        finally:
            del sys.modules["fake_jobs_empty"]
