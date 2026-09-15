from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FUND_TYPE_EQUITY = "equity"
FUND_TYPE_FIXED_INCOME = "fixed_income"
FUND_TYPE_MIXED = "mixed"
FUND_TYPE_MONEY_MARKET = "money_market"
FUND_TYPE_INDEX = "index"
FUND_TYPE_COMMODITY = "commodity"
FUND_TYPE_REAL_ESTATE = "real_estate"
FUND_TYPE_HEDGE = "hedge"
FUND_TYPE_PRIVATE_EQUITY = "private_equity"


@dataclass
class FundClassification:
    fund_type: str = ""
    risk_level: str = "medium"
    investment_goal: str = ""
    geographic_focus: str = ""
    asset_allocation: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
