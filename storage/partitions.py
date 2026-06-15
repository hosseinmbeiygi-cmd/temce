from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class PartitionManager:
    def __init__(self, base_path: str | None = None) -> None:
        self.base = Path(base_path or settings.data_dir)

    def _partition_path(self, source: str, dataset: str, dt: date) -> Path:
        return self.base / source / dataset / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}"

    def ensure_partition(self, source: str, dataset: str, dt: date) -> Path:
        p = self._partition_path(source, dataset, dt)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def write_partition(self, source: str, dataset: str, dt: date, filename: str, content: str) -> Path:
        part_dir = self.ensure_partition(source, dataset, dt)
        file_path = part_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def list_partitions(self, source: str, dataset: str) -> list[date]:
        base = self.base / source / dataset
        if not base.exists():
            return []
        partitions: list[date] = []
        for year_dir in sorted(base.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                for day_dir in sorted(month_dir.iterdir()):
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue
                    partitions.append(date(int(year_dir.name), int(month_dir.name), int(day_dir.name)))
        return partitions

    def list_files_in_partition(self, source: str, dataset: str, dt: date) -> list[Path]:
        p = self._partition_path(source, dataset, dt)
        if not p.exists():
            return []
        return sorted(p.iterdir())

    def delete_partition(self, source: str, dataset: str, dt: date) -> bool:
        p = self._partition_path(source, dataset, dt)
        if p.exists():
            shutil.rmtree(p)
            logger.info("Deleted partition: %s", p)
            return True
        return False

    def get_partition_size(self, source: str, dataset: str, dt: date) -> int:
        p = self._partition_path(source, dataset, dt)
        if not p.exists():
            return 0
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    def partition_date_range(self, source: str, dataset: str, start: date, end: date) -> list[date]:
        current = start
        result = []
        while current <= end:
            p = self._partition_path(source, dataset, current)
            if p.exists():
                result.append(current)
            current += timedelta(days=1)
        return result
