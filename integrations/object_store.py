from __future__ import annotations

from pathlib import Path

from core.logging import get_logger
from core.paths import safe_resolve

logger = get_logger(__name__)


class ObjectStore:
    def __init__(self, base_path: str = "./data/objects") -> None:
        self.base_path = str(Path(base_path).resolve())

    async def upload(self, key: str, data: bytes) -> str:
        path = safe_resolve(self.base_path, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("Uploaded object: %s", key)
        return str(path)

    async def download(self, key: str) -> bytes:
        path = safe_resolve(self.base_path, key)
        if not path.exists():
            logger.debug("Object not found: %s", key)
            raise FileNotFoundError("Object not found")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = safe_resolve(self.base_path, key)
        if path.exists():
            path.unlink()
            logger.info("Deleted object: %s", key)
