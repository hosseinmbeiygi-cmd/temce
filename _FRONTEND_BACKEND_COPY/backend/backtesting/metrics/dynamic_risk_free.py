"""Dynamic Risk-Free Rate — historical rates for Iran's economy.

In Iran, the risk-free rate (bank deposit rate / treasury bill yield)
fluctuates significantly (18% to 40%+). Using a fixed rate makes
cross-period Sharpe comparisons misleading.

This module provides:
- Historical risk-free rates by year
- Inflation-adjusted (real) return calculation
- Rolling risk-free rate for walk-forward analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Historical risk-free rates and inflation for Iran (approximate)
# Sources: CBI, SCI
IRAN_ECONOMIC_DATA = {
    1397: {"risk_free": 0.18, "inflation": 0.30},  # 2018-2019
    1398: {"risk_free": 0.18, "inflation": 0.41},  # 2019-2020
    1399: {"risk_free": 0.20, "inflation": 0.36},  # 2020-2021
    1400: {"risk_free": 0.23, "inflation": 0.40},  # 2021-2022
    1401: {"risk_free": 0.28, "inflation": 0.45},  # 2022-2023
    1402: {"risk_free": 0.30, "inflation": 0.47},  # 2023-2024
    1403: {"risk_free": 0.32, "inflation": 0.35},  # 2024-2025
}

# Gregorian year mapping (approximate)
YEAR_MAPPING = {
    2019: 1397,
    2020: 1398,
    2021: 1399,
    2022: 1400,
    2023: 1401,
    2024: 1402,
    2025: 1403,
}


@dataclass
class RiskFreeRateResult:
    """Risk-free rate and inflation data for a period."""

    risk_free_rate: float = 0.25  # annualized
    inflation_rate: float = 0.35  # annualized
    real_rate: float = 0.0  # risk_free - inflation (approximate)
    year: int = 1403
    source: str = "CBI_approximate"


class DynamicRiskFreeRate:
    """Provides dynamic risk-free rates for Iranian market backtests."""

    def __init__(self, custom_rates: dict[int, dict[str, float]] | None = None) -> None:
        self._rates = dict(IRAN_ECONOMIC_DATA)
        if custom_rates:
            self._rates.update(custom_rates)

    def get_rate(self, jalali_year: int) -> RiskFreeRateResult:
        """Get risk-free rate for a Jalali year."""
        data = self._rates.get(jalali_year, {"risk_free": 0.25, "inflation": 0.35})
        rf = data["risk_free"]
        inf = data["inflation"]
        return RiskFreeRateResult(
            risk_free_rate=rf,
            inflation_rate=inf,
            real_rate=rf - inf,
            year=jalali_year,
        )

    def get_rate_for_date(self, gregorian_year: int) -> RiskFreeRateResult:
        """Get risk-free rate for a Gregorian year."""
        jalali = YEAR_MAPPING.get(gregorian_year, 1403)
        return self.get_rate(jalali)

    def get_rolling_rate(self, years: list[int]) -> list[RiskFreeRateResult]:
        """Get risk-free rates for multiple years."""
        return [self.get_rate(y) for y in years]

    @staticmethod
    def compute_real_return(nominal_return: float, inflation_rate: float) -> float:
        """Compute real (inflation-adjusted) return.

        Real Return ≈ Nominal Return - Inflation
        More precisely: (1 + nominal) / (1 + inflation) - 1
        """
        if inflation_rate <= -1:
            return nominal_return
        return (1 + nominal_return) / (1 + inflation_rate) - 1

    @staticmethod
    def compute_real_sharpe(
        nominal_sharpe: float,
        nominal_return: float,
        inflation_rate: float,
    ) -> float:
        """Approximate real Sharpe ratio."""
        real_return = DynamicRiskFreeRate.compute_real_return(nominal_return, inflation_rate)
        # Simplified: real_sharpe ≈ nominal_sharpe * (real_return / nominal_return)
        if abs(nominal_return) < 1e-8:
            return 0.0
        return nominal_sharpe * (real_return / nominal_return)

    def compute_all_metrics(
        self,
        nominal_return: float,
        nominal_sharpe: float,
        jalali_year: int,
    ) -> dict[str, Any]:
        """Compute all inflation-adjusted metrics."""
        rf_data = self.get_rate(jalali_year)
        real_return = self.compute_real_return(nominal_return, rf_data.inflation_rate)
        real_sharpe = self.compute_real_sharpe(nominal_sharpe, nominal_return, rf_data.inflation_rate)

        return {
            "nominal_return": round(nominal_return, 4),
            "real_return": round(real_return, 4),
            "nominal_sharpe": round(nominal_sharpe, 4),
            "real_sharpe": round(real_sharpe, 4),
            "risk_free_rate": rf_data.risk_free_rate,
            "inflation_rate": rf_data.inflation_rate,
            "year": jalali_year,
        }
