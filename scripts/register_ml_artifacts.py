#!/usr/bin/env python
"""Register trained ML model artifacts into the ML database tables.

Scans an artifacts directory (default: ``ml_artifacts/``) where each sub-folder
holds the trained versions of one model (e.g. ``xgboost_فولاد``), reads each
version's ``metadata.json`` and **upserts** the model + version + training run
rows into:

- ``ml_models``          — one row per model folder (``model_type_symbol``)
- ``ml_model_versions``  — one row per version folder (``v1-xxxx``)
- ``ml_training_runs``   — one row per training run (from metadata ``id``)

After registration the ML API endpoints (``/ml/models``, ``/ml/runs``) and the
inference/comparison services read the **real trained models** instead of the
in-memory demo seed data.

Usage:
    python scripts/register_ml_artifacts.py                     # default ./ml_artifacts
    python scripts/register_ml_artifacts.py --artifacts-dir ./data/models
    python scripts/register_ml_artifacts.py --dry-run           # scan only, no DB writes
    python scripts/register_ml_artifacts.py --only xgboost_فولاد catboost_پدرخش
"""
from __future__ import annotations

import sys
from pathlib import Path

# --- auto PYTHONPATH ---
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import argparse
import asyncio
import contextlib
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from core.database import close_database, get_session, init_database
from core.logging import get_logger
from models.ml import MlModelModel, MlModelVersionModel, MlTrainingRunModel

logger = get_logger(__name__)

if sys.platform == "win32":
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


# ── Pure scan logic (no DB) ──────────────────────────────────────────────


def _read_metadata(meta_file: Path) -> dict[str, Any]:
    with open(meta_file, encoding="utf-8") as f:
        return json.load(f)


def _resolve_latest_version(folder: Path, versions: list[dict[str, Any]]) -> str:
    """Pick the latest version name using latest_path.txt when present."""
    lp = folder / "latest_path.txt"
    if lp.exists():
        raw = lp.read_text(encoding="utf-8").strip()
        # normalize windows backslashes and take the last path component
        name = raw.replace("\\", "/").rstrip("/").split("/")[-1]
        if any(v["version"] == name for v in versions):
            return name
    if versions:
        return sorted(v["version"] for v in versions)[-1]
    return "v1"


def scan_artifacts_dir(artifacts_dir: str | Path) -> list[dict[str, Any]]:
    """Scan an artifacts directory and return model descriptors (no DB access)."""
    base = Path(artifacts_dir)
    if not base.is_dir():
        raise FileNotFoundError(f"Artifacts directory not found: {base}")

    models: list[dict[str, Any]] = []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        versions: list[dict[str, Any]] = []
        for sub in sorted(folder.iterdir()):
            if not sub.is_dir():
                continue
            meta_file = sub / "metadata.json"
            if not meta_file.exists():
                continue
            try:
                meta = _read_metadata(meta_file)
            except Exception as e:  # pragma: no cover
                logger.warning("Skipping %s: %s", sub, e)
                continue
            versions.append({
                "version": sub.name,
                "path": str(sub.resolve()),
                "metadata": meta,
            })
        if not versions:
            continue
        models.append({
            "id": folder.name,
            "name": folder.name,
            "latest_version": _resolve_latest_version(folder, versions),
            "versions": versions,
        })
    return models


# ── Row builders ──────────────────────────────────────────────────────────


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _json(v: Any) -> str | None:
    return json.dumps(v, ensure_ascii=False, default=str) if v is not None else None


def build_model_rows(descriptor: dict[str, Any]) -> tuple[dict, list[dict], list[dict]]:
    """Convert a scanned model descriptor into (model_row, version_rows, run_rows)."""
    name = descriptor["name"]
    latest = descriptor["latest_version"]
    versions = descriptor["versions"]

    # metadata of the latest version drives model-level fields
    latest_meta = next(
        (v["metadata"] for v in versions if v["version"] == latest),
        versions[0]["metadata"],
    )
    model_type = latest_meta.get("model_type") or name.split("_", 1)[0]
    symbol = latest_meta.get("symbol") or (name.split("_", 1)[1] if "_" in name else "")
    task_type = latest_meta.get("task_type") or "regression"
    feature_names = latest_meta.get("feature_names", [])

    model_row: dict[str, Any] = {
        "id": descriptor["id"],
        "name": name,
        "task": task_type,
        "framework": model_type,
        "latest_version": latest,
        "description": f"مدل {model_type} آموزش‌دیده روی {symbol} — {len(feature_names)} ویژگی",
        "tags": _json([symbol, model_type, latest_meta.get("experiment_name", "")]),
        "updated_at": _parse_dt(latest_meta.get("created_at")),
    }

    version_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    for v in versions:
        meta = v["metadata"]
        version_id = f"{descriptor['id']}::{v['version']}"
        if len(version_id) > 50:
            version_id = hashlib.sha1(version_id.encode("utf-8"), usedforsecurity=False).hexdigest()[:40]

        version_rows.append({
            "id": version_id,
            "model_id": descriptor["id"],
            "version": v["version"],
            "stage": "production" if v["version"] == latest else "development",
            "metrics": _json(meta.get("metrics", {})),
            "parameters": _json({
                "feature_groups": meta.get("feature_groups", []),
                "feature_names": meta.get("feature_names", []),
                "hyperparameters": meta.get("hyperparameters", {}),
                "train_samples": meta.get("train_samples"),
                "start_date": meta.get("start_date"),
                "end_date": meta.get("end_date"),
                "checksum": meta.get("checksum"),
                "sklearn_version": meta.get("sklearn_version"),
            }),
            "artifact_path": v["path"],
            "training_run_id": meta.get("id"),
        })

        created = _parse_dt(meta.get("created_at"))
        run_rows.append({
            "id": meta.get("id") or version_id,
            "experiment_name": meta.get("experiment_name") or f"{model_type}-{symbol}",
            "run_name": f"{model_type}-{symbol}",
            "status": meta.get("status") or "completed",
            "model_type": meta.get("model_type") or model_type,
            "config": _json({
                "symbol": symbol,
                "feature_groups": meta.get("feature_groups", []),
                "hyperparameters": meta.get("hyperparameters", {}),
                "start_date": meta.get("start_date"),
                "end_date": meta.get("end_date"),
            }),
            "metrics": _json(meta.get("metrics", {})),
            "best_params": _json(meta.get("hyperparameters", {})),
            "progress_pct": 100.0,
            "started_at": created,
            "finished_at": created,
        })

    return model_row, version_rows, run_rows


# ── DB upsert helpers ─────────────────────────────────────────────────────


async def _upsert_model(session, row: dict) -> None:
    existing = await session.get(MlModelModel, row["id"])
    if existing:
        for k, v in row.items():
            setattr(existing, k, v)
    else:
        session.add(MlModelModel(**row))


async def _upsert_version(session, row: dict) -> None:
    existing = await session.get(MlModelVersionModel, row["id"])
    if existing:
        for k, v in row.items():
            setattr(existing, k, v)
    else:
        session.add(MlModelVersionModel(**row))


async def _upsert_run(session, row: dict) -> None:
    existing = await session.get(MlTrainingRunModel, row["id"])
    if existing:
        for k, v in row.items():
            setattr(existing, k, v)
    else:
        session.add(MlTrainingRunModel(**row))


async def register_all(session, models: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert all scanned models. Returns counts of (models, versions, runs)."""
    counts = {"models": 0, "versions": 0, "runs": 0}
    for descriptor in models:
        model_row, version_rows, run_rows = build_model_rows(descriptor)
        await _upsert_model(session, model_row)
        counts["models"] += 1
        for vrow in version_rows:
            await _upsert_version(session, vrow)
            counts["versions"] += 1
        for rrow in run_rows:
            await _upsert_run(session, rrow)
            counts["runs"] += 1
    await session.commit()
    return counts


# ── CLI ───────────────────────────────────────────────────────────────────


async def _run(artifacts_dir: Path, dry_run: bool, only: list[str]) -> int:
    await init_database()

    models = scan_artifacts_dir(artifacts_dir)
    if only:
        models = [m for m in models if m["name"] in only]

    print(f"\n{'=' * 64}")
    print(f"  ML ARTIFACT REGISTRATION {'[DRY-RUN]' if dry_run else ''}")
    print(f"{'=' * 64}")
    print(f"  Artifacts dir: {artifacts_dir}")
    print(f"  Models found:  {len(models)}")

    if not models:
        print("  Nothing to register.")
        await close_database()
        return 0

    if dry_run:
        total_versions = sum(len(m["versions"]) for m in models)
        total_runs = sum(
            sum(1 for v in m["versions"] if v["metadata"].get("id")) for m in models
        )
        print(f"  Would register: {len(models)} models / {total_versions} versions / {total_runs} runs")
        for m in models:
            latest_meta = next(
                (v["metadata"] for v in m["versions"] if v["version"] == m["latest_version"]),
                m["versions"][0]["metadata"],
            )
            print(
                f"    • {m['name']:<35} "
                f"{latest_meta.get('model_type', '?'):<22} "
                f"{latest_meta.get('task_type', '?'):<14} "
                f"v={m['latest_version']}"
            )
        await close_database()
        return 0

    total_versions = 0
    total_runs = 0
    try:
        async for session in get_session():
            counts = await register_all(session, models)
            total_versions = counts["versions"]
            total_runs = counts["runs"]
            print(f"\n  ✅ Registered: {counts['models']} models / "
                  f"{counts['versions']} versions / {counts['runs']} runs")
    finally:
        await close_database()

    print("\n  Summary:")
    print(f"    Models:   {len(models)}")
    print(f"    Versions: {total_versions}")
    print(f"    Runs:     {total_runs}")
    print(f"{'=' * 64}\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register trained ML artifacts into ml_models / ml_model_versions / ml_training_runs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--artifacts-dir", type=Path, default=Path("ml_artifacts"),
                        help="Directory containing trained model folders (default: ./ml_artifacts)")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, don't write to DB")
    parser.add_argument("--only", nargs="*", help="Only register these model folder names")
    args = parser.parse_args()

    sys.exit(asyncio.run(_run(args.artifacts_dir, args.dry_run, args.only or [])))


if __name__ == "__main__":
    main()
