from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

FUND_REQUIRED_FIELDS = ["name"]
NAV_REQUIRED_FIELDS = ["fund_id", "nav_date"]
HOLDINGS_REQUIRED_FIELDS = ["fund_id", "instrument_id"]

FUND_POSITIVE_FIELDS = ["nav", "unit_price"]
NAV_POSITIVE_FIELDS = ["nav", "unit_price"]
HOLDINGS_POSITIVE_FIELDS = ["quantity", "market_value"]


def validate_fund(data: dict[str, Any]) -> Result[dict[str, Any]]:
    for field in FUND_REQUIRED_FIELDS:
        if field not in data or data[field] is None or data[field] == "":
            logger.warning("Fund validation failed: missing required field '%s'", field)
            return Result.fail(f"Missing required field: {field}")
    for field in FUND_POSITIVE_FIELDS:
        val = data.get(field, 0)
        if isinstance(val, (int, float)) and val < 0:
            logger.warning("Fund validation failed: negative %s = %s", field, val)
            return Result.fail(f"Invalid negative {field}: {val}")
    fund_type = data.get("fund_type", "")
    if fund_type and fund_type not in {
        "equity",
        "fixed_income",
        "mixed",
        "money_market",
        "index",
        "commodity",
        "real_estate",
        "hedge",
        "private_equity",
    }:
        logger.warning("Fund validation failed: invalid fund_type '%s'", fund_type)
        return Result.fail(f"Invalid fund_type: {fund_type}")
    return Result.ok(data)


def validate_nav(data: dict[str, Any]) -> Result[dict[str, Any]]:
    for field in NAV_REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            logger.warning("NAV validation failed: missing required field '%s'", field)
            return Result.fail(f"Missing required field: {field}")
    for field in NAV_POSITIVE_FIELDS:
        val = data.get(field, 0)
        if isinstance(val, (int, float)) and val < 0:
            logger.warning("NAV validation failed: negative %s = %s", field, val)
            return Result.fail(f"Invalid negative {field}: {val}")
    return Result.ok(data)


def validate_holdings(data: dict[str, Any]) -> Result[dict[str, Any]]:
    for field in HOLDINGS_REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            logger.warning("Holdings validation failed: missing required field '%s'", field)
            return Result.fail(f"Missing required field: {field}")
    for field in HOLDINGS_POSITIVE_FIELDS:
        val = data.get(field, 0)
        if isinstance(val, (int, float)) and val < 0:
            logger.warning("Holdings validation failed: negative %s = %s", field, val)
            return Result.fail(f"Invalid negative {field}: {val}")
    weight = data.get("weight_pct", 0)
    if isinstance(weight, (int, float)) and (weight < 0 or weight > 100):
        logger.warning("Holdings validation failed: weight_pct out of range: %s", weight)
        return Result.fail(f"weight_pct out of range [0, 100]: {weight}")
    return Result.ok(data)
