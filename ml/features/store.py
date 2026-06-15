from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class FeatureStore:
    def __init__(self, base_dir: str = "./data/features") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, features: dict[str, Any]) -> None:
        path = self.base_dir / f"{key}.json"
        with open(path, "w") as f:
            json.dump(features, f)
        logger.debug("Saved features: %s", key)

    def load(self, key: str) -> dict[str, Any] | None:
        path = self.base_dir / f"{key}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)
