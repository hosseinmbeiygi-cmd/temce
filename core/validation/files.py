from __future__ import annotations

from pathlib import Path


def validate_file_exists(path: str | Path) -> None:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not p.is_file():
        raise ValueError(f"Path is not a file: {path}")


def validate_directory_exists(path: str | Path) -> None:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not p.is_dir():
        raise ValueError(f"Path is not a directory: {path}")


def validate_file_extension(path: str | Path, allowed_extensions: list[str]) -> None:
    ext = Path(path).suffix.lower()
    if ext not in allowed_extensions:
        raise ValueError(f"File extension '{ext}' not allowed. Allowed: {allowed_extensions}")


def validate_file_size(path: str | Path, max_size_mb: float = 100) -> None:
    size_bytes = Path(path).stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File size {size_mb:.1f}MB exceeds maximum {max_size_mb}MB")


def validate_writable(path: str | Path) -> None:
    p = Path(path)
    if p.exists() and not p.is_file():
        raise ValueError(f"Path exists and is not a file: {path}")
    parent = p.parent
    if not parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {parent}")
    if not os.access(str(parent), os.W_OK):
        raise PermissionError(f"No write permission for directory: {parent}")


import os
