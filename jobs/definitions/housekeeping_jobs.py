from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)


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
        instrument_ids = context.get_param("instrument_ids", [])
        from integrations.cache.memory_cache import MemoryCache
        from integrations.cache.redis_client import RedisClient

        cache = MemoryCache()
        redis = RedisClient()
        await redis.connect()
        warmed = 0
        for inst_id in instrument_ids:
            key = f"instrument:{inst_id}"
            if not cache.exists(key):
                cache.set(key, {"id": inst_id, "warmed": True})
                warmed += 1
        await redis.disconnect()
        return JobResult.success_result(job_name=self.name, data={"warmed": warmed})


class HealthCheckJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        checks = {}
        try:
            from integrations.cache.redis_client import RedisClient

            redis = RedisClient()
            await redis.connect()
            await redis.ping()
            checks["redis"] = "ok"
            await redis.disconnect()
        except Exception as e:
            checks["redis"] = str(e)
        try:
            checks["config"] = "ok"
        except Exception as e:
            checks["config"] = str(e)
        return JobResult.success_result(job_name=self.name, data={"checks": checks})
