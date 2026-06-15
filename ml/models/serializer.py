from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ModelSerializer:
    def save(self, model: Any, path: str) -> None:
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "wb") as f:
            pickle.dump(model, f)
        logger.debug("Saved model to %s", path)

    def load(self, path: str) -> Any:
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Model not found: {path}")
        with open(path_obj, "rb") as f:
            return pickle.load(f)
