from __future__ import annotations

import logging
import sys
from pathlib import Path

from core.config import settings
from core.logging import JsonFormatter


def setup_logging() -> None:
    fmt = settings.log_format
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        console.setFormatter(JsonFormatter())
    else:
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    handlers.append(console)

    if settings.log_file:
        path = Path(settings.log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        handlers.append(fh)

    logging.basicConfig(level=level, handlers=handlers, force=True)


def setup_root_logger() -> None:
    setup_logging()
