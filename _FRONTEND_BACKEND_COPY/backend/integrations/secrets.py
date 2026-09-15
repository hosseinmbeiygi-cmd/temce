from __future__ import annotations

import os

from core.logging import get_logger

logger = get_logger(__name__)


class SecretsManager:
    def get(self, key: str, default: str | None = None) -> str | None:
        return os.environ.get(key, default)

    def get_required(self, key: str) -> str:
        value = os.environ.get(key)
        if value is None:
            logger.debug("Required secret not found: %s", key)
            raise ValueError("Required secret not found")
        return value
