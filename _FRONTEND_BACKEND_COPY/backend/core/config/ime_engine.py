"""Central config loader for the IME decision-support engine.

Single source of truth for all thresholds defined in the v5.0 architecture
document (Appendix ه). Mirrors the dict-based, deep-merge pattern of
``services.signal_decision_engine.SignalPolicy`` so thresholds stay versioned
in YAML and never drift from code defaults.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "config" / "ime_engine_config.yaml"


def _defaults() -> dict[str, Any]:
    """Code fallback — used only when the YAML is missing or unreadable."""
    return {
        "config_version": "1.0.0",
        "engine": "ime_decision_support",
        "data": {
            "staleness_threshold_seconds": 10,
            "delivery_risk_window_days": 3,
            "depth_erosion_factor": 0.30,
        },
        "iv": {
            "search_bounds": [0.01, 5.0],
            "convergence_tolerance": 0.001,
            "max_iterations": 100,
        },
        "surface": {"min_valid_points": 3},
        "sabr": {
            "min_strikes_per_maturity": 5,
            "min_active_maturities": 2,
            "calibration_rmse_threshold": 0.02,
            "stability_window_days": 20,
        },
        "cointegration": {"min_series_length": 250},
        "signal_factory": {
            "calendar_arb_ratio_threshold": 0.95,
            "iv_rank_threshold": 0.80,
            "iv_to_rv_ratio_threshold": 1.3,
            "slippage_to_gross_edge_max_ratio": 0.50,
        },
        "sizing": {
            "half_kelly_min_sample_size": 100,
            "daily_loss_cap_reduction_trigger": 0.50,
        },
        "drift": {"model_drift_sigma_threshold": 2.0, "model_drift_window_trades": 10},
        "disaster_recovery": {"rto_minutes": 15, "rpo_minutes": 5},
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_ime_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the central IME engine config, deep-merging YAML over code defaults."""
    cfg = _defaults()
    target = Path(path) if path else _DEFAULT_PATH
    try:
        import yaml

        with open(target, encoding="utf-8") as f:
            overrides = yaml.safe_load(f)
        if isinstance(overrides, dict):
            _deep_merge(cfg, overrides)
            logger.info("Loaded IME engine config from %s (version=%s)", target, cfg.get("config_version"))
    except Exception as exc:  # pragma: no cover - defensive, same as SignalPolicy
        logger.warning("Failed to load IME engine config from %s: %s — using defaults", target, exc)
    return deepcopy(cfg)


# ── Convenience accessors (fail loudly on typo'd keys, never silently default) ──


def ime_threshold(config: dict[str, Any], *path: str) -> Any:
    """Return a config value by dotted path; raise KeyError if absent."""
    node: Any = config
    for part in path:
        node = node[part]
    return node
