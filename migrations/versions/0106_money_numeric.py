"""Tier-1 money columns Float -> NUMERIC(24,8) — audit IEEE-754 fix.

Revision ID: 0106
Revises: 0105

Accounting-boundary tables only (all small: signals=4, paper_trades~3k,
paper_equity_history~10, gold_* tiny). Raw vendor feed tables (quotes,
snapshots, indicators) stay Float by design — documented boundary.

NUMERIC(24,8): exact storage + exact SQL aggregates. Python boundary
keeps float via Numeric(asdecimal=False) so no Decimal/float TypeError
in existing arithmetic; models updated to match.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0106"
down_revision: str | None = "0105"
branch_labels: str | None = None
depends_on: str | None = None

_COLS: dict[str, list[str]] = {
    "signals": ["entry", "stop_loss", "take_profit", "confidence",
                "actual_outcome_price", "actual_return_pct"],
    "paper_trades": ["entry_price", "stop_loss_price", "target1_price",
                     "target2_price", "quantity", "capital_allocated",
                     "exit_price", "pnl", "pnl_pct"],
    "paper_equity_history": ["equity", "cash", "open_value", "realized_pnl"],
    "alert_history": ["trigger_value"],
    "gold_alert_rules": ["threshold"],
    "gold_alert_events": ["trigger_value", "threshold"],
    "gold_holdings": ["quantity", "buy_price", "buy_amount_irt"],
    "gold_trades": ["quantity", "price", "amount_irt", "fee_irt", "pnl_irt"],
    "gold_dca_plans": ["total_capital_irt"],
}


def _col_type(conn, table: str, col: str) -> str | None:
    row = conn.execute(
        sa.text("SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "JOIN pg_class ON pg_class.oid = attrelid "
                "WHERE relname = :t AND attname = :c AND NOT attisdropped"),
        {"t": table, "c": col},
    ).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()
    for table, cols in _COLS.items():
        tbl = conn.execute(sa.text("SELECT to_regclass(:n)"),
                           {"n": f"public.{table}"}).scalar()
        if tbl is None:
            print(f"  - {table}: missing — skipping")
            continue
        for col in cols:
            typ = _col_type(conn, table, col)
            if typ is None:
                print(f"  - {table}.{col}: missing — skipping")
            elif typ == "numeric":
                print(f"  = {table}.{col}: already numeric")
            else:
                conn.execute(sa.text(
                    f"ALTER TABLE {table} ALTER COLUMN {col} "
                    f"TYPE NUMERIC(24,8) USING {col}::numeric"))
                print(f"  + {table}.{col}: {typ} -> NUMERIC(24,8)")


def downgrade() -> None:
    conn = op.get_bind()
    for table, cols in _COLS.items():
        tbl = conn.execute(sa.text("SELECT to_regclass(:n)"),
                           {"n": f"public.{table}"}).scalar()
        if tbl is None:
            continue
        for col in cols:
            if _col_type(conn, table, col) == "numeric":
                conn.execute(sa.text(
                    f"ALTER TABLE {table} ALTER COLUMN {col} "
                    f"TYPE DOUBLE PRECISION USING {col}::float8"))
