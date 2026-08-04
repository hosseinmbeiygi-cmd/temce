"""FileScanner — discover all files in the codal Excel directory."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from bulk_importer.config import CODEX_EXCEL_DIR, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

EXTENSIONS = frozenset({".xlsx", ".xls", ".html", ".htm", ".csv"})


@dataclass
class ScannedFile:
    """Metadata for one discovered file."""
    file_path: str
    file_name: str
    file_size_bytes: int
    sha256: str
    issuer_symbol: str | None
    report_type: str | None
    report_date_jalali: str | None


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash of a file, streaming in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def scan_directory(
    root: str | Path | None = None,
    max_size_mb: int = MAX_FILE_SIZE_MB,
    fast: bool = True,
) -> list[ScannedFile]:
    """Recursively scan directory for codal Excel/HTML files.

    Args:
        fast: If True, use path+size as dedup key (skip SHA-256).
              SHA-256 computed later during parse for idempotency.
    """
    from bulk_importer.detector import parse_filename_metadata

    root = Path(root or CODEX_EXCEL_DIR)
    if not root.exists():
        logger.warning("Scan directory does not exist: %s", root)
        return []

    max_bytes = max_size_mb * 1024 * 1024
    results: list[ScannedFile] = []
    skipped = 0

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            fpath = Path(dirpath) / fname

            if fpath.suffix.lower() not in EXTENSIONS:
                continue

            try:
                size = fpath.stat().st_size
            except OSError:
                continue

            if size > max_bytes or size == 0:
                skipped += 1
                continue

            # Fast mode: use path+size as provisional key
            if fast:
                file_hash = f"fast:{fpath}:{size}"
            else:
                try:
                    file_hash = sha256_file(fpath)
                except OSError:
                    continue

            meta = parse_filename_metadata(fpath)

            results.append(ScannedFile(
                file_path=str(fpath),
                file_name=fname,
                file_size_bytes=size,
                sha256=file_hash,
                issuer_symbol=meta.get("issuer_symbol"),
                report_type=meta.get("report_type"),
                report_date_jalali=meta.get("report_date_jalali"),
            ))

    logger.info("Scanned %d files (skipped %d oversized/empty)", len(results), skipped)
    return results
