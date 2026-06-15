from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from domain.market_data.quote import Quote
from pipelines.normalization.quote_normalizer import QuoteNormalizer
from pipelines.validation.quote_validator import QuoteValidator
from services.quote_service import QuoteService

logger = get_logger(__name__)


class QuoteIngestionPipeline:
    def __init__(
        self,
        normalizer: QuoteNormalizer | None = None,
        validator: QuoteValidator | None = None,
        quote_service: QuoteService | None = None,
    ) -> None:
        self.normalizer = normalizer or QuoteNormalizer()
        self.validator = validator or QuoteValidator()
        self.quote_service = quote_service or QuoteService()

    async def process(self, raw_data: list[dict[str, Any]]) -> Result[int]:
        try:
            normalized = [self.normalizer.normalize(d) for d in raw_data]
            valid = [n for n in normalized if self.validator.validate(n)]
            quotes = [Quote(**v) for v in valid]
            count = 0
            for q in quotes:
                r = await self.quote_service.save_quote(q)
                if r.success:
                    count += 1
            logger.info("Pipeline processed %d/%d quotes", count, len(quotes))
            return Result.ok(count)
        except Exception as e:
            logger.error("Pipeline failed: %s", e)
            return Result.fail(str(e))
