"""File fingerprinting service — SHA-256 and duplicate detection."""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_sha256(file_path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash, streaming in chunks to avoid loading entire file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
