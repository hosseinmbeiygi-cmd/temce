#!/usr/bin/env python
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import os
from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def bootstrap() -> None:
    dirs = [
        settings.data_dir,
        settings.ml_model_dir,
        os.path.join(settings.data_dir, "raw"),
        os.path.join(settings.data_dir, "processed"),
        os.path.join(settings.data_dir, "archives"),
        os.path.join(settings.data_dir, "exports"),
        os.path.join(settings.data_dir, "temp"),
        os.path.join(settings.data_dir, "models"),
        os.path.join(settings.data_dir, "backups"),
        os.path.join(settings.data_dir, "manifests"),
        os.path.join(settings.data_dir, "snapshots"),
        os.path.join(settings.data_dir, "logs"),
    ]

    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        logger.info("Created directory: %s", d)

    env_file = Path(".env")
    if not env_file.exists():
        env_example = Path(".env.example")
        if env_example.exists():
            env_file.write_text(env_example.read_text())
            logger.info("Created .env from .env.example")
        else:
            logger.warning("No .env.example found. Manual configuration required.")

    logger.info("Bootstrap complete.")


if __name__ == "__main__":
    bootstrap()
