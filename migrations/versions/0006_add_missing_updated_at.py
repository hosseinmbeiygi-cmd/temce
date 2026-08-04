"""Add updated_at column to tables that have created_at but are missing updated_at

Tables with created_at but missing updated_at (52 total):
- analysis_reports, brsapi_*, codal_*, commodity_*, etc.
- news_articles, trades, signals, recommendations, orderbooks, etc.

This fixes SQLAlchemy TimestampMixin compatibility.

Revision ID: 0006
Revises: 0005_add_performance_indexes
"""
from __future__ import annotations

import contextlib

import sqlalchemy as sa
from alembic import op

revision = "0006_add_missing_updated_at"
down_revision = "0005_add_performance_indexes"
branch_labels = None
depends_on = None

TABLES_NEEDING_UPDATED_AT = [
    "analysis_reports",
    "brsapi_candlesticks",
    "brsapi_codal_announcements",
    "brsapi_commodity_prices",
    "brsapi_crypto_prices",
    "brsapi_currency_24h",
    "brsapi_currency_prices",
    "brsapi_gold_24h",
    "brsapi_gold_coin_history",
    "brsapi_gold_coin_prices",
    "brsapi_gold_currency_pro_daily_history",
    "brsapi_gold_currency_pro_history_24h",
    "brsapi_gold_currency_pro_prices",
    "brsapi_historical_daily",
    "brsapi_historical_real_legal",
    "brsapi_ime_certificates",
    "brsapi_ime_funds",
    "brsapi_ime_futures",
    "brsapi_ime_options",
    "brsapi_ime_physical_trades",
    "brsapi_index_values",
    "brsapi_intraday_trades",
    "brsapi_nav_records",
    "brsapi_option_snapshots",
    "brsapi_raw_payloads",
    "brsapi_shareholder_records",
    "brsapi_symbol_snapshots",
    "codal_announcements",
    "codal_financial_statements",
    "codal_reports",
    "commodity_trades",
    "data_lineage",
    "fact_growth",
    "fact_quality_signals",
    "fact_ratios",
    "fact_text_analytics",
    "import_document_tables",
    "indicators",
    "macro_indicators",
    "ml_predictions",
    "news_articles",
    "orderbooks",
    "recommendations",
    "signals",
    "symbol_relations",
    "tabdeal_accounts",
    "tabdeal_balances",
    "tabdeal_listen_keys",
    "tabdeal_markets",
    "tabdeal_orders",
    "tabdeal_trades",
    "trades",
]


def upgrade() -> None:
    for table_name in TABLES_NEEDING_UPDATED_AT:
        with contextlib.suppress(Exception):
            op.add_column(
                table_name,
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=True,
                    server_default=None,
                ),
            )


def downgrade() -> None:
    for table_name in TABLES_NEEDING_UPDATED_AT:
        with contextlib.suppress(Exception):
            op.drop_column(table_name, "updated_at")
