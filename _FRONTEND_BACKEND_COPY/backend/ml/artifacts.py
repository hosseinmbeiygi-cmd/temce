from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from core.config import settings
from core.logging import get_logger
from core.paths import safe_resolve
from ml.types import ModelArtifactMeta

logger = get_logger(__name__)


class ArtifactManager:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.ml_model_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _model_path(self, model_id: str, version: str) -> Path:
        return safe_resolve(self.base_dir, f"{model_id}/{version}")

    def save_model(self, model_obj: Any, meta: ModelArtifactMeta) -> str:
        path = self._model_path(meta.model_id, meta.version)
        path.mkdir(parents=True, exist_ok=True)

        model_file = path / "model.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(model_obj, f)

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
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info("Model saved to %s", path)
        return str(path)

    def load_model(self, model_id: str, version: str = "latest") -> tuple[Any, ModelArtifactMeta]:
        if version == "latest":
            versions = sorted([p.name for p in (self.base_dir / model_id).iterdir() if p.is_dir()])
            if not versions:
                raise FileNotFoundError(f"No versions for model {model_id}")
            version = versions[-1]

        path = self._model_path(model_id, version)

        with open(path / "model.pkl", "rb") as f:
            model = pickle.load(f)

        with open(path / "metadata.json", encoding="utf-8") as f:
            meta_dict = json.load(f)

        meta = ModelArtifactMeta(**meta_dict)
        return model, meta

    def list_models(self) -> list[str]:
        return [p.name for p in self.base_dir.iterdir() if p.is_dir()]

    def list_versions(self, model_id: str) -> list[str]:
        model_dir = self.base_dir / model_id
        if not model_dir.exists():
            return []
        return sorted([p.name for p in model_dir.iterdir() if p.is_dir()])
