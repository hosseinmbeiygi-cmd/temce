from __future__ import annotations

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.macro_service import MacroService

logger = get_logger(__name__)


class MacroDataJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        indicators = context.get_param("indicators", ["inflation", "interest_rate", "money_supply"])
        service = MacroService()
        results = {}
        for indicator in indicators:
            result = await service.get_indicator(indicator)
            if result.success:
                results[indicator] = result.value
        return JobResult.success_result(job_name=self.name, data={"indicators": results})


class GoldPriceJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        service = MacroService()
        result = await service.get_gold_prices()
        if result.success:
            return JobResult.success_result(job_name=self.name, data={"gold_prices": result.value})
        return JobResult.failure(result.error, job_name=self.name)


class MetalsPriceJob(BaseJob):
    async def execute(self, context: JobContext) -> JobResult:
        metals = context.get_param("metals", ["copper", "steel", "aluminum"])
        service = MacroService()
        results = {}
        for metal in metals:
            result = await service.get_metal_price(metal)
            if result.success:
                results[metal] = result.value
        return JobResult.success_result(job_name=self.name, data={"metals": results})
