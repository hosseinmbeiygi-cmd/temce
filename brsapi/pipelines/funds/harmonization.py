from __future__ import annotations

from typing import Any

from core.ids import new_id

FUND_NORMALIZE_MAP = {
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

NAV_NORMALIZE_MAP = {
    "date": "nav_date",
    "nav": "nav",
    "unit_price": "unit_price",
    "daily_return_pct": "daily_return_pct",
    "cumulative_return_pct": "cumulative_return_pct",
    "total_assets": "total_assets",
    "total_liabilities": "total_liabilities",
    "total_units": "total_units",
}

HOLDINGS_NORMALIZE_MAP = {
    "instrument_id": "instrument_id",
    "symbol": "symbol",
    "quantity": "quantity",
    "market_value": "market_value",
    "weight_pct": "weight_pct",
    "asset_type": "asset_type",
}


def normalize_fund_data(raw: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"id": new_id("fund")}
    for raw_key, value in raw.items():
        key = FUND_NORMALIZE_MAP.get(raw_key, raw_key)
        normalized[key] = value
    if "name" not in normalized or not normalized["name"]:
        normalized["name"] = normalized.get("symbol", "Unknown Fund")
    if "currency" not in normalized:
        normalized["currency"] = "IRR"
    if "status" not in normalized:
        normalized["status"] = "active"
    normalized.setdefault("nav", 0.0)
    normalized.setdefault("total_units", 0)
    normalized.setdefault("unit_price", 0.0)
    normalized.setdefault("extra", {})
    return normalized


def normalize_nav_data(raw: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"id": new_id("nav")}
    for raw_key, value in raw.items():
        key = NAV_NORMALIZE_MAP.get(raw_key, raw_key)
        normalized[key] = value
    if "nav" in normalized and isinstance(normalized["nav"], str):
        try:
            normalized["nav"] = float(normalized["nav"].replace(",", ""))
        except (ValueError, AttributeError):
            normalized["nav"] = 0.0
    if "unit_price" in normalized and isinstance(normalized["unit_price"], str):
        try:
            normalized["unit_price"] = float(normalized["unit_price"].replace(",", ""))
        except (ValueError, AttributeError):
            normalized["unit_price"] = 0.0
    normalized.setdefault("daily_return_pct", 0.0)
    normalized.setdefault("cumulative_return_pct", 0.0)
    normalized.setdefault("total_assets", 0.0)
    normalized.setdefault("total_liabilities", 0.0)
    normalized.setdefault("total_units", 0)
    normalized.setdefault("extra", {})
    return normalized


def normalize_holdings(raw: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"id": new_id("hold")}
    for raw_key, value in raw.items():
        key = HOLDINGS_NORMALIZE_MAP.get(raw_key, raw_key)
        normalized[key] = value
    if "quantity" in normalized and isinstance(normalized["quantity"], str):
        try:
            normalized["quantity"] = int(normalized["quantity"].replace(",", ""))
        except (ValueError, AttributeError):
            normalized["quantity"] = 0
    if "market_value" in normalized and isinstance(normalized["market_value"], str):
        try:
            normalized["market_value"] = float(normalized["market_value"].replace(",", ""))
        except (ValueError, AttributeError):
            normalized["market_value"] = 0.0
    if "weight_pct" in normalized and isinstance(normalized["weight_pct"], str):
        try:
            normalized["weight_pct"] = float(normalized["weight_pct"].replace(",", ""))
        except (ValueError, AttributeError):
            normalized["weight_pct"] = 0.0
    normalized.setdefault("quantity", 0)
    normalized.setdefault("market_value", 0.0)
    normalized.setdefault("weight_pct", 0.0)
    normalized.setdefault("asset_type", "")
    normalized.setdefault("extra", {})
    return normalized
