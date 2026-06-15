from __future__ import annotations

from core.feature_flags import get_feature_flags
from core.feature_flags.flags import (
    ENABLE_AUDIT,
    ENABLE_CIRCUIT_BREAKER,
    ENABLE_METRICS,
    ENABLE_PROVIDER_FAILOVER,
    ENABLE_SENTRY,
    USE_ADVANCED_BACKTEST,
    USE_CACHE,
    USE_ML_MODELS,
    USE_WEBSOCKET,
    FlagDefinition,
)
from core.logging import get_logger

logger = get_logger(__name__)


class FeatureFlagManager:
    def __init__(self) -> None:
        self._flags: dict[str, FlagDefinition] = {}
        self._initialized = False

    def register(self, flag: FlagDefinition) -> None:
        self._flags[flag.name] = flag
        logger.debug("Registered feature flag: %s", flag.name)

    def is_enabled(self, name: str, context_id: str | None = None) -> bool:
        flag = self._flags.get(name)
        if flag is None:
            return get_feature_flags().is_enabled(name)
        return flag.is_enabled(context_id)

    def enable(self, name: str) -> None:
        if name in self._flags:
            self._flags[name].set_override("global", True)

    def disable(self, name: str) -> None:
        if name in self._flags:
            self._flags[name].set_override("global", False)

    def set_override(self, name: str, context_id: str, value: bool) -> None:
        if name in self._flags:
            self._flags[name].set_override(context_id, value)

    def clear_override(self, name: str, context_id: str) -> None:
        if name in self._flags:
            self._flags[name].clear_override(context_id)

    def all_flags(self) -> dict[str, bool]:
        return {name: self.is_enabled(name) for name in self._flags}

    def initialize(self) -> None:
        if self._initialized:
            return
        flags = [
            USE_ML_MODELS,
            USE_WEBSOCKET,
            USE_CACHE,
            USE_ADVANCED_BACKTEST,
            ENABLE_AUDIT,
            ENABLE_SENTRY,
            ENABLE_METRICS,
            ENABLE_PROVIDER_FAILOVER,
            ENABLE_CIRCUIT_BREAKER,
        ]
        for flag in flags:
            self.register(flag)
        self._initialized = True


manager = FeatureFlagManager()
