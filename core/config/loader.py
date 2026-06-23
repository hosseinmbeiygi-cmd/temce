from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from core.logging import get_logger
from core.paths import safe_resolve

logger = get_logger(__name__)


class ConfigLoader:
    def __init__(self, config_dir: str | Path = "./config") -> None:
        self.config_dir = safe_resolve(Path.cwd(), str(config_dir))

    def load_yaml(self, name: str) -> dict[str, Any]:
        path = safe_resolve(self.config_dir, f"{name}.yaml")
        if not path.exists():
            path = safe_resolve(self.config_dir, f"{name}.yml")
        if not path.exists():
            logger.warning("Config file not found: %s", path)
            return {}
        with open(str(path), encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_json(self, name: str) -> dict[str, Any]:
        import json

        path = safe_resolve(self.config_dir, f"{name}.json")
        if not path.exists():
            return {}
        with open(str(path), encoding="utf-8") as f:
            return json.load(f)

    def load_from_env(self, prefix: str = "") -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in os.environ.items():
            if prefix and not key.startswith(prefix):
                continue
            result[key] = value
        return result

    def merge(self, *configs: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for cfg in configs:
            merged.update(cfg)
        return merged

    def apply_to(self, model: BaseModel, data: dict[str, Any]) -> BaseModel:
        return model.model_validate(data)
