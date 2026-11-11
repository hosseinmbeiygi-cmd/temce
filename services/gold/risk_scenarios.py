"""Gold portfolio stress testing for the Iranian market.

The engine is deliberately pure: callers pass positions and equity, and the
function returns scenario P&L, margin pressure and concentration statistics.
It never reads a database or a provider.

Exposure convention
-------------------
``exposure_irr`` is the position's current market exposure in IRR. For an
option, ``delta`` converts that exposure to underlying-equivalent exposure and
``vega_irr_per_vol_point`` adds the IRR P&L for a one-point change in implied
volatility (``0.01`` means one volatility point).

Scenario shocks are decimal returns: ``0.10`` means +10%.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

ASSET_TYPES = (
    "gold",
    "coin",
    "fund",
    "etf",
    "certificate",
    "futures",
    "option",
    "fx",
    "cash",
    "other",
)

DIRECTIONS = ("long", "short")


@dataclass(frozen=True)
class GoldRiskScenario:
    """One named set of market shocks."""

    scenario_id: str
    name_fa: str
    name_en: str
    description_fa: str
    shocks: Mapping[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name_fa": self.name_fa,
            "name_en": self.name_en,
            "description_fa": self.description_fa,
            "shocks": dict(self.shocks),
        }


GOLD_RISK_SCENARIOS: tuple[GoldRiskScenario, ...] = (
    GoldRiskScenario(
        scenario_id="usd_spike",
        name_fa="جهش دلار",
        name_en="USD spike",
        description_fa="افزایش ۱۵٪ دلار آزاد با انتقال محدود به طلای داخلی.",
        shocks={
            "xau_usd_pct": 0.0,
            "usd_irr_pct": 0.15,
            "local_premium_pct": 0.02,
            "fund_discount_pct": 0.0,
            "volatility_points": 0.03,
            "liquidity_haircut_pct": 0.0,
        },
    ),
    GoldRiskScenario(
        scenario_id="global_gold_selloff",
        name_fa="ریزش جهانی طلا",
        name_en="Global gold selloff",
        description_fa="ریزش ۱۰٪ اونس جهانی با جبران جزئی از سوی دلار.",
        shocks={
            "xau_usd_pct": -0.10,
            "usd_irr_pct": 0.03,
            "local_premium_pct": -0.01,
            "fund_discount_pct": 0.0,
            "volatility_points": 0.05,
            "liquidity_haircut_pct": 0.01,
        },
    ),
    GoldRiskScenario(
        scenario_id="coin_bubble_unwind",
        name_fa="ترکیدن حباب سکه",
        name_en="Coin bubble unwind",
        description_fa="اصلاح ۱۸٪ حباب سکه هم‌زمان با فشار فروش جهانی.",
        shocks={
            "xau_usd_pct": -0.03,
            "usd_irr_pct": 0.02,
            "local_premium_pct": -0.18,
            "fund_discount_pct": 0.0,
            "volatility_points": 0.08,
            "liquidity_haircut_pct": 0.03,
        },
    ),
    GoldRiskScenario(
        scenario_id="fund_discount_widening",
        name_fa="گشایش تخفیف صندوق‌ها",
        name_en="Fund discount widening",
        description_fa="افزایش ۶٪ تخفیف صندوق‌های طلا نسبت به NAV.",
        shocks={
            "xau_usd_pct": -0.02,
            "usd_irr_pct": 0.01,
            "local_premium_pct": 0.0,
            "fund_discount_pct": -0.06,
            "volatility_points": 0.02,
            "liquidity_haircut_pct": 0.01,
        },
    ),
    GoldRiskScenario(
        scenario_id="stagflation_iran",
        name_fa="رکود تورمی ایران",
        name_en="Iran stagflation",
        description_fa="جهش ۲۰٪ دلار و ۸٪ اونس با رشد تقاضای فیزیکی.",
        shocks={
            "xau_usd_pct": 0.08,
            "usd_irr_pct": 0.20,
            "local_premium_pct": 0.05,
            "fund_discount_pct": 0.01,
            "volatility_points": 0.04,
            "liquidity_haircut_pct": 0.0,
        },
    ),
    GoldRiskScenario(
        scenario_id="liquidity_freeze",
        name_fa="قفل نقدشوندگی",
        name_en="Liquidity freeze",
        description_fa="کاهش عمق بازار، اسپرد گسترده و هزینه خروج ۱۰٪.",
        shocks={
            "xau_usd_pct": -0.05,
            "usd_irr_pct": 0.05,
            "local_premium_pct": -0.08,
            "fund_discount_pct": -0.03,
            "volatility_points": 0.10,
            "liquidity_haircut_pct": 0.10,
        },
    ),
    GoldRiskScenario(
        scenario_id="rate_shock",
        name_fa="شوک نرخ بهره",
        name_en="Rate shock",
        description_fa="افزایش نرخ بهره و ۱۰ واحد رشد نوسان ضمنی.",
        shocks={
            "xau_usd_pct": -0.06,
            "usd_irr_pct": 0.02,
            "local_premium_pct": -0.02,
            "fund_discount_pct": -0.01,
            "volatility_points": 0.10,
            "liquidity_haircut_pct": 0.01,
        },
    ),
    GoldRiskScenario(
        scenario_id="black_swan",
        name_fa="شوک سیاه",
        name_en="Black swan",
        description_fa="ریزش ۱۸٪ اونس، جهش ۲۵٪ دلار و قفل نقدشوندگی.",
        shocks={
            "xau_usd_pct": -0.18,
            "usd_irr_pct": 0.25,
            "local_premium_pct": -0.12,
            "fund_discount_pct": -0.10,
            "volatility_points": 0.20,
            "liquidity_haircut_pct": 0.15,
        },
    ),
)

SCENARIOS_BY_ID = {scenario.scenario_id: scenario for scenario in GOLD_RISK_SCENARIOS}

_SHOCK_KEYS = (
    "xau_usd_pct",
    "usd_irr_pct",
    "local_premium_pct",
    "fund_discount_pct",
    "volatility_points",
    "liquidity_haircut_pct",
)

def _as_float(name: str, value: Any, *, default: float | None = None) -> float:
    if value is None and default is not None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _validate_shocks(raw: Mapping[str, Any] | None) -> dict[str, float]:
    source = raw or {}
    shocks: dict[str, float] = {}
    for key in _SHOCK_KEYS:
        value = _as_float(key, source.get(key, 0.0))
        if key in ("xau_usd_pct", "usd_irr_pct", "local_premium_pct", "fund_discount_pct"):
            if value <= -1.0:
                raise ValueError(f"{key} must be greater than -1")
        if key == "liquidity_haircut_pct" and not 0.0 <= value <= 1.0:
            raise ValueError("liquidity_haircut_pct must be in [0, 1]")
        shocks[key] = value
    return shocks


def _position(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    symbol = str(raw.get("symbol") or f"position_{index + 1}").strip()
    asset_type = str(raw.get("asset_type") or "other").strip().lower()
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"asset_type must be one of {ASSET_TYPES}, got {asset_type!r}")
    direction = str(raw.get("direction") or "long").strip().lower()
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be long or short, got {direction!r}")
    exposure = _as_float("exposure_irr", raw.get("exposure_irr"))
    if exposure < 0:
        raise ValueError("exposure_irr must be non-negative")
    delta = _as_float("delta", raw.get("delta"), default=1.0)
    vega = _as_float(
        "vega_irr_per_vol_point",
        raw.get("vega_irr_per_vol_point"),
        default=0.0,
    )
    margin = _as_float("margin_irr", raw.get("margin_irr"), default=0.0)
    maintenance = _as_float(
        "maintenance_margin_irr",
        raw.get("maintenance_margin_irr"),
        default=margin * 0.5,
    )
    if margin < 0 or maintenance < 0:
        raise ValueError("margin values must be non-negative")
    return {
        "symbol": symbol,
        "asset_type": asset_type,
        "direction": direction,
        "exposure_irr": exposure,
        "delta": delta,
        "vega_irr_per_vol_point": vega,
        "margin_irr": margin,
        "maintenance_margin_irr": maintenance,
    }

def _market_return(asset_type: str, shocks: Mapping[str, float]) -> float:
    """Return the pre-direction, pre-cost return for one asset type."""
    global_and_fx = (1.0 + shocks["xau_usd_pct"]) * (
        1.0 + shocks["usd_irr_pct"]
    ) - 1.0
    if asset_type == "cash":
        return 0.0
    if asset_type == "fx":
        return shocks["usd_irr_pct"]
    if asset_type == "coin":
        return global_and_fx + shocks["local_premium_pct"]
    if asset_type in ("fund", "etf"):
        return global_and_fx + shocks["fund_discount_pct"]
    if asset_type in ("futures", "certificate"):
        return global_and_fx + 0.5 * shocks["local_premium_pct"]
    if asset_type == "option":
        return global_and_fx
    return global_and_fx


def _position_pnl(position: Mapping[str, Any], shocks: Mapping[str, float]) -> dict[str, Any]:
    exposure = float(position["exposure_irr"])
    direction_sign = 1.0 if position["direction"] == "long" else -1.0
    market_return = _market_return(str(position["asset_type"]), shocks)
    if position["asset_type"] == "option":
        market_return *= float(position["delta"])
    directional_return = market_return * direction_sign
    vega_pnl = float(position["vega_irr_per_vol_point"]) * shocks["volatility_points"]
    market_pnl = exposure * directional_return
    liquidity_cost = exposure * shocks["liquidity_haircut_pct"]
    pnl = market_pnl + vega_pnl - liquidity_cost
    return {
        "symbol": position["symbol"],
        "asset_type": position["asset_type"],
        "direction": position["direction"],
        "exposure_irr": round(exposure, 2),
        "market_return_pct": round(directional_return * 100.0, 4),
        "market_pnl_irr": round(market_pnl, 2),
        "vega_pnl_irr": round(vega_pnl, 2),
        "liquidity_cost_irr": round(liquidity_cost, 2),
        "pnl_irr": round(pnl, 2),
    }


def _scenario_result(
    scenario: GoldRiskScenario,
    positions: Sequence[Mapping[str, Any]],
    equity_irr: float,
    total_maintenance: float,
) -> dict[str, Any]:
    shocks = _validate_shocks(scenario.shocks)
    rows = [_position_pnl(position, shocks) for position in positions]
    total_pnl = sum(row["pnl_irr"] for row in rows)
    post_equity = equity_irr + total_pnl
    worst_position = min(rows, key=lambda row: row["pnl_irr"]) if rows else None
    margin_call = bool(total_maintenance > 0 and post_equity < total_maintenance)
    forced_liquidation = bool(post_equity <= 0.0)
    return {
        "scenario_id": scenario.scenario_id,
        "name_fa": scenario.name_fa,
        "name_en": scenario.name_en,
        "description_fa": scenario.description_fa,
        "shocks": shocks,
        "pnl_irr": round(total_pnl, 2),
        "pnl_pct_of_equity": round(total_pnl / equity_irr * 100.0, 4) if equity_irr else None,
        "post_equity_irr": round(post_equity, 2),
        "margin_call": margin_call,
        "forced_liquidation": forced_liquidation,
        "maintenance_coverage_ratio": (
            round(post_equity / total_maintenance, 4) if total_maintenance > 0 else None
        ),
        "worst_position": worst_position,
        "positions": rows,
    }


def _risk_level(worst_pnl_pct: float | None, margin_call: bool, forced: bool) -> str:
    if forced:
        return "CRITICAL"
    if margin_call:
        return "HIGH"
    if worst_pnl_pct is None:
        return "UNKNOWN"
    loss = abs(min(worst_pnl_pct, 0.0))
    if loss < 5.0:
        return "LOW"
    if loss < 12.0:
        return "MEDIUM"
    if loss < 25.0:
        return "HIGH"
    return "CRITICAL"

def stress_test_gold_portfolio(
    equity_irr: float,
    positions: Sequence[Mapping[str, Any]],
    scenarios: Sequence[Mapping[str, Any] | GoldRiskScenario] | None = None,
) -> dict[str, Any]:
    """Stress-test a gold portfolio against named Iran-market scenarios.

    ``scenarios`` may contain scenario dicts (``scenario_id``, names and
    ``shocks``) or :class:`GoldRiskScenario` instances. When omitted, the
    built-in :data:`GOLD_RISK_SCENARIOS` set is used.
    """
    equity = _as_float("equity_irr", equity_irr)
    if equity <= 0:
        raise ValueError("equity_irr must be positive")

    prepared_positions = [_position(raw, index) for index, raw in enumerate(positions)]
    # ``None`` means "use the built-ins"; an explicit empty list is invalid.
    scenario_source = GOLD_RISK_SCENARIOS if scenarios is None else scenarios
    selected: list[GoldRiskScenario] = []
    for index, raw in enumerate(scenario_source):
        if isinstance(raw, GoldRiskScenario):
            selected.append(raw)
            continue
        scenario_id = str(raw.get("scenario_id") or f"custom_{index + 1}")
        selected.append(
            GoldRiskScenario(
                scenario_id=scenario_id,
                name_fa=str(raw.get("name_fa") or scenario_id),
                name_en=str(raw.get("name_en") or scenario_id),
                description_fa=str(raw.get("description_fa") or ""),
                shocks=_validate_shocks(raw.get("shocks") or {}),
            )
        )
    if not selected:
        raise ValueError("at least one scenario is required")

    gross_exposure = sum(position["exposure_irr"] for position in prepared_positions)
    signed_exposure = sum(
        position["exposure_irr"]
        * (1.0 if position["direction"] == "long" else -1.0)
        for position in prepared_positions
    )
    total_margin = sum(position["margin_irr"] for position in prepared_positions)
    total_maintenance = sum(
        position["maintenance_margin_irr"] for position in prepared_positions
    )
    concentration_hhi = (
        sum((position["exposure_irr"] / gross_exposure) ** 2 for position in prepared_positions)
        if gross_exposure > 0
        else None
    )
    largest_position_pct = (
        max(position["exposure_irr"] for position in prepared_positions)
        / gross_exposure
        * 100.0
        if gross_exposure > 0
        else None
    )
    by_asset_type: dict[str, float] = {}
    for position in prepared_positions:
        key = position["asset_type"]
        by_asset_type[key] = by_asset_type.get(key, 0.0) + position["exposure_irr"]

    results = [
        _scenario_result(scenario, prepared_positions, equity, total_maintenance)
        for scenario in selected
    ]
    worst = min(
        results,
        key=lambda row: row["pnl_pct_of_equity"]
        if row["pnl_pct_of_equity"] is not None
        else 0.0,
    )
    return {
        "available": bool(prepared_positions),
        "reason": None if prepared_positions else "no positions supplied",
        "equity_irr": round(equity, 2),
        "gross_exposure_irr": round(gross_exposure, 2),
        "net_exposure_irr": round(signed_exposure, 2),
        "net_exposure_pct_of_equity": round(signed_exposure / equity * 100.0, 4),
        "gross_leverage_ratio": round(gross_exposure / equity, 4),
        "margin_irr": round(total_margin, 2),
        "maintenance_margin_irr": round(total_maintenance, 2),
        "margin_utilization_pct": round(total_margin / equity * 100.0, 4),
        "concentration_hhi": round(concentration_hhi, 6) if concentration_hhi is not None else None,
        "largest_position_pct": round(largest_position_pct, 4) if largest_position_pct is not None else None,
        "exposure_by_asset_type_irr": {
            key: round(value, 2) for key, value in sorted(by_asset_type.items())
        },
        "risk_level": _risk_level(
            worst["pnl_pct_of_equity"],
            any(row["margin_call"] for row in results),
            any(row["forced_liquidation"] for row in results),
        ),
        "worst_case": worst,
        "scenarios": results,
    }


def list_risk_scenarios() -> list[dict[str, Any]]:
    """Return the built-in scenario catalogue for API clients."""
    return [scenario.as_dict() for scenario in GOLD_RISK_SCENARIOS]


__all__ = [
    "ASSET_TYPES",
    "DIRECTIONS",
    "GOLD_RISK_SCENARIOS",
    "GoldRiskScenario",
    "list_risk_scenarios",
    "stress_test_gold_portfolio",
]
