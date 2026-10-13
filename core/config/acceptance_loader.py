"""Acceptance gate for the Gold Engine specification (``acceptance.yaml``).

Single source of truth for the production gate:

* which market rules apply to each gold instrument (currency, risk-free rate,
  trading-day count, spread model, annualisation factor), and
* whether a walk-forward result is allowed to go live.

The configuration lives at the repository root as ``acceptance.yaml``
(spec v1.0, 2026-10-13). Nothing here reads or logs environment/secret files.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

ACCEPTANCE_FILENAME = "acceptance.yaml"

# ``core/config/acceptance_loader.py`` -> parents[2] is the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[2]

_REQUIRED_INSTRUMENT_KEYS = (
    "currency",
    "risk_free_rate",
    "trading_days_per_year",
    "spread_model",
)

# Canonical metric -> accepted aliases in a walk-forward metrics payload.
# The walk-forward optimizer emits ``walk_forward_efficiency`` and embeds the
# DSR block separately, so both spellings are accepted.
_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "wfe": ("wfe", "walk_forward_efficiency"),
    "dsr": ("dsr", "deflated_sharpe"),
    "oos_sharpe": ("oos_sharpe", "avg_oos_sharpe", "sharpe"),
    "max_drawdown": ("max_drawdown", "max_dd"),
    "profit_factor": ("profit_factor",),
    "trade_count": ("trade_count", "total_trades", "trades"),
}


def acceptance_config_path() -> Path:
    """Filesystem path of the acceptance configuration."""
    return _REPO_ROOT / ACCEPTANCE_FILENAME


def _validate(config: dict[str, Any]) -> None:
    """Light schema validation so a malformed config fails loudly."""
    for key in ("version", "asset_class", "market_rules", "thresholds"):
        if key not in config:
            raise ValueError(f"acceptance config missing required key '{key}'")

    gold = config["market_rules"].get("gold")
    if not isinstance(gold, dict) or not gold:
        raise ValueError("acceptance config must define market_rules.gold")

    for instrument, rules in gold.items():
        missing = [k for k in _REQUIRED_INSTRUMENT_KEYS if k not in rules]
        if missing:
            raise ValueError(f"market_rules.gold.{instrument} missing keys: {missing}")

    thresholds = config["thresholds"]
    for section in ("walk_forward", "risk_management"):
        if not isinstance(thresholds.get(section), dict):
            raise ValueError(f"acceptance config missing thresholds.{section}")


@lru_cache(maxsize=8)
def _load(path_str: str) -> dict[str, Any]:
    import yaml  # local import: PyYAML is an optional runtime dependency

    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"acceptance config not found: {path}")

    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level")

    _validate(raw)
    return raw


def get_acceptance_config(path: str | Path | None = None) -> dict[str, Any]:
    """Return the validated acceptance configuration (cached per path)."""
    resolved = Path(path) if path is not None else acceptance_config_path()
    return _load(str(resolved))


def get_gold_market_rules(instrument: str) -> dict[str, Any]:
    """Market rules for a single gold instrument.

    Returns the instrument's currency, risk-free rate, trading-day count and
    spread model, plus ``annualization_factor`` (``sqrt(trading_days_per_year)``)
    — the factor that scales a per-period Sharpe into an annual figure
    (252 for XAU/USD, 240 for the domestic IME/ETF instruments).

    Raises ``KeyError`` for an instrument that is not in the gold universe.
    """
    gold = get_acceptance_config()["market_rules"]["gold"]
    if instrument not in gold:
        raise KeyError(f"unknown gold instrument '{instrument}'; known: {sorted(gold)}")

    rules: dict[str, Any] = dict(gold[instrument])
    rules["instrument"] = instrument
    rules["annualization_factor"] = math.sqrt(float(rules["trading_days_per_year"]))
    return rules


def _read_metric(metrics: dict[str, Any], canonical: str) -> tuple[bool, Any]:
    for alias in _METRIC_ALIASES[canonical]:
        if metrics.get(alias) is not None:
            return True, metrics[alias]
    return False, None


def evaluate_acceptance(metrics: dict[str, Any]) -> dict[str, Any]:
    """Gate a walk-forward result against the acceptance thresholds.

    Returns ``{"status": "PASS" | "REJECT", "reasons": [...]}``. Every criterion
    must hold; a metric that cannot be found is a rejection, never a pass.

    Drawdown is accepted in either convention — a fraction (``0.20``) or a
    percentage (``20.0``) — and normalised to a fraction before comparison.
    """
    thresholds = get_acceptance_config()["thresholds"]
    wf = thresholds["walk_forward"]
    rm = thresholds["risk_management"]

    reasons: list[str] = []

    def _number(canonical: str) -> float | None:
        present, value = _read_metric(metrics, canonical)
        if not present:
            aliases = ", ".join(_METRIC_ALIASES[canonical])
            reasons.append(f"missing metric '{canonical}' (looked for: {aliases})")
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            reasons.append(f"metric '{canonical}' is not numeric: {value!r}")
            return None

    wfe = _number("wfe")
    if wfe is not None and wfe < float(wf["min_wfe"]):
        reasons.append(f"WFE {wfe:.3f} < min_wfe {float(wf['min_wfe']):.2f}")

    dsr = _number("dsr")
    if dsr is not None and dsr < float(wf["min_dsr"]):
        reasons.append(f"DSR {dsr:.3f} < min_dsr {float(wf['min_dsr']):.2f}")

    oos_sharpe = _number("oos_sharpe")
    if oos_sharpe is not None and oos_sharpe < float(wf["min_oos_sharpe"]):
        reasons.append(
            f"OOS Sharpe {oos_sharpe:.3f} < min_oos_sharpe {float(wf['min_oos_sharpe']):.2f}"
        )

    max_dd = _number("max_drawdown")
    if max_dd is not None:
        fraction = max_dd / 100.0 if max_dd > 1.0 else max_dd
        if fraction > float(rm["max_drawdown"]):
            reasons.append(
                f"Max Drawdown {fraction:.3f} > max_drawdown {float(rm['max_drawdown']):.2f}"
            )

    profit_factor = _number("profit_factor")
    if profit_factor is not None and profit_factor < float(rm["min_profit_factor"]):
        reasons.append(
            f"Profit Factor {profit_factor:.3f} < min_profit_factor "
            f"{float(rm['min_profit_factor']):.2f}"
        )

    trade_count = _number("trade_count")
    if trade_count is not None and trade_count < int(rm["min_trade_count"]):
        reasons.append(
            f"Trade Count {int(trade_count)} < min_trade_count {int(rm['min_trade_count'])}"
        )

    return {"status": "PASS" if not reasons else "REJECT", "reasons": reasons}
