from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.backtest_service import BacktestService

logger = get_logger(__name__)


class BacktestExecutionJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        strategy_name = context.get_param("strategy_name", "")
        instrument_ids = context.get_param("instrument_ids", [])
        start_date = context.get_param("start_date", "")
        end_date = context.get_param("end_date", "")
        capital = context.get_param("capital", 1_000_000_000)
        service = BacktestService()
        result = await service.run(
            strategy_name=strategy_name,
            instrument_ids=instrument_ids,
            start_date=start_date,
            end_date=end_date,
            capital=capital,
        )
        if result.success:
            return JobResult.success_result(job_name=self.name, data={"backtest_id": result.value})
        return JobResult.failure(result.error, job_name=self.name)


class BacktestOptimizationJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        strategy_name = context.get_param("strategy_name", "")
        param_grid = context.get_param("param_grid", {})
        service = BacktestService()
        result = await service.optimize(strategy_name=strategy_name, param_grid=param_grid)
        if result.success:
            return JobResult.success_result(job_name=self.name, data={"best_params": result.value})
        return JobResult.failure(result.error, job_name=self.name)
