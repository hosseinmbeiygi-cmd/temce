"""
BrsApi — Initial Table Creation
================================

Migration version: 0022_create_brsapi_tables
Revision ID:      ``0022``
Revises:          ``0021`` (the last existing migration)

Creates all BrsApi integration tables:
- Raw payloads & sync log
- TSETMC data (snapshots, details, indices, NAV, options, trades, history, shareholders)
- IME data (futures, options, certificates, funds, physical trades)
- Commodity & crypto prices
- Codal announcements
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | None = None
depends_on: str | None = None


def _create_raw_payloads() -> None:
    op.create_table(
        "brsapi_raw_payloads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("endpoint", sa.String(100), nullable=False, index=True),
        sa.Column("params", sa.Text(), nullable=True, comment="URL params as JSON"),
        sa.Column("status_code", sa.Integer(), nullable=True, default=200),
        sa.Column("payload", sa.Text(), nullable=False, comment="Raw JSON payload"),
        sa.Column("size_bytes", sa.Integer(), nullable=True, default=0),
        sa.Column("fetched_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True, index=True),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_sync_log() -> None:
    op.create_table(
        "brsapi_sync_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("endpoint", sa.String(100), nullable=False, index=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=True, default="success",
                  comment="success | partial | error"),
        sa.Column("items_count", sa.Integer(), nullable=True, default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True, default=0.0),
        sa.Column("params_snapshot", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sync_log_endpoint_time", "brsapi_sync_log", ["endpoint", "started_at"])
    op.create_index("idx_sync_log_started", "brsapi_sync_log", ["started_at"])


def _create_symbol_snapshots() -> None:
    op.create_table(
        "brsapi_symbol_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ins_id", sa.String(50), nullable=False, index=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("isin", sa.String(50), nullable=True, index=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("sector_id", sa.String(20), nullable=True),
        sa.Column("shares_count", sa.BigInteger(), nullable=True),
        sa.Column("base_volume", sa.BigInteger(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("eps", sa.Float(), nullable=True),
        sa.Column("pe_ratio", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_yesterday", sa.Float(), nullable=True),
        sa.Column("price_first", sa.Float(), nullable=True),
        sa.Column("price_last", sa.Float(), nullable=True),
        sa.Column("price_last_change", sa.Float(), nullable=True),
        sa.Column("price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("price_close_change", sa.Float(), nullable=True),
        sa.Column("price_close_change_pct", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.BigInteger(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("buy_real_count", sa.Integer(), nullable=True),
        sa.Column("buy_legal_count", sa.Integer(), nullable=True),
        sa.Column("sell_real_count", sa.Integer(), nullable=True),
        sa.Column("sell_legal_count", sa.Integer(), nullable=True),
        sa.Column("buy_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("buy_legal_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_legal_volume", sa.BigInteger(), nullable=True),
        # Orderbook (5 levels bid)
        *(sa.Column(f"bid_count_{i}", sa.Integer(), nullable=True) for i in range(1, 6)),
        *(sa.Column(f"bid_volume_{i}", sa.BigInteger(), nullable=True) for i in range(1, 6)),
        *(sa.Column(f"bid_price_{i}", sa.Float(), nullable=True) for i in range(1, 6)),
        # Orderbook (5 levels ask)
        *(sa.Column(f"ask_count_{i}", sa.Integer(), nullable=True) for i in range(1, 6)),
        *(sa.Column(f"ask_volume_{i}", sa.BigInteger(), nullable=True) for i in range(1, 6)),
        *(sa.Column(f"ask_price_{i}", sa.Float(), nullable=True) for i in range(1, 6)),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True, index=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True, index=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_snap_ins_fetched", "brsapi_symbol_snapshots", ["ins_id", "fetched_at"])
    op.create_index("idx_snap_symbol_fetched", "brsapi_symbol_snapshots", ["symbol", "fetched_at"])


def _create_symbol_details() -> None:
    op.create_table(
        "brsapi_symbol_details",
        sa.Column("ins_id", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("name_en", sa.String(200), nullable=True),
        sa.Column("isin", sa.String(50), nullable=True, index=True),
        sa.Column("code_12", sa.String(20), nullable=True),
        sa.Column("code_5", sa.String(20), nullable=True),
        sa.Column("code_4", sa.String(20), nullable=True),
        sa.Column("market", sa.String(30), nullable=True),
        sa.Column("board", sa.String(50), nullable=True),
        sa.Column("board_id", sa.String(20), nullable=True),
        sa.Column("board_code", sa.String(10), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("sector_id", sa.String(20), nullable=True),
        sa.Column("sub_sector", sa.String(100), nullable=True),
        sa.Column("sub_sector_id", sa.String(20), nullable=True),
        sa.Column("shares_count", sa.BigInteger(), nullable=True),
        sa.Column("shares_issued", sa.BigInteger(), nullable=True),
        sa.Column("base_volume", sa.BigInteger(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("free_float_pct", sa.Float(), nullable=True),
        sa.Column("eps", sa.Float(), nullable=True),
        sa.Column("pe_ratio", sa.Float(), nullable=True),
        sa.Column("group_pe_ratio", sa.Float(), nullable=True),
        sa.Column("ps_ratio", sa.Float(), nullable=True),
        sa.Column("price_min_week", sa.Float(), nullable=True),
        sa.Column("price_max_week", sa.Float(), nullable=True),
        sa.Column("price_min_year", sa.Float(), nullable=True),
        sa.Column("price_max_year", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_yesterday", sa.Float(), nullable=True),
        sa.Column("price_first", sa.Float(), nullable=True),
        sa.Column("price_last", sa.Float(), nullable=True),
        sa.Column("price_last_change", sa.Float(), nullable=True),
        sa.Column("price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("price_close_change", sa.Float(), nullable=True),
        sa.Column("price_close_change_pct", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.BigInteger(), nullable=True),
        sa.Column("trade_volume_avg_month", sa.BigInteger(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("buy_real_count", sa.Integer(), nullable=True),
        sa.Column("buy_legal_count", sa.Integer(), nullable=True),
        sa.Column("sell_real_count", sa.Integer(), nullable=True),
        sa.Column("sell_legal_count", sa.Integer(), nullable=True),
        sa.Column("buy_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("buy_legal_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_legal_volume", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(20), nullable=True),
        sa.Column("date", sa.String(20), nullable=True),
        sa.Column("date_update", sa.String(20), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("assembly", sa.Text(), nullable=True, comment="JSON array of assembly info"),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("ins_id"),
    )


def _create_index_values() -> None:
    op.create_table(
        "brsapi_index_values",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False, index=True),
        sa.Column("state", sa.String(20), nullable=True),
        sa.Column("index_value", sa.Float(), nullable=True),
        sa.Column("index_change", sa.Float(), nullable=True),
        sa.Column("index_change_pct", sa.Float(), nullable=True),
        sa.Column("index_equal_weight", sa.Float(), nullable=True),
        sa.Column("index_equal_weight_change", sa.Float(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("market_value_main", sa.Float(), nullable=True),
        sa.Column("market_value_base", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.BigInteger(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("date", sa.String(20), nullable=True, index=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_index_name_date", "brsapi_index_values", ["name", "date"])


def _create_nav_records() -> None:
    op.create_table(
        "brsapi_nav_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("nav_issue", sa.Float(), nullable=True, comment="NAV صدور"),
        sa.Column("nav_redemption", sa.Float(), nullable=True, comment="NAV ابطال"),
        sa.Column("date", sa.String(20), nullable=True, index=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_nav_symbol_date", "brsapi_nav_records", ["symbol", "date"])


def _create_option_snapshots() -> None:
    op.create_table(
        "brsapi_option_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ins_id", sa.String(50), nullable=False, index=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("isin", sa.String(50), nullable=True),
        sa.Column("underlying_symbol", sa.String(50), nullable=True, index=True),
        sa.Column("underlying_id", sa.String(50), nullable=True),
        sa.Column("option_type", sa.String(10), nullable=True, comment="call / put"),
        sa.Column("contract_size", sa.Integer(), nullable=True),
        sa.Column("strike_price", sa.Float(), nullable=True),
        sa.Column("open_interest", sa.Integer(), nullable=True),
        sa.Column("date_begin", sa.String(20), nullable=True),
        sa.Column("date_end", sa.String(20), nullable=True, index=True),
        sa.Column("days_remaining", sa.Integer(), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("sector_id", sa.String(20), nullable=True),
        # Underlying prices
        sa.Column("underlying_price_yesterday", sa.Float(), nullable=True),
        sa.Column("underlying_price_last", sa.Float(), nullable=True),
        sa.Column("underlying_price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("underlying_price_close", sa.Float(), nullable=True),
        sa.Column("underlying_price_close_change_pct", sa.Float(), nullable=True),
        # Option prices
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_yesterday", sa.Float(), nullable=True),
        sa.Column("price_first", sa.Float(), nullable=True),
        sa.Column("price_last", sa.Float(), nullable=True),
        sa.Column("price_last_change", sa.Float(), nullable=True),
        sa.Column("price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("price_close_change", sa.Float(), nullable=True),
        sa.Column("price_close_change_pct", sa.Float(), nullable=True),
        # Trades
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.Integer(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("notional_value", sa.Float(), nullable=True),
        # Real/Legal
        sa.Column("buy_real_count", sa.Integer(), nullable=True),
        sa.Column("buy_legal_count", sa.Integer(), nullable=True),
        sa.Column("sell_real_count", sa.Integer(), nullable=True),
        sa.Column("sell_legal_count", sa.Integer(), nullable=True),
        sa.Column("buy_real_volume", sa.Integer(), nullable=True),
        sa.Column("buy_legal_volume", sa.Integer(), nullable=True),
        sa.Column("sell_real_volume", sa.Integer(), nullable=True),
        sa.Column("sell_legal_volume", sa.Integer(), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_option_underlying", "brsapi_option_snapshots", ["underlying_symbol", "date_end"])
    op.create_index("idx_option_symbol_fetched", "brsapi_option_snapshots", ["symbol", "fetched_at"])


def _create_intraday_trades() -> None:
    op.create_table(
        "brsapi_intraday_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("row", sa.Integer(), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("canceled", sa.Boolean(), nullable=True, default=False, server_default="false"),
        sa.Column("trade_date", sa.String(20), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trade_symbol_date", "brsapi_intraday_trades", ["symbol", "trade_date"])


def _create_historical_daily() -> None:
    op.create_table(
        "brsapi_historical_daily",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("date", sa.String(20), nullable=False, index=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.BigInteger(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_yesterday", sa.Float(), nullable=True),
        sa.Column("price_first", sa.Float(), nullable=True),
        sa.Column("price_last", sa.Float(), nullable=True),
        sa.Column("price_last_change", sa.Float(), nullable=True),
        sa.Column("price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("price_close_change", sa.Float(), nullable=True),
        sa.Column("price_close_change_pct", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hist_symbol_date", "brsapi_historical_daily", ["symbol", "date"])


def _create_historical_real_legal() -> None:
    op.create_table(
        "brsapi_historical_real_legal",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("date", sa.String(20), nullable=False, index=True),
        sa.Column("buy_real_count", sa.Integer(), nullable=True),
        sa.Column("buy_legal_count", sa.Integer(), nullable=True),
        sa.Column("sell_real_count", sa.Integer(), nullable=True),
        sa.Column("sell_legal_count", sa.Integer(), nullable=True),
        sa.Column("buy_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("buy_legal_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_legal_volume", sa.BigInteger(), nullable=True),
        sa.Column("buy_real_value", sa.Float(), nullable=True),
        sa.Column("buy_legal_value", sa.Float(), nullable=True),
        sa.Column("sell_real_value", sa.Float(), nullable=True),
        sa.Column("sell_legal_value", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_rl_symbol_date", "brsapi_historical_real_legal", ["symbol", "date"])


def _create_candlesticks() -> None:
    op.create_table(
        "brsapi_candlesticks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("date", sa.String(20), nullable=False),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("candle_type", sa.String(10), nullable=True, default="1",
                  comment="1=realtime, 2=unadjusted, 3=adjusted"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_candle_symbol_date", "brsapi_candlesticks", ["symbol", "date", "candle_type"])


def _create_shareholder_records() -> None:
    op.create_table(
        "brsapi_shareholder_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("shareholder_name", sa.String(200), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("percent", sa.Float(), nullable=True),
        sa.Column("change", sa.BigInteger(), nullable=True),
        sa.Column("date", sa.String(20), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sh_symbol_date", "brsapi_shareholder_records", ["symbol", "date"])


def _create_ime_tables() -> None:
    # IME Futures
    op.create_table(
        "brsapi_ime_futures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contract_code", sa.String(50), nullable=False, index=True),
        sa.Column("contract_description", sa.String(300), nullable=True),
        sa.Column("contract_size", sa.Integer(), nullable=True),
        sa.Column("contract_size_unit", sa.String(50), nullable=True),
        sa.Column("contract_currency", sa.String(10), nullable=True),
        sa.Column("date_end", sa.String(20), nullable=True, index=True),
        sa.Column("date_end_text", sa.String(50), nullable=True),
        sa.Column("days_remaining", sa.Integer(), nullable=True),
        sa.Column("margin_initial", sa.Float(), nullable=True),
        sa.Column("margin_maintenance", sa.Float(), nullable=True),
        sa.Column("open_interest", sa.Integer(), nullable=True),
        sa.Column("open_interest_change", sa.Integer(), nullable=True),
        sa.Column("open_interest_change_pct", sa.Float(), nullable=True),
        *(sa.Column(f"price_{field}", sa.Float(), nullable=True) for field in
          ("yesterday", "first", "first_change", "first_change_pct",
           "max", "max_change", "max_change_pct",
           "min", "min_change", "min_change_pct",
           "last", "last_change", "last_change_pct", "last_settlement")),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.Integer(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("trade_value_unit", sa.String(20), nullable=True),
        sa.Column("buy_real_count", sa.Integer(), nullable=True),
        sa.Column("buy_legal_count", sa.Integer(), nullable=True),
        sa.Column("sell_real_count", sa.Integer(), nullable=True),
        sa.Column("sell_legal_count", sa.Integer(), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("date_update", sa.String(20), nullable=True),
        sa.Column("time_update", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ime_futures_code_date", "brsapi_ime_futures", ["contract_code", "date_update"])

    # IME Options
    op.create_table(
        "brsapi_ime_options",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contract_category", sa.String(100), nullable=True),
        sa.Column("contract_category_sub", sa.String(50), nullable=True),
        sa.Column("contract_category_commodity", sa.String(50), nullable=True),
        sa.Column("strike_price", sa.Float(), nullable=True),
        sa.Column("level_strike", sa.String(10), nullable=True),
        # Call side
        sa.Column("call_contract_code", sa.String(50), nullable=True, index=True),
        sa.Column("call_contract_description", sa.String(300), nullable=True),
        sa.Column("call_contract_size", sa.Integer(), nullable=True),
        sa.Column("call_date_end", sa.String(20), nullable=True),
        sa.Column("call_days_remaining", sa.Integer(), nullable=True),
        sa.Column("call_margin_initial", sa.Float(), nullable=True),
        sa.Column("call_margin_required", sa.Float(), nullable=True),
        sa.Column("call_open_interest", sa.Integer(), nullable=True),
        sa.Column("call_price_yesterday", sa.Float(), nullable=True),
        sa.Column("call_price_last", sa.Float(), nullable=True),
        sa.Column("call_price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("call_price_max", sa.Float(), nullable=True),
        sa.Column("call_price_min", sa.Float(), nullable=True),
        sa.Column("call_trade_count", sa.Integer(), nullable=True),
        sa.Column("call_trade_volume", sa.Integer(), nullable=True),
        sa.Column("call_trade_value", sa.Float(), nullable=True),
        # Put side
        sa.Column("put_contract_code", sa.String(50), nullable=True, index=True),
        sa.Column("put_contract_description", sa.String(300), nullable=True),
        sa.Column("put_contract_size", sa.Integer(), nullable=True),
        sa.Column("put_date_end", sa.String(20), nullable=True),
        sa.Column("put_days_remaining", sa.Integer(), nullable=True),
        sa.Column("put_margin_initial", sa.Float(), nullable=True),
        sa.Column("put_margin_required", sa.Float(), nullable=True),
        sa.Column("put_open_interest", sa.Integer(), nullable=True),
        sa.Column("put_price_yesterday", sa.Float(), nullable=True),
        sa.Column("put_price_last", sa.Float(), nullable=True),
        sa.Column("put_price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("put_trade_count", sa.Integer(), nullable=True),
        sa.Column("put_trade_volume", sa.Integer(), nullable=True),
        sa.Column("put_trade_value", sa.Float(), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("date_update", sa.String(20), nullable=True),
        sa.Column("time_update", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ime_option_call_code", "brsapi_ime_options", ["call_contract_code"])
    op.create_index("idx_ime_option_put_code", "brsapi_ime_options", ["put_contract_code"])

    # IME Certificates
    op.create_table(
        "brsapi_ime_certificates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("commodity", sa.String(100), nullable=True),
        sa.Column("contract_code", sa.String(50), nullable=False, index=True),
        sa.Column("contract_description", sa.String(300), nullable=True),
        sa.Column("contract_size", sa.Integer(), nullable=True),
        sa.Column("contract_size_unit", sa.String(50), nullable=True),
        sa.Column("contract_currency", sa.String(10), nullable=True),
        sa.Column("price_yesterday", sa.Float(), nullable=True),
        sa.Column("price_first", sa.Float(), nullable=True),
        sa.Column("price_first_change", sa.Float(), nullable=True),
        sa.Column("price_first_change_pct", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_last", sa.Float(), nullable=True),
        sa.Column("price_last_change", sa.Float(), nullable=True),
        sa.Column("price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.Integer(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("trade_value_unit", sa.String(20), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("date_update", sa.String(20), nullable=True),
        sa.Column("time_update", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # IME Funds
    op.create_table(
        "brsapi_ime_funds",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ins_id", sa.String(50), nullable=False, index=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("isin", sa.String(50), nullable=True),
        sa.Column("shares_count", sa.BigInteger(), nullable=True),
        sa.Column("base_volume", sa.BigInteger(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_yesterday", sa.Float(), nullable=True),
        sa.Column("price_first", sa.Float(), nullable=True),
        sa.Column("price_last", sa.Float(), nullable=True),
        sa.Column("price_last_change", sa.Float(), nullable=True),
        sa.Column("price_last_change_pct", sa.Float(), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("price_close_change", sa.Float(), nullable=True),
        sa.Column("price_close_change_pct", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("trade_volume", sa.BigInteger(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("buy_real_count", sa.Integer(), nullable=True),
        sa.Column("buy_legal_count", sa.Integer(), nullable=True),
        sa.Column("sell_real_count", sa.Integer(), nullable=True),
        sa.Column("sell_legal_count", sa.Integer(), nullable=True),
        sa.Column("buy_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("buy_legal_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_real_volume", sa.BigInteger(), nullable=True),
        sa.Column("sell_legal_volume", sa.BigInteger(), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ime_fund_symbol_fetched", "brsapi_ime_funds", ["symbol", "fetched_at"])

    # IME Physical Trades
    op.create_table(
        "brsapi_ime_physical_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(100), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("category_id", sa.String(50), nullable=True),
        sa.Column("offer_code", sa.String(50), nullable=True),
        sa.Column("market_hall", sa.String(100), nullable=True),
        sa.Column("producer", sa.String(200), nullable=True),
        sa.Column("supplier", sa.String(200), nullable=True),
        sa.Column("broker", sa.String(100), nullable=True),
        sa.Column("contract_type", sa.String(30), nullable=True),
        sa.Column("settlement_type", sa.String(50), nullable=True),
        sa.Column("date_price_settlement", sa.String(20), nullable=True),
        sa.Column("date_delivery", sa.String(20), nullable=True),
        sa.Column("location_delivery", sa.String(200), nullable=True),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("packaging_type", sa.String(50), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("method_offer", sa.String(30), nullable=True),
        sa.Column("method_purchase", sa.String(30), nullable=True),
        sa.Column("date_trade", sa.String(20), nullable=True, index=True),
        sa.Column("price_base", sa.Float(), nullable=True),
        sa.Column("volume_contract", sa.Float(), nullable=True),
        sa.Column("volume_offer", sa.Float(), nullable=True),
        sa.Column("demand", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("price_weighted_avg", sa.Float(), nullable=True),
        sa.Column("trade_value", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ime_physical_trade_date", "brsapi_ime_physical_trades", ["date_trade"])


def _create_commodity_prices() -> None:
    op.create_table(
        "brsapi_commodity_prices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("change_value", sa.Float(), nullable=True),
        sa.Column("change_percent", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True, server_default="USD"),
        sa.Column("category", sa.String(20), nullable=True, index=True,
                  comment="precious_metal | base_metal | energy | other"),
        sa.Column("date", sa.String(20), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("time_unix", sa.BigInteger(), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_commodity_symbol_fetched", "brsapi_commodity_prices", ["symbol", "fetched_at"])
    op.create_index("idx_commodity_cat_fetched", "brsapi_commodity_prices", ["category", "fetched_at"])


def _create_crypto_prices() -> None:
    op.create_table(
        "brsapi_crypto_prices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("price_usd", sa.Float(), nullable=True),
        sa.Column("price_toman", sa.Float(), nullable=True),
        sa.Column("price_irr", sa.Float(), nullable=True),
        sa.Column("change_percent", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("volume_24h", sa.Float(), nullable=True),
        sa.Column("icon_url", sa.String(500), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True, default=0, server_default="0"),
        sa.Column("date", sa.String(20), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("time_unix", sa.BigInteger(), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_crypto_symbol_fetched", "brsapi_crypto_prices", ["symbol", "fetched_at"])
    op.create_index("idx_crypto_rank", "brsapi_crypto_prices", ["rank"])


def _create_codal_announcements() -> None:
    op.create_table(
        "brsapi_codal_announcements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(50), nullable=True, index=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("date_title", sa.String(20), nullable=True),
        sa.Column("date_send", sa.String(20), nullable=True),
        sa.Column("time_send", sa.String(20), nullable=True),
        sa.Column("date_publish", sa.String(20), nullable=True, index=True),
        sa.Column("time_publish", sa.String(20), nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("link_pdf", sa.String(500), nullable=True),
        sa.Column("link_excel", sa.String(500), nullable=True),
        sa.Column("link_attachment", sa.String(500), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_codal_symbol_publish", "brsapi_codal_announcements", ["symbol", "date_publish"])
    op.create_index("idx_codal_publish_date", "brsapi_codal_announcements", ["date_publish"])


# ─────── UPGRADE ──────────────────────────────────


def upgrade() -> None:
    _create_raw_payloads()
    _create_sync_log()
    _create_symbol_snapshots()
    _create_symbol_details()
    _create_index_values()
    _create_nav_records()
    _create_option_snapshots()
    _create_intraday_trades()
    _create_historical_daily()
    _create_historical_real_legal()
    _create_candlesticks()
    _create_shareholder_records()
    _create_ime_tables()
    _create_commodity_prices()
    _create_crypto_prices()
    _create_codal_announcements()


# ─────── DOWNGRADE ────────────────────────────────


def downgrade() -> None:
    tables = [
        "brsapi_codal_announcements",
        "brsapi_crypto_prices",
        "brsapi_commodity_prices",
        "brsapi_ime_physical_trades",
        "brsapi_ime_funds",
        "brsapi_ime_certificates",
        "brsapi_ime_options",
        "brsapi_ime_futures",
        "brsapi_shareholder_records",
        "brsapi_candlesticks",
        "brsapi_historical_real_legal",
        "brsapi_historical_daily",
        "brsapi_intraday_trades",
        "brsapi_option_snapshots",
        "brsapi_nav_records",
        "brsapi_index_values",
        "brsapi_symbol_details",
        "brsapi_symbol_snapshots",
        "brsapi_sync_log",
        "brsapi_raw_payloads",
    ]
    for table in tables:
        op.drop_table(table, if_exists=True)
