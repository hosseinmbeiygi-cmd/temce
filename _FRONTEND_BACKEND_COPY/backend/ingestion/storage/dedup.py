from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class DeduplicationEngine:
    def __init__(self, redis_client: Any, window_minutes: int = 60) -> None:
        self._redis = redis_client
        self._window = timedelta(minutes=window_minutes)

    def _make_key(self, source: str, payload: bytes) -> str:
        content_hash = hashlib.sha256(payload).hexdigest()
        return f"dedup:{source}:{content_hash}"

    async def is_duplicate(self, source: str, payload: bytes) -> bool:
        key = self._make_key(source, payload)
        return bool(await self._redis.exists(key))

    async def mark_seen(self, source: str, payload: bytes) -> None:
        key = self._make_key(source, payload)
        await self._redis.setex(key, int(self._window.total_seconds()), "1")
