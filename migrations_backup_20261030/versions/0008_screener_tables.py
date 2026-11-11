"""Add screener tables for the 110-column CANSLIM screening system.

Three new tables:
  1. screener_profiles   — static fundamental data per symbol (weekly updates)
  2. screener_snapshots  — intraday time-series snapshots (every ~2 minutes)
  3. screener_signals    — final scores, decisions and risk management output

Revision ID: 0008
Revises: 0007
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ════════════════════════════════════════════
    # TABLE 1: screener_profiles
    # ════════════════════════════════════════════
    op.create_table(
        "screener_profiles",

        # PK
        sa.Column("symbol", sa.String(20), primary_key=True, index=True),

        # بخش اول: اطلاعات پایه
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("sub_industry", sa.String(100), nullable=True),
        sa.Column("free_float_shares", sa.BigInteger(), nullable=True),

        # بخش دوم: داده‌های بنیادی
        sa.Column("eps_current", sa.Float(), nullable=True),
        sa.Column("eps_prev_year", sa.Float(), nullable=True),
        sa.Column("exchange_rate_base", sa.Float(), nullable=True),
        sa.Column("inflation_rate", sa.Float(), nullable=True),
        sa.Column("net_operating_profit", sa.Float(), nullable=True),
        sa.Column("accumulated_loss", sa.Float(), nullable=True),
        sa.Column("registered_capital", sa.Float(), nullable=True),
        sa.Column("legal_reserve", sa.Float(), nullable=True),
        sa.Column("gross_margin", sa.Float(), nullable=True),
        sa.Column("feedstock_price", sa.Float(), nullable=True),
        sa.Column("feedstock_change_pct", sa.Float(), nullable=True),
        sa.Column("capital_increase_type", sa.String(30), nullable=True),
        sa.Column("capital_increase_pct", sa.Float(), nullable=True),

        # بخش سوم: ارزش‌گذاری و کلان
        sa.Column("industry_pe", sa.Float(), nullable=True),
        sa.Column("bank_interest_rate", sa.Float(), nullable=True),
        sa.Column("bond_rate", sa.Float(), nullable=True),
        sa.Column("nima_rate", sa.Float(), nullable=True),
        sa.Column("free_market_rate", sa.Float(), nullable=True),

        # بخش پنجم: فیلترهای رویدادی
        sa.Column("ceo_change_success", sa.Integer(), server_default="0"),
        sa.Column("ceo_change_fail", sa.Integer(), server_default="0"),
        sa.Column("annual_meeting_near", sa.Integer(), server_default="0"),
        sa.Column("annual_meeting_passed", sa.Integer(), server_default="0"),
        sa.Column("capital_increase_cash", sa.Integer(), server_default="0"),
        sa.Column("capital_increase_reval", sa.Integer(), server_default="0"),
        sa.Column("price_liberation_news", sa.Integer(), server_default="0"),
        sa.Column("gov_support_news", sa.Integer(), server_default="0"),
        sa.Column("heavy_legal_case", sa.Integer(), server_default="0"),
        sa.Column("telegram_pump", sa.Integer(), server_default="0"),
        sa.Column("end_of_month", sa.Integer(), server_default="0"),
        sa.Column("pre_holiday", sa.Integer(), server_default="0"),
        sa.Column("political_tension", sa.Integer(), server_default="0"),
        sa.Column("political_relief", sa.Integer(), server_default="0"),
        sa.Column("feedstock_meeting", sa.Integer(), server_default="0"),
        sa.Column("big_ipo", sa.Integer(), server_default="0"),
        sa.Column("new_shareholder_capital", sa.Integer(), server_default="0"),
        sa.Column("positive_mgmt_news", sa.Integer(), server_default="0"),
        sa.Column("negative_mgmt_news", sa.Integer(), server_default="0"),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ════════════════════════════════════════════
    # TABLE 2: screener_snapshots (time-series)
    # ════════════════════════════════════════════
    op.create_table(
        "screener_snapshots",

        # PK (composite)
        sa.Column("symbol", sa.String(20), primary_key=True, index=True),
        sa.Column("timestamp", sa.DateTime(), primary_key=True, index=True),

        # OHLC
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),

        # قیمت و تغییرات
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("price_change_pct", sa.Float(), nullable=True),

        # حجم و ارزش
        sa.Column("today_volume", sa.BigInteger(), nullable=True),
        sa.Column("avg_daily_value", sa.Float(), nullable=True),

        # حقوقی
        sa.Column("institutional_buy", sa.BigInteger(), nullable=True),
        sa.Column("institutional_sell", sa.BigInteger(), nullable=True),

        # فرابورس
        sa.Column("farabourse_price", sa.Float(), nullable=True),
        sa.Column("farabourse_volume", sa.BigInteger(), nullable=True),

        # بافرهای محاسباتی
        sa.Column("atr_14", sa.Float(), nullable=True),
        sa.Column("volume_ma_50", sa.Float(), nullable=True),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Create TimescaleDB hypertable for snapshots (like other time-series tables)
    op.execute(
        "SELECT create_hypertable('screener_snapshots', 'timestamp', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )

    # Index for time-range queries (PK already covers unique(symbol, timestamp))
    op.create_index(
        "ix_screener_snapshots_time_only",
        "screener_snapshots",
        ["timestamp"],
    )

    # ════════════════════════════════════════════
    # TABLE 3: screener_signals
    # ════════════════════════════════════════════
    op.create_table(
        "screener_signals",

        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),

        # شناسه
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now(), index=True),

        # قیمت‌ها
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("live_pe", sa.Float(), nullable=True),
        sa.Column("pe_ratio", sa.Float(), nullable=True),

        # داده‌های بازار
        sa.Column("institutional_ratio", sa.Float(), nullable=True),
        sa.Column("volume_spike", sa.Float(), nullable=True),
        sa.Column("liquidity_pct", sa.Float(), nullable=True),
        sa.Column("nima_free_spread", sa.Float(), nullable=True),

        # نمرات میانی
        sa.Column("score_fundamental", sa.Float(), nullable=True),
        sa.Column("score_valuation", sa.Float(), nullable=True),
        sa.Column("score_institutional", sa.Float(), nullable=True),
        sa.Column("score_technical", sa.Float(), nullable=True),
        sa.Column("score_macro", sa.Float(), nullable=True),
        sa.Column("score_gov_support", sa.Float(), nullable=True),
        sa.Column("score_liquidity", sa.Float(), nullable=True),
        sa.Column("score_farabourse", sa.Float(), nullable=True),
        sa.Column("score_feedstock", sa.Float(), nullable=True),

        # نمرات نهایی
        sa.Column("risk_ok", sa.Boolean(), nullable=True),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("adjusted_score", sa.Float(), nullable=True),
        sa.Column("negative_filters_count", sa.Integer(), nullable=True),
        sa.Column("rule_50_30", sa.String(10), nullable=True),

        # مدیریت ریسک
        sa.Column("stop_loss_price", sa.Float(), nullable=True),
        sa.Column("position_size", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(20), nullable=True),

        # رهگیری نتیجه
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(30), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("outcome_correct", sa.Boolean(), nullable=True),
        sa.Column("outcome_set_at", sa.DateTime(), nullable=True),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes for signal table
    op.create_index("ix_screener_signals_symbol_time", "screener_signals", ["symbol", "generated_at"])
    op.create_index("ix_screener_signals_decision", "screener_signals", ["decision"])
    op.create_index("ix_screener_signals_final_score", "screener_signals", ["final_score"])


def downgrade() -> None:
    op.drop_table("screener_signals")
    op.drop_table("screener_snapshots")
    op.drop_table("screener_profiles")
