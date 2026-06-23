from __future__ import annotations

import os
from pathlib import Path

from core.logging import get_logger
from core.paths import safe_resolve, validate_safe_path

logger = get_logger(__name__)


class FileShare:
    def __init__(self, base_path: str = "./data/fileshare") -> None:
        self.base_path = str(Path(base_path).resolve())

    def upload_file(self, local_path: str, remote_name: str) -> str:
        import shutil

        src = validate_safe_path(local_path)
        dest = safe_resolve(self.base_path, remote_name)
        os.makedirs(str(dest.parent), exist_ok=True)
        shutil.copy2(str(src), str(dest))
        logger.info("File uploaded: %s -> %s", local_path, dest)
        return str(dest)

    def download_file(self, remote_name: str, local_path: str) -> str:
        import shutil

        src = safe_resolve(self.base_path, remote_name)
        dest = validate_safe_path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))
        logger.info("File downloaded: %s -> %s", src, local_path)
        return str(dest)
