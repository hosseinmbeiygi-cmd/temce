from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.logging import get_logger
from storage.layout import StorageLayout

logger = get_logger(__name__)


class RetentionPolicy:
    def __init__(self, layout: StorageLayout | None = None) -> None:
        self.layout = layout or StorageLayout()

    def apply_policy(self, path: Path, max_age_days: int, pattern: str = "*") -> int:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        removed = 0
        for f in path.glob(pattern):
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    f.unlink()
                    removed += 1
            elif f.is_dir():
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    shutil.rmtree(f)
                    removed += 1
        if removed:
            logger.info("Retention: removed %d items from %s (max_age=%dd)", removed, path, max_age_days)
        return removed

    def clean_raw_data(self, max_age_days: int = 30) -> int:
        return self.apply_policy(self.layout.raw, max_age_days)

    def clean_temp_data(self, max_age_days: int = 1) -> int:
        return self.apply_policy(self.layout.temp, max_age_days)

    def clean_archives(self, max_age_days: int = 90) -> int:
        return self.apply_policy(self.layout.archives, max_age_days)

    def clean_exports(self, max_age_days: int = 7) -> int:
        return self.apply_policy(self.layout.exports, max_age_days)

    def clean_backups(self, max_age_days: int = 180) -> int:
        return self.apply_policy(self.layout.backups, max_age_days)

    def clean_all(
        self,
        raw_days: int = 30,
        temp_days: int = 1,
        archive_days: int = 90,
        export_days: int = 7,
        backup_days: int = 180,
    ) -> dict[str, int]:
        return {
            "raw": self.clean_raw_data(raw_days),
            "temp": self.clean_temp_data(temp_days),
            "archives": self.clean_archives(archive_days),
            "exports": self.clean_exports(export_days),
            "backups": self.clean_backups(backup_days),
        }

    def size_by_category(self) -> dict[str, int]:
        cats = {
            "raw": self.layout.raw,
            "processed": self.layout.processed,
            "archives": self.layout.archives,
            "exports": self.layout.exports,
            "temp": self.layout.temp,
            "models": self.layout.models,
            "backups": self.layout.backups,
        }
        return {name: sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) for name, path in cats.items()}
