from __future__ import annotations

from typing import Any

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.funds.entities import Fund, FundHolding
from domain.funds.nav import FundNAV

logger = get_logger(__name__)


async def persist_fund(data: dict[str, Any], repository: Any) -> Result[Fund]:
    fund = Fund(
        id=data.get("id", new_id("fund")),
        name=data.get("name", ""),
        symbol=data.get("symbol", ""),
        isin=data.get("isin", ""),
        fund_type=data.get("fund_type", ""),
        manager=data.get("manager", ""),
        custodian=data.get("custodian", ""),
        currency=data.get("currency", "IRR"),
        nav=data.get("nav", 0.0),
        total_units=data.get("total_units", 0),
        unit_price=data.get("unit_price", 0.0),
        status=data.get("status", "active"),
        extra=data.get("extra", {}),
    )
    result = await repository.save(fund)
    if result.success:
        logger.info("Persisted fund %s (%s)", fund.name, fund.id)
    else:
        logger.error("Failed to persist fund %s: %s", fund.name, result.error)
    return result


async def persist_nav_history(
    fund_id: str,
    nav_data_list: list[dict[str, Any]],
    repository: Any,
) -> Result[int]:
    count = 0
    for nav_data in nav_data_list:
        nav = FundNAV(
            id=nav_data.get("id", new_id("nav")),
            fund_id=fund_id,
            nav_date=nav_data.get("nav_date"),
            nav=nav_data.get("nav", 0.0),
            unit_price=nav_data.get("unit_price", 0.0),
            total_assets=nav_data.get("total_assets", 0.0),
            total_liabilities=nav_data.get("total_liabilities", 0.0),
            total_units=nav_data.get("total_units", 0),
            daily_return_pct=nav_data.get("daily_return_pct", 0.0),
            cumulative_return_pct=nav_data.get("cumulative_return_pct", 0.0),
            extra=nav_data.get("extra", {}),
        )
        result = await repository.save(nav)
        if result.success:
            count += 1
        else:
            logger.error("Failed to persist NAV for fund %s: %s", fund_id, result.error)
    logger.info("Persisted %d NAV records for fund %s", count, fund_id)
    return Result.ok(count)


async def persist_holdings(
    fund_id: str,
    holdings_data: list[dict[str, Any]],
    repository: Any,
) -> Result[int]:
    count = 0
    for hold_data in holdings_data:
        holding = FundHolding(
            id=hold_data.get("id", new_id("hold")),
            fund_id=fund_id,
            instrument_id=hold_data.get("instrument_id", ""),
            symbol=hold_data.get("symbol", ""),
            quantity=hold_data.get("quantity", 0),
            market_value=hold_data.get("market_value", 0.0),
            weight_pct=hold_data.get("weight_pct", 0.0),
            asset_type=hold_data.get("asset_type", ""),
            extra=hold_data.get("extra", {}),
        )
        result = await repository.save(holding)
        if result.success:
            count += 1
        else:
            logger.error("Failed to persist holding for fund %s: %s", fund_id, result.error)
    logger.info("Persisted %d holdings for fund %s", count, fund_id)
    return Result.ok(count)
