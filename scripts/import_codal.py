#!/usr/bin/env python
"""
Bulk Codal Disclosure Import CLI

Import codal (کدال) disclosure Excel/CSV files into the database.
Each file name becomes the default trading symbol.

Usage:
    # Import all XLSX files from a directory:
    python scripts/import_codal.py path/to/codal/files/

    # Include CSV files too:
    python scripts/import_codal.py path/to/files/ --include-csv

    # Dry-run (parse only, don't save):
    python scripts/import_codal.py path/to/files/ --dry-run

    # Only import specific symbols:
    python scripts/import_codal.py path/to/files/ --only فولاد فملی

    # Custom data source tag:
    python scripts/import_codal.py path/to/files/ --source manual_codal

Excel structure (Persian columns):
    نماد | نوع گزارش | سال مالی | دوره | تاریخ انتشار | خلاصه | لینک
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
from repositories.codal_repository import CodalRepository
from repositories.instrument_repository import InstrumentRepository
from services.codal_import_service import CodalImportService

logger = get_logger(__name__)


def _print_summary(summary: object, elapsed: float, dry_run: bool) -> None:
    tag = " [DRY-RUN — no data was saved]" if dry_run else ""
    print()
    print("=" * 60)
    print(f"  📋  CODAL IMPORT SUMMARY{tag}")
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
        print(f"\n  {'File':<35} {'Rows':>5} {'New':>5} {'Upd':>5} {'Err':>4}")
        print("  " + "-" * 58)
        for fname, info in sorted(summary.per_file.items()):
            err_count = len(info.get("errors", []))
            print(
                f"  {fname:<35} {info['rows']:>5} "
                f"{info['imported']:>5} {info['updated']:>5} {err_count:>4}"
            )
    print()


async def _run(
    directory: Path,
    *,
    only_symbols: list[str] | None = None,
    data_source: str = "manual_import",
    dry_run: bool = False,
    max_concurrent: int = 10,
) -> int:
    await init_database()

    error_count = 0

    async for session in get_session():
        codal_repo = CodalRepository(session=session)
        instrument_repo = InstrumentRepository(session=session)
        service = CodalImportService(codal_repo=codal_repo, instrument_repo=instrument_repo)

        start = time.monotonic()

        if dry_run:
            from services.codal_import_service import parse_csv, parse_xlsx

            xlsx_files = sorted(directory.glob("*.xlsx"))
            csv_files = sorted(directory.glob("*.csv"))
            all_files = xlsx_files + csv_files
            if only_symbols:
                all_files = [f for f in all_files if f.stem in only_symbols]

            total_rows = 0
            total_files = len(all_files)
            errors: list[str] = []
            per_file: dict[str, dict] = {}

            for fp in all_files:
                try:
                    content = fp.read_bytes()
                    if fp.name.lower().endswith(".xlsx"):
                        rows, _ = parse_xlsx(content)
                    else:
                        rows, _ = parse_csv(content)
                    per_file[fp.name] = {"rows": len(rows)}
                    total_rows += len(rows)
                except Exception as exc:
                    per_file[fp.name] = {"rows": 0}
                    errors.append(f"{fp.name}: {exc}")

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
                    "success_rate": property(lambda self: 100.0 if not errors else 50.0),
                })(),
                elapsed, dry_run=True,
            )
        else:
            summary = await service.import_directory(
                directory, data_source=data_source, max_concurrent=max_concurrent
            )
            elapsed = time.monotonic() - start
            _print_summary(summary, elapsed, dry_run=False)
            error_count = len(summary.errors)

    await close_database()
    return 1 if error_count > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-import Codal disclosure files (XLSX/CSV).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/import_codal.py ./codal_files/
  python scripts/import_codal.py ./codal_files/ --dry-run
  python scripts/import_codal.py ./codal_files/ --only فولاد شپنا
  """,
    )
    parser.add_argument("directory", type=Path, help="Directory containing .xlsx/.csv files")
    parser.add_argument("--dry-run", action="store_true", help="Parse files but don't save to DB")
    parser.add_argument("--source", default="manual_import", help="Data source tag")
    parser.add_argument("--only", nargs="*", help="Only process these symbols")
    parser.add_argument("--max-concurrent", type=int, default=10, help="Max concurrent imports")
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
