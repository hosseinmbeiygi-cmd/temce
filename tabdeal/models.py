"""
Tabdeal exchange ORM models.

Stores orders, trades, account info, and market data from the Tabdeal API.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TabdealOrderModel(Base):
    """
    Tabdeal spot/futures order history.

    One row per order creation or status update.
    """

    __tablename__ = "tabdeal_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    client_order_id: Mapped[str | None] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tabdeal_symbol: Mapped[str | None] = mapped_column(String(30))
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY / SELL
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # LIMIT / MARKET / STOP_LOSS_LIMIT
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # NEW / FILLED / CANCELED / ...
    price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[float | None] = mapped_column(Float)
    executed_qty: Mapped[float | None] = mapped_column(Float)
    cumulative_quote_qty: Mapped[float | None] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float)
    time_in_force: Mapped[str | None] = mapped_column(String(10))
    reduce_only: Mapped[bool | None] = mapped_column(Boolean, default=False)
    is_working: Mapped[bool | None] = mapped_column(Boolean, default=False)
    is_spot: Mapped[bool] = mapped_column(Boolean, default=True, comment="True=spot, False=futures")
    fee: Mapped[float | None] = mapped_column(Float)
    transact_time: Mapped[int | None] = mapped_column(BigInteger, comment="Server timestamp ms")
    update_time: Mapped[int | None] = mapped_column(BigInteger)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_tabdeal_order_symbol_status", "symbol", "status"),
        Index("idx_tabdeal_order_time", "transact_time"),
    )


class TabdealTradeModel(Base):
    """
    Tabdeal user trade fills (myTrades).
    """

    __tablename__ = "tabdeal_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tabdeal_symbol: Mapped[str | None] = mapped_column(String(30))
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    quote_qty: Mapped[float | None] = mapped_column(Float)
    commission: Mapped[float | None] = mapped_column(Float)
    commission_asset: Mapped[str | None] = mapped_column(String(10))
    is_buyer: Mapped[bool | None] = mapped_column(Boolean)
    is_maker: Mapped[bool | None] = mapped_column(Boolean)
    trade_time: Mapped[int | None] = mapped_column(BigInteger, comment="Server timestamp ms")
    is_spot: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_tabdeal_trade_symbol_time", "symbol", "trade_time"),
    )


class TabdealAccountModel(Base):
    """
    Tabdeal account snapshot (balances, permissions).
    """

    __tablename__ = "tabdeal_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_type: Mapped[str | None] = mapped_column(String(20))
    can_trade: Mapped[bool | None] = mapped_column(Boolean)
    can_withdraw: Mapped[bool | None] = mapped_column(Boolean)
    can_deposit: Mapped[bool | None] = mapped_column(Boolean)
    maker_commission: Mapped[int | None] = mapped_column(Integer)
    taker_commission: Mapped[int | None] = mapped_column(Integer)
    balances_json: Mapped[str | None] = mapped_column(Text, comment="Full balances array as JSON")
    permissions_json: Mapped[str | None] = mapped_column(Text)
    update_time: Mapped[int | None] = mapped_column(BigInteger)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TabdealBalanceModel(Base):
    """
    Individual asset balance within a Tabdeal account.
    """

    __tablename__ = "tabdeal_balances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    asset: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    free: Mapped[float] = mapped_column(Float, default=0.0)
    frozen: Mapped[float] = mapped_column(Float, default=0.0)
    is_spot: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TabdealMarketInfoModel(Base):
    """
    Tabdeal exchange market/symbol info.
    """

    __tablename__ = "tabdeal_markets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tabdeal_symbol: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str | None] = mapped_column(String(20))
    base_asset: Mapped[str | None] = mapped_column(String(10))
    quote_asset: Mapped[str | None] = mapped_column(String(10))
    base_precision: Mapped[int | None] = mapped_column(Integer)
    quote_precision: Mapped[int | None] = mapped_column(Integer)
    order_types_json: Mapped[str | None] = mapped_column(Text)
    min_price: Mapped[float | None] = mapped_column(Float)
    max_price: Mapped[float | None] = mapped_column(Float)
    tick_size: Mapped[float | None] = mapped_column(Float)
    min_qty: Mapped[float | None] = mapped_column(Float)
    step_size: Mapped[float | None] = mapped_column(Float)
    min_notional: Mapped[float | None] = mapped_column(Float)
    is_spot: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_tabdeal_market_status", "status"),
    )


class TabdealListenKeyModel(Base):
    """
    Tabdeal WebSocket listen key management.
    """

    __tablename__ = "tabdeal_listen_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listen_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    ws_type: Mapped[str] = mapped_column(String(20), default="spot", comment="spot / futures")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
