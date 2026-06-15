from __future__ import annotations

from core.logging import get_logger
from ml.types import ModelArtifactMeta

logger = get_logger(__name__)


class ModelRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, list[ModelArtifactMeta]] = {}

    def register(self, meta: ModelArtifactMeta) -> None:
        if meta.model_id not in self._entries:
            self._entries[meta.model_id] = []
        self._entries[meta.model_id].append(meta)
        logger.info("Model %s version %s registered", meta.model_id, meta.version)

    def get(self, model_id: str, version: str | None = None) -> ModelArtifactMeta | None:
        entries = self._entries.get(model_id)
        if not entries:
            return None
        if version:
            for e in entries:
                if e.version == version:
                    return e
            return None
        return entries[-1]

    def get_production(self, model_id: str) -> ModelArtifactMeta | None:
        entries = self._entries.get(model_id)
        if not entries:
            return None
        for e in reversed(entries):
            if e.stage == "production":
                return e
        return None

    def promote(self, model_id: str, version: str, stage: str = "production") -> bool:
        entry = self.get(model_id, version)
        if not entry:
            return False
        entry.stage = stage
        logger.info("Model %s v%s promoted to %s", model_id, version, stage)
        return True

    def list_models(self) -> list[str]:
        return list(self._entries.keys())

    def list_versions(self, model_id: str) -> list[ModelArtifactMeta]:
        return self._entries.get(model_id, [])


model_registry_global = ModelRegistry()
