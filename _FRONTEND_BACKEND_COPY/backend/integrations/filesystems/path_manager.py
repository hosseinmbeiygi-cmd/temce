from __future__ import annotations

from datetime import date
from pathlib import Path


class PathManager:
    def __init__(self, base_dir: str | Path, use_date_prefix: bool = True):
        self._base = Path(base_dir).resolve()
        self._use_date_prefix = use_date_prefix

    def resolve(self, relative: str, ref_date: date | None = None) -> Path:
        from core.paths import safe_resolve

        parts = []
        if self._use_date_prefix:
            d = ref_date or date.today()
            parts = [str(d.year), f"{d.month:02d}", f"{d.day:02d}"]
        parts.append(relative)
        return safe_resolve(self._base, "/".join(parts))

    def quote_path(self, instrument_id: str, timeframe: str = "1d", ref_date: date | None = None) -> Path:
        return self.resolve(f"quotes/{instrument_id}/{timeframe}", ref_date)

    def signal_path(self, instrument_id: str, ref_date: date | None = None) -> Path:
        return self.resolve(f"signals/{instrument_id}", ref_date)

    def recommendation_path(self, instrument_id: str, ref_date: date | None = None) -> Path:
        return self.resolve(f"recommendations/{instrument_id}", ref_date)

    def report_path(self, report_type: str, name: str, fmt: str = "csv") -> Path:
        return self._base / "reports" / report_type / f"{name}.{fmt}"

    def export_path(self, export_type: str, filename: str) -> Path:
        return self._base / "exports" / export_type / filename

    def backup_path(self, name: str, ref_date: date | None = None) -> Path:
        d = ref_date or date.today()
        return self._base / "backups" / f"{d.isoformat()}" / name

    def temp_path(self, suffix: str = ".tmp") -> Path:
        import uuid

        return self._base / "tmp" / f"{uuid.uuid4().hex}{suffix}"

    def log_path(self, logger_name: str, ref_date: date | None = None) -> Path:
        d = ref_date or date.today()
        return self._base / "logs" / f"{d.isoformat()}" / f"{logger_name}.log"

    def model_path(self, model_name: str, version: str = "") -> Path:
        if version:
            return self._base / "models" / model_name / version
        return self._base / "models" / model_name

    def ensure_dir(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_to_base(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._base))
        except ValueError:
            return str(path)

    @property
    def base(self) -> Path:
        return self._base
