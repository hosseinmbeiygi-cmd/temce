#!/usr/bin/env python
"""
Data Import CLI — Thin wrapper around ``services.instrument_import_service``.

The FastAPI endpoint ``POST /api/v1/instruments/import`` and this script share the
exact same parsing & persistence logic, so behaviour stays consistent.

Usage:
    python scripts/import_data.py path/to/symbols.csv
    python scripts/import_data.py path/to/symbols.json
    python scripts/import_data.py path/to/symbols.xlsx

Common columns: symbol (required), name, isin, market_type, asset_class,
    sector_code, group_code, sub_group_code, tick_size, lot_size, par_value,
    eps, shares_count, base_volume, exchange_code, board_code.
"""
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path when invoked as ``python scripts/import_data.py``.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.database import close_database, get_session, init_database  # noqa: E402
from core.logging import get_logger  # noqa: E402
from services.instrument_import_service import InstrumentImportService  # noqa: E402

logger = get_logger(__name__)


async def _run(file_path: Path) -> int:
    await init_database()

    async for session in get_session():
        from repositories.instrument_repository import InstrumentRepository

        service = InstrumentImportService(repo=InstrumentRepository(session=session))
        content = file_path.read_bytes()
        result = await service.import_from_bytes(file_path.name, content)

    await close_database()

    if not result.success:
        logger.error("Import failed: %s", result.error)
        return 1

    summary = result.value
    logger.info("=" * 50)
    logger.info("  Import Summary")
    logger.info("=" * 50)
    logger.info("  File:                %s", file_path.name)
    logger.info("  Total rows:          %d", summary.total_rows)
    logger.info("  Parse errors:        %d", len(summary.parse_errors))
    logger.info("  Successfully saved:  %d", summary.imported)
    logger.info("  Import errors:       %d", len(summary.import_errors))
    logger.info("=" * 50)

    if summary.parse_errors:
        logger.warning("First parse errors:")
        for err in summary.parse_errors[:5]:
            logger.warning("  - %s", err)
    if summary.import_errors:
        logger.warning("First import errors:")
        for err in summary.import_errors[:5]:
            logger.warning("  - %s", err)

    return 0 if summary.imported else 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import symbol data (CSV / JSON / Excel) into the database.",
    )
    parser.add_argument("path", type=Path, help="Path to a .csv / .json / .xlsx file")
    args = parser.parse_args()

    if not args.path.exists():
        logger.error("File not found: %s", args.path)
        sys.exit(1)

    sys.exit(asyncio.run(_run(args.path)))


if __name__ == "__main__":
    main()
