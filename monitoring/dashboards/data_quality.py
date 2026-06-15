from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from monitoring.metrics.service import metrics_service

logger = get_logger(__name__)


class DataQualityDashboard:
    def __init__(self) -> None:
        self._freshness_records: dict[str, dict[str, datetime]] = {}
        self._completeness_records: dict[str, dict[str, bool]] = {}
        self._consistency_records: dict[str, dict[str, Any]] = {}

    def record_freshness(self, entity_type: str, entity_id: str, timestamp: datetime) -> None:
        if entity_type not in self._freshness_records:
            self._freshness_records[entity_type] = {}
        self._freshness_records[entity_type][entity_id] = timestamp
        metrics_service.record_data_freshness(entity_type, timestamp)

    def record_completeness(self, entity_type: str, entity_id: str, is_complete: bool) -> None:
        if entity_type not in self._completeness_records:
            self._completeness_records[entity_type] = {}
        self._completeness_records[entity_type][entity_id] = is_complete

    def record_consistency(self, entity_type: str, entity_id: str, checksum: str) -> None:
        if entity_type not in self._consistency_records:
            self._consistency_records[entity_type] = {}
        self._consistency_records[entity_type][entity_id] = checksum

    def check_freshness(self, entity_type: str) -> dict[str, Any]:
        records = self._freshness_records.get(entity_type, {})
        now = datetime.now(UTC)
        stale_threshold_seconds = 3600
        fresh_entities = []
        stale_entities = []
        missing_entities = []
        for eid, ts in records.items():
            age_seconds = (now - ts).total_seconds()
            if age_seconds > stale_threshold_seconds:
                stale_entities.append({"entity_id": eid, "age_seconds": round(age_seconds)})
            else:
                fresh_entities.append({"entity_id": eid, "age_seconds": round(age_seconds)})
        return {
            "entity_type": entity_type,
            "total": len(records),
            "fresh_count": len(fresh_entities),
            "stale_count": len(stale_entities),
            "missing_count": len(missing_entities),
            "fresh_entities": fresh_entities,
            "stale_entities": stale_entities,
            "missing_entities": missing_entities,
            "timestamp": now.isoformat(),
        }

    def check_completeness(self, entity_type: str) -> dict[str, Any]:
        records = self._completeness_records.get(entity_type, {})
        complete_count = sum(1 for v in records.values() if v)
        incomplete_count = sum(1 for v in records.values() if not v)
        total = len(records)
        completeness_pct = (complete_count / total * 100) if total > 0 else 0.0
        incomplete_ids = [eid for eid, v in records.items() if not v]
        return {
            "entity_type": entity_type,
            "total": total,
            "complete_count": complete_count,
            "incomplete_count": incomplete_count,
            "completeness_percent": round(completeness_pct, 2),
            "incomplete_entities": incomplete_ids,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def check_consistency(self, entity_type: str) -> dict[str, Any]:
        records = self._consistency_records.get(entity_type, {})
        checksum_groups: dict[str, list[str]] = {}
        for eid, checksum in records.items():
            checksum_groups.setdefault(checksum, []).append(eid)
        inconsistent_groups = {checksum: eids for checksum, eids in checksum_groups.items() if len(eids) == 1}
        consistent_count = sum(len(eids) for eids in checksum_groups.values() if len(eids) > 1)
        total = len(records)
        return {
            "entity_type": entity_type,
            "total": total,
            "consistent_count": consistent_count,
            "inconsistent_groups": len(inconsistent_groups),
            "unique_checksums": len(checksum_groups),
            "inconsistent_entity_ids": [eid for eids in inconsistent_groups.values() for eid in eids],
            "timestamp": datetime.now(UTC).isoformat(),
        }


data_quality_dashboard = DataQualityDashboard()
