"""Audit F-01 — the ML artifact loader must find and read what training wrote.

``ArtifactManager`` used to read ``data/models`` (empty) with a bare
``pickle.load`` of ``model.pkl``, so every real artifact failed three times
over: wrong root, wrong file name, and a zlib-wrapped joblib payload. The whole
ML stage silently fell back to zero predictions. These tests pin each layer of
that chain against the layout the training toolchain actually produces.
"""

from __future__ import annotations

import hashlib
import io
import json
import pickle
import zlib
from pathlib import Path

import joblib
import pytest

from core.config import settings
from ml.artifacts import (
    ArtifactManager,
    decode_artifact_bytes,
    load_artifact_file,
    resolve_artifact_root,
)
from ml.types import ModelArtifactMeta

# ═══════════════════════════════════════════════════════════════════════════════
# ── Root resolution
# ═══════════════════════════════════════════════════════════════════════════════


def _make_model_dir(root: Path, model_id: str = "xgboost_X", version: str = "v1-abc") -> Path:
    model_dir = root / model_id / version
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model_pipeline.pkl").write_bytes(b"payload")
    return model_dir


def test_explicit_base_dir_always_wins(tmp_path):
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    assert resolve_artifact_root(str(explicit)) == explicit.resolve()


def test_configured_dir_with_models_is_used(tmp_path, monkeypatch):
    configured = tmp_path / "configured"
    _make_model_dir(configured)
    monkeypatch.setattr(settings, "ml_model_dir", str(configured), raising=False)

    assert resolve_artifact_root() == configured.resolve()


def test_empty_configured_dir_falls_back_to_ml_artifacts(tmp_path, monkeypatch):
    configured = tmp_path / "data" / "models"
    configured.mkdir(parents=True)
    fallback = tmp_path / "ml_artifacts"
    _make_model_dir(fallback)
    monkeypatch.setattr(settings, "ml_model_dir", str(configured), raising=False)
    monkeypatch.chdir(tmp_path)

    assert resolve_artifact_root() == fallback.resolve()


def test_empty_configured_dir_without_fallback_stays_configured(tmp_path, monkeypatch):
    configured = tmp_path / "data" / "models"
    configured.mkdir(parents=True)
    monkeypatch.setattr(settings, "ml_model_dir", str(configured), raising=False)
    monkeypatch.chdir(tmp_path)

    assert resolve_artifact_root() == configured.resolve()


# ═══════════════════════════════════════════════════════════════════════════════
# ── Payload formats
# ═══════════════════════════════════════════════════════════════════════════════


def test_zlib_wrapped_joblib_payload_is_decoded():
    """The external toolchain stores zlib(joblib.dump(...)) — not a raw pickle."""
    buffer = io.BytesIO()
    joblib.dump({"weights": [1, 2, 3]}, buffer)
    raw = zlib.compress(buffer.getvalue())
    assert raw[:1] == b"\x78"

    assert decode_artifact_bytes(raw) == buffer.getvalue()
    assert load_artifact_file.__module__  # sanity: importable helper
    loaded = pickle.loads(decode_artifact_bytes(raw))
    assert loaded == {"weights": [1, 2, 3]}


def test_plain_pickle_payload_is_left_untouched():
    raw = pickle.dumps({"a": 1})
    assert decode_artifact_bytes(raw) == raw


def test_bytes_that_only_look_compressed_fall_through(tmp_path):
    """A bare pickle starting with 0x78 must survive the zlib sniff."""
    raw = b"\x78" + b"not really zlib"
    assert decode_artifact_bytes(raw) == raw


# ═══════════════════════════════════════════════════════════════════════════════
# ── ArtifactManager against the training toolchain's layout
# ═══════════════════════════════════════════════════════════════════════════════


def _write_external_artifact(root: Path, model_id: str = "xgboost_X") -> None:
    """Write ``<model>/<version>/{model_pipeline.pkl,metadata.json,latest_path.txt}``."""

    model_dir = root / model_id
    old = model_dir / "v1-old"
    new = model_dir / "v1-new"
    blobs: dict[Path, bytes] = {}
    for path, value in ((old, {"which": "old"}), (new, {"which": "new"})):
        path.mkdir(parents=True)
        buffer = io.BytesIO()
        joblib.dump(value, buffer)
        blobs[path] = zlib.compress(buffer.getvalue())
        (path / "model_pipeline.pkl").write_bytes(blobs[path])

    for path, version in ((old, "v1-old"), (new, "v1-new")):
        (path / "metadata.json").write_text(
            json.dumps(
                {
                    "symbol": "X",
                    "model_type": "xgboost",
                    "metrics": {"mean_r2": -0.54},
                    "feature_names": ["open", "close"],
                    "hyperparameters": {"max_depth": 4},
                    "version": version,
                    # The training toolchain records the *file* digest (md5) in
                    # ``checksum``; a placeholder would make the artifact
                    # unverifiable for the integrity gate (ML-007).
                    "checksum": hashlib.md5(blobs[path]).hexdigest(),
                    "python_version": "3.11.9",
                    "sklearn_version": "1.9.0",
                    "created_at": "2026-07-18T22:18:20+00:00",
                }
            ),
            encoding="utf-8",
        )
    # Windows-style pointer, exactly as the training host writes it.
    (model_dir / "latest_path.txt").write_text(
        f"{model_dir}\\v1-old".replace("/", "\\"), encoding="utf-8"
    )


def test_manager_reads_versioned_artifacts_and_maps_metadata(tmp_path):

    _write_external_artifact(tmp_path)
    manager = ArtifactManager(base_dir=str(tmp_path))

    model, meta = manager.load_model("xgboost_X")

    assert model == {"which": "old"}  # latest_path.txt wins over the sort order
    assert isinstance(meta, ModelArtifactMeta)
    assert meta.version == "v1-old"
    assert meta.metrics == {"mean_r2": -0.54}
    assert meta.feature_names == ["open", "close"]
    assert meta.params == {"max_depth": 4}
    assert meta.artifact_hash == hashlib.md5(
        (tmp_path / "xgboost_X" / "v1-old" / "model_pipeline.pkl").read_bytes()
    ).hexdigest()
    assert meta.library_versions["sklearn"] == "1.9.0"
    assert meta.model_id == "xgboost_X"


def test_manager_can_request_a_specific_version(tmp_path):
    _write_external_artifact(tmp_path)
    manager = ArtifactManager(base_dir=str(tmp_path))

    model, meta = manager.load_model("xgboost_X", version="v1-new")

    assert model == {"which": "new"}
    assert meta.version == "v1-new"


def test_manager_still_reads_its_own_model_pkl(tmp_path):
    """Artifacts written by save_model (plain model.pkl) keep working."""
    model_dir = tmp_path / "xgboost_X" / "v1-own"
    model_dir.mkdir(parents=True)
    with open(model_dir / "model.pkl", "wb") as f:
        pickle.dump({"own": True}, f)

    model, meta = ArtifactManager(base_dir=str(tmp_path)).load_model("xgboost_X")

    assert model == {"own": True}
    assert meta.version == "v1-own"
    assert meta.stage == "development"


def test_unknown_model_reports_the_directory_it_searched(tmp_path):
    manager = ArtifactManager(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError) as excinfo:
        manager.load_model("xgboost_missing")
    assert "xgboost_missing" in str(excinfo.value)


def test_latest_version_helper_is_exposed(tmp_path):
    _write_external_artifact(tmp_path)
    manager = ArtifactManager(base_dir=str(tmp_path))
    assert manager.latest_version("xgboost_X") == "v1-old"
    assert manager.latest_version("nope") is None


# ═══════════════════════════════════════════════════════════════════════════════
# ── ModelLoader sees the same tree
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_model_loader_reads_the_versioned_layout(tmp_path):
    from ml.model_loader import ModelLoader

    _write_external_artifact(tmp_path)
    loader = ModelLoader(base_dir=str(tmp_path))

    model = await loader.get_model("X", "xgboost")

    assert model == {"which": "old"}


def test_model_loader_can_pin_an_exact_version(tmp_path):
    from ml.model_loader import ModelLoader

    _write_external_artifact(tmp_path)
    loader = ModelLoader(base_dir=str(tmp_path))

    assert loader._load_from_disk("xgboost_X@v1-new") == {"which": "new"}
