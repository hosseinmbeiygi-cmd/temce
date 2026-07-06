#!/usr/bin/env python
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import signal

from core.logging import get_logger

logger = get_logger(__name__)

shutdown_event = asyncio.Event()


def handle_signal(sig: int, frame: object | None = None) -> None:
    logger.info("Received signal %s, shutting down...", signal.Signals(sig).name)
    shutdown_event.set()


async def worker_loop(name: str, interval_seconds: int) -> None:
    logger.info("Worker '%s' started (interval=%ds)", name, interval_seconds)
    while not shutdown_event.is_set():
        logger.debug("Worker '%s' heartbeat", name)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


async def main() -> None:
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    workers = [
        worker_loop("market_data", 5),
        worker_loop("codal_sync", 60),
        worker_loop("news_sync", 120),
        worker_loop("indicator_compute", 300),
        worker_loop("ml_training", 3600),
    ]

    logger.info("Starting %d workers...", len(workers))
    await asyncio.gather(*workers, return_exceptions=True)
    logger.info("All workers stopped.")


if __name__ == "__main__":
    asyncio.run(main())
