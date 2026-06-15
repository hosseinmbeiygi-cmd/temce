#!/usr/bin/env python
from __future__ import annotations

import uvicorn

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("Starting API server on %s:%d", settings.server_host, settings.server_port)
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
        workers=settings.workers,
    )


if __name__ == "__main__":
    main()
