from __future__ import annotations

from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class FileManager:
    def __init__(self, base_path: str | None = None) -> None:
        self.base_path = Path(base_path or settings.data_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        return self.base_path.joinpath(*parts)

    def ensure_dir(self, *parts: str) -> Path:
        p = self.path(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def exists(self, *parts: str) -> bool:
        return self.path(*parts).exists()

    def read_text(self, *parts: str) -> str:
        return self.path(*parts).read_text(encoding="utf-8")

    def write_text(self, content: str, *parts: str) -> None:
        p = self.path(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def list_files(self, pattern: str = "*") -> list[Path]:
        return list(self.base_path.glob(pattern))

    def delete(self, *parts: str) -> bool:
        p = self.path(*parts)
        if p.exists():
            p.unlink()
            return True
        return False

    @property
    def size_bytes(self) -> int:
        return sum(f.stat().st_size for f in self.base_path.rglob("*") if f.is_file())


file_manager = FileManager()
