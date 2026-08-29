"""0042 – brsapi_raw_payloads: add v5.0 Raw_Tick audit columns.

Revision ID: 0042
Revises: 0041
Create Date: 2026-08-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "brsapi_raw_payloads",
        sa.Column("receive_time", sa.DateTime(), nullable=True, comment="Wall-clock at client receive"),
    )
    op.add_column(
        "brsapi_raw_payloads",
        sa.Column("market_time", sa.DateTime(), nullable=True, comment="Market timestamp inside the payload"),
    )
    op.add_column(
        "brsapi_raw_payloads",
        sa.Column("response_latency_ms", sa.Float(), nullable=True, comment="Round-trip latency in ms"),
    )
    op.add_column(
        "brsapi_raw_payloads",
        sa.Column("schema_version", sa.String(40), nullable=True, comment="Payload schema version (raw_payload.vN)"),
    )
    op.add_column(
        "brsapi_raw_payloads",
        sa.Column("checksum_sha256", sa.String(64), nullable=True, comment="SHA256 of payload"),
    )
    op.create_index(
        "ix_brsapi_raw_payloads_checksum_sha256",
        "brsapi_raw_payloads",
        ["checksum_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_brsapi_raw_payloads_checksum_sha256", table_name="brsapi_raw_payloads")
    op.drop_column("brsapi_raw_payloads", "checksum_sha256")
    op.drop_column("brsapi_raw_payloads", "schema_version")
    op.drop_column("brsapi_raw_payloads", "response_latency_ms")
    op.drop_column("brsapi_raw_payloads", "market_time")
    op.drop_column("brsapi_raw_payloads", "receive_time")
