from __future__ import annotations

import asyncio

from core.logging import get_logger
from apps.scheduler.app import SchedulerApp

logger = get_logger(__name__)


def main() -> None:
    """Entry point for the job scheduler service.

    Usage:
        python -m apps.scheduler

    Starts APScheduler with predefined jobs (sync_instruments,
    sync_quotes, sync_codal, sync_news) and runs forever.
    """
    app = SchedulerApp()
    try:
        asyncio.run(app.run_forever())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error("Scheduler failed: %s", e)
        raise


if __name__ == "__main__":
    main()
