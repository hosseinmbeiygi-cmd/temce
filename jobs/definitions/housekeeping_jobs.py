from __future__ import annotations

from datetime import timedelta

from core.logging import get_logger
from core.time import utc_now_naive
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


class DatabaseRetentionJob(BaseJob):
    """Trim fast-growing operational tables (audit finding: unbounded growth).

    ``job_runs``, ``audit_logs`` and ``provider_health_history`` only ever get
    INSERTs — no housekeeping job touched them, so they grow until the disk
    does. Deletes run in bounded batches so a big backlog cannot lock the
    table for minutes in one transaction.
    """

    _TABLES = {
        "job_runs": "started_at",
        "audit_logs": "timestamp",
        "provider_health_history": "checked_at",
    }

    async def execute(self, context: JobContext) -> JobResult:
        retention_days = context.get_param("db_retention_days", 180)
        batch_size = context.get_param("delete_batch_size", 5_000)
        cutoff = utc_now_naive() - timedelta(days=retention_days)

        from sqlalchemy import text

        from core.database import get_session

        deleted: dict[str, int] = {}
        async for session in get_session():
            for table, ts_col in self._TABLES.items():
                total = 0
                try:
                    while True:
                        res = await session.execute(
                            text(
                                f"DELETE FROM {table} WHERE {ts_col} < :cutoff "
                                "AND ctid IN ("
                                "SELECT ctid FROM "
                                f"{table} WHERE {ts_col} < :cutoff LIMIT :batch)"
                            ),
                            {"cutoff": cutoff, "batch": batch_size},
                        )
                        n = res.rowcount or 0
                        await session.commit()
                        total += n
                        if n < batch_size:
                            break
                except Exception:
                    await session.rollback()
                    logger.exception("DB retention failed for %s", table)
                deleted[table] = total
        return JobResult.success_result(job_name=self.name, data={"deleted": deleted, "cutoff": cutoff.isoformat()})


class DataRetentionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        retention_days = context.get_param("retention_days", 365)
        data_types = context.get_param("data_types", ["quotes", "trades", "logs"])
        from integrations.filesystems.local_storage import LocalStorage
        from integrations.filesystems.retention_manager import RetentionManager

        storage = LocalStorage(base_path=context.get_param("data_path", "./data"))
        manager = RetentionManager(storage)
        for dt in data_types:
            manager.add_rule(f"{dt}/**/*", retention_days)
        result = await manager.apply_rules()
        return JobResult.success_result(job_name=self.name, data={"deleted_by_type": result})


class CacheWarmupJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        """Warm the shared Redis cache (get_cache) for the given instruments.

        Previously this wrote to a throwaway in-memory MemoryCache that was
        discarded at the end of the job — effectively a no-op. Now it warms
        the app-wide Redis cache (single shared connection).
        NOTE: with a large ``instrument_ids`` list this writes day-long TTL
        entries into Redis for each id — a real write burst by design.
        """
        instrument_ids = context.get_param("instrument_ids", [])
        from core.cache import get_cache

        cache = get_cache()
        await cache.initialize()
        warmed = 0
        for inst_id in instrument_ids:
            key = f"instrument:{inst_id}"
            if await cache.get(key) is None:
                await cache.set(key, {"id": inst_id, "warmed": True}, ttl=86400)
                warmed += 1
        return JobResult.success_result(job_name=self.name, data={"warmed": warmed})


class HealthCheckJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        checks = {}
        try:
            from core.cache import get_cache

            cache = get_cache()
            await cache.initialize()
            checks["redis"] = "ok" if await cache.ping() else "unreachable"
        except Exception as e:
            checks["redis"] = str(e)
        try:
            checks["config"] = "ok"
        except Exception as e:
            checks["config"] = str(e)
        return JobResult.success_result(job_name=self.name, data={"checks": checks})
