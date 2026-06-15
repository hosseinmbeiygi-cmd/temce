from __future__ import annotations

from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_path(subdir: str = "") -> Path:
    from core.config import settings

    base = Path(settings.data_dir)
    return ensure_dir(base / subdir) if subdir else ensure_dir(base)


def models_path(subdir: str = "") -> Path:
    from core.config import settings

    base = Path(settings.ml_model_dir)
    return ensure_dir(base / subdir) if subdir else ensure_dir(base)


def logs_path() -> Path:
    return ensure_dir(data_path("logs"))


def reports_path() -> Path:
    return ensure_dir(data_path("reports"))


def temp_path() -> Path:
    return ensure_dir(data_path("tmp"))


def config_path() -> Path:
    return Path.cwd()
