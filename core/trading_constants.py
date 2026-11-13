"""Shared trading-day constants for annualisation and backtesting.

Each market segment has a different number of trading sessions per year.
Import the right constant instead of hard-coding a number so that every
annualisation formula stays consistent with acceptance.yaml.

Day-count convention (OF5):
- CALENDAR_DAYS_PER_YEAR (365): used for Black-Scholes T = dte / 365 and
  theta (time-decay per calendar day), since options expire on calendar days.
- TRADING_DAYS_PER_YEAR_* (240-252): used for Sharpe, VaR simulation and
  return annualisation, since performance is measured in trading sessions.
  Mixing the two gives a 44.8 % theta gap (365/252 − 1); use the right
  constant for the right context.
"""

from __future__ import annotations

# Calendar days per year — for BS time-to-expiry and theta (OF5)
CALENDAR_DAYS_PER_YEAR: int = 365

# NYSE / global markets (XAU, crypto, USD-denominated instruments)
TRADING_DAYS_PER_YEAR_GLOBAL: int = 252

# Tehran Stock Exchange — roughly 250 sessions per year
TRADING_DAYS_PER_YEAR_TSE: int = 250

# Iran Mercantile Exchange and domestic ETFs — fewer sessions
TRADING_DAYS_PER_YEAR_IME: int = 240

# Fallback alias used by instruments that span multiple markets
TRADING_DAYS_PER_YEAR_DEFAULT: int = TRADING_DAYS_PER_YEAR_TSE
