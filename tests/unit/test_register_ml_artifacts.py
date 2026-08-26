"""Unit tests for the pure scan/build logic of scripts/register_ml_artifacts.py.

Tests the functions that parse the artifacts directory and build DB rows —
no database access required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from scripts.register_ml_artifacts import (
    build_model_rows,
    scan_artifacts_dir,
)


def _make_meta(
    model_type: str,
    symbol: str,
    run_id: str = "abc123",
    task: str = "regression",
    created_at: str = "2026-07-21T22:46:10.772508+00:00",
) -> dict:
    return {
        "id": run_id,
        "experiment_name": "default",
        "model_type": model_type,
        "symbol": symbol,
        "task_type": task,
        "status": "completed",
        "metrics": {"mean_r2": 0.42, "mean_rmse": 0.06},
        "fold_metrics": [],
        "feature_names": ["f1", "f2", "f3"],
        "feature_groups": ["price", "technical"],
        "hyperparameters": {"lr": 0.01},
        "train_samples": 400,
        "start_date": "2026-01-23",
        "end_date": "2026-07-22",
        "created_at": created_at,
        "version": "v1-aaa",
    }


@pytest.fixture()
def artifacts_dir(tmp_path: Path) -> Path:
    """Create a small fake artifacts directory with two model folders."""
    base = tmp_path / "ml_artifacts"
    # Model 1: two versions + latest_path.txt
    m1 = base / "xgboost_فولاد"
    (m1 / "v1-aaa").mkdir(parents=True)
    (m1 / "v1-bbb").mkdir()
    (m1 / "v1-aaa" / "metadata.json").write_text(
        json.dumps(_make_meta("xgboost", "فولاد", run_id="aaa111"), ensure_ascii=False),
        encoding="utf-8",
    )
    (m1 / "v1-aaa" / "model_pipeline.pkl").write_bytes(b"\x80\x04fake")
    (m1 / "v1-bbb" / "metadata.json").write_text(
        json.dumps(_make_meta("xgboost", "فولاد", run_id="bbb222"), ensure_ascii=False),
        encoding="utf-8",
    )
    (m1 / "latest_path.txt").write_text(
        "ml_artifacts\\xgboost_فولاد\\v1-bbb", encoding="utf-8"
    )

    # Model 2: single version, no latest_path.txt
    m2 = base / "catboost_پدرخش"
    (m2 / "v1-ccc").mkdir(parents=True)
    (m2 / "v1-ccc" / "metadata.json").write_text(
        json.dumps(_make_meta("catboost", "پدرخش", run_id="ccc333"), ensure_ascii=False),
        encoding="utf-8",
    )

    # A folder without metadata (should be ignored)
    (base / "random_dir").mkdir()
    return base


def test_scan_artifacts_dir_finds_only_valid_models(artifacts_dir: Path):
    models = scan_artifacts_dir(artifacts_dir)
    names = [m["name"] for m in models]
    assert "xgboost_فولاد" in names
    assert "catboost_پدرخش" in names
    assert "random_dir" not in names
    assert len(models) == 2


def test_latest_version_resolution_from_latest_path(artifacts_dir: Path):
    models = scan_artifacts_dir(artifacts_dir)
    xgb = next(m for m in models if m["name"] == "xgboost_فولاد")
    # latest_path.txt points to v1-bbb (windows-style path is normalized)
    assert xgb["latest_version"] == "v1-bbb"
    assert len(xgb["versions"]) == 2


def test_latest_version_fallback_when_no_latest_path(artifacts_dir: Path):
    models = scan_artifacts_dir(artifacts_dir)
    cat = next(m for m in models if m["name"] == "catboost_پدرخش")
    assert cat["latest_version"] == "v1-ccc"


def test_build_model_rows_maps_metadata_to_tables():
    descriptor = {
        "id": "xgboost_فولاد",
        "name": "xgboost_فولاد",
        "latest_version": "v1-aaa",
        "versions": [
            {
                "version": "v1-aaa",
                "path": "C:/fake/ml_artifacts/xgboost_فولاد/v1-aaa",
                "metadata": _make_meta("xgboost", "فولاد", run_id="aaa111"),
            },
            {
                "version": "v1-bbb",
                "path": "C:/fake/ml_artifacts/xgboost_فولاد/v1-bbb",
                "metadata": _make_meta("xgboost", "فولاد", run_id="bbb222"),
            },
        ],
    }
    model_row, version_rows, run_rows = build_model_rows(descriptor)

    assert model_row["id"] == "xgboost_فولاد"
    assert model_row["task"] == "regression"
    assert model_row["framework"] == "xgboost"
    assert model_row["latest_version"] == "v1-aaa"

    # 2 versions → stage: latest=production, older=development
    assert len(version_rows) == 2
    prod = next(v for v in version_rows if v["version"] == "v1-aaa")
    dev = next(v for v in version_rows if v["version"] == "v1-bbb")
    assert prod["stage"] == "production"
    assert dev["stage"] == "development"
    assert prod["artifact_path"] == "C:/fake/ml_artifacts/xgboost_فولاد/v1-aaa"
    assert prod["training_run_id"] == "aaa111"

    # 2 training runs, one per version, keyed by metadata id
    assert len(run_rows) == 2
    run_ids = {r["id"] for r in run_rows}
    assert run_ids == {"aaa111", "bbb222"}
    for r in run_rows:
        assert r["status"] == "completed"
        assert r["progress_pct"] == 100.0
        assert r["model_type"] == "xgboost"
