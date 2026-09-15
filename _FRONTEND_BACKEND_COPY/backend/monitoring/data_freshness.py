from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"


@dataclass
class EntityUpdate:
    entity_type: str
    entity_id: str
    timestamp: datetime


class FreshnessMonitor:
    def __init__(self) -> None:
        self._updates: dict[str, dict[str, datetime]] = {}

    async def record_update(self, entity_type: str, entity_id: str, timestamp: datetime) -> None:
        if entity_type not in self._updates:
            self._updates[entity_type] = {}
        self._updates[entity_type][entity_id] = timestamp
        logger.debug(
            "Recorded update for %s/%s at %s",
            entity_type,
            entity_id,
            timestamp.isoformat(),
        )

    async def check_staleness(self, entity_type: str, max_age_seconds: float) -> list[dict[str, Any]]:
        stale_entities: list[dict[str, Any]] = []
        records = self._updates.get(entity_type, {})
        now = datetime.now(UTC)
        for entity_id, last_update in records.items():
            age_seconds = (now - last_update).total_seconds()
            if age_seconds > max_age_seconds:
                stale_entities.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "last_update": last_update.isoformat(),
                        "age_seconds": round(age_seconds, 2),
                        "status": FreshnessStatus.STALE.value,
                    }
                )
        logger.info(
            "Staleness check for %s: %d/%d entities stale",
            entity_type,
            len(stale_entities),
            len(records),
        )
        return stale_entities

    async def get_entity_status(self, entity_type: str, entity_id: str, max_age_seconds: float) -> FreshnessStatus:
        records = self._updates.get(entity_type, {})
        if entity_id not in records:
            return FreshnessStatus.MISSING
        now = datetime.now(UTC)
        age_seconds = (now - records[entity_id]).total_seconds()
        if age_seconds > max_age_seconds:
            return FreshnessStatus.STALE
        return FreshnessStatus.FRESH

    def get_freshness_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {}
        now = datetime.now(UTC)
        for entity_type, records in self._updates.items():
            ages: list[float] = []
            for ts in records.values():
                age = (now - ts).total_seconds()
                ages.append(age)
            if ages:
                report[entity_type] = {
                    "total_entities": len(records),
                    "max_age_seconds": round(max(ages), 2),
                    "min_age_seconds": round(min(ages), 2),
                    "avg_age_seconds": round(sum(ages) / len(ages), 2),
                    "last_update": max(records.values()).isoformat(),
                }
            else:
                report[entity_type] = {
                    "total_entities": 0,
                    "max_age_seconds": None,
                    "min_age_seconds": None,
                    "avg_age_seconds": None,
                    "last_update": None,
                }
        return report

    def get_all_entity_types(self) -> list[str]:
        return list(self._updates.keys())

    def get_entity_ids(self, entity_type: str) -> list[str]:
        return list(self._updates.get(entity_type, {}).keys())


freshness_monitor = FreshnessMonitor()
