"""Orchestrator — main pipeline: scan → detect → parse → validate → persist."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from bulk_importer.adapters.base import ParseResult
from bulk_importer.config import COMMIT_EVERY, MAX_WORKERS, FileStatus
from bulk_importer.detector import detect_format
from bulk_importer.dispatcher import dispatch
from bulk_importer.models import DocumentFile
from bulk_importer.normalizer import detect_logical_sections, normalize_tables
from bulk_importer.persistence import Persistence
from bulk_importer.scanner import ScannedFile, scan_directory
from bulk_importer.validator import validate_parse_result

logger = logging.getLogger(__name__)


@dataclass
class ImportStats:
    """Running statistics for an import batch."""
    total: int = 0
    scanned: int = 0
    skipped_existing: int = 0
    parsed_ok: int = 0
    parsed_partial: int = 0
    parse_failed: int = 0
    validation_failed: int = 0
    saved: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def processed(self) -> int:
        return self.parsed_ok + self.parsed_partial + self.parse_failed + self.failed

    def summary(self) -> dict:
        return {
            "total": self.total,
            "scanned": self.scanned,
            "skipped_existing": self.skipped_existing,
            "parsed_ok": self.parsed_ok,
            "parsed_partial": self.parsed_partial,
            "parse_failed": self.parse_failed,
            "validation_failed": self.validation_failed,
            "saved": self.saved,
            "failed": self.failed,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "files_per_second": round(self.scanned / max(self.elapsed_seconds, 0.01), 1),
        }


def _process_file_worker(file_path: str) -> dict:
    """Worker function for parallel file processing (must be top-level for pickle)."""
    try:
        fmt = detect_format(file_path)
        if fmt == "unknown":
            return {"path": file_path, "format": "unknown", "result": None, "error": "unsupported format"}

        result = dispatch(file_path, fmt)

        # Normalize
        result.tables = normalize_tables(result.tables)
        result.tables = detect_logical_sections(result.tables)

        return {
            "path": file_path,
            "format": fmt,
            "result": result,
            "error": None,
        }
    except Exception as e:
        return {"path": file_path, "format": None, "result": None, "error": str(e)}


class Orchestrator:
    """Main import orchestrator — coordinates the full pipeline."""

    def __init__(
        self,
        persistence: Persistence | None = None,
        max_workers: int = MAX_WORKERS,
        batch_size: int = COMMIT_EVERY,
    ):
        self.persistence = persistence or Persistence()
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.batch_id = uuid.uuid4().hex[:12]

    def run(
        self,
        scan_root: str | Path | None = None,
        resume: bool = True,
        dry_run: bool = False,
    ) -> ImportStats:
        """Run the full import pipeline.

        Args:
            scan_root: Directory to scan (default: codal_excel_files)
            resume: Skip files already scanned/parsed (idempotent)
            dry_run: Parse but don't persist to DB
        """
        stats = ImportStats()
        start_time = time.time()

        # Ensure tables exist
        if not dry_run:
            self.persistence.create_tables()
            self.persistence.ensure_indexes()

        # ── Phase 1: Discovery ──
        logger.info("Phase 1: Scanning files in %s ...", scan_root or "default")
        scanned_files = scan_directory(scan_root)
        stats.scanned = len(scanned_files)
        stats.total = len(scanned_files)
        logger.info("Found %d files", len(scanned_files))

        if not scanned_files:
            stats.elapsed_seconds = time.time() - start_time
            return stats

        # ── Phase 2: Register + Dedup ──
        if not dry_run:
            logger.info("Phase 2: Registering files and deduplication...")
            files_to_process = self._register_files(scanned_files, stats)
        else:
            files_to_process = scanned_files

        logger.info(
            "To process: %d files (skipped %d existing)",
            len(files_to_process), stats.skipped_existing,
        )

        # ── Phase 3: Parse (parallel) ──
        logger.info("Phase 3: Parsing %d files with %d workers...", len(files_to_process), self.max_workers)
        file_paths = [f.file_path for f in files_to_process]
        results_map: dict[str, dict] = {}

        if self.max_workers <= 1 or len(file_paths) < 10:
            for fp in file_paths:
                results_map[fp] = _process_file_worker(fp)
                if len(results_map) % 1000 == 0:
                    logger.info("  Parsed %d / %d files...", len(results_map), len(file_paths))
        else:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(_process_file_worker, fp): fp
                    for fp in file_paths
                }
                for i, future in enumerate(as_completed(futures)):
                    fp = futures[future]
                    try:
                        results_map[fp] = future.result(timeout=120)
                    except Exception as e:
                        results_map[fp] = {"path": fp, "format": None, "result": None, "error": str(e)}

                    if (i + 1) % 1000 == 0:
                        logger.info("  Parsed %d / %d files...", i + 1, len(file_paths))

        logger.info("Phase 3 done: %d results collected", len(results_map))

        # ── Phase 4: Validate + Persist ──
        logger.info("Phase 4: Validating and persisting...")
        if not dry_run:
            self._validate_and_persist(results_map, stats)
        else:
            self._validate_only(results_map, stats)

        stats.elapsed_seconds = time.time() - start_time
        logger.info("Import complete: %s", stats.summary())
        return stats

    def _register_files(
        self,
        scanned_files: list[ScannedFile],
        stats: ImportStats,
    ) -> list[ScannedFile]:
        """Register scanned files in DB, skip duplicates by file_path."""
        session = self.persistence.SessionLocal()
        files_to_process: list[ScannedFile] = []

        try:
            from sqlalchemy import select
            existing_paths = set(
                session.execute(
                    select(DocumentFile.file_path).where(
                        DocumentFile.file_status.in_([FileStatus.SAVED, FileStatus.PARSED])
                    )
                ).scalars().all()
            )

            for sf in scanned_files:
                if sf.file_path in existing_paths:
                    stats.skipped_existing += 1
                    continue

                doc = self.persistence.get_or_create_document_file(
                    session,
                    file_path=sf.file_path,
                    file_name=sf.file_name,
                    file_size=sf.file_size_bytes,
                    sha256=sf.sha256,
                    issuer_symbol=sf.issuer_symbol,
                    report_type=sf.report_type,
                    report_date_jalali=sf.report_date_jalali,
                    detected_format=None,
                )

                if doc.file_status in (FileStatus.SAVED, FileStatus.PARSED):
                    stats.skipped_existing += 1
                    continue

                files_to_process.append(sf)

                if len(files_to_process) % self.batch_size == 0:
                    session.commit()
                    logger.info("  Registered %d files so far...", len(files_to_process))

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return files_to_process

    def _validate_and_persist(
        self,
        results_map: dict[str, dict],
        stats: ImportStats,
    ):
        """Validate results and persist to DB in batches."""
        from sqlalchemy import select

        session = self.persistence.SessionLocal()
        batch_count = 0

        try:
            # Classify results
            error_paths: list[tuple[str, str]] = []
            unsupported_paths: list[str] = []
            valid_results: dict[str, dict] = {}

            for file_path, res in results_map.items():
                error = res.get("error")
                result: ParseResult | None = res.get("result")
                fmt = res.get("format", "unknown")

                if error:
                    stats.failed += 1
                    if len(stats.errors) < 200:
                        stats.errors.append(f"{file_path}: {error}")
                    error_paths.append((file_path, error))
                    continue

                if result is None or result.status == "unsupported" or fmt == "unknown":
                    stats.parse_failed += 1
                    unsupported_paths.append(file_path)
                    continue

                vr = validate_parse_result(result)
                if not vr.is_valid:
                    stats.validation_failed += 1
                    if len(stats.errors) < 200:
                        stats.errors.append(f"{file_path}: {vr.errors}")
                    error_paths.append((file_path, "; ".join(vr.errors)))
                    continue

                valid_results[file_path] = res

            logger.info("  Classification: %d errors, %d unsupported, %d valid",
                         len(error_paths), len(unsupported_paths), len(valid_results))

            # Batch update error/unsupported statuses (single query each)
            if error_paths:
                from sqlalchemy import update
                paths = [p for p, _ in error_paths]
                session.execute(
                    update(DocumentFile)
                    .where(DocumentFile.file_path.in_(paths))
                    .values(file_status=FileStatus.FAILED)
                )
            if unsupported_paths:
                from sqlalchemy import update
                session.execute(
                    update(DocumentFile)
                    .where(DocumentFile.file_path.in_(unsupported_paths))
                    .values(file_status=FileStatus.UNSUPPORTED)
                )
            session.commit()

            # Load all DocumentFile records for valid results in one query
            all_paths = list(valid_results.keys())
            if not all_paths:
                return

            # Load in chunks to avoid memory issues with very large IN clauses
            doc_map: dict[str, DocumentFile] = {}
            chunk_size = 5000
            for i in range(0, len(all_paths), chunk_size):
                chunk = all_paths[i:i + chunk_size]
                docs = session.execute(
                    select(DocumentFile).where(DocumentFile.file_path.in_(chunk))
                ).scalars().all()
                doc_map.update({doc.file_path: doc for doc in docs})

            logger.info("  Loaded %d DocumentFile records from DB", len(doc_map))

            # Save valid results
            for file_path, res in valid_results.items():
                doc = doc_map.get(file_path)
                if doc is None:
                    stats.failed += 1
                    continue

                result: ParseResult = res["result"]

                try:
                    with session.no_autoflush:
                        self.persistence.save_parse_result(session, doc, result)
                    doc.file_status = FileStatus.SAVED
                    stats.saved += 1
                    if result.errors:
                        stats.parsed_partial += 1
                    else:
                        stats.parsed_ok += 1
                except Exception as e:
                    session.rollback()
                    doc.file_status = FileStatus.FAILED
                    doc.error_message = str(e)
                    stats.failed += 1
                    if len(stats.errors) < 200:
                        stats.errors.append(f"{file_path}: save failed: {e}")

                batch_count += 1
                if batch_count % self.batch_size == 0:
                    try:
                        session.commit()
                        logger.info("  Persisted %d / %d (saved=%d, failed=%d)...",
                                    batch_count, len(valid_results), stats.saved, stats.failed)
                    except Exception as e:
                        session.rollback()
                        logger.warning("Batch commit failed at %d: %s", batch_count, e)

            session.commit()
            logger.info("  Final persist: saved=%d, failed=%d", stats.saved, stats.failed)

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _validate_only(
        self,
        results_map: dict[str, dict],
        stats: ImportStats,
    ):
        """Validate results without persisting (dry run)."""
        for _file_path, res in results_map.items():
            error = res.get("error")
            result: ParseResult | None = res.get("result")

            if error:
                stats.failed += 1
            elif result is None or result.status == "unsupported":
                stats.parse_failed += 1
            else:
                vr = validate_parse_result(result)
                if vr.is_valid:
                    stats.parsed_ok += 1
                else:
                    stats.validation_failed += 1
