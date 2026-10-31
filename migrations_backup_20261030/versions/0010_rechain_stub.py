"""Re-chain stub — placeholder for a previously-removed revision.

Second half of the chain repair started in ``0009_rechain_stub``. This
no-op revision links ``0009`` → ``0010`` so that
``0011_add_price_volume_columns`` (whose ``down_revision`` is ``"0010"``)
resolves correctly.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op — chain repair only."""
    pass


def downgrade() -> None:
    """No-op — chain repair only."""
    pass
