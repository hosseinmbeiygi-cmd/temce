from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


class ObjectStore:
    def __init__(self, base_path: str = "./data/objects") -> None:
        self.base_path = base_path

    async def upload(self, key: str, data: bytes) -> str:
        import os

        path = os.path.join(self.base_path, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        logger.info("Uploaded object: %s", key)
        return path

    async def download(self, key: str) -> bytes:
        import os

        path = os.path.join(self.base_path, key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Object not found: {key}")
        with open(path, "rb") as f:
            return f.read()

    async def delete(self, key: str) -> None:
        import os

        path = os.path.join(self.base_path, key)
        if os.path.exists(path):
            os.remove(path)
            logger.info("Deleted object: %s", key)
