from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class BaseEnricher(ABC):
    """Base class for all pipeline enrichers.

    Enrichers add computed fields, cross-references, or derived data
    to normalized records before persistence.
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    def enrich(self, record: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single record with additional computed fields."""
        ...

    def enrich_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Enrich a batch of records. Override for batch-level enrichment."""
        enriched = []
        for record in records:
            try:
                enriched.append(self.enrich(record))
            except Exception as e:
                logger.warning("Enrichment failed for record in %s: %s", self.name, e)
                enriched.append(record)
        return enriched

    def validate_enrichment(self, original: dict[str, Any], enriched: dict[str, Any]) -> bool:
        """Verify enrichment didn't lose required fields."""
        required_keys = {"id", "instrument_id"}
        for key in required_keys:
            if key in original and key not in enriched:
                logger.error("Enrichment lost required field '%s' in %s", key, self.name)
                return False
        return True
