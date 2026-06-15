#!/usr/bin/env python
from __future__ import annotations

import sys

from core.logging import get_logger
from storage.retention import RetentionPolicy

logger = get_logger(__name__)


def cleanup(dry_run: bool = True) -> None:
    policy = RetentionPolicy()
    if dry_run:
        logger.info("DRY RUN - no files will be deleted")
        sizes = policy.size_by_category()
        for cat, size in sizes.items():
            logger.info("  %s: %.2f MB", cat, size / (1024 * 1024))
        return

    results = policy.clean_all()
    for cat, count in results.items():
        logger.info("Cleaned %d items from %s", count, cat)

    sizes = policy.size_by_category()
    for cat, size in sizes.items():
        logger.info("  %s after cleanup: %.2f MB", cat, size / (1024 * 1024))


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    cleanup(dry_run=dry_run)
