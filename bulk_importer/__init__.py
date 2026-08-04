"""Codal Excel Bulk Importer — idempotent, batch, auditable.

Usage:
    python -m bulk_importer.cli import          # Run import
    python -m bulk_importer.cli import --dry-run # Parse only
    python -m bulk_importer.cli stats           # Show statistics
    python -m bulk_importer.cli retry           # Retry failed files
    python -m bulk_importer.cli reset           # Reset all statuses
"""

from bulk_importer.config import FileStatus
from bulk_importer.detector import detect_format, parse_filename_metadata
from bulk_importer.orchestrator import Orchestrator
from bulk_importer.persistence import Persistence
from bulk_importer.scanner import ScannedFile, scan_directory

__all__ = [
    "FileStatus",
    "detect_format",
    "parse_filename_metadata",
    "scan_directory",
    "ScannedFile",
    "Orchestrator",
    "Persistence",
]
