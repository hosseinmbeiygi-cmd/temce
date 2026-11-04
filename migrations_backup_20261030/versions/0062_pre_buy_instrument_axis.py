"""add the instrument axis to pre-buy sheets

Revision ID: 0062
Revises: 0061
Create Date: 2026-09-21

``core.question_bank.registry`` now composes the bank from a shared core plus one module
per instrument class, so a sheet must record *which* bank judged it. Judging a call option
with share questions is not a soft degradation — the ★ stoppers are different ones — so the
type is stored, indexed and carried into the frozen review.

Two columns on ``pre_buy_sheets``:

* ``instrument_type`` — VARCHAR + CHECK per the house rule (no PostgreSQL ENUM). The default
  is ``'equity'`` because every row written so far *is* a stock sheet: the platform only ever
  resolved the equity bank. The default records what happened, it does not reinterpret data.
* ``instrument_basis`` — the table and column that decided the type, or the fact that a human
  chose it. A classification is a claim about the user's instrument; keeping the evidence for
  it on the row is what makes a wrong one reviewable instead of silent.

Additive only: ``ADD COLUMN IF NOT EXISTS`` with a server default, so no existing sheet,
review or answer is touched, and re-running the statement is harmless.

``pre_buy_reviews`` gains only ``instrument_type``. The basis stays on the sheet, which the
review already points at, rather than duplicating a string into the append-only table.
"""

from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

_TYPES = (
    "equity", "etf", "fund", "leveraged_fund", "fixed_income", "commodity_fund",
    "commodity_certificate", "future", "option", "portfolio_allocation", "unknown",
)
_TYPE_LIST = ", ".join(f"'{t}'" for t in _TYPES)

_DDL = [
    """
    ALTER TABLE pre_buy_sheets
        ADD COLUMN IF NOT EXISTS instrument_type VARCHAR(24) NOT NULL DEFAULT 'equity'
    """,
    "ALTER TABLE pre_buy_sheets ADD COLUMN IF NOT EXISTS instrument_basis VARCHAR(240)",
    "ALTER TABLE pre_buy_sheets DROP CONSTRAINT IF EXISTS pre_buy_sheets_instrument_type_check",
    f"""
    ALTER TABLE pre_buy_sheets ADD CONSTRAINT pre_buy_sheets_instrument_type_check
        CHECK (instrument_type IN ({_TYPE_LIST}))
    """,
    "CREATE INDEX IF NOT EXISTS idx_pb_sheet_instrument ON pre_buy_sheets (instrument_type)",
    "ALTER TABLE pre_buy_reviews ADD COLUMN IF NOT EXISTS instrument_type VARCHAR(24) NOT NULL DEFAULT 'equity'",
    "ALTER TABLE pre_buy_reviews DROP CONSTRAINT IF EXISTS pre_buy_reviews_instrument_type_check",
    f"""
    ALTER TABLE pre_buy_reviews ADD CONSTRAINT pre_buy_reviews_instrument_type_check
        CHECK (instrument_type IN ({_TYPE_LIST}))
    """,
    "CREATE INDEX IF NOT EXISTS idx_pb_review_instrument ON pre_buy_reviews (instrument_type)",
]


def upgrade() -> None:
    for stmt in _DDL:
        op.execute(stmt)


def downgrade() -> None:
    # Drops only what this revision added. No sheet, review, answer or pre-existing column
    # is touched, so the decision history survives a downgrade and is restored by re-running
    # ``upgrade``.
    op.execute("DROP INDEX IF EXISTS idx_pb_review_instrument")
    op.execute("ALTER TABLE pre_buy_reviews DROP CONSTRAINT IF EXISTS pre_buy_reviews_instrument_type_check")
    op.execute("ALTER TABLE pre_buy_reviews DROP COLUMN IF EXISTS instrument_type")
    op.execute("DROP INDEX IF EXISTS idx_pb_sheet_instrument")
    op.execute("ALTER TABLE pre_buy_sheets DROP CONSTRAINT IF EXISTS pre_buy_sheets_instrument_type_check")
    op.execute("ALTER TABLE pre_buy_sheets DROP COLUMN IF EXISTS instrument_basis")
    op.execute("ALTER TABLE pre_buy_sheets DROP COLUMN IF EXISTS instrument_type")
