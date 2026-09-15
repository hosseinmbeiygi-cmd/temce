from __future__ import annotations

DEFAULT_FLAGS: dict[str, bool] = {
    "use_ml_models": True,
    "use_websocket": True,
    "use_cache": True,
    "use_advanced_backtest": False,
    "enable_audit": True,
    "enable_sentry": False,
    "enable_metrics": True,
    "enable_provider_failover": True,
    "enable_auto_retry": True,
    "enable_rate_limiting": True,
    "enable_circuit_breaker": True,
    "enable_telemetry": False,
    "enable_profiling": False,
    "use_async_database": True,
    "enable_request_logging": True,
    "enable_websocket_compression": False,
}


def get_default_flag(name: str) -> bool:
    return DEFAULT_FLAGS.get(name, False)
