from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class FileArchiveHealth:
    def __init__(self, archive_dir: Path) -> None:
        self.archive_dir = archive_dir

    async def check(self) -> dict[str, Any]:
        exists = self.archive_dir.exists()
        writable = os.access(str(self.archive_dir), os.W_OK) if exists else False
        files = (
            list(self.archive_dir.glob("*.csv"))
            + list(self.archive_dir.glob("*.json"))
            + list(self.archive_dir.glob("*.xlsx"))
        )
        return {
            "status": ProviderHealth.HEALTHY if exists else ProviderHealth.DOWN,
            "directory": str(self.archive_dir),
            "exists": exists,
            "file_count": len(files),
            "writable": writable,
        }
