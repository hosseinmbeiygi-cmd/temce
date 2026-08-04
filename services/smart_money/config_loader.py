"""Config-driven Smart Money Engine configuration.

Loads weights, thresholds, phase rules, and normalizer ranges from YAML.
Supports hot-reload and multiple config profiles.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "smart_money.yaml"


@dataclass
class PhaseCondition:
    field_name: str
    operator: str  # >, <, >=, <=, ==, !=
    value: float


@dataclass
class PhaseRule:
    name: str
    priority: int
    label: str
    conditions: list[PhaseCondition]
    logic: str = "all"  # all | any


@dataclass
class SmartMoneyConfig:
    version: str = "2.0.0"
    profile: str = "default"
    analysis_mode: str = "full"

    # Composite weights
    smc_weights: dict[str, float] = field(default_factory=dict)
    acc_weights: dict[str, float] = field(default_factory=dict)
    abs_final_weights: dict[str, float] = field(default_factory=dict)
    fl_weights: dict[str, float] = field(default_factory=dict)
    br_weights: dict[str, float] = field(default_factory=dict)

    # Penalty weights
    penalty_dr_weights: dict[str, float] = field(default_factory=dict)
    penalty_fbr_weights: dict[str, float] = field(default_factory=dict)
    penalty_dc_weights: dict[str, float] = field(default_factory=dict)
    smc_adjustment: dict[str, float] = field(default_factory=dict)

    # Phase rules (sorted by priority)
    phase_rules: list[PhaseRule] = field(default_factory=list)

    # Normalizer ranges
    normalizer_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)

    # Data quality
    data_quality: dict[str, Any] = field(default_factory=dict)

    # Lookback windows
    lookback: dict[str, int] = field(default_factory=dict)

    # Cache
    cache: dict[str, Any] = field(default_factory=dict)

    # Layer weights (raw)
    layer_weights: dict[str, dict[str, float]] = field(default_factory=dict)

    # Metadata
    _loaded_at: float = 0.0
    _file_path: str = ""


_OPERATORS: dict[str, Any] = {
    ">": lambda v, c: v > c,
    ">=": lambda v, c: v >= c,
    "<": lambda v, c: v < c,
    "<=": lambda v, c: v <= c,
    "==": lambda v, c: abs(v - c) < 0.001,
    "!=": lambda v, c: abs(v - c) >= 0.001,
}


def _apply_condition(value: float, cond: PhaseCondition) -> bool:
    op_fn = _OPERATORS.get(cond.operator)
    return op_fn(value, cond.value) if op_fn else False


def load_config(path: str | Path | None = None, reload: bool = False) -> SmartMoneyConfig:
    """Load Smart Money config from YAML file with caching."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        logger.warning("Config file not found at %s — using defaults", config_path)
        return SmartMoneyConfig()

    try:
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("Failed to load config from %s: %s", config_path, exc)
        return SmartMoneyConfig()

    cfg = SmartMoneyConfig()
    cfg._file_path = str(config_path)
    cfg._loaded_at = time.time()

    # Engine metadata
    engine = raw.get("engine", {})
    cfg.version = engine.get("version", "2.0.0")
    cfg.profile = engine.get("profile", "default")
    cfg.analysis_mode = engine.get("analysis_mode", "full")

    # Composite weights
    cw = raw.get("composite_weights", {})
    cfg.smc_weights = cw.get("smc", {"acc": 0.28, "abs_final": 0.27, "fl": 0.20, "br": 0.25})
    cfg.acc_weights = cw.get("accumulation", {})
    cfg.abs_final_weights = cw.get("absorption_final", {})
    cfg.fl_weights = cw.get("float_lock", {})
    cfg.br_weights = cw.get("breakout_readiness", {})

    # Penalties
    pen = raw.get("penalties", {})
    cfg.penalty_dr_weights = pen.get("distribution_risk", {})
    cfg.penalty_fbr_weights = pen.get("fake_breakout_risk", {})
    cfg.penalty_dc_weights = pen.get("dead_compression", {})
    cfg.smc_adjustment = pen.get("smc_adjustment", {"dr": 0.15, "fbr": 0.10, "dc": 0.08})

    # Phase rules
    phases_raw = raw.get("phases", {})
    phase_list = []
    for name, pconf in phases_raw.items():
        conditions = []
        for fname, cconf in pconf.get("conditions", {}).items():
            conditions.append(PhaseCondition(
                field_name=fname,
                operator=cconf.get("op", ">"),
                value=cconf.get("value", 0.0),
            ))
        phase_list.append(PhaseRule(
            name=name,
            priority=pconf.get("priority", 99),
            label=pconf.get("label", name),
            conditions=conditions,
            logic=pconf.get("logic", "all"),
        ))
    cfg.phase_rules = sorted(phase_list, key=lambda r: r.priority)

    # Normalizer ranges
    nr = raw.get("normalizer_ranges", {})
    for key, val in nr.items():
        if isinstance(val, list) and len(val) == 2:
            cfg.normalizer_ranges[key] = (float(val[0]), float(val[1]))

    # Data quality
    cfg.data_quality = raw.get("data_quality", {})

    # Lookback
    cfg.lookback = raw.get("lookback", {"short": 5, "medium": 10, "long": 20, "ahm_window": 5})

    # Cache
    cfg.cache = raw.get("cache", {})

    # Layer weights (raw)
    cfg.layer_weights = raw.get("layer_weights", {})

    logger.info("Smart Money config loaded: version=%s profile=%s", cfg.version, cfg.profile)
    return cfg


def classify_phase_from_config(
    config: SmartMoneyConfig,
    scores: dict[str, float],
) -> str:
    """Classify phase using config-driven rules instead of hard-coded conditions.

    Optimized: short-circuits evaluation and avoids list allocation.
    """
    for rule in config.phase_rules:
        if not rule.conditions:
            continue

        if rule.logic == "all":
            # AND logic: all conditions must match
            if all(
                _apply_condition(scores.get(c.field_name, 0.0), c)
                for c in rule.conditions
            ):
                return rule.name
        elif rule.logic == "any":
            # OR logic: any condition matches
            if any(
                _apply_condition(scores.get(c.field_name, 0.0), c)
                for c in rule.conditions
            ):
                return rule.name

    return "neutral"


def compute_weighted_score(config: SmartMoneyConfig, weights: dict[str, float], features: dict[str, float]) -> float:
    """Compute a weighted score from features using config-driven weights."""
    score = 0.0
    total_weight = 0.0
    for key, weight in weights.items():
        val = features.get(key, 0.0)
        score += weight * val
        total_weight += weight

    # Normalize if weights don't sum to 1
    if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
        score /= total_weight

    return min(1.0, max(0.0, score))
