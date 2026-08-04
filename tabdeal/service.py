"""
Tabdeal service layer.

Fetches data from the Tabdeal API and persists it to the database.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from tabdeal.client import TabdealClient
from tabdeal.models import (
    TabdealAccountModel,
    TabdealBalanceModel,
    TabdealMarketInfoModel,
    TabdealOrderModel,
    TabdealTradeModel,
)

logger = get_logger(__name__)


class TabdealService:
    """Service for fetching Tabdeal data and persisting to DB."""

    def __init__(self, session: AsyncSession, client: TabdealClient):
        self.session = session
        self.client = client

    # ── Orders ──────────────────────────────────────────────────

    async def sync_spot_orders(self, symbol: str | None = None, limit: int = 100) -> int:
        """Fetch open + recent orders from Tabdeal and upsert into DB."""
        orders = await self.client.get_open_orders(symbol=symbol)
        count = 0
        for o in orders:
            await self._upsert_order(o, is_spot=True)
            count += 1
        # Also fetch all orders (recent)
        all_orders = await self.client.get_all_orders(symbol=symbol, limit=limit)
        for o in all_orders:
            await self._upsert_order(o, is_spot=True)
            count += 1
        await self.session.commit()
        logger.info("Synced %d spot orders", count)
        return count

    async def sync_fapi_orders(self, symbol: str | None = None, limit: int = 100) -> int:
        """Fetch futures orders from Tabdeal FAPI and upsert into DB."""
        orders = await self.client.fapi_open_orders(symbol=symbol, limit=limit)
        count = 0
        for o in orders:
            await self._upsert_order(o, is_spot=False)
            count += 1
        await self.session.commit()
        logger.info("Synced %d fapi orders", count)
        return count

    async def _upsert_order(self, data: dict[str, Any], is_spot: bool = True) -> None:
        order_id = data.get("orderId")
        if not order_id:
            return
        stmt = select(TabdealOrderModel).where(
            TabdealOrderModel.order_id == order_id,
            TabdealOrderModel.is_spot == is_spot,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        fields = {
            "client_order_id": data.get("clientOrderId"),
            "symbol": data.get("symbol", ""),
            "tabdeal_symbol": data.get("tabdealSymbol"),
            "side": data.get("side", ""),
            "type": data.get("type", ""),
            "status": data.get("status", ""),
            "price": _float(data.get("price")),
            "quantity": _float(data.get("origQty")),
            "executed_qty": _float(data.get("executedQty")),
            "cumulative_quote_qty": _float(data.get("cumulativeQuoteQty")),
            "stop_price": _float(data.get("stopPrice")),
            "time_in_force": data.get("timeInForce"),
            "reduce_only": data.get("reduceOnly"),
            "is_working": data.get("isWorking"),
            "is_spot": is_spot,
            "fee": _float(data.get("fee")),
            "transact_time": data.get("transactTime"),
            "update_time": data.get("updateTime"),
            "raw_json": json.dumps(data, ensure_ascii=False),
        }

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            self.session.add(TabdealOrderModel(order_id=order_id, **fields))

    # ── Trades ──────────────────────────────────────────────────

    async def sync_spot_trades(self, symbol: str, start_time: int | None = None, end_time: int | None = None) -> int:
        trades = await self.client.my_trades(symbol=symbol, start_time=start_time, end_time=end_time, limit=1000)
        count = 0
        for t in trades:
            await self._upsert_trade(t, is_spot=True)
            count += 1
        await self.session.commit()
        logger.info("Synced %d spot trades for %s", count, symbol)
        return count

    async def _upsert_trade(self, data: dict[str, Any], is_spot: bool = True) -> None:
        trade_id = data.get("id")
        if not trade_id:
            return
        stmt = select(TabdealTradeModel).where(TabdealTradeModel.trade_id == trade_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        fields = {
            "order_id": data.get("orderId", 0),
            "symbol": data.get("symbol", ""),
            "tabdeal_symbol": data.get("tabdealSymbol"),
            "price": _float(data.get("price")) or 0.0,
            "quantity": _float(data.get("qty")) or 0.0,
            "quote_qty": _float(data.get("quoteQty")),
            "commission": _float(data.get("commission")),
            "commission_asset": data.get("commissionAsset"),
            "is_buyer": data.get("isBuyer"),
            "is_maker": data.get("isMaker"),
            "trade_time": data.get("time"),
            "is_spot": is_spot,
            "raw_json": json.dumps(data, ensure_ascii=False),
        }

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            self.session.add(TabdealTradeModel(trade_id=trade_id, **fields))

    # ── Account ─────────────────────────────────────────────────

    async def sync_account(self) -> dict:
        """Fetch account info and store balance snapshots."""
        data = await self.client.account()
        account = TabdealAccountModel(
            account_type=data.get("accountType"),
            can_trade=data.get("canTrade"),
            can_withdraw=data.get("canWithdraw"),
            can_deposit=data.get("canDeposit"),
            maker_commission=data.get("makerCommission"),
            taker_commission=data.get("takerCommission"),
            balances_json=json.dumps(data.get("balances", []), ensure_ascii=False),
            permissions_json=json.dumps(data.get("permissions", []), ensure_ascii=False),
            update_time=data.get("updateTime"),
            raw_json=json.dumps(data, ensure_ascii=False),
        )
        self.session.add(account)
        await self.session.flush()

        # Upsert balances
        for b in data.get("balances", []):
            asset = b.get("asset", "")
            stmt = select(TabdealBalanceModel).where(
                TabdealBalanceModel.asset == asset,
                TabdealBalanceModel.account_id == account.id,
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            free = _float(b.get("free")) or 0.0
            frozen = _float(b.get("freeze")) or 0.0
            if existing:
                existing.free = free
                existing.frozen = frozen
            else:
                self.session.add(TabdealBalanceModel(
                    account_id=account.id, asset=asset, free=free, frozen=frozen, is_spot=True,
                ))

        await self.session.commit()
        logger.info("Synced Tabdeal account with %d balances", len(data.get("balances", [])))
        return data

    # ── Markets ─────────────────────────────────────────────────

    async def sync_markets(self) -> int:
        """Fetch exchange info and upsert market metadata."""
        data = await self.client.exchange_info()
        items = data if isinstance(data, list) else data.get("symbols", [])
        count = 0
        for m in items:
            symbol = m.get("symbol", "")
            stmt = select(TabdealMarketInfoModel).where(TabdealMarketInfoModel.symbol == symbol)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

            filters = {f.get("filterType"): f for f in m.get("filters", [])}
            price_filter = filters.get("PRICE_FILTER", {})
            lot_filter = filters.get("LOT_SIZE", {})
            notional_filter = filters.get("MIN_NOTIONAL", {})

            fields = {
                "tabdeal_symbol": m.get("tabdealSymbol"),
                "status": m.get("status"),
                "base_asset": m.get("baseAsset"),
                "quote_asset": m.get("quoteAsset"),
                "base_precision": m.get("baseAssetPrecision"),
                "quote_precision": m.get("quoteAssetPrecision"),
                "order_types_json": json.dumps(m.get("orderTypes", []), ensure_ascii=False),
                "min_price": _float(price_filter.get("minPrice")),
                "max_price": _float(price_filter.get("maxPrice")),
                "tick_size": _float(price_filter.get("tickSize")),
                "min_qty": _float(lot_filter.get("minQty")),
                "step_size": _float(lot_filter.get("stepSize")),
                "min_notional": _float(notional_filter.get("minNotional")),
                "is_spot": True,
                "raw_json": json.dumps(m, ensure_ascii=False),
            }

            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                self.session.add(TabdealMarketInfoModel(symbol=symbol, **fields))
            count += 1

        await self.session.commit()
        logger.info("Synced %d Tabdeal markets", count)
        return count

    # ── Query helpers ───────────────────────────────────────────

    async def get_orders(self, symbol: str | None = None, status: str | None = None, is_spot: bool = True, limit: int = 100) -> list[dict]:
        stmt = select(TabdealOrderModel).where(TabdealOrderModel.is_spot == is_spot)
        if symbol:
            stmt = stmt.where(TabdealOrderModel.symbol == symbol)
        if status:
            stmt = stmt.where(TabdealOrderModel.status == status)
        stmt = stmt.order_by(TabdealOrderModel.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return [_row_dict(r) for r in result.scalars().all()]

    async def get_trades(self, symbol: str | None = None, is_spot: bool = True, limit: int = 100) -> list[dict]:
        stmt = select(TabdealTradeModel).where(TabdealTradeModel.is_spot == is_spot)
        if symbol:
            stmt = stmt.where(TabdealTradeModel.symbol == symbol)
        stmt = stmt.order_by(TabdealTradeModel.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return [_row_dict(r) for r in result.scalars().all()]

    async def get_account_snapshot(self) -> dict | None:
        stmt = select(TabdealAccountModel).order_by(TabdealAccountModel.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            return None
        return _row_dict(account)

    async def get_balances(self, account_id: int | None = None) -> list[dict]:
        stmt = select(TabdealBalanceModel).where(TabdealBalanceModel.free > 0)
        if account_id:
            stmt = stmt.where(TabdealBalanceModel.account_id == account_id)
        stmt = stmt.order_by(TabdealBalanceModel.asset)
        result = await self.session.execute(stmt)
        return [_row_dict(r) for r in result.scalars().all()]

    async def get_markets(self, status: str | None = None, is_spot: bool = True) -> list[dict]:
        stmt = select(TabdealMarketInfoModel).where(TabdealMarketInfoModel.is_spot == is_spot)
        if status:
            stmt = stmt.where(TabdealMarketInfoModel.status == status)
        stmt = stmt.order_by(TabdealMarketInfoModel.symbol)
        result = await self.session.execute(stmt)
        return [_row_dict(r) for r in result.scalars().all()]


# ── Helpers ─────────────────────────────────────────────────────

def _float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _row_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy row to a dict, excluding raw_json for cleaner output."""
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if col.name == "raw_json":
            continue
        d[col.name] = val
    return d
