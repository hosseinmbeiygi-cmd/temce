from __future__ import annotations

import os
from typing import Any


class FeatureFlag:
    def __init__(self, name: str = "", default: bool = False) -> None:
        self.name = name
        self.default = default
        self._overrides: dict[str, bool] = {}
        self._flags: dict[str, bool] = {}

    @property
    def enabled(self) -> bool:
        env_val = os.environ.get(f"FF_{self.name.upper()}")
        if env_val is not None:
            return env_val.lower() in ("1", "true", "yes", "on")
        return self.default

    def __bool__(self) -> bool:
        return self.enabled

    def is_enabled(self, name: str) -> bool:
        if name in self._overrides:
            return self._overrides[name]
        if name in self._flags:
            return self._flags[name]
        env_val = os.environ.get(f"FF_{name.upper()}")
        if env_val is not None:
            return env_val.lower() in ("1", "true", "yes", "on")
        return False

    def enable(self, name: str) -> None:
        self._flags[name] = True

    def disable(self, name: str) -> None:
        self._flags[name] = False

    def override(self, name: str, value: bool) -> _OverrideContext:
        return _OverrideContext(self, name, value)

    def list_flags(self) -> dict[str, bool]:
        result = dict(self._flags)
        result.update(self._overrides)
        return result


class _OverrideContext:
    def __init__(self, ff: FeatureFlag, name: str, value: bool) -> None:
        self.ff = ff
        self.name = name
        self.value = value
        self._previous: bool | None = None

    def __enter__(self) -> _OverrideContext:
        self._previous = self.ff._overrides.get(self.name)
        self.ff._overrides[self.name] = self.value
        return self

    def __exit__(self, *args: Any) -> None:
        if self._previous is not None:
            self.ff._overrides[self.name] = self._previous
        else:
            self.ff._overrides.pop(self.name, None)


class FeatureFlags:
    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}

    def add(self, name: str, default: bool = False) -> FeatureFlag:
        flag = FeatureFlag(name, default)
        self._flags[name] = flag
        return flag

    def is_enabled(self, name: str) -> bool:
        flag = self._flags.get(name)
        if flag is None:
            return False
        return flag.enabled

    def get(self, name: str) -> FeatureFlag | None:
        return self._flags.get(name)

    def all(self) -> dict[str, bool]:
        return {name: flag.enabled for name, flag in self._flags.items()}


_flags = FeatureFlags()

USE_ML_MODELS = _flags.add("use_ml_models", default=True)
USE_WEBSOCKET = _flags.add("use_websocket", default=True)
USE_CACHE = _flags.add("use_cache", default=True)
USE_ADVANCED_BACKTEST = _flags.add("use_advanced_backtest", default=False)
ENABLE_AUDIT = _flags.add("enable_audit", default=True)
ENABLE_SENTRY = _flags.add("enable_sentry", default=False)
ENABLE_METRICS = _flags.add("enable_metrics", default=True)


def get_feature_flags() -> FeatureFlags:
    return _flags
