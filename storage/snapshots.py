from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import settings
from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


class SnapshotManager:
    def __init__(self, snapshot_dir: str | None = None) -> None:
        self.snapshot_dir = Path(snapshot_dir or settings.data_dir / "snapshots")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, name: str, files: list[Path], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        snapshot_id = new_id("snap")
        timestamp = datetime.now(UTC).isoformat()
        snapshot: dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "name": name,
            "created_at": timestamp,
            "file_count": len(files),
            "files": [],
            "metadata": metadata or {},
        }
        snap_dir = self.snapshot_dir / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.exists():
                dest = snap_dir / f.name
                shutil.copy2(f, dest)
                snapshot["files"].append({"name": f.name, "size_bytes": f.stat().st_size, "source": str(f)})
        manifest_path = snap_dir / "snapshot.json"
        manifest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Created snapshot: %s (%d files)", snapshot_id, len(files))
        return snapshot

    def list_snapshots(self) -> list[dict[str, Any]]:
        snapshots = []
        for d in self.snapshot_dir.iterdir():
            if d.is_dir():
                manifest = d / "snapshot.json"
                if manifest.exists():
                    snapshots.append(json.loads(manifest.read_text(encoding="utf-8")))
        return sorted(snapshots, key=lambda x: x["created_at"], reverse=True)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        manifest = self.snapshot_dir / snapshot_id / "snapshot.json"
        if not manifest.exists():
            return None
        return json.loads(manifest.read_text(encoding="utf-8"))

    def restore_snapshot(self, snapshot_id: str, target_dir: Path) -> int:
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            logger.error("Snapshot not found: %s", snapshot_id)
            return 0
        snap_dir = self.snapshot_dir / snapshot_id
        target_dir.mkdir(parents=True, exist_ok=True)
        restored = 0
        for f in snapshot["files"]:
            src = snap_dir / f["name"]
            if src.exists():
                shutil.copy2(src, target_dir / f["name"])
                restored += 1
        logger.info("Restored %d files from snapshot %s", restored, snapshot_id)
        return restored

    def delete_snapshot(self, snapshot_id: str) -> bool:
        snap_dir = self.snapshot_dir / snapshot_id
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
            logger.info("Deleted snapshot: %s", snapshot_id)
            return True
        return False

    def snapshot_summary(self) -> dict[str, Any]:
        snapshots = self.list_snapshots()
        total_size = 0
        for snap_dir in self.snapshot_dir.iterdir():
            if snap_dir.is_dir():
                total_size += sum(f.stat().st_size for f in snap_dir.rglob("*") if f.is_file())
        return {"total_snapshots": len(snapshots), "total_size_bytes": total_size}
