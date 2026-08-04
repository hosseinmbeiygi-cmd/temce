"""Codal Excel Bulk Importer — CLI entry point."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bulk_importer.config import CODEX_EXCEL_DIR, MAX_WORKERS
from bulk_importer.orchestrator import Orchestrator
from bulk_importer.persistence import Persistence


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_import(args):
    """Run the full import pipeline."""
    setup_logging(args.verbose)
    logger = logging.getLogger("bulk_importer.cli")

    scan_root = Path(args.dir) if args.dir else CODEX_EXCEL_DIR
    if not scan_root.exists():
        logger.error("Directory not found: %s", scan_root)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Codal Excel Bulk Importer")
    logger.info("=" * 60)
    logger.info("Source: %s", scan_root)
    logger.info("Workers: %d", args.workers)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("Resume: %s", args.resume)
    logger.info("")

    persistence = Persistence()
    orchestrator = Orchestrator(
        persistence=persistence,
        max_workers=args.workers,
        batch_size=args.batch,
    )

    stats = orchestrator.run(
        scan_root=scan_root,
        resume=args.resume,
        dry_run=args.dry_run,
    )

    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("IMPORT RESULTS")
    logger.info("=" * 60)
    summary = stats.summary()
    for key, val in summary.items():
        logger.info("  %-25s: %s", key, val)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info("\nResults saved to %s", args.output)

    return 0 if stats.failed == 0 else 1


def cmd_stats(args):
    """Show import statistics."""
    setup_logging(args.verbose)
    persistence = Persistence()
    session = persistence.SessionLocal()
    try:
        stats = persistence.get_stats(session)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    finally:
        session.close()


def cmd_retry_failed(args):
    """Retry all failed files."""
    setup_logging(args.verbose)
    logger = logging.getLogger("bulk_importer.cli")

    persistence = Persistence()
    session = persistence.SessionLocal()
    try:
        from sqlalchemy import update

        from bulk_importer.config import FileStatus
        from bulk_importer.models import DocumentFile

        # Reset failed files to pending
        result = session.execute(
            update(DocumentFile)
            .where(DocumentFile.file_status.in_([FileStatus.FAILED, FileStatus.UNSUPPORTED]))
            .values(file_status=FileStatus.SCANNED, error_message=None)
        )
        session.commit()
        logger.info("Reset %d failed files for retry", result.rowcount)
    finally:
        session.close()

    # Now run import
    return cmd_import(args)


def cmd_reset(args):
    """Reset all file statuses to pending."""
    setup_logging(args.verbose)
    logger = logging.getLogger("bulk_importer.cli")

    if not args.yes:
        confirm = input("Are you sure you want to reset ALL file statuses? (y/N): ")
        if confirm.lower() != "y":
            logger.info("Aborted.")
            return 0

    persistence = Persistence()
    session = persistence.SessionLocal()
    try:
        from sqlalchemy import update

        from bulk_importer.config import FileStatus
        from bulk_importer.models import DocumentFile

        result = session.execute(
            update(DocumentFile)
            .values(file_status=FileStatus.SCANNED, error_message=None)
        )
        session.commit()
        logger.info("Reset %d files to 'scanned' status", result.rowcount)
    finally:
        session.close()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Codal Excel Bulk Importer — parse 100k+ financial report files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ── import ──
    p_import = subparsers.add_parser("import", help="Run the full import pipeline")
    p_import.add_argument("-d", "--dir", type=str, default=None,
                          help="Directory to scan (default: config.CODEX_EXCEL_DIR)")
    p_import.add_argument("-w", "--workers", type=int, default=MAX_WORKERS,
                          help=f"Parallel workers (default: {MAX_WORKERS})")
    p_import.add_argument("-b", "--batch", type=int, default=500,
                          help="Batch size for commits (default: 500)")
    p_import.add_argument("--dry-run", action="store_true",
                          help="Parse only, don't persist to DB")
    p_import.add_argument("--no-resume", action="store_true",
                          help="Re-process all files (ignore existing)")
    p_import.add_argument("-o", "--output", type=str, default=None,
                          help="Save results JSON to file")
    p_import.add_argument("-v", "--verbose", action="store_true")
    p_import.set_defaults(func=cmd_import, resume=True)

    # Fix: --no-resume sets resume=False
    def _set_no_resume(args):
        args.resume = not args.no_resume
        return cmd_import(args)
    p_import.set_defaults(func=_set_no_resume)

    # ── stats ──
    p_stats = subparsers.add_parser("stats", help="Show import statistics")
    p_stats.add_argument("-v", "--verbose", action="store_true")
    p_stats.set_defaults(func=cmd_stats)

    # ── retry ──
    p_retry = subparsers.add_parser("retry", help="Retry failed files")
    p_retry.add_argument("-d", "--dir", type=str, default=None)
    p_retry.add_argument("-w", "--workers", type=int, default=MAX_WORKERS)
    p_retry.add_argument("-b", "--batch", type=int, default=500)
    p_retry.add_argument("-o", "--output", type=str, default=None)
    p_retry.add_argument("-v", "--verbose", action="store_true")
    p_retry.set_defaults(func=cmd_retry_failed, no_resume=False, resume=True)

    # ── reset ──
    p_reset = subparsers.add_parser("reset", help="Reset all file statuses")
    p_reset.add_argument("-y", "--yes", action="store_true",
                         help="Skip confirmation")
    p_reset.add_argument("-v", "--verbose", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    exit_code = args.func(args)
    sys.exit(exit_code or 0)


if __name__ == "__main__":
    main()
