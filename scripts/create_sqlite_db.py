#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def create_database() -> None:
    db_url = settings.database_url
    logger.info("Creating SQLite database: %s", db_url)

    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        if db_file.exists():
            logger.info("Database already exists: %s", db_file)
        else:
            db_file.touch()
            logger.info("Created database file: %s", db_file)
    else:
        logger.info("Not a SQLite database URL: %s", db_url)


def run_migrations() -> None:
    logger.info("Running Alembic migrations...")
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrations applied successfully.")
    except ImportError:
        logger.warning("Alembic not installed. Skip migrations.")
    except Exception as e:
        logger.error("Migration failed: %s", e)


if __name__ == "__main__":
    create_database()
    if "--no-migrate" not in sys.argv:
        run_migrations()
