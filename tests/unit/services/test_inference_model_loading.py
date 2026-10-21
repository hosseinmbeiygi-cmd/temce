"""Audit F-01, inference path — the DB-registry loader must read real artifacts.

``InferenceService._load_from_db_registry`` unpickled ``model_pipeline.pkl`` with
a bare ``pickle.load``, which raises ``UnpicklingError: invalid load key, 'x'``
on every artifact the training toolchain wrote (zlib-wrapped joblib dumps). The
failure was swallowed and surfaced as "No trained model available", so
``/api/v1/ml/predict`` could never load a model that was plainly on disk.
"""

from __future__ import annotations

import io
import json
import pickle
import types
import zlib
from pathlib import Path

import joblib
import pytest

from ml.types import FeatureMatrix
from services.inference_service import InferenceService


class _FakeScalars:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    """Returns the registry rows for any statement it is given."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def execute(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult(self._rows)


class _FakeModelRepo:
    def __init__(self, rows: list) -> None:
        self._session = _FakeSession(rows)


class _TinyModel:
    def predict(self, fm):
        return types.SimpleNamespace(predictions=[0.25])


def _write_zlib_joblib_artifact(root: Path, model_id: str = "xgboost_X") -> Path:
    version_dir = root / model_id / "v1-abc"
    version_dir.mkdir(parents=True)
    buffer = io.BytesIO()
    joblib.dump(_TinyModel(), buffer)
    (version_dir / "model_pipeline.pkl").write_bytes(zlib.compress(buffer.getvalue()))
    (version_dir / "metadata.json").write_text(
        json.dumps({"feature_names": ["open", "close"], "stage": "production"}),
        encoding="utf-8",
    )
    return version_dir


def _registry_row(
    artifact_path: Path,
    stage: str = "production",
    parameters: str | None = None,
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        artifact_path=str(artifact_path), stage=stage, parameters=parameters
    )


def _service(rows: list) -> InferenceService:
    return InferenceService(model_repo=_FakeModelRepo(rows))


@pytest.mark.asyncio
async def test_registry_loader_reads_a_zlib_joblib_artifact(tmp_path):
    version_dir = _write_zlib_joblib_artifact(tmp_path)
    svc = _service([_registry_row(version_dir)])

    loaded = await svc._load_from_db_registry(
        "xgboost_X", FeatureMatrix(data=[], feature_names=["open", "close"])
    )

    assert loaded is not None, "the artifact on disk must load through the DB registry"
    model, feature_names, from_path = loaded
    assert from_path is True
    assert feature_names == ["open", "close"]
    assert hasattr(model, "predict")


@pytest.mark.asyncio
async def test_registry_loader_still_reads_a_plain_pickle(tmp_path):
    version_dir = tmp_path / "xgboost_X" / "v1-own"
    version_dir.mkdir(parents=True)
    with open(version_dir / "model.pkl", "wb") as f:
        pickle.dump(_TinyModel(), f)
    svc = _service([_registry_row(version_dir)])

    loaded = await svc._load_from_db_registry(
        "xgboost_X", FeatureMatrix(data=[], feature_names=["open"])
    )

    assert loaded is not None
    assert loaded[2] is True


@pytest.mark.asyncio
async def test_registry_loader_prefers_the_production_version(tmp_path):
    prod = _write_zlib_joblib_artifact(tmp_path / "prod", "xgboost_Y")
    dev = _write_zlib_joblib_artifact(tmp_path / "dev", "xgboost_Y")
    svc = _service([
        _registry_row(dev, "development", parameters=json.dumps({"feature_names": ["dev_only"]})),
        _registry_row(prod, "production", parameters=json.dumps({"feature_names": ["prod_only"]})),
    ])

    loaded = await svc._load_from_db_registry(
        "xgboost_Y", FeatureMatrix(data=[], feature_names=["open", "close"])
    )

    assert loaded is not None
    _, feature_names, _ = loaded
    assert feature_names == ["prod_only"], "the production version must be the one loaded"


@pytest.mark.asyncio
async def test_registry_loader_returns_none_when_the_file_is_gone(tmp_path):
    svc = _service([_registry_row(tmp_path / "missing" / "v1-x")])

    loaded = await svc._load_from_db_registry(
        "xgboost_X", FeatureMatrix(data=[], feature_names=["open"])
    )

    assert loaded is None
