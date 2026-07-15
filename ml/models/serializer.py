from __future__ import annotations

import pickle
from typing import Any

from core.logging import get_logger
from core.paths import validate_safe_path

logger = get_logger(__name__)


class ModelSerializer:
    def save(self, model: Any, path: str) -> None:
        safe = validate_safe_path(path)
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_bytes(pickle.dumps(model))
        logger.debug("Saved model to %s", safe)

    def load(self, path: str) -> Any:
        safe = validate_safe_path(path)
        if not safe.exists():
            raise FileNotFoundError(f"Model not found: {path}")
        return pickle.loads(safe.read_bytes())
