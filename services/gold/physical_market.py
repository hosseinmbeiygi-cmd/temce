"""Iran physical-market completeness calculators.

This module is additive to ``physical_arbitrage``: the Phase 1-5 functions and
their published outputs stay unchanged.  Everything here is pure (no DB, no
network, no cache) so the formulas can be verified with hand-computed values.

Conventions:

* prices are IRR per gram unless the parameter name says otherwise;
* fee rates are decimals (``0.0015`` = 0.15%), matching ``IME_EXCHANGE_FEE``;
* assays are fineness values out of 1000 (745, 750, 755, 995, ...).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from services.gold.constants import (
    AED_PEG,
    GERAMI_MINTING_FEE_IRR,
    IME_BULLION_ASSAY,
    IME_EXCHANGE_FEE,
    MIN_NET_SPREAD_PCT,
    PURITY_18K,
)
from services.gold.physical_arbitrage import (
    _canonical_coin_key,
    calculate_coin_bubbles,
)

DEFAULT_ASSAY_SCENARIOS: tuple[int, ...] = tuple(range(745, 756))


def _as_finite_float(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return number


def _require_positive(name: str, value: Any) -> float:
    number = _as_finite_float(name, value)
    if number <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return number


def _require_non_negative(name: str, value: Any) -> float:
    number = _as_finite_float(name, value)
    if number < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")
    return number


def calculate_gram18_from_mesghal_decimal(
    mesghal_price: float | int | str | Decimal,
) -> Decimal:
    """Convert a 17-karat mesghal quote to an 18-karat gram price exactly.

    ``Decimal`` arithmetic avoids the 2-decimal intermediate rounding that a
    float-based implementation can introduce::

        gram18 = mesghal / 4.6083 * (750 / 705)

    The result keeps the caller's Decimal context precision; it is not rounded
    to a fixed number of decimal places.
    """
    try:
        value = Decimal(str(mesghal_price))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(
            f"mesghal_price must be a finite positive number, got {mesghal_price!r}"
        ) from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(
            f"mesghal_price must be a finite positive number, got {mesghal_price!r}"
        )
    return value / Decimal("4.6083") * (Decimal("750") / Decimal("705"))


def calculate_assay_variance_scenarios(
    weight_grams: float,
    base_gram18_price: float,
    assays: Iterable[int] | None = None,
) -> dict[str, Any]:
    """Value a melted-gold position across the 745-755 assay band.

    ``real_weight_gram18 = weight * assay / 750`` and ``value = real_weight *
    base_gram18_price``.  Deltas are measured against the 750 (18-karat)
    reference.  Decimal arithmetic is used so the band is not distorted by
    binary-float rounding before the final float conversion.
    """
    weight = Decimal(str(_require_non_negative("weight_grams", weight_grams)))
    base_price = Decimal(str(_require_positive("base_gram18_price", base_gram18_price)))

    requested = DEFAULT_ASSAY_SCENARIOS if assays is None else assays
    assay_list = sorted({int(assay) for assay in requested})
    if not assay_list:
        raise ValueError("assays must not be empty")
    if any(assay <= 0 for assay in assay_list):
        raise ValueError("assays must be positive")

    base_value = weight * base_price
    scenarios: dict[int, dict[str, float]] = {}
    for assay in assay_list:
        real_weight = weight * Decimal(assay) / Decimal("750")
        value = real_weight * base_price
        delta = value - base_value
        scenarios[assay] = {
            "assay": assay,
            "real_weight_gram18": float(real_weight),
            "value_irr": float(value),
            "delta_vs_750_irr": float(delta),
            "delta_vs_750_pct": float(delta / base_value * Decimal("100")) if base_value else 0.0,
        }

    values = [row["value_irr"] for row in scenarios.values()]
    min_value = min(values)
    max_value = max(values)
    return {
        "weight_grams": float(weight),
        "base_gram18_price_irr": float(base_price),
        "assays": assay_list,
        "scenarios": scenarios,
        "min_assay": assay_list[0],
        "max_assay": assay_list[-1],
        "min_value_irr": min_value,
        "max_value_irr": max_value,
        "range_value_irr": max_value - min_value,
        "range_pct_of_base": (
            (max_value - min_value) / float(base_value) * 100.0 if base_value else 0.0
        ),
    }


def rolling_zscore_percentile(
    history: Sequence[float] | Iterable[float], current: float
) -> dict[str, Any]:
    """Compare ``current`` with a historical sample.

    * ``z_score = (current - mean) / population_std``; ``None`` when there are
      fewer than two observations or the sample has zero variance.
    * ``percentile`` is the share of historical observations at or below
      ``current`` (0-100), so a new high is the 100th percentile.
    * non-finite history entries are ignored rather than poisoning the sample.
    """
    current_value = _as_finite_float("current", current)
    values: list[float] = []
    for item in history:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    sample_size = len(values)
    if sample_size == 0:
        return {
            "sample_size": 0,
            "mean": None,
            "std": None,
            "z_score": None,
            "percentile": None,
        }

    mean = sum(values) / sample_size
    variance = sum((value - mean) ** 2 for value in values) / sample_size
    std = math.sqrt(variance)
    z_score = None if sample_size < 2 or std == 0.0 else (current_value - mean) / std
    percentile = sum(1 for value in values if value <= current_value) / sample_size * 100.0
    return {
        "sample_size": sample_size,
        "mean": mean,
        "std": std,
        "z_score": z_score,
        "percentile": percentile,
    }


def calculate_coin_bubbles_with_history(
    ounce_usd: float,
    usd_irr: float,
    coin_prices: dict[str, float],
    *,
    history_by_coin: Mapping[str, Sequence[float]] | None = None,
    gerami_minting_fee_irr: float = GERAMI_MINTING_FEE_IRR,
) -> dict[str, dict[str, Any]]:
    """All available coin bubbles plus nominal bubble and history statistics.

    The base breakdown comes from :func:`calculate_coin_bubbles` unchanged.
    Additive fields:

    * ``bubble_abs_irr`` - nominal bubble in IRR (market - intrinsic);
    * ``bubble_zscore`` / ``bubble_percentile`` / ``history_sample_size``;
    * ``bubble_history_mean`` / ``bubble_history_std``.

    Missing coin prices are not fabricated; the returned mapping only contains
    coins the caller actually supplied.
    """
    bubbles = calculate_coin_bubbles(
        ounce_usd,
        usd_irr,
        coin_prices,
        gerami_minting_fee_irr=gerami_minting_fee_irr,
    )

    history_map: dict[str, list[float]] = {}
    for raw_key, values in (history_by_coin or {}).items():
        canonical = _canonical_coin_key(str(raw_key))
        if canonical is None or canonical in history_map:
            continue
        history_map[canonical] = list(values or [])

    for coin, row in bubbles.items():
        stats = rolling_zscore_percentile(history_map.get(coin, []), row["bubble_pct"])
        row["bubble_abs_irr"] = row["market_price_irr"] - row["intrinsic_value_irr"]
        row["history_sample_size"] = stats["sample_size"]
        row["bubble_zscore"] = stats["z_score"]
        row["bubble_percentile"] = stats["percentile"]
        row["bubble_history_mean"] = stats["mean"]
        row["bubble_history_std"] = stats["std"]

    return bubbles


def calculate_ime_certificate_spread(
    cert_price_irr: float,
    melted_gram18_price_irr: float,
    *,
    cert_assay: float = IME_BULLION_ASSAY,
    melted_assay: float = PURITY_18K,
    cert_fee_rate: float = IME_EXCHANGE_FEE,
    melted_fee_rate: float = IME_EXCHANGE_FEE,
    quantity_grams: float = 1.0,
    storage_irr_per_gram_per_day: float = 0.0,
    holding_days: int = 0,
    delivery_irr_per_gram: float = 0.0,
    min_net_spread_pct: float = MIN_NET_SPREAD_PCT,
) -> dict[str, Any]:
    """IME 995 certificate vs Tehran 750 melted gold, both directions.

    ``quantity_grams`` is the certificate/fine-equivalent (995) quantity.  The
    physical 750 quantity needed for the same fine gold is
    ``quantity * cert_assay / melted_assay``.  Fees are charged on both legs,
    and storage/delivery are charged per physical gram in both directions.  The
    action is the better of the two directions when its net spread clears
    ``min_net_spread_pct``.
    """
    cert_price = _require_positive("cert_price_irr", cert_price_irr)
    melted_price = _require_positive("melted_gram18_price_irr", melted_gram18_price_irr)
    quantity = _require_positive("quantity_grams", quantity_grams)
    cert_assay_value = _require_positive("cert_assay", cert_assay)
    melted_assay_value = _require_positive("melted_assay", melted_assay)
    cert_fee = _require_non_negative("cert_fee_rate", cert_fee_rate)
    melted_fee = _require_non_negative("melted_fee_rate", melted_fee_rate)
    storage_rate = _require_non_negative(
        "storage_irr_per_gram_per_day", storage_irr_per_gram_per_day
    )
    delivery_rate = _require_non_negative(
        "delivery_irr_per_gram", delivery_irr_per_gram
    )
    threshold = _require_non_negative("min_net_spread_pct", min_net_spread_pct)
    if holding_days is None or int(holding_days) != holding_days or holding_days < 0:
        raise ValueError(f"holding_days must be a non-negative integer, got {holding_days!r}")

    assay_uplift = cert_assay_value / melted_assay_value
    melted_equivalent_grams = quantity * assay_uplift
    cert_notional = cert_price * quantity
    melted_notional = melted_price * melted_equivalent_grams

    cert_fee_irr = cert_notional * cert_fee
    melted_fee_irr = melted_notional * melted_fee
    storage_cost_irr = storage_rate * melted_equivalent_grams * float(holding_days)
    delivery_cost_irr = delivery_rate * melted_equivalent_grams
    total_friction_irr = (
        cert_fee_irr + melted_fee_irr + storage_cost_irr + delivery_cost_irr
    )

    cert_proceeds_irr = cert_notional - cert_fee_irr
    melted_cost_irr = melted_notional + melted_fee_irr
    buy_melted_friction = melted_cost_irr + storage_cost_irr + delivery_cost_irr
    buy_melted_net = cert_proceeds_irr - buy_melted_friction
    buy_melted_pct = (
        buy_melted_net / buy_melted_friction * 100.0 if buy_melted_friction else 0.0
    )

    cert_cost_irr = cert_notional + cert_fee_irr
    melted_proceeds_irr = (
        melted_notional - melted_fee_irr - storage_cost_irr - delivery_cost_irr
    )
    buy_cert_net = melted_proceeds_irr - cert_cost_irr
    buy_cert_pct = buy_cert_net / cert_cost_irr * 100.0 if cert_cost_irr else 0.0

    if buy_melted_pct >= buy_cert_pct and buy_melted_pct >= threshold:
        action = "BUY_MELTED_SELL_IME_CERT"
    elif buy_cert_pct > buy_melted_pct and buy_cert_pct >= threshold:
        action = "BUY_IME_CERT_SELL_MELTED"
    else:
        action = "NO_ARBITRAGE"

    return {
        "cert_price_irr": cert_price,
        "melted_gram18_price_irr": melted_price,
        "cert_assay": cert_assay_value,
        "melted_assay": melted_assay_value,
        "assay_uplift": assay_uplift,
        "quantity_grams": quantity,
        "melted_equivalent_grams": melted_equivalent_grams,
        "cert_notional_irr": cert_notional,
        "melted_notional_irr": melted_notional,
        "cert_fee_rate": cert_fee,
        "melted_fee_rate": melted_fee,
        "cert_fee_irr": cert_fee_irr,
        "melted_fee_irr": melted_fee_irr,
        "storage_cost_irr": storage_cost_irr,
        "delivery_cost_irr": delivery_cost_irr,
        "total_friction_irr": total_friction_irr,
        "buy_melted_sell_cert": {
            "cert_proceeds_irr": cert_proceeds_irr,
            "melted_cost_irr": melted_cost_irr,
            "storage_cost_irr": storage_cost_irr,
            "delivery_cost_irr": delivery_cost_irr,
            "net_spread_irr": buy_melted_net,
            "net_spread_pct": buy_melted_pct,
        },
        "buy_cert_sell_melted": {
            "cert_cost_irr": cert_cost_irr,
            "melted_proceeds_irr": melted_proceeds_irr,
            "storage_cost_irr": storage_cost_irr,
            "delivery_cost_irr": delivery_cost_irr,
            "net_spread_irr": buy_cert_net,
            "net_spread_pct": buy_cert_pct,
        },
        "min_net_spread_pct": threshold,
        "action": action,
        "is_profitable": action != "NO_ARBITRAGE",
    }


def _limit_check(projected_grams: float, limit_grams: float | None) -> dict[str, Any]:
    if limit_grams is None:
        return {
            "configured": False,
            "limit_grams": None,
            "utilization_pct": None,
            "status": "not_configured",
        }
    limit = _require_positive("limit_grams", limit_grams)
    return {
        "configured": True,
        "limit_grams": limit,
        "utilization_pct": projected_grams / limit * 100.0,
        "status": "ok" if projected_grams <= limit else "breach",
    }


def validate_ime_position_limit(
    quantity_grams: float,
    *,
    current_position_grams: float = 0.0,
    position_limit_grams: float | None = None,
    ownership_limit_grams: float | None = None,
) -> dict[str, Any]:
    """Check a proposed IME certificate quantity against configured limits.

    Limits are arguments, not constants.  Callers load them from
    ``config/ime_engine_config.yaml`` (``physical_market`` section).  When a
    limit is ``None`` it is reported as ``not_configured`` rather than treated
    as a guessed regulatory value.
    """
    quantity = _require_positive("quantity_grams", quantity_grams)
    current = _require_non_negative(
        "current_position_grams", current_position_grams
    )
    projected = current + quantity

    position = _limit_check(projected, position_limit_grams)
    ownership = _limit_check(projected, ownership_limit_grams)

    violations = [
        name
        for name, check in (("position", position), ("ownership", ownership))
        if check["status"] == "breach"
    ]
    configured = position["configured"] or ownership["configured"]
    if not configured:
        ok: bool | None = None
        status = "not_configured"
    elif violations:
        ok = False
        status = "breach"
    else:
        ok = True
        status = "ok"

    return {
        "ok": ok,
        "status": status,
        "quantity_grams": quantity,
        "current_position_grams": current,
        "projected_grams": projected,
        "position": position,
        "ownership": ownership,
        "violations": violations,
    }


def aed_hawala_spread(usd_irt: float, aed_irt: float) -> dict[str, Any]:
    """Tehran USD vs the AED hawala-implied USD (``AED * 3.6725``)."""
    usd = _require_positive("usd_irt", usd_irt)
    aed = _require_positive("aed_irt", aed_irt)
    parity = aed * AED_PEG
    spread = usd - parity
    return {
        "usd_irt": usd,
        "aed_irt": aed,
        "parity_usd_irr": parity,
        "spread_irr": spread,
        "spread_pct": spread / parity * 100.0,
    }


def evaluate_aed_hawala_alert(
    history_pct: Sequence[float] | Iterable[float],
    current_pct: float,
    *,
    alert_zscore: float | None,
) -> dict[str, Any]:
    """Add an alert flag to the AED hawala spread z-score.

    ``alert_zscore`` comes from config.  ``None`` disables alerting without
    inventing a threshold.
    """
    threshold = (
        None
        if alert_zscore is None
        else _require_non_negative("alert_zscore", alert_zscore)
    )
    stats = rolling_zscore_percentile(history_pct, current_pct)
    z_score = stats["z_score"]
    alert = bool(
        z_score is not None and threshold is not None and abs(z_score) >= threshold
    )
    return {**stats, "alert": alert, "alert_zscore": threshold}


__all__ = [
    "DEFAULT_ASSAY_SCENARIOS",
    "aed_hawala_spread",
    "calculate_assay_variance_scenarios",
    "calculate_coin_bubbles_with_history",
    "calculate_gram18_from_mesghal_decimal",
    "calculate_ime_certificate_spread",
    "evaluate_aed_hawala_alert",
    "rolling_zscore_percentile",
    "validate_ime_position_limit",
]
