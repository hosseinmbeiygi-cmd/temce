from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from scipy.interpolate import CubicSpline

from domain.common.base_entity import BaseEntity


@dataclass
class VolatilitySurface(BaseEntity):
    underlying_id: str
    date: date | None = None
    surface_data: dict[str, dict[str, float]] = field(default_factory=dict)
    model: str = "svi"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        underlying_id: str,
        date: date | None = None,
        surface_data: dict[str, dict[str, float]] | None = None,
        model: str = "svi",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.underlying_id = underlying_id
        self.date = date
        self.surface_data = surface_data or {}
        self.model = model
        self.extra = extra or {}

    def get_volatility(self, strike: float, expiry: str) -> float:
        expiry_str = str(expiry)
        if expiry_str in self.surface_data and str(strike) in self.surface_data[expiry_str]:
            return self.surface_data[expiry_str][str(strike)]
        return 0.0

    def add_point(self, expiry: str, strike: float, volatility: float) -> None:
        if expiry not in self.surface_data:
            self.surface_data[expiry] = {}
        self.surface_data[expiry][str(strike)] = volatility
        self.mark_updated()


# =============================================================================
# Tier 1/2 vol surface per IME v5.0 doc (§3.2)
# =============================================================================


def cubic_spline_surface_iv(
    strikes: list[float], vols: list[float], query_strike: float, min_valid_points: int = 3
) -> float | None:
    """Tier-1 Cubic Spline interpolation between valid strikes (per expiry).

    سند §3.2: سطح نوسان پیش‌فرض با درون‌یابی Cubic Spline بین Strikeهای معتبر.
    Returns None when the query is outside the valid strike range or there are
    too few points — conservative guard, never silently extrapolates.
    """
    if len(strikes) != len(vols) or len(strikes) < min_valid_points:
        return None
    pairs = sorted(zip(strikes, vols, strict=True))
    xs = [float(p[0]) for p in pairs]
    ys = [float(p[1]) for p in pairs]
    if query_strike < xs[0] or query_strike > xs[-1]:
        return None
    spline = CubicSpline(xs, ys, extrapolate=False)
    value = float(spline(query_strike))
    if value <= 0 or not (0.0 <= value <= 10.0):  # negative/invalid vol → None
        return None
    return value


def sabr_sufficiency_gate(
    strikes_per_maturity: dict[str, list[float]],
    calibration_rmse: float | None,
    min_strikes: int = 5,
    min_maturities: int = 2,
    rmse_threshold: float = 0.02,
    stability_window_days: int = 20,
    calibrated_days: int = 0,
) -> tuple[bool, list[str]]:
    """Tier-2 SABR activation gate — data-sufficiency criteria per doc §3.2.

    Activates only when: ≥5 valid strikes per maturity, ≥2 active maturities,
    calibration RMSE below threshold, and calibration stable over the window.
    Otherwise the system stays on Cubic Spline (Tier 1).
    """
    reasons: list[str] = []
    for maturity, strikes in strikes_per_maturity.items():
        if len(strikes) < min_strikes:
            reasons.append(f"maturity {maturity}: {len(strikes)} strikes < {min_strikes} required")
    if len(strikes_per_maturity) < min_maturities:
        reasons.append(f"{len(strikes_per_maturity)} active maturities < {min_maturities} required")
    if calibration_rmse is None or calibration_rmse >= rmse_threshold:
        reasons.append(f"calibration RMSE {calibration_rmse} not below {rmse_threshold}")
    if calibrated_days < stability_window_days:
        reasons.append(f"calibration stability window {calibrated_days}d < {stability_window_days}d")
    return (not reasons, reasons)
