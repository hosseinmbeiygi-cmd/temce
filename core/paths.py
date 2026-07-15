from __future__ import annotations

import re
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)

# Pattern to detect path traversal attempts
_PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.(?:/|\\|$)")


def sanitize_path_component(component: str) -> str:
    """Sanitize a single path component, removing dangerous characters."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", component)


def safe_resolve(base: Path | str, user_path: str) -> Path:
    """
    Safely resolve a user-supplied path against a base directory.
    
    Prevents path traversal attacks by:
    1. Resolving the full path
    2. Checking the resolved path starts with the resolved base directory
    
    Raises ValueError if path traversal is detected.
    """
    base_resolved = Path(base).resolve()
    full = (base_resolved / user_path).resolve()

    try:
        full.relative_to(base_resolved)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: '{user_path}' resolves outside '{base_resolved}'"
        )
    return full


def safe_ensure_dir(base: Path | str, subdir: str = "") -> Path:
    """Ensure a directory exists within a base path, preventing traversal."""
    base_resolved = Path(base).resolve()
    if subdir:
        target = base_resolved / subdir
        target = target.resolve()
        try:
            target.relative_to(base_resolved)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: '{subdir}' resolves outside '{base_resolved}'"
            )
    else:
        target = base_resolved
    target.mkdir(parents=True, exist_ok=True)
    return target


def validate_safe_path(path: str | Path) -> Path:
    """
    Validate that a path does not contain path traversal patterns.
    
    This is a lighter check for standalone path arguments (not relative to a base).
    """
    p = Path(path)
    resolved = p.resolve()
    if _PATH_TRAVERSAL_PATTERN.search(str(p)):
        raise ValueError(f"Path traversal detected in: '{path}'")
    return resolved


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_path(subdir: str = "") -> Path:
    from core.config import settings

    base = Path(settings.data_dir)
    return safe_ensure_dir(base, subdir) if subdir else ensure_dir(base)


def models_path(subdir: str = "") -> Path:
    from core.config import settings

    base = Path(settings.ml_model_dir)
    return safe_ensure_dir(base, subdir) if subdir else ensure_dir(base)


def logs_path() -> Path:
    return ensure_dir(data_path("logs"))


def reports_path() -> Path:
    return ensure_dir(data_path("reports"))


def temp_path() -> Path:
    return ensure_dir(data_path("tmp"))


def config_path() -> Path:
    return Path.cwd()
