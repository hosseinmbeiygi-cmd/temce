"""Fix BrsApi model schema mismatches

- Index: state column 20→50 (StringDataRightTruncationError)
- Option: add orderbook columns (bid/ask count/volume/price 1-5)
- IME Options: add call_contract_id, put_contract_id
- IME Certificates: add price_max_change, price_max_change_pct, price_min_change, price_min_change_pct
- IME Funds: add orderbook columns (bid/ask count/volume/price 1-5)

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # ── 1. Index: state column 20→50 ─────────────────────────
    op.alter_column(
        "brsapi_index_values",
        "state",
        type_=sa.String(50),
        existing_type=sa.String(20),
        nullable=True,
    )
    
    # ── 2. Option orderbook fields (5 levels) ─────────────────
    for table in ("brsapi_option_snapshots",):
        for side, prefix in [("bid", "zd"), ("ask", "zo")]:
            for i in range(1, 6):
                col_count = f"{side}_count_{i}"
                col_volume = f"{side}_volume_{i}"
                col_price = f"{side}_price_{i}"
                if not _column_exists(conn, table, col_count):
                    op.add_column(table, sa.Column(col_count, sa.Integer(), nullable=True))
                if not _column_exists(conn, table, col_volume):
                    op.add_column(table, sa.Column(col_volume, sa.Integer(), nullable=True))
                if not _column_exists(conn, table, col_price):
                    op.add_column(table, sa.Column(col_price, sa.Float(), nullable=True))
    
    # ── 3. IME Options: call_contract_id, put_contract_id ─────
    for col in ("call_contract_id", "put_contract_id"):
        if not _column_exists(conn, "brsapi_ime_options", col):
            op.add_column("brsapi_ime_options", sa.Column(col, sa.BigInteger(), nullable=True))
    
    # ── 4. IME Certificates: price_max_change etc. ────────────
    for col in ("price_max_change", "price_max_change_pct", "price_min_change", "price_min_change_pct"):
        if not _column_exists(conn, "brsapi_ime_certificates", col):
            op.add_column("brsapi_ime_certificates", sa.Column(col, sa.Float(), nullable=True))
    
    # ── 5. IME Funds: orderbook (5 levels) ───────────────────
    for side, cnt_prefix, vol_prefix in [("bid", "zd", "qd"), ("ask", "zo", "qo")]:
        for i in range(1, 6):
            col_count = f"{side}_count_{i}"
            col_volume = f"{side}_volume_{i}"
            col_price = f"{side}_price_{i}"
            if not _column_exists(conn, "brsapi_ime_funds", col_count):
                op.add_column("brsapi_ime_funds", sa.Column(col_count, sa.Integer(), nullable=True))
            if not _column_exists(conn, "brsapi_ime_funds", col_volume):
                op.add_column("brsapi_ime_funds", sa.Column(col_volume, sa.BigInteger(), nullable=True))
            if not _column_exists(conn, "brsapi_ime_funds", col_price):
                op.add_column("brsapi_ime_funds", sa.Column(col_price, sa.Float(), nullable=True))

    # ── 6. IME Futures: verify all orderbook columns exist ──
    # The model defines them but the DB table might be from an older migration.
    for side in ("bid", "ask"):
        for i in range(1, 4):
            for col_def in [
                (f"{side}_volume_{i}", sa.Integer()),
                (f"{side}_price_{i}", sa.Float()),
            ]:
                col_name, col_type = col_def
                if not _column_exists(conn, "brsapi_ime_futures", col_name):
                    op.add_column("brsapi_ime_futures", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    # Reverse changes (drop added columns, revert state size)
    conn = op.get_bind()
    
    # 1. Index state back to 20
    op.alter_column(
        "brsapi_index_values",
        "state",
        type_=sa.String(20),
        existing_type=sa.String(50),
        nullable=True,
    )
    
    # 2. Option orderbook
    for table in ("brsapi_option_snapshots",):
        for side in ("bid", "ask"):
            for i in range(1, 6):
                for suffix in ("count", "volume", "price"):
                    col = f"{side}_{suffix}_{i}"
                    if _column_exists(conn, table, col):
                        op.drop_column(table, col)
    
    # 3. IME Options
    for col in ("call_contract_id", "put_contract_id"):
        if _column_exists(conn, "brsapi_ime_options", col):
            op.drop_column("brsapi_ime_options", col)
    
    # 4. IME Certificates
    for col in ("price_max_change", "price_max_change_pct", "price_min_change", "price_min_change_pct"):
        if _column_exists(conn, "brsapi_ime_certificates", col):
            op.drop_column("brsapi_ime_certificates", col)
    
    # 5. IME Funds orderbook
    for side in ("bid", "ask"):
        for i in range(1, 6):
            for suffix in ("count", "volume", "price"):
                col = f"{side}_{suffix}_{i}"
                if _column_exists(conn, "brsapi_ime_funds", col):
                    op.drop_column("brsapi_ime_funds", col)


def _column_exists(conn: Any, table: str, column: str) -> bool:
    """Check if a column exists in PostgreSQL."""
    from sqlalchemy import text
    try:
        result = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        )
        return result.fetchone() is not None
    except Exception:
        return False
