from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class ArchiveManager:
    def __init__(self, archive_dir: str | None = None) -> None:
        self.archive_dir = Path(archive_dir or settings.data_dir / "archives")
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def create_zip(self, source_paths: list[Path], archive_name: str, compress: bool = True) -> Path:
        archive_path = self.archive_dir / f"{archive_name}.zip"
        compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
        with zipfile.ZipFile(archive_path, "w", compression) as zf:
            for src in source_paths:
                if src.exists():
                    zf.write(src, src.name)
        logger.info("Created zip archive: %s", archive_path)
        return archive_path

    def create_tar_gz(self, source_dir: Path, archive_name: str) -> Path:
        archive_path = self.archive_dir / f"{archive_name}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(source_dir, arcname=source_dir.name)
        logger.info("Created tar.gz archive: %s", archive_path)
        return archive_path

    def extract_zip(self, archive_path: Path, extract_dir: Path) -> Path:
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_dir)
        logger.info("Extracted %s to %s", archive_path, extract_dir)
        return extract_dir

    def extract_tar_gz(self, archive_path: Path, extract_dir: Path) -> Path:
        extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)
        logger.info("Extracted %s to %s", archive_path, extract_dir)
        return extract_dir

    def list_archives(self) -> list[Path]:
        return list(self.archive_dir.glob("*.zip")) + list(self.archive_dir.glob("*.tar.gz"))

    def delete_archive(self, archive_name: str) -> bool:
        for ext in (".zip", ".tar.gz"):
            p = self.archive_dir / f"{archive_name}{ext}"
            if p.exists():
                p.unlink()
                logger.info("Deleted archive: %s", p)
                return True
        return False

    @property
    def total_size_bytes(self) -> int:
        return sum(f.stat().st_size for f in self.list_archives())
