"""Data Versioning — tracks data lineage and versions for reproducibility.

Every backtest must know exactly which data it used. This module:
- Registers data versions with content hashes
- Tracks data source and transformation history
- Validates data integrity before backtesting
- Provides Data Manifest for each run
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DataVersion:
    """A specific version of a dataset."""
    version_id: str = ""
    name: str = ""
    description: str = ""
    source: str = ""                    # e.g., "brsapi", "tsetmc", "codal"
    format: str = "parquet"             # parquet, csv, json
    created_at: str = ""
    row_count: int = 0
    date_start: str = ""
    date_end: str = ""
    symbols_count: int = 0
    content_hash: str = ""              # hash of actual data content
    schema_version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataManifest:
    """Complete data provenance for a backtest run."""
    data_version: str = ""
    data_hash: str = ""
    source: str = ""
    row_count: int = 0
    date_start: str = ""
    date_end: str = ""
    symbols: list[str] = field(default_factory=list)
    schema_version: str = ""
    transformations: list[str] = field(default_factory=list)
    quality_score: float = 1.0
    missing_data_pct: float = 0.0
    outliers_removed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DataVersionRegistry:
    """Registry of all data versions."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._versions: dict[str, DataVersion] = {}
        self._storage_path = Path(storage_path) if storage_path else None

    def register(self, version: DataVersion) -> None:
        """Register a new data version."""
        self._versions[version.version_id] = version
        logger.info("Data version registered: %s (%s)", version.version_id, version.name)

    def get(self, version_id: str) -> DataVersion | None:
        return self._versions.get(version_id)

    def list_versions(self) -> list[DataVersion]:
        return list(self._versions.values())

    def compute_content_hash(self, data: list[dict[str, Any]]) -> str:
        """Compute a hash of the data content for integrity checking."""
        if not data:
            return "empty"
        try:
            sample = data[:200]  # hash first 200 rows for speed
            content = json.dumps(sample, sort_keys=True, default=str)
            return hashlib.sha256(content.encode()).hexdigest()[:20]
        except Exception:
            return "hash_error"

    def build_manifest(
        self,
        data: list[dict[str, Any]],
        version_id: str = "",
        source: str = "unknown",
        transformations: list[str] | None = None,
    ) -> DataManifest:
        """Build a DataManifest from actual data."""
        if not data:
            return DataManifest()

        dates = [d.get("date", "") for d in data if d.get("date")]
        symbols = list({d.get("symbol", "") for d in data if d.get("symbol")})

        manifest = DataManifest(
            data_version=version_id,
            data_hash=self.compute_content_hash(data),
            source=source,
            row_count=len(data),
            date_start=min(dates) if dates else "",
            date_end=max(dates) if dates else "",
            symbols=sorted(symbols),
            schema_version="1.0.0",
            transformations=transformations or [],
        )
        return manifest

    def save_registry(self, path: str | Path) -> None:
        """Save registry to JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {vid: asdict(v) for vid, v in self._versions.items()}
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def load_registry(self, path: str | Path) -> None:
        """Load registry from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for vid, vdata in data.items():
            self._versions[vid] = DataVersion(**vdata)
