"""Shared trading-day constants for annualisation and backtesting.

Each market segment has a different number of trading sessions per year.
Import the right constant instead of hard-coding a number so that every
annualisation formula stays consistent with acceptance.yaml.
"""

from __future__ import annotations

# NYSE / global markets (XAU, crypto, USD-denominated instruments)
TRADING_DAYS_PER_YEAR_GLOBAL: int = 252

# Tehran Stock Exchange — roughly 250 sessions per year
TRADING_DAYS_PER_YEAR_TSE: int = 250

# Iran Mercantile Exchange and domestic ETFs — fewer sessions
TRADING_DAYS_PER_YEAR_IME: int = 240

# Fallback alias used by instruments that span multiple markets
TRADING_DAYS_PER_YEAR_DEFAULT: int = TRADING_DAYS_PER_YEAR_TSE
