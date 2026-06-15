from __future__ import annotations

import os

from core.logging import get_logger

logger = get_logger(__name__)


class FileShare:
    def __init__(self, base_path: str = "./data/fileshare") -> None:
        self.base_path = base_path

    def upload_file(self, local_path: str, remote_name: str) -> str:
        import shutil

        dest = os.path.join(self.base_path, remote_name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(local_path, dest)
        logger.info("File uploaded: %s -> %s", local_path, dest)
        return dest

    def download_file(self, remote_name: str, local_path: str) -> str:
        src = os.path.join(self.base_path, remote_name)
        import shutil

        shutil.copy2(src, local_path)
        logger.info("File downloaded: %s -> %s", src, local_path)
        return local_path
