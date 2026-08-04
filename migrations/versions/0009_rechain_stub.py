"""Re-chain stub — placeholder for a previously-removed revision.

The migration chain had a gap: ``0011_add_price_volume_columns`` pointed at
revision ``0010``, but no ``0009``/``0010`` files existed, which made
``alembic history``/``upgrade head`` crash with:
    "Revision 0010 referenced from 0010 -> 0011 is not present"

This no-op revision restores a linear chain 0008 → 0009 → 0010 → 0011.
No schema changes are performed here — it exists only to repair the
revision graph so Alembic can resolve the full history.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op — chain repair only."""
    pass


def downgrade() -> None:
    """No-op — chain repair only."""
    pass
