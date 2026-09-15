from __future__ import annotations

from core.feature_flags import FeatureFlag


class FlagDefinition:
    def __init__(self, name: str, default: bool = False, description: str = "") -> None:
        self.name = name
        self.default = default
        self.description = description
        self._overrides: dict[str, bool] = {}

    def set_override(self, context_id: str, value: bool) -> None:
        self._overrides[context_id] = value

    def clear_override(self, context_id: str) -> None:
        self._overrides.pop(context_id, None)

    def is_enabled(self, context_id: str | None = None) -> bool:
        if context_id and context_id in self._overrides:
            return self._overrides[context_id]
        return FeatureFlag(self.name, self.default).enabled


USE_ML_MODELS = FlagDefinition("use_ml_models", True, "Enable ML model inference")
USE_WEBSOCKET = FlagDefinition("use_websocket", True, "Enable WebSocket connections")
USE_CACHE = FlagDefinition("use_cache", True, "Enable caching layer")
USE_ADVANCED_BACKTEST = FlagDefinition("use_advanced_backtest", False, "Enable advanced backtesting features")
ENABLE_AUDIT = FlagDefinition("enable_audit", True, "Enable audit logging")
ENABLE_SENTRY = FlagDefinition("enable_sentry", False, "Enable Sentry error tracking")
ENABLE_METRICS = FlagDefinition("enable_metrics", True, "Enable metrics collection")
ENABLE_PROVIDER_FAILOVER = FlagDefinition("enable_provider_failover", True, "Enable provider failover")
ENABLE_CIRCUIT_BREAKER = FlagDefinition("enable_circuit_breaker", True, "Enable circuit breaker")
