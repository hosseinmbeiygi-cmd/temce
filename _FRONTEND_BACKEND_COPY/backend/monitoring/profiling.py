from __future__ import annotations

import time

from core.logging import get_logger

logger = get_logger(__name__)


class Profiler:
    def __init__(self) -> None:
        self._spans: dict[str, float] = {}

    def start(self, name: str) -> None:
        self._spans[name] = time.monotonic()

    def stop(self, name: str) -> float:
        start = self._spans.pop(name, None)
        if start is None:
            return 0.0
        elapsed = time.monotonic() - start
        logger.info("Profile [%s]: %.3fs", name, elapsed)
        return elapsed

    def snapshot(self) -> dict[str, float]:
        return dict(self._spans)
