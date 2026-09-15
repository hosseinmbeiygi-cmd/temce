"""M2: ml_artifacts lifecycle — retention + eviction.

Keeps at most N latest versions per (symbol, algo) and prunes older
artifacts by mtime. Production-stage artifacts are never deleted.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# Default: keep 3 latest per prefix, delete anything >90d (except prod)
KEEP_LATEST = 3
MAX_AGE_DAYS = 90


def _is_production(meta_path: Path) -> bool:
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data.get("stage") == "production"
    except Exception:
        return False


def prune_ml_artifacts(
    base_dir: str | None = None,
    keep_latest: int = KEEP_LATEST,
    max_age_days: int = MAX_AGE_DAYS,
    dry_run: bool = False,
) -> dict[str, Any]:
    base = Path(base_dir or settings.ml_model_dir).resolve()
    if not base.exists():
        return {"deleted": 0, "kept": 0, "skipped_prod": 0}

    cutoff = time.time() - max_age_days * 86400
    # Group by artifact prefix (algo) — dir names like xgboost_فولاد
    groups: dict[str, list[Path]] = {}
    for p in base.iterdir():
        if not p.is_dir():
            continue
        # algo is prefix before '_' — fallback to full name
        algo = p.name.split("_")[0] if "_" in p.name else p.name
        groups.setdefault(algo, []).append(p)

    deleted = 0
    kept = 0
    skipped_prod = 0

    for algo, dirs in groups.items():
        # Sort by mtime descending (newest first)
        dirs_sorted = sorted(dirs, key=lambda d: d.stat().st_mtime, reverse=True)
        for idx, d in enumerate(dirs_sorted):
            meta = d / "metadata.json"
            is_prod = _is_production(meta) if meta.exists() else False
            if is_prod:
                skipped_prod += 1
                kept += 1
                continue
            is_old = d.stat().st_mtime < cutoff
            is_beyond_keep = idx >= keep_latest
            if is_beyond_keep and is_old:
                if not dry_run:
                    try:
                        shutil.rmtree(d)
                    except Exception as exc:
                        logger.warning("Failed to delete %s: %s", d, exc)
                        continue
                deleted += 1
                logger.info("Pruned ml artifact %s (algo=%s idx=%d)", d.name, algo, idx)
            elif is_beyond_keep and not is_old:
                # Beyond keep but still fresh — keep for now (grace period)
                kept += 1
            else:
                kept += 1

    return {"deleted": deleted, "kept": kept, "skipped_prod": skipped_prod, "base": str(base)}
