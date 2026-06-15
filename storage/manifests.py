from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import settings
from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


class ManifestManager:
    def __init__(self, manifest_dir: str | None = None) -> None:
        self.manifest_dir = Path(manifest_dir or settings.data_dir / "manifests")
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def create_manifest(
        self, dataset: str, files: list[Path], metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "manifest_id": new_id("mf"),
            "dataset": dataset,
            "created_at": datetime.now(UTC).isoformat(),
            "file_count": len(files),
            "files": [
                {
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=UTC).isoformat(),
                }
                for f in files
                if f.exists()
            ],
            "metadata": metadata or {},
        }
        path = self.manifest_dir / f"{manifest['manifest_id']}.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Created manifest: %s", path)
        return manifest

    def get_manifest(self, manifest_id: str) -> dict[str, Any] | None:
        path = self.manifest_dir / f"{manifest_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_manifests(self, dataset: str | None = None) -> list[dict[str, Any]]:
        results = []
        for p in self.manifest_dir.glob("*.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            if dataset is None or data.get("dataset") == dataset:
                results.append(data)
        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    def delete_manifest(self, manifest_id: str) -> bool:
        path = self.manifest_dir / f"{manifest_id}.json"
        if path.exists():
            path.unlink()
            logger.info("Deleted manifest: %s", manifest_id)
            return True
        return False

    def update_metadata(self, manifest_id: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
        manifest = self.get_manifest(manifest_id)
        if manifest is None:
            return None
        manifest["metadata"].update(metadata)
        manifest["updated_at"] = datetime.now(UTC).isoformat()
        path = self.manifest_dir / f"{manifest_id}.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
