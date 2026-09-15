from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class ModelRegistry:
    """Model registry for ML model versioning and management."""

    def __init__(self) -> None:
        self._models: dict[str, dict[str, Any]] = {}

    def register(self, name: str, task: str, framework: str, tags: list[str] | None = None) -> str:
        import uuid

        model_id = uuid.uuid4().hex[:12]
        self._models[model_id] = {
            "id": model_id,
            "name": name,
            "task": task,
            "framework": framework,
            "versions": [],
            "tags": tags or [],
            "created_at": datetime.now(UTC).isoformat(),
        }
        return model_id

    def get(self, model_id: str) -> dict[str, Any] | None:
        return self._models.get(model_id)

    def add_version(
        self,
        model_id: str,
        version: str,
        metrics: dict[str, float] | None = None,
        parameters: dict[str, Any] | None = None,
        stage: str = "development",
        artifact_path: str = "",
    ) -> dict[str, Any]:
        model = self._models.get(model_id)
        if model is None:
            raise ValueError(f"Model {model_id} not found")
        version_obj = {
            "version": version,
            "stage": stage,
            "metrics": metrics or {},
            "parameters": parameters or {},
            "artifact_path": artifact_path,
            "created_at": datetime.now(UTC).isoformat(),
        }
        model["versions"].append(version_obj)
        model["latest_version"] = version
        return version_obj

    def get_version(self, model_id: str, version: str) -> dict[str, Any] | None:
        model = self._models.get(model_id)
        if model is None:
            return None
        for v in model.get("versions", []):
            if v["version"] == version:
                return v
        return None

    def list_models(self) -> list[dict[str, Any]]:
        return list(self._models.values())
