from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

FUND_FIELD_MAP = {
    "fund_id": "fund_id",
    "name": "name",
    "symbol": "symbol",
    "isin": "isin",
    "fund_type": "fund_type",
    "manager": "manager",
    "custodian": "custodian",
    "currency": "currency",
    "nav": "nav",
    "total_units": "total_units",
    "unit_price": "unit_price",
    "status": "status",
}

NAV_FIELD_MAP = {
    "date": "nav_date",
    "nav": "nav",
    "unit_price": "unit_price",
    "daily_return_pct": "daily_return_pct",
    "cumulative_return_pct": "cumulative_return_pct",
    "total_assets": "total_assets",
    "total_liabilities": "total_liabilities",
    "total_units": "total_units",
}

HOLDINGS_FIELD_MAP = {
    "instrument_id": "instrument_id",
    "symbol": "symbol",
    "quantity": "quantity",
    "market_value": "market_value",
    "weight_pct": "weight_pct",
    "asset_type": "asset_type",
}


class FundMapping:
    def __init__(
        self,
        fund_field_map: dict[str, str] | None = None,
        nav_field_map: dict[str, str] | None = None,
        holdings_field_map: dict[str, str] | None = None,
    ) -> None:
        self.fund_field_map = fund_field_map or FUND_FIELD_MAP
        self.nav_field_map = nav_field_map or NAV_FIELD_MAP
        self.holdings_field_map = holdings_field_map or HOLDINGS_FIELD_MAP

    def map_fund(self, data: dict[str, Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for raw_key, value in data.items():
            target_key = self.fund_field_map.get(raw_key, raw_key)
            mapped[target_key] = value
        return mapped

    def map_nav(self, data: dict[str, Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for raw_key, value in data.items():
            target_key = self.nav_field_map.get(raw_key, raw_key)
            mapped[target_key] = value
        return mapped

    def map_holdings(self, data: dict[str, Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for raw_key, value in data.items():
            target_key = self.holdings_field_map.get(raw_key, raw_key)
            mapped[target_key] = value
        return mapped

    def map_fund_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map_fund(row) for row in data]

    def map_nav_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map_nav(row) for row in data]

    def map_holdings_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map_holdings(row) for row in data]
