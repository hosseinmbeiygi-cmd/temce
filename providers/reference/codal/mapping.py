from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


CODAL_FIELD_MAP = {
    "id": "report_id",
    "symbol": "symbol",
    "company": "company_name",
    "report_type": "report_type",
    "period": "period",
    "year": "fiscal_year",
    "publish_date": "publish_date",
    "title": "title",
    "description": "description",
    "url": "url",
    "file_name": "file_name",
    "file_size": "file_size",
}


class CodalMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or CODAL_FIELD_MAP

    def map(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def map_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map(row) for row in data]
