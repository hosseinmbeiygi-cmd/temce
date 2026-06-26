#!/usr/bin/env python
"""
Bulk Daily Quote Import CLI

Import hundreds of CSV files (one per symbol) into the database in one command.
Each CSV file name becomes the trading symbol, and the file content should have
Persian column headers (تاریخ, باز, بالا, پایین, بسته, حجم, ارزش, …).

Usage:
    # Import all CSV files from a directory:
    python scripts/import_quotes.py path/to/daily/files/

    # Dry-run (parse only, don't save):
    python scripts/import_quotes.py path/to/files/ --dry-run

    # Only import specific symbols (by file name without .csv):
    python scripts/import_quotes.py path/to/files/ --only فولاد فملی وبانک

    # Custom data source tag (default: csv_import):
    python scripts/import_quotes.py path/to/files/ --source tsetmc

Directory structure example:
    daily/2024-12-15/
        فولاد.csv
        فملی.csv
        وبانک.csv
        …
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.database import close_database, get_session, init_database
from core.logging import get_logger
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.quote_import_service import QuoteImportService

logger = get_logger(__name__)


def _print_summary(summary: object, elapsed: float, dry_run: bool) -> None:
    """Print a tidy result table."""
    tag = " [DRY-RUN — no data was saved]" if dry_run else ""

    print()
    print("=" * 60)
    print(f"  📊  QUOTE IMPORT SUMMARY{tag}")
    print("=" * 60)
    print(f"  Time:       {elapsed:.1f}s")
    print(f"  Files:      {summary.total_files}")
    print(f"  Rows:       {summary.total_rows}")
    if not dry_run:
        print(f"  Imported:   {summary.imported} (new)")
        print(f"  Updated:    {summary.updated}")
    print(f"  Skipped:    {summary.skipped}")
    print(f"  Errors:     {len(summary.errors)}")
    print(f"  Success:    {summary.success_rate:.0f}%")
    print("=" * 60)

    if summary.errors:
        print("\n  ❌ Errors (showing first 10):")
        for err in summary.errors[:10]:
            print(f"    • {err}")
        if len(summary.errors) > 10:
            print(f"    … and {len(summary.errors) - 10} more")

    if summary.per_file:
        print(f"\n  {'File':<30} {'Rows':>5} {'New':>5} {'Upd':>5} {'Err':>4}")
        print("  " + "-" * 55)
        for fname, info in sorted(summary.per_file.items()):
            err_count = len(info.get("errors", []))
            print(
                f"  {fname:<30} {info['rows']:>5} "
                f"{info['imported']:>5} {info['updated']:>5} {err_count:>4}"
            )

    print()


async def _run(
    directory: Path,
    *,
    only_symbols: list[str] | None = None,
    data_source: str = "csv_import",
    dry_run: bool = False,
    max_concurrent: int = 20,
) -> int:
    await init_database()

    error_count = 0

    async for session in get_session():
        quote_repo = QuoteRepository(session=session)
        instrument_repo = InstrumentRepository(session=session)
        service = QuoteImportService(quote_repo=quote_repo, instrument_repo=instrument_repo)

        start = time.monotonic()

        if dry_run:
            # Dry-run: parse files using the same service parser, but don't save
            csv_files = sorted(directory.glob("*.csv"))
            if only_symbols:
                csv_files = [f for f in csv_files if f.stem in only_symbols]

            from services.quote_import_service import parse_persian_csv

            total_rows = 0
            total_files = len(csv_files)
            errors: list[str] = []
            per_file: dict[str, dict] = {}

            for f in csv_files:
                try:
                    content = f.read_bytes()
                    rows = parse_persian_csv(content, f.name)
                    per_file[f.name] = {"rows": len(rows)}
                    total_rows += len(rows)
                except Exception as exc:
                    per_file[f.name] = {"rows": 0}
                    errors.append(f"{f.name}: {exc}")

            elapsed = time.monotonic() - start
            _print_summary(
                type("DrySummary", (), {
                    "total_files": total_files,
                    "total_rows": total_rows,
                    "imported": 0,
                    "updated": 0,
                    "skipped": 0,
                    "errors": errors,
                    "per_file": per_file,
                    "success_rate": property(lambda self: 100.0 if not errors else (total_rows / max(1, total_rows + len(errors)) * 100)),
                })(),
                elapsed, dry_run=True,
            )
        else:
            summary = await service.import_directory(
                directory,
                data_source=data_source,
                max_concurrent=max_concurrent,
            )

            elapsed = time.monotonic() - start
            _print_summary(summary, elapsed, dry_run=False)
            error_count = len(summary.errors)

    await close_database()
    return 1 if error_count > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-import daily quote CSV files (one file per symbol).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("directory", type=Path, help="Directory containing .csv files (one per symbol)")
    parser.add_argument("--dry-run", action="store_true", help="Parse files but don't save to DB")
    parser.add_argument("--source", default="csv_import", help="Data source tag (default: csv_import)")
    parser.add_argument("--only", nargs="*", help="Only process these symbols (file names without .csv)")
    parser.add_argument("--max-concurrent", type=int, default=20, help="Max concurrent file imports (default: 20)")
    args = parser.parse_args()

    if not args.directory.is_dir():
        logger.error("Directory not found: %s", args.directory)
        sys.exit(1)

    sys.exit(asyncio.run(_run(
        args.directory,
        only_symbols=args.only,
        data_source=args.source,
        dry_run=args.dry_run,
        max_concurrent=args.max_concurrent,
    )))


if __name__ == "__main__":
    main()
