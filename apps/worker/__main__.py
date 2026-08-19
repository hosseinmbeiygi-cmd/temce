"""Entry point for the job queue worker service.

Usage:
    python -m apps.worker
"""

from __future__ import annotations

import asyncio

from apps.worker.app import WorkerApp
from core.logging import get_logger

logger = get_logger(__name__)


async def main() -> None:
    app = WorkerApp()
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:  # noqa: BLE001
        logger.exception("Worker failed: %s", e)
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
