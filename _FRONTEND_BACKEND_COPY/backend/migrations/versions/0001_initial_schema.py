"""Initial schema - 19 tables based on BrsApi.ir endpoints

Revision ID: 0001
Revises: None
"""

import sqlalchemy as sa
from alembic import op

TIMESTAMPTZ = sa.DateTime(timezone=True)

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. symbols
    op.create_table(
        "symbols",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(200)),
        sa.Column("isin", sa.String(50), index=True),
        sa.Column("market_type", sa.String(20)),
        sa.Column("asset_class", sa.String(20), index=True),
        sa.Column("industry", sa.String(200)),
        sa.Column("industry_id", sa.Integer),
        sa.Column("total_shares", sa.BigInteger),
        sa.Column("base_volume", sa.BigInteger),
        sa.Column("eps", sa.Numeric),
        sa.Column("pe", sa.Numeric),
        sa.Column("tick_size", sa.Numeric),
        sa.Column("lot_size", sa.Integer, server_default="1"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 2. symbol_snapshots
    op.create_table(
        "symbol_snapshots",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("time", TIMESTAMPTZ, nullable=False),
        sa.Column("price_last", sa.Numeric),
        sa.Column("price_close", sa.Numeric),
        sa.Column("price_first", sa.Numeric),
        sa.Column("price_yesterday", sa.Numeric),
        sa.Column("price_change", sa.Numeric),
        sa.Column("price_change_pct", sa.Numeric),
        sa.Column("price_close_change", sa.Numeric),
        sa.Column("price_close_change_pct", sa.Numeric),
        sa.Column("price_min", sa.Numeric),
        sa.Column("price_max", sa.Numeric),
        sa.Column("limit_low", sa.Numeric),
        sa.Column("limit_high", sa.Numeric),
        sa.Column("trade_count", sa.Integer),
        sa.Column("trade_volume", sa.BigInteger),
        sa.Column("trade_value", sa.Numeric),
        sa.Column("market_value", sa.Numeric),
        sa.Column("real_buy_count", sa.Integer),
        sa.Column("real_sell_count", sa.Integer),
        sa.Column("legal_buy_count", sa.Integer),
        sa.Column("legal_sell_count", sa.Integer),
        sa.Column("real_buy_volume", sa.BigInteger),
        sa.Column("real_sell_volume", sa.BigInteger),
        sa.Column("legal_buy_volume", sa.BigInteger),
        sa.Column("legal_sell_volume", sa.BigInteger),
        sa.PrimaryKeyConstraint("symbol_id", "time"),
    )
    op.create_index("idx_symbol_snapshots_time", "symbol_snapshots", ["time"])
    op.execute(
        "SELECT create_hypertable('symbol_snapshots', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )

    # 3. orderbook_snapshots
    op.create_table(
        "orderbook_snapshots",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("time", TIMESTAMPTZ, nullable=False),
        sa.Column("bid_count_1", sa.Integer),
        sa.Column("bid_volume_1", sa.BigInteger),
        sa.Column("bid_price_1", sa.Numeric),
        sa.Column("ask_count_1", sa.Integer),
        sa.Column("ask_volume_1", sa.BigInteger),
        sa.Column("ask_price_1", sa.Numeric),
        sa.Column("bid_count_2", sa.Integer),
        sa.Column("bid_volume_2", sa.BigInteger),
        sa.Column("bid_price_2", sa.Numeric),
        sa.Column("ask_count_2", sa.Integer),
        sa.Column("ask_volume_2", sa.BigInteger),
        sa.Column("ask_price_2", sa.Numeric),
        sa.Column("bid_count_3", sa.Integer),
        sa.Column("bid_volume_3", sa.BigInteger),
        sa.Column("bid_price_3", sa.Numeric),
        sa.Column("ask_count_3", sa.Integer),
        sa.Column("ask_volume_3", sa.BigInteger),
        sa.Column("ask_price_3", sa.Numeric),
        sa.Column("bid_count_4", sa.Integer),
        sa.Column("bid_volume_4", sa.BigInteger),
        sa.Column("bid_price_4", sa.Numeric),
        sa.Column("ask_count_4", sa.Integer),
        sa.Column("ask_volume_4", sa.BigInteger),
        sa.Column("ask_price_4", sa.Numeric),
        sa.Column("bid_count_5", sa.Integer),
        sa.Column("bid_volume_5", sa.BigInteger),
        sa.Column("bid_price_5", sa.Numeric),
        sa.Column("ask_count_5", sa.Integer),
        sa.Column("ask_volume_5", sa.BigInteger),
        sa.Column("ask_price_5", sa.Numeric),
        sa.PrimaryKeyConstraint("symbol_id", "time"),
    )
    op.execute(
        "SELECT create_hypertable('orderbook_snapshots', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )

    # 4. intraday_trades
    op.create_table(
        "intraday_trades",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("seq_no", sa.Integer, nullable=False),
        sa.Column("time", sa.Time, nullable=False),
        sa.Column("volume", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric, nullable=False),
        sa.Column("is_canceled", sa.Boolean, server_default="false"),
        sa.PrimaryKeyConstraint("symbol_id", "trade_date", "seq_no"),
    )
    op.execute(
        "SELECT create_hypertable('intraday_trades', 'trade_date', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )

    # 5. daily_history
    op.create_table(
        "daily_history",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("trade_count", sa.Integer),
        sa.Column("trade_volume", sa.BigInteger),
        sa.Column("trade_value", sa.Numeric),
        sa.Column("price_min", sa.Numeric),
        sa.Column("price_max", sa.Numeric),
        sa.Column("price_yesterday", sa.Numeric),
        sa.Column("price_first", sa.Numeric),
        sa.Column("price_last", sa.Numeric),
        sa.Column("price_last_change", sa.Numeric),
        sa.Column("price_last_change_pct", sa.Numeric),
        sa.Column("price_close", sa.Numeric),
        sa.Column("price_close_change", sa.Numeric),
        sa.Column("price_close_change_pct", sa.Numeric),
        sa.PrimaryKeyConstraint("symbol_id", "trade_date"),
    )
    op.execute(
        "SELECT create_hypertable('daily_history', 'trade_date', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE)"
    )

    # 6. daily_real_legal
    op.create_table(
        "daily_real_legal",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("real_buy_count", sa.Integer),
        sa.Column("real_sell_count", sa.Integer),
        sa.Column("legal_buy_count", sa.Integer),
        sa.Column("legal_sell_count", sa.Integer),
        sa.Column("real_buy_volume", sa.BigInteger),
        sa.Column("real_sell_volume", sa.BigInteger),
        sa.Column("legal_buy_volume", sa.BigInteger),
        sa.Column("legal_sell_volume", sa.BigInteger),
        sa.Column("real_buy_value", sa.Numeric),
        sa.Column("real_sell_value", sa.Numeric),
        sa.Column("legal_buy_value", sa.Numeric),
        sa.Column("legal_sell_value", sa.Numeric),
        sa.PrimaryKeyConstraint("symbol_id", "trade_date"),
    )
    op.execute(
        "SELECT create_hypertable('daily_real_legal', 'trade_date', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE)"
    )

    # 7. candlesticks
    op.create_table(
        "candlesticks",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("candle_type", sa.SmallInteger, nullable=False),
        sa.Column("time", TIMESTAMPTZ, nullable=False),
        sa.Column("open", sa.Numeric, nullable=False),
        sa.Column("high", sa.Numeric, nullable=False),
        sa.Column("low", sa.Numeric, nullable=False),
        sa.Column("close", sa.Numeric, nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.PrimaryKeyConstraint("symbol_id", "candle_type", "time"),
    )
    op.execute(
        "SELECT create_hypertable('candlesticks', 'time', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )

    # 8. shareholders
    op.create_table(
        "shareholders",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("record_date", sa.Date, nullable=False),
        sa.Column("holder_name", sa.String(500), nullable=False),
        sa.Column("volume", sa.BigInteger),
        sa.Column("percent", sa.Numeric),
        sa.Column("change", sa.Numeric),
        sa.PrimaryKeyConstraint("symbol_id", "record_date", "holder_name"),
    )
    op.execute(
        "SELECT create_hypertable('shareholders', 'record_date', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE)"
    )

    # 9. codal_announcements
    op.create_table(
        "codal_announcements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), index=True),
        sa.Column("symbol_name", sa.String(200)),
        sa.Column("title", sa.Text),
        sa.Column("code", sa.String(50)),
        sa.Column("category", sa.Integer),
        sa.Column("date_title", sa.Date),
        sa.Column("date_send", TIMESTAMPTZ),
        sa.Column("date_publish", TIMESTAMPTZ, index=True),
        sa.Column("link", sa.Text),
        sa.Column("link_pdf", sa.Text),
        sa.Column("link_excel", sa.Text),
        sa.Column("link_attachment", sa.Text),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 10. indices
    op.create_table(
        "indices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200)),
        sa.Column("value", sa.Numeric),
        sa.Column("change_value", sa.Numeric),
        sa.Column("change_pct", sa.Numeric),
        sa.Column("time", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 11. etf_nav
    op.create_table(
        "etf_nav",
        sa.Column("symbol_id", sa.BigInteger, sa.ForeignKey("symbols.id"), nullable=False),
        sa.Column("time", TIMESTAMPTZ, nullable=False),
        sa.Column("nav", sa.Numeric),
        sa.Column("price", sa.Numeric),
        sa.Column("discount_premium", sa.Numeric),
        sa.PrimaryKeyConstraint("symbol_id", "time"),
    )
    op.execute(
        "SELECT create_hypertable('etf_nav', 'time', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )

    # 12. options
    op.create_table(
        "options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(50)),
        sa.Column("underlying_symbol", sa.String(20)),
        sa.Column("strike_price", sa.Numeric),
        sa.Column("expiry_date", sa.Date),
        sa.Column("option_type", sa.String(10)),
        sa.Column("price_last", sa.Numeric),
        sa.Column("price_close", sa.Numeric),
        sa.Column("trade_count", sa.Integer),
        sa.Column("trade_volume", sa.BigInteger),
        sa.Column("time", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 13. commodity_trades
    op.create_table(
        "commodity_trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(50)),
        sa.Column("name", sa.String(200)),
        sa.Column("trade_date", sa.Date),
        sa.Column("price", sa.Numeric),
        sa.Column("volume", sa.Numeric),
        sa.Column("value", sa.Numeric),
        sa.Column("counter_party", sa.String(200)),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 14. commodity_funds
    op.create_table(
        "commodity_funds",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(50)),
        sa.Column("name", sa.String(200)),
        sa.Column("nav", sa.Numeric),
        sa.Column("price", sa.Numeric),
        sa.Column("time", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 15. commodity_certificates
    op.create_table(
        "commodity_certificates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(50)),
        sa.Column("name", sa.String(200)),
        sa.Column("price", sa.Numeric),
        sa.Column("volume", sa.BigInteger),
        sa.Column("time", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 16. commodity_futures
    op.create_table(
        "commodity_futures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(50)),
        sa.Column("name", sa.String(200)),
        sa.Column("expiry_date", sa.Date),
        sa.Column("price_last", sa.Numeric),
        sa.Column("price_close", sa.Numeric),
        sa.Column("trade_count", sa.Integer),
        sa.Column("trade_volume", sa.BigInteger),
        sa.Column("time", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 17. commodity_options
    op.create_table(
        "commodity_options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(50)),
        sa.Column("name", sa.String(200)),
        sa.Column("underlying", sa.String(50)),
        sa.Column("strike_price", sa.Numeric),
        sa.Column("expiry_date", sa.Date),
        sa.Column("option_type", sa.String(10)),
        sa.Column("price_last", sa.Numeric),
        sa.Column("time", TIMESTAMPTZ, server_default=sa.func.now()),
    )

    # 18. commodity_prices
    op.create_table(
        "commodity_prices",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("time", TIMESTAMPTZ, nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("price", sa.Numeric),
        sa.Column("change_value", sa.Numeric),
        sa.Column("change_pct", sa.Numeric),
        sa.Column("unit", sa.String(20)),
        sa.PrimaryKeyConstraint("symbol", "time"),
    )
    op.execute(
        "SELECT create_hypertable('commodity_prices', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )

    # 19. gold_currency_prices
    op.create_table(
        "gold_currency_prices",
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("time", TIMESTAMPTZ, nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("name_en", sa.String(100)),
        sa.Column("sign", sa.String(10)),
        sa.Column("price", sa.Numeric),
        sa.Column("change_value", sa.Numeric),
        sa.Column("change_pct", sa.Numeric),
        sa.Column("unit", sa.String(20)),
        sa.Column("section", sa.String(20)),
        sa.PrimaryKeyConstraint("symbol", "time"),
    )
    op.execute(
        "SELECT create_hypertable('gold_currency_prices', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("gold_currency_prices")
    op.drop_table("commodity_prices")
    op.drop_table("commodity_options")
    op.drop_table("commodity_futures")
    op.drop_table("commodity_certificates")
    op.drop_table("commodity_funds")
    op.drop_table("commodity_trades")
    op.drop_table("options")
    op.drop_table("etf_nav")
    op.drop_table("indices")
    op.drop_table("codal_announcements")
    op.drop_table("shareholders")
    op.drop_table("candlesticks")
    op.drop_table("daily_real_legal")
    op.drop_table("daily_history")
    op.drop_table("intraday_trades")
    op.drop_table("orderbook_snapshots")
    op.drop_table("symbol_snapshots")
    op.drop_table("symbols")
