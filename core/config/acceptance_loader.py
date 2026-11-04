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

# ── سند دستیار طلا/نقره: بخش‌های ۲۰، ۲۶، ۲۷.۱ و ۲۷.۳ ──────────────────────

#: §۲۷.۱ — هر ابزار باید تعرفهٔ خودش را اعلام کند؛ «غایب» با «صفر» یکی نیست.
FEE_INSTRUMENTS: tuple[str, ...] = (
    "commodity_fund",
    "coin_certificate",
    "bullion_certificate",
    "futures",
    "option",
)

_FEE_TERM_KEYS = ("label_fa", "fee_per_side", "fee_cap_irr", "tax_exempt", "provenance")
_SESSION_KEYS = ("pre_open", "open", "close")
_TEST_SESSIONS = ("sat_to_wed", "thursday")

#: منشأ هر عدد: صریح در سند / فرض منتظر تأیید / عدد قابل‌اتکا پیدا نشد.
PROVENANCE_VALUES = frozenset({"spec", "assumption", "unavailable"})

_TOP_LEVEL_REQUIRED = (
    "version",
    "asset_class",
    "market_rules",
    "thresholds",
    "fee_schedule",
    "signal_filter",
    "market_hours",
)


def acceptance_config_path() -> Path:
    """Filesystem path of the acceptance configuration."""
    return _REPO_ROOT / ACCEPTANCE_FILENAME


def _validate_clock(value: Any, where: str) -> None:
    """``"HH:MM"`` در بازهٔ ۲۴ ساعت، وگرنه خطای صریح."""
    text = str(value)
    parts = text.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"{where} must be 'HH:MM', got {value!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"{where} is out of range: {value!r}")


def _validate_provenance(value: Any, where: str) -> None:
    if value not in PROVENANCE_VALUES:
        raise ValueError(
            f"{where} must be one of {sorted(PROVENANCE_VALUES)}, got {value!r}"
        )


def _validate_fee_schedule(config: dict[str, Any]) -> None:
    """§۲۷.۱ — هر ابزار تعرفهٔ خودش را دارد و عدد ناموجود باید ``None`` بماند."""
    schedule = config["fee_schedule"]
    for key in ("version", "last_updated", "instruments"):
        if key not in schedule:
            raise ValueError(f"fee_schedule missing required key '{key}'")

    instruments = schedule["instruments"]
    if not isinstance(instruments, dict):
        raise ValueError("fee_schedule.instruments must be a mapping")

    missing = [k for k in FEE_INSTRUMENTS if k not in instruments]
    if missing:
        raise ValueError(f"fee_schedule.instruments missing: {missing}")

    for name, terms in instruments.items():
        missing_keys = [k for k in _FEE_TERM_KEYS if k not in terms]
        if missing_keys:
            raise ValueError(f"fee_schedule.instruments.{name} missing keys: {missing_keys}")
        fee = terms["fee_per_side"]
        if fee is not None:
            # صفر یک نرخ جعلی می‌سازد؛ عدد ناموجود باید None باشد، نه 0.
            if not isinstance(fee, (int, float)) or not 0.0 < float(fee) < 1.0:
                raise ValueError(
                    f"fee_schedule.instruments.{name}.fee_per_side must be null or in (0,1): {fee!r}"
                )
        _validate_provenance(terms["provenance"], f"fee_schedule.instruments.{name}.provenance")


def _validate_signal_filter(config: dict[str, Any]) -> None:
    """§۲۶ — آستانه‌ها باید مثبت باشند و منشأشان مشخص باشد."""
    flt = config["signal_filter"]
    for key in ("min_net_profit_pct", "min_risk_reward", "require_positive_ev", "provenance"):
        if key not in flt:
            raise ValueError(f"signal_filter missing required key '{key}'")

    for key in ("min_net_profit_pct", "min_risk_reward"):
        value = flt[key]
        if not isinstance(value, (int, float)) or float(value) <= 0:
            raise ValueError(f"signal_filter.{key} must be a positive number, got {value!r}")

    provenance = flt["provenance"]
    if not isinstance(provenance, dict):
        raise ValueError("signal_filter.provenance must be a mapping")
    for key in ("min_net_profit_pct", "min_risk_reward"):
        if key not in provenance:
            raise ValueError(f"signal_filter.provenance missing key '{key}'")
        _validate_provenance(provenance[key], f"signal_filter.provenance.{key}")


def _validate_market_hours(config: dict[str, Any]) -> None:
    """§۲۷.۳ — ساعت‌ها، دامنه و تسویه باید کامل و خوانا باشند."""
    hours = config["market_hours"]
    for key in (
        *_TEST_SESSIONS,
        "friday_closed",
        "price_band_pct",
        "emergency_band_pcts",
        "settlement_days",
        "provenance",
    ):
        if key not in hours:
            raise ValueError(f"market_hours missing required key '{key}'")

    for session in _TEST_SESSIONS:
        block = hours[session]
        if not isinstance(block, dict):
            raise ValueError(f"market_hours.{session} must be a mapping")
        missing = [k for k in _SESSION_KEYS if k not in block]
        if missing:
            raise ValueError(f"market_hours.{session} missing keys: {missing}")
        for key in _SESSION_KEYS:
            _validate_clock(block[key], f"market_hours.{session}.{key}")

    if not isinstance(hours["emergency_band_pcts"], list) or not hours["emergency_band_pcts"]:
        raise ValueError("market_hours.emergency_band_pcts must be a non-empty list")
    if float(hours["price_band_pct"]) <= 0:
        raise ValueError(
            f"market_hours.price_band_pct must be positive, got {hours['price_band_pct']!r}"
        )
    if int(hours["settlement_days"]) < 0:
        raise ValueError(f"market_hours.settlement_days must be >= 0, got {hours['settlement_days']!r}")
    _validate_provenance(hours["provenance"], "market_hours.provenance")


def _validate(config: dict[str, Any]) -> None:
    """Light schema validation so a malformed config fails loudly."""
    for key in _TOP_LEVEL_REQUIRED:
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

    _validate_fee_schedule(config)
    _validate_signal_filter(config)
    _validate_market_hours(config)


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

    try:
        _validate(raw)
    except ValueError as err:
        # Always name the offending file: the path is a parameter, so a bare key
        # path would not say which config is malformed.
        raise ValueError(f"{path} is not a valid acceptance config: {err}") from err

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


# ── Walk-forward wiring ──────────────────────────────────────────────────────

# Threshold key -> the raw field of the walk-forward output it is judged
# against. ``evaluate_walk_forward_result`` emits one row per threshold so the
# verdict stays auditable against the raw result (RELIABILITY_REPORT item 8:
# every threshold must reference a specific part of the raw output).
WALK_FORWARD_METRIC_SOURCES: dict[str, str] = {
    "min_wfe": "walk_forward_efficiency",
    "min_dsr": "deflated_sharpe.deflated_sharpe",
    "min_oos_sharpe": "avg_oos_sharpe",
    "max_drawdown": "max(oos_results[*].max_dd)",
    "min_profit_factor": "profit_factor",
    "min_trade_count": "sum(oos_results[*].trades)",
}

# (threshold key, section, canonical metric, comparison, label)
_CRITERIA: tuple[tuple[str, str, str, str, str], ...] = (
    ("min_wfe", "walk_forward", "wfe", ">=", "WFE"),
    ("min_dsr", "walk_forward", "dsr", ">=", "DSR"),
    ("min_oos_sharpe", "walk_forward", "oos_sharpe", ">=", "OOS Sharpe"),
    ("max_drawdown", "risk_management", "max_drawdown", "<=", "Max Drawdown"),
    ("min_profit_factor", "risk_management", "profit_factor", ">=", "Profit Factor"),
    ("min_trade_count", "risk_management", "trade_count", ">=", "Trade Count"),
)


def walk_forward_metrics(result: dict[str, Any]) -> dict[str, Any]:
    """Flatten a ``WalkForwardOptimizer`` result into the gate's metric payload.

    The gate compares scalars, while the raw result nests the DSR block and
    keeps one row per fold under ``oos_results``. Aggregation mirrors how the
    raw result is meant to be read: the worst fold's drawdown, the summed trade
    count, and a profit factor built from the summed gross profit/loss.

    A fold set with no losing round trip has no finite profit factor. The gate
    is handed an infinite one so the criterion can pass, while the serialised
    result keeps ``None`` instead of the non-standard JSON value ``Infinity``.
    """
    dsr_block = result.get("deflated_sharpe")
    dsr = dsr_block.get("deflated_sharpe") if isinstance(dsr_block, dict) else dsr_block

    folds = [f for f in (result.get("oos_results") or []) if isinstance(f, dict)]
    drawdowns = [f["max_dd"] for f in folds if f.get("max_dd") is not None]
    trade_counts = [f["trades"] for f in folds if f.get("trades") is not None]
    gross_profit = sum(f.get("gross_profit") or 0.0 for f in folds)
    gross_loss = sum(f.get("gross_loss") or 0.0 for f in folds)

    profit_factor = result.get("profit_factor")
    if profit_factor is None and gross_loss <= 0.0 < gross_profit:
        profit_factor = math.inf

    return {
        "wfe": result.get("walk_forward_efficiency"),
        "dsr": dsr,
        "oos_sharpe": result.get("avg_oos_sharpe"),
        "max_drawdown": max(drawdowns) if drawdowns else None,
        "profit_factor": profit_factor,
        "trade_count": sum(trade_counts) if trade_counts else None,
    }


def _json_scalar(value: Any) -> Any:
    """JSON-safe scalar: non-finite numbers become ``None``, never ``Infinity``."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _threshold_rows(metrics: dict[str, Any], thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    """One evidence row per threshold, naming the raw field it was judged on."""
    rows: list[dict[str, Any]] = []

    for key, section, metric, comparison, label in _CRITERIA:
        limit = thresholds[section][key]
        row: dict[str, Any] = {
            "threshold": key,
            "section": section,
            "metric": metric,
            "source": WALK_FORWARD_METRIC_SOURCES[key],
            "limit": limit,
            "comparison": comparison,
            "value": None,
            "passed": False,
        }

        present, raw = _read_metric(metrics, metric)
        if not present:
            row["detail"] = f"{label} is absent from the walk-forward output"
            rows.append(row)
            continue

        try:
            value = float(raw)
        except (TypeError, ValueError):
            row["detail"] = f"{label} is not numeric: {raw!r}"
            rows.append(row)
            continue

        comparable = value
        if metric == "max_drawdown":
            # The gate accepts a fraction or a percentage; report what was compared.
            comparable = round(value / 100.0, 6) if value > 1.0 else value
            row["observed"] = _json_scalar(value)

        passed = comparable >= float(limit) if comparison == ">=" else comparable <= float(limit)
        row["value"] = _json_scalar(round(comparable, 6))
        row["passed"] = passed
        row["detail"] = f"{label} {comparable:g} {comparison} {limit}{'' if passed else ' — breached'}"
        rows.append(row)

    return rows


# ── سند دستیار طلا و نقره: دسترسگرها (بخش‌های ۲۰، ۲۶، ۲۷.۱، ۲۷.۳) ────────


def get_fee_schedule(path: str | Path | None = None) -> dict[str, Any]:
    """§۲۷.۱ — جدول تعرفهٔ نسخه‌دار به‌همراه کارمزد رفت‌وبرگشت هر ابزار.

    ``round_trip_fee_per_side`` فقط وقتی عدد می‌گیرد که هر دو سمت نرخ داشته باشند؛
    ابزاری که نرخش «ناموجود» است ``None`` می‌ماند و صفر نمی‌شود، چون صفر یک
    هزینهٔ جعلی می‌سازد.
    """
    schedule = get_acceptance_config(path)["fee_schedule"]
    instruments: dict[str, Any] = {}
    for name, terms in schedule["instruments"].items():
        row = dict(terms)
        fee = row["fee_per_side"]
        row["round_trip_fee_per_side"] = None if fee is None else float(fee) * 2.0
        instruments[name] = row

    return {
        "version": schedule["version"],
        "last_updated": schedule["last_updated"],
        "instruments": instruments,
    }


def get_fee_terms(instrument: str, path: str | Path | None = None) -> dict[str, Any]:
    """تعرفهٔ یک ابزار. برای ابزاری خارج از فهرست، ``KeyError`` می‌دهد."""
    schedule = get_fee_schedule(path)
    if instrument not in schedule["instruments"]:
        raise KeyError(
            f"unknown fee instrument '{instrument}'; known: {sorted(schedule['instruments'])}"
        )
    return dict(schedule["instruments"][instrument])


def get_signal_filter(path: str | Path | None = None) -> dict[str, Any]:
    """§۲۶ — آستانه‌های فیلتر ارزش معامله (سود خالص، ریسک/ریوارد، الزام EV مثبت)."""
    return dict(get_acceptance_config(path)["signal_filter"])


def get_market_hours(path: str | Path | None = None) -> dict[str, Any]:
    """§۲۷.۳ — ساعت جلسه‌ها، دامنهٔ نوسان، دامنه‌های اضطراری و روزهای تسویه."""
    return dict(get_acceptance_config(path)["market_hours"])


def get_assistant_rules(path: str | Path | None = None) -> dict[str, Any]:
    """بسته‌ٔ کامل قواعد دستیار برای مصرف API و صفحه‌های طلا/نقره.

    همین یک فراخوانی، تنها منبع اعداد فرانت‌اند است تا هیچ نرخی در کامپوننت
    هاردکد نشود.
    """
    return {
        "version": get_acceptance_config(path)["version"],
        "fee_schedule": get_fee_schedule(path),
        "signal_filter": get_signal_filter(path),
        "market_hours": get_market_hours(path),
    }


def required_gross_move_pct(
    target_net_pct: float,
    buy_fee_pct: float,
    sell_fee_pct: float,
    spread_pct: float = 0.0,
    slippage_pct: float = 0.0,
    other_pct: float = 0.0,
) -> float:
    """§۲۰ — کمترین حرکت ناخالص لازم: ``g* = هدف + c_buy + c_sell + s + ℓ``.

    همهٔ ورودی‌ها به درصدند (نه کسر) تا با واحدهای جدول تعرفهٔ §۲۷.۱ هم‌خوان باشند.
    """
    return target_net_pct + buy_fee_pct + sell_fee_pct + spread_pct + slippage_pct + other_pct


def evaluate_walk_forward_result(result: dict[str, Any]) -> dict[str, Any]:
    """Gate a raw walk-forward result and record the evidence per threshold.

    Returns ``{"spec_version", "status", "reasons", "thresholds"}``. ``status``
    and ``reasons`` come from :func:`evaluate_acceptance` — the single gate
    authority — while ``thresholds`` carries one row per ``acceptance.yaml``
    threshold naming the raw field it was judged against, the observed value and
    the configured limit, so the verdict can be audited against the raw output.
    """
    config = get_acceptance_config()
    metrics = walk_forward_metrics(result)
    verdict = evaluate_acceptance(metrics)

    return {
        "spec_version": config["version"],
        "status": verdict["status"],
        "reasons": verdict["reasons"],
        "thresholds": _threshold_rows(metrics, config["thresholds"]),
    }
