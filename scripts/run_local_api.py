#!/usr/bin/env python
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

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
