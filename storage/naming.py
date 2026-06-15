from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)


class NamingConvention:
    DATE_FORMAT = "%Y%m%d"
    TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

    @staticmethod
    def sanitize(name: str) -> str:
        sanitized = re.sub(r"[^\w\-_.]", "_", name)
        sanitized = re.sub(r"_+", "_", sanitized)
        return sanitized.strip("_")

    @staticmethod
    def quote_filename(symbol: str, date: str | None = None, suffix: str = "json") -> str:
        dt = date or datetime.now(UTC).strftime(NamingConvention.DATE_FORMAT)
        return f"quote_{NamingConvention.sanitize(symbol)}_{dt}.{suffix}"

    @staticmethod
    def trade_filename(symbol: str, date: str | None = None, suffix: str = "json") -> str:
        dt = date or datetime.now(UTC).strftime(NamingConvention.DATE_FORMAT)
        return f"trade_{NamingConvention.sanitize(symbol)}_{dt}.{suffix}"

    @staticmethod
    def orderbook_filename(symbol: str, date: str | None = None, suffix: str = "json") -> str:
        dt = date or datetime.now(UTC).strftime(NamingConvention.DATE_FORMAT)
        return f"orderbook_{NamingConvention.sanitize(symbol)}_{dt}.{suffix}"

    @staticmethod
    def snapshot_filename(prefix: str, timestamp: str | None = None, suffix: str = "parquet") -> str:
        ts = timestamp or datetime.now(UTC).strftime(NamingConvention.TIMESTAMP_FORMAT)
        return f"{NamingConvention.sanitize(prefix)}_{ts}.{suffix}"

    @staticmethod
    def partition_path(base: Path, source: str, date_str: str, dataset: str) -> Path:
        year, month, day = (
            date_str[:4],
            date_str[5:7] if "-" in date_str else date_str[4:6],
            date_str[8:10] if "-" in date_str else date_str[6:8],
        )
        return base / source / dataset / f"year={year}" / f"month={month}" / f"day={day}"

    @staticmethod
    def archive_name(dataset: str, date_from: str, date_to: str) -> str:
        return f"{dataset}_{date_from}_{date_to}"

    @staticmethod
    def manifest_name(dataset: str, batch_id: str) -> str:
        return f"manifest_{dataset}_{batch_id}"
