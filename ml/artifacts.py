from __future__ import annotations

import contextlib
import hashlib
import io
import json
import pickle
import platform
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import settings
from core.logging import get_logger
from core.paths import safe_resolve
from ml.types import ModelArtifactMeta

logger = get_logger(__name__)


def decode_artifact_bytes(raw: bytes) -> bytes:
    """Return the raw pickle payload of a stored model artifact.

    Two on-disk layouts exist in the wild:

    * a bare pickle written by :meth:`ArtifactManager.save_model` (starts with
      the protocol marker ``0x80``), and
    * a zlib-compressed pickle produced by the external training toolchain
      that populates ``ml_artifacts/`` (starts with the zlib magic ``0x78``).

    Loading the compressed layout with a bare ``pickle.load`` raises
    ``UnpicklingError: invalid load key, 'x'`` on the very first byte, which is
    exactly what both loaders used to do (audit F-01).

    The format is detected from the first byte rather than assumed, so a bare
    pickle whose payload happens to start with ``0x78`` is still handled: the
    decompress is attempted and its result is used only if it decodes as a
    pickle.
    """
    if raw[:1] == b"\x78":
        try:
            inflated = zlib.decompress(raw)
        except zlib.error:
            return raw  # Not actually zlib; fall through to the plain path.
        if inflated[:1] == b"\x80":
            return inflated
    return raw


def load_artifact_file(path: Path) -> Any:
    """Load a stored model artifact, transparently handling its container.

    Three layout variations exist in ``ml_artifacts/``: bare pickles written by
    :meth:`ArtifactManager.save_model`, and zlib-compressed **joblib** dumps
    from the external training toolchain. The latter raise
    ``UnpicklingError: STACK_GLOBAL requires str`` under a bare ``pickle.loads``
    because their numpy internals need joblib's unpickler (audit F-01).
    """
    return load_artifact_bytes(Path(path).read_bytes())


def load_artifact_bytes(raw: bytes) -> Any:
    """Decode ``raw`` artifact bytes and return the object they hold."""
    data = decode_artifact_bytes(raw)
    try:
        return pickle.loads(data)
    except pickle.UnpicklingError as pickle_exc:
        try:
            import joblib
        except ImportError:
            raise pickle_exc from None
        try:
            return joblib.load(io.BytesIO(data))
        except Exception as joblib_exc:
            raise pickle.UnpicklingError(
                f"artifact is neither a plain pickle ({pickle_exc}) "
                f"nor a joblib dump ({joblib_exc})"
            ) from joblib_exc


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# Model files the training paths write, newest format first (audit F-01).
MODEL_FILE_CANDIDATES = ("model_pipeline.pkl", "model.pkl")


def latest_version(model_dir: Path) -> str | None:
    """Newest version folder of one model, or ``None`` when there is none.

    The external training pipeline drops a ``latest_path.txt`` next to the
    version folders pointing at the version it considers current; that pointer
    wins over the lexicographic order of the ``v1-<hash>`` folder names, which
    is not chronological.
    """
    pointer = model_dir / "latest_path.txt"
    try:
        raw = pointer.read_text(encoding="utf-8").strip()
    except OSError:
        raw = ""
    if raw:
        # The pointer is a Windows-style path on the training host.
        name = Path(raw.replace("\\", "/")).name
        if name and (model_dir / name).is_dir():
            return name

    versions = sorted(p.name for p in model_dir.iterdir() if p.is_dir())
    return versions[-1] if versions else None


def _holds_model_folders(root: Path) -> bool:
    """True when *root* contains at least one model folder (``<model>/<version>``)."""
    try:
        return any(child.is_dir() for child in root.iterdir())
    except OSError:
        return False


def resolve_artifact_root(explicit: str | None = None) -> Path:
    """Pick the directory that actually holds the trained model folders.

    Audit F-01: ``ArtifactManager`` read ``settings.ml_model_dir`` — configured
    as ``data/models`` (empty) — while every trained artifact lives under
    ``ml_artifacts/``. The loader therefore raised ``FileNotFoundError`` on
    every model, the backtest ML signal silently fell back to zeros, and the
    pipeline looked like it had no ML at all.

    An explicitly passed directory always wins, so callers that point at a
    specific tree (tests, QA round-trips) keep control. Otherwise the
    configured directory is used when it holds model folders, and the
    repository's ``ml_artifacts/`` is used as a fallback when it does not.
    """
    if explicit:
        return Path(explicit).resolve()

    configured = Path(settings.ml_model_dir).resolve()
    if _holds_model_folders(configured):
        return configured

    fallback = (Path.cwd() / "ml_artifacts").resolve()
    if fallback != configured and _holds_model_folders(fallback):
        logger.warning(
            "ML model dir %s holds no model folders — reading artifacts from %s "
            "(set ML_MODEL_DIR to silence this)",
            configured,
            fallback,
        )
        return fallback

    return configured


def _collect_library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for lib in ("sklearn", "xgboost", "lightgbm", "catboost", "torch"):
        with contextlib.suppress(Exception):
            import importlib

            mod = importlib.import_module(lib)
            versions[lib] = getattr(mod, "__version__", "unknown")
    return versions


class ArtifactManager:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = resolve_artifact_root(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _model_path(self, model_id: str, version: str) -> Path:
        return safe_resolve(self.base_dir, f"{model_id}/{version}")

    def save_model(self, model_obj: Any, meta: ModelArtifactMeta) -> str:
        path = self._model_path(meta.model_id, meta.version)
        path.mkdir(parents=True, exist_ok=True)

        model_file = path / "model.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(model_obj, f)

        # M1: content hash + provenance
        with contextlib.suppress(Exception):
            meta.artifact_hash = _sha256_file(model_file)
            meta.file_size_bytes = model_file.stat().st_size
        meta.python_version = platform.python_version()
        meta.library_versions = _collect_library_versions()

        meta_file = path / "metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model_id": meta.model_id,
                    "version": meta.version,
                    "metrics": meta.metrics,
                    "params": meta.params,
                    "feature_names": meta.feature_names,
                    "stage": meta.stage,
                    "created_at": meta.created_at.isoformat(),
                    "artifact_hash": meta.artifact_hash,
                    "file_size_bytes": meta.file_size_bytes,
                    "dataset_hash": meta.dataset_hash,
                    "python_version": meta.python_version,
                    "library_versions": meta.library_versions,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info("Model saved to %s (hash=%s size=%d)", path, meta.artifact_hash[:12], meta.file_size_bytes)
        return str(path)

    def load_model(self, model_id: str, version: str = "latest") -> tuple[Any, ModelArtifactMeta]:
        model_dir = self.base_dir / model_id
        if not model_dir.is_dir():
            raise FileNotFoundError(f"No artifact directory for model {model_id} under {self.base_dir}")

        if version == "latest":
            resolved = latest_version(model_dir)
            if resolved is None:
                raise FileNotFoundError(f"No versions for model {model_id}")
            version = resolved

        path = self._model_path(model_id, version)

        # The external training pipeline stores ``model_pipeline.pkl``; models
        # saved through :meth:`save_model` are ``model.pkl`` (audit F-01).
        model_file = next(
            (candidate for candidate in (path / n for n in MODEL_FILE_CANDIDATES)
             if candidate.exists()),
            None,
        )
        if model_file is None:
            raise FileNotFoundError(
                f"No model file in {path} (tried: {list(MODEL_FILE_CANDIDATES)})"
            )

        model = load_artifact_file(model_file)

        return model, self._load_meta(model_id, version, path)

    @staticmethod
    def _load_meta(model_id: str, version: str, path: Path) -> ModelArtifactMeta:
        """Build artifact metadata from whatever ``metadata.json`` carries.

        Artifacts written by the external training pipeline describe themselves
        with different keys (``symbol``/``model_type``/``hyperparameters``/
        ``checksum``) than :meth:`save_model` does, so the file is mapped onto
        :class:`ModelArtifactMeta` field by field instead of splatted into the
        constructor, which used to raise ``TypeError`` on every real artifact.
        """
        data: dict[str, Any] = {}
        meta_file = path / "metadata.json"
        if meta_file.exists():
            with open(meta_file, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded

        created_raw = data.get("created_at")
        try:
            created_at = (
                datetime.fromisoformat(str(created_raw)) if created_raw else datetime.now(UTC)
            )
        except ValueError:
            created_at = datetime.now(UTC)

        library_versions = {
            lib: str(data[f"{lib}_version"])
            for lib in ("sklearn", "xgboost", "lightgbm", "catboost", "numpy", "pandas")
            if data.get(f"{lib}_version")
        }

        return ModelArtifactMeta(
            model_id=str(data.get("model_id") or model_id),
            version=str(data.get("version") or version),
            path=str(path),
            metrics=dict(data.get("metrics") or {}),
            params=dict(data.get("hyperparameters") or data.get("params") or {}),
            feature_names=list(data.get("feature_names") or []),
            created_at=created_at,
            stage=str(data.get("stage") or "development"),
            artifact_hash=str(data.get("artifact_hash") or data.get("checksum") or ""),
            file_size_bytes=int(data.get("file_size_bytes") or 0),
            dataset_hash=str(data.get("dataset_hash") or ""),
            python_version=str(data.get("python_version") or ""),
            library_versions=library_versions,
        )

    def list_models(self) -> list[str]:
        return [p.name for p in self.base_dir.iterdir() if p.is_dir()]

    def list_versions(self, model_id: str) -> list[str]:
        model_dir = self.base_dir / model_id
        if not model_dir.exists():
            return []
        return sorted([p.name for p in model_dir.iterdir() if p.is_dir()])

    def latest_version(self, model_id: str) -> str | None:
        """Version the loader would pick for *model_id* (``latest_path.txt`` aware)."""
        model_dir = self.base_dir / model_id
        return latest_version(model_dir) if model_dir.is_dir() else None
