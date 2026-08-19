"""
Feature Store tables
---------------------

Creates the two persistence tables that back the engineered-feature
pipeline and the nightly 110-column screener snapshot:

+--------------------------+---------------------------------------------------+
| Table                    | Purpose                                           |
+==========================+===================================================+
| ml_engineered_features   | Per-(symbol, trade_date) engineered feature rows  |
|                          | computed by ``scripts/build_feature_store.py``    |
|                          | from BrsApi data via the FeatureEngine.          |
+--------------------------+---------------------------------------------------+
| screener_daily_scores    | Daily CANSLIM-style score snapshot with market    |
|                          | /industry ranks + raw 110-column JSONB payload.   |
+--------------------------+---------------------------------------------------+

Revision ID:     0035_feature_store_tables
Revises:         0034_deprecate_old_tables_create_views
Create Date:     2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0035_feature_store_tables"
down_revision = "0034_deprecate_old_tables_create_views"
branch_labels = None
depends_on = None


# ── Upgrade ────────────────────────────────────────────────────────────────

def upgrade() -> None:
    # ── 1. ml_engineered_features ─────────────────────────────────────────
    # Typed columns cover the hot features queried by the ML pipeline /
    # decision engine; the full 115-feature payload is preserved in
    # ``features_json`` so nothing is lost when the FeatureEngine adds or
    # renames fields between schema versions.
    op.create_table(
        "ml_engineered_features",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),

        # ── Price ──
        sa.Column("price_close", sa.Float, nullable=True),
        sa.Column("price_open", sa.Float, nullable=True),
        sa.Column("price_high", sa.Float, nullable=True),
        sa.Column("price_low", sa.Float, nullable=True),

        # ── Volume & value ──
        sa.Column("volume", sa.BigInteger, nullable=True),
        sa.Column("trade_value", sa.Float, nullable=True),
        sa.Column("trade_count", sa.Integer, nullable=True),

        # ── Technical indicators ──
        sa.Column("rsi_14", sa.Float, nullable=True),
        sa.Column("macd_histogram", sa.Float, nullable=True),
        sa.Column("macd_signal", sa.Float, nullable=True),
        sa.Column("bb_upper", sa.Float, nullable=True),
        sa.Column("bb_lower", sa.Float, nullable=True),
        sa.Column("bb_middle", sa.Float, nullable=True),
        sa.Column("sma_5", sa.Float, nullable=True),
        sa.Column("sma_10", sa.Float, nullable=True),
        sa.Column("sma_20", sa.Float, nullable=True),
        sa.Column("sma_50", sa.Float, nullable=True),
        sa.Column("sma_200", sa.Float, nullable=True),
        sa.Column("ema_5", sa.Float, nullable=True),
        sa.Column("ema_10", sa.Float, nullable=True),
        sa.Column("ema_20", sa.Float, nullable=True),
        sa.Column("atr_14", sa.Float, nullable=True),
        sa.Column("volume_zscore", sa.Float, nullable=True),
        sa.Column("volume_ma_20_ratio", sa.Float, nullable=True),

        # ── Real / legal flow ──
        sa.Column("real_buy_ratio", sa.Float, nullable=True),
        sa.Column("legal_buy_ratio", sa.Float, nullable=True),
        sa.Column("real_sell_ratio", sa.Float, nullable=True),
        sa.Column("legal_sell_ratio", sa.Float, nullable=True),
        sa.Column("net_legal_flow", sa.Float, nullable=True),

        # ── Fundamental ──
        sa.Column("eps", sa.Float, nullable=True),
        sa.Column("pe_ratio", sa.Float, nullable=True),
        sa.Column("free_float_pct", sa.Float, nullable=True),
        sa.Column("market_cap", sa.Float, nullable=True),

        # ── Macro correlations ──
        sa.Column("gold_correlation_3d", sa.Float, nullable=True),
        sa.Column("usd_correlation_3d", sa.Float, nullable=True),
        sa.Column("index_correlation_3d", sa.Float, nullable=True),

        # ── Queue features ──
        sa.Column("queue_status", sa.String(16), nullable=True),
        sa.Column("queue_volume_ratio", sa.Float, nullable=True),
        sa.Column("queue_days_streak", sa.Integer, nullable=True),
        sa.Column("queue_type_change", sa.String(20), nullable=True),
        sa.Column("distance_to_limit", sa.Float, nullable=True),

        # ── Outcome labels (targets for supervised ML) ──
        sa.Column("target_return_5d", sa.Float, nullable=True),
        sa.Column("target_return_10d", sa.Float, nullable=True),
        sa.Column("target_direction_5d", sa.Integer, nullable=True),

        # ── Score summary ──
        sa.Column("score_total", sa.Float, nullable=True),
        sa.Column("final_decision", sa.String(16), nullable=True),

        # ── Full payload + metadata ──
        sa.Column("features_json", JSONB, nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),

        sa.PrimaryKeyConstraint("symbol", "trade_date"),
    )

    op.create_index("idx_feat_symbol_date_desc", "ml_engineered_features",
                    ["symbol", sa.text("trade_date DESC")])
    op.create_index("idx_feat_calculated_at", "ml_engineered_features",
                    ["calculated_at"])
    op.create_index("idx_feat_target", "ml_engineered_features",
                    ["target_direction_5d", "trade_date"])

    # ── 2. screener_daily_scores ──────────────────────────────────────────
    op.create_table(
        "screener_daily_scores",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("score_total", sa.REAL, nullable=True),
        sa.Column("score_momentum", sa.REAL, nullable=True),
        sa.Column("score_value", sa.REAL, nullable=True),
        sa.Column("score_growth", sa.REAL, nullable=True),
        sa.Column("score_quality", sa.REAL, nullable=True),
        sa.Column("score_liquidity", sa.REAL, nullable=True),
        sa.Column("score_sentiment", sa.REAL, nullable=True),
        sa.Column("rank_in_market", sa.Integer, nullable=True),
        sa.Column("rank_in_industry", sa.Integer, nullable=True),
        sa.Column("percentile_score", sa.REAL, nullable=True),
        sa.Column("raw_scores", JSONB, nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "trade_date"),
    )

    op.create_index("idx_screener_date_rank", "screener_daily_scores",
                    ["trade_date", "rank_in_market"])


# ── Downgrade ──────────────────────────────────────────────────────────────

def downgrade() -> None:
    op.drop_table("screener_daily_scores")
    op.drop_table("ml_engineered_features")
