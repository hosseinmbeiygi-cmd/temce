"""Iranian market risk-free rate calculator.

Provides context-appropriate risk-free rates for backtesting:
- Default: TSE index historical average return (~25-30% annually for Iran)
- Or configurable via settings
"""

from __future__ import annotations

# Iranian market constants (annualized)
# Based on TSE historical data and central bank rates
IRAN_RISK_FREE_RATES = {
    "conservative": 0.15,  # 15% — minimum deposit rate (حساب سپرده)
    "moderate": 0.25,  # 25% — average T-bill rate (اوراق خزانه)
    "aggressive": 0.30,  # 30% — long-term deposit rate (بلندمدت)
    "inflation_hedged": 0.20,  # 20% — real return above inflation
}


def get_risk_free_rate(
    mode: str = "moderate",
    custom_rate: float | None = None,
) -> float:
    """Get the appropriate risk-free rate for Iranian market backtesting.

    Args:
        mode: One of 'conservative', 'moderate', 'aggressive', 'inflation_hedged'
        custom_rate: Override with a custom annualized rate (0.0 to 1.0)

    Returns:
        Annualized risk-free rate as a decimal (e.g., 0.25 for 25%)
    """
    if custom_rate is not None and 0 <= custom_rate <= 1.0:
        return custom_rate

    return IRAN_RISK_FREE_RATES.get(mode, IRAN_RISK_FREE_RATES["moderate"])


# Historical Iranian risk-free rates by year (central bank & treasury data)
# Sources: CBI, Iran Fara Bourse — estimated averages per Persian year
_HISTORICAL_RATES: dict[int, float] = {
    1395: 0.20,  # 1395: ~20%
    1396: 0.22,  # 1396: ~22%
    1397: 0.25,  # 1397: ~25%
    1398: 0.28,  # 1398: ~28%
    1399: 0.30,  # 1399: ~30% (high inflation era)
    1400: 0.30,  # 1400: ~30%
    1401: 0.28,  # 1401: ~28%
    1402: 0.26,  # 1402: ~26%
    1403: 0.25,  # 1403: ~25%
    1404: 0.25,  # 1404: ~25%
}


def get_risk_free_rate_for_period(
    start_year: int | None = None,
    end_year: int | None = None,
) -> float:
    """Get risk-free rate appropriate for a specific time period.

    Uses historical rate lookup when available, falling back to the
    moderate (25%) default for years not in the historical table.

    Args:
        start_year: Persian year (e.g., 1400). If None, returns default.
        end_year: Persian year. If provided, averages rates across the range.

    Returns:
        Annualized risk-free rate as decimal.
    """
    if start_year is None:
        return get_risk_free_rate("moderate")

    years = range(start_year, (end_year or start_year) + 1)
    rates = [_HISTORICAL_RATES.get(y) for y in years if _HISTORICAL_RATES.get(y) is not None]

    if not rates:
        return get_risk_free_rate("moderate")

    return sum(rates) / len(rates)
