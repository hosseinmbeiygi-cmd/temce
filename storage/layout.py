from __future__ import annotations

from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class StorageLayout:
    def __init__(self, base_path: str | None = None) -> None:
        self.base = Path(base_path or settings.data_dir)

    @property
    def raw(self) -> Path:
        p = self.base / "raw"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def processed(self) -> Path:
        p = self.base / "processed"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def archives(self) -> Path:
        p = self.base / "archives"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def exports(self) -> Path:
        p = self.base / "exports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def temp(self) -> Path:
        p = self.base / "temp"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def models(self) -> Path:
        p = self.base / "models"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def backups(self) -> Path:
        p = self.base / "backups"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def logs(self) -> Path:
        p = self.base / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def schemas(self) -> Path:
        p = self.base / "schemas"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def raw_for(self, source: str) -> Path:
        p = self.raw / source
        p.mkdir(parents=True, exist_ok=True)
        return p

    def processed_for(self, dataset: str) -> Path:
        p = self.processed / dataset
        p.mkdir(parents=True, exist_ok=True)
        return p

    def clean_temp(self) -> int:
        count = 0
        for f in self.temp.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
            elif f.is_dir():
                shutil.rmtree(f)
                count += 1
        logger.info("Cleaned %d temp items", count)
        return count


import shutil
