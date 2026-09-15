from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.paths import safe_resolve

logger = get_logger(__name__)


class FeatureStore:
    def __init__(self, base_dir: str = "./data/features") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, features: dict[str, Any]) -> None:
        path = safe_resolve(self.base_dir, f"{key}.json")
        path.write_text(json.dumps(features), encoding="utf-8")
        logger.debug("Saved features: %s", key)

    def load(self, key: str) -> dict[str, Any] | None:
        path = safe_resolve(self.base_dir, f"{key}.json")
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
