"""add pre-buy decision sheet tables

Revision ID: 0060
Revises: 0059
Create Date: 2026-09-20

The «بانک سؤالات پیش از خرید سهم» needs a place to keep a *judgement record*, not just
answers. Two tables, split by mutability:

* ``pre_buy_sheets`` — the working draft. Exactly one open draft per user per symbol
  (enforced by a partial unique index on ``status = 'DRAFT'``), rewritten as the user
  fills the 115 questions. ``verdict``/``completion_pct``/``detail`` are cached output of
  ``core.question_bank.engine.evaluate``; they are always recomputed server-side, so a
  client cannot submit a cleared sheet it did not actually complete.
* ``pre_buy_reviews`` — append-only submissions. Every submit freezes ``answers`` +
  ``evidence`` + ``detail`` and their ``input_hash``, which is what makes the sheet
  defensible a year later. Editing after submit creates a new row rather than mutating
  this one.

Answers and evidence are JSONB keyed by question code (``PB-001`` … ``PB-115``) with
``bank_version`` stored alongside, so an old sheet still renders after the bank is
revised even though unknown codes are ignored by the engine. Status and verdict are
``VARCHAR + CHECK`` per the house rule (no PostgreSQL ENUM), and additive-only: nothing
existing is touched.

``next_review_at`` comes from stage 9's «تاریخ بازبینی بعدی» so a later sweep can flag
sheets whose analysis has quietly gone stale.
"""

from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS pre_buy_sheets (
        id               BIGSERIAL PRIMARY KEY,
        user_id          VARCHAR(50)  NOT NULL REFERENCES users(id),
        symbol           VARCHAR(60)  NOT NULL,
        instrument_name  VARCHAR(150),
        bank_version     VARCHAR(20)  NOT NULL,
        status           VARCHAR(20)  NOT NULL DEFAULT 'DRAFT'
                         CHECK (status IN ('DRAFT', 'SUBMITTED', 'ABANDONED')),
        answers          JSONB        NOT NULL DEFAULT '{}'::jsonb,
        evidence         JSONB        NOT NULL DEFAULT '{}'::jsonb,
        detail           JSONB,
        verdict          VARCHAR(30)  NOT NULL DEFAULT 'not_started'
                         CHECK (verdict IN ('not_started', 'in_progress', 'blocked_unknown',
                                            'hold', 'vetoed', 'cleared')),
        completion_pct   INTEGER      NOT NULL DEFAULT 0
                         CHECK (completion_pct BETWEEN 0 AND 100),
        input_hash       VARCHAR(64),
        updated_at       TIMESTAMP,
        submitted_at     TIMESTAMP,
        next_review_at   TIMESTAMP,
        created_at       TIMESTAMP    NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pb_sheet_user ON pre_buy_sheets (user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_pb_sheet_symbol ON pre_buy_sheets (symbol)",
    "CREATE INDEX IF NOT EXISTS idx_pb_sheet_review ON pre_buy_sheets (next_review_at)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_pb_sheet_open_draft
        ON pre_buy_sheets (user_id, symbol)
        WHERE status = 'DRAFT'
    """,
    """
    CREATE TABLE IF NOT EXISTS pre_buy_reviews (
        id              BIGSERIAL PRIMARY KEY,
        sheet_id        BIGINT       NOT NULL REFERENCES pre_buy_sheets(id) ON DELETE CASCADE,
        user_id         VARCHAR(50)  NOT NULL REFERENCES users(id),
        symbol          VARCHAR(60)  NOT NULL,
        bank_version    VARCHAR(20)  NOT NULL,
        answers         JSONB        NOT NULL,
        evidence        JSONB        NOT NULL,
        detail          JSONB,
        verdict         VARCHAR(30)  NOT NULL
                        CHECK (verdict IN ('not_started', 'in_progress', 'blocked_unknown',
                                           'hold', 'vetoed', 'cleared')),
        completion_pct  INTEGER      NOT NULL DEFAULT 0,
        input_hash      VARCHAR(64)  NOT NULL,
        statement       TEXT,
        created_at      TIMESTAMP    NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pb_review_user ON pre_buy_reviews (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_pb_review_symbol ON pre_buy_reviews (symbol, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_pb_review_hash ON pre_buy_reviews (input_hash)",
]


def upgrade() -> None:
    for stmt in _DDL:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pre_buy_reviews")
    op.execute("DROP TABLE IF EXISTS pre_buy_sheets")
