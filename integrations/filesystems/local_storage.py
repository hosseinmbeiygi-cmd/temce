from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class LocalStorage:
    def __init__(self, base_path: str | Path):
        self._base = Path(base_path).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    async def write(self, relative_path: str, data: bytes) -> Result[str]:
        full = self._resolve(relative_path)
        full.parent.mkdir(parents=True, exist_ok=True)
        try:
            full.write_bytes(data)
            return Result.ok(str(full))
        except OSError as e:
            return Result.fail(str(e))

    async def read(self, relative_path: str) -> Result[bytes]:
        full = self._resolve(relative_path)
        if not full.exists():
            return Result.fail(f"File not found: {relative_path}")
        try:
            return Result.ok(full.read_bytes())
        except OSError as e:
            return Result.fail(str(e))

    async def delete(self, relative_path: str) -> Result[bool]:
        full = self._resolve(relative_path)
        if not full.exists():
            return Result.fail(f"File not found: {relative_path}")
        try:
            full.unlink()
            return Result.ok(True)
        except OSError as e:
            return Result.fail(str(e))

    async def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).exists()

    async def list(self, subdir: str = "", pattern: str = "*") -> list[str]:
        from core.paths import safe_resolve
        target = safe_resolve(self._base, subdir) if subdir else self._base
        if not target.is_dir():
            return []
        return [str(p.relative_to(self._base)) for p in target.glob(pattern) if p.is_file()]

    async def move(self, src: str, dst: str) -> Result[str]:
        src_full = self._resolve(src)
        dst_full = self._resolve(dst)
        dst_full.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src_full), str(dst_full))
            return Result.ok(str(dst_full))
        except OSError as e:
            return Result.fail(str(e))

    async def copy(self, src: str, dst: str) -> Result[str]:
        src_full = self._resolve(src)
        dst_full = self._resolve(dst)
        dst_full.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(str(src_full), str(dst_full))
            return Result.ok(str(dst_full))
        except OSError as e:
            return Result.fail(str(e))

    async def size(self, relative_path: str) -> int:
        full = self._resolve(relative_path)
        return full.stat().st_size if full.exists() else 0

    def _resolve(self, relative_path: str) -> Path:
        from core.paths import safe_resolve
        return safe_resolve(self._base, relative_path)

    def iter_files(self, subdir: str = "", pattern: str = "**/*") -> AsyncIterator[str]:
        from core.paths import safe_resolve
        target = safe_resolve(self._base, subdir) if subdir else self._base
        for p in target.glob(pattern):
            if p.is_file():
                yield str(p.relative_to(self._base))

    @property
    def base_path(self) -> Path:
        return self._base
