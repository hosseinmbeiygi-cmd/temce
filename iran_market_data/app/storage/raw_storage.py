from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import ensure_dir, safe_ensure_dir
from core.time import now_tehran


class RawStorage:
    """Save raw collected data (JSON, HTML, files) to disk."""

    def __init__(self, base_dir: str = "data/raw") -> None:
        if Path(base_dir).is_absolute():
            self.base_dir = ensure_dir(base_dir)
        else:
            self.base_dir = safe_ensure_dir(Path.cwd(), base_dir)

    @property
    def timestamp(self) -> str:
        return now_tehran().strftime("%Y%m%d_%H%M%S")

    def save_json(self, source: str, name: str, data: Any) -> Path:
        folder = self.base_dir / "json" / source
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / f"{name}_{self.timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return file_path

    def save_html(self, source: str, name: str, html: str) -> Path:
        folder = self.base_dir / "html" / source
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / f"{name}_{self.timestamp}.html"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        return file_path

    def save_file(self, source: str, filename: str, content: bytes) -> Path:
        suffix = filename.split(".")[-1].lower()

        if suffix in ("xls", "xlsx", "csv"):
            folder_type = "excel"
        elif suffix == "pdf":
            folder_type = "pdf"
        else:
            folder_type = "files"

        folder = self.base_dir / folder_type / source
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / filename

        with open(file_path, "wb") as f:
            f.write(content)

        return file_path
