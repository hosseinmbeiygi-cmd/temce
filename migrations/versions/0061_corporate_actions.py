"""corporate actions + cumulative daily adjust factors

Revision ID: 0061
Revises: 0060
Create Date: 2026-09-21

Closes the biggest data gap found in the senior audit (2026-09-21 §2):
``daily_history`` stores raw TSETMC prices with **no adjustment factor**,
so every capital increase / bonus share / DPS payment silently corrupts
moving averages, RSI and any backtest that spans the event date.

Two tables, one job:

* ``corporate_actions`` — the event ledger (per symbol, per ex-date):
  ``action_type`` ∈ capital_increase | bonus | dividend,
  ``ratio`` (new shares per old share − 1, e.g. 1.0 for a 100% capital
  increase from retained earnings/bonus) and ``dps`` (cash dividend in
  Rials per share). ``source`` records where the row came from (manual,
  codal) plus an optional ``codal_ref`` for traceability.
* ``daily_adjust_factors`` — the *materialized cumulative* factor per
  (symbol, trade_date), computed backwards from the newest event by
  ``services/corporate_action_service.py``. Kept as a real table (not a
  recursive SQL view) so indicator reads are a single indexed lookup.

Factor conventions (standard TSE practice):
  capital_increase/bonus → 1 / (1 + ratio)
  dividend               → (close_at_ex − dps) / close_at_ex   (close from daily_history)

Prices before the ex-date are multiplied by the factor; prices from the
ex-date onward stay raw (= factor 1). Indicators/backtests read the
adjusted series; display and per-capita money-flow stay raw.
"""

from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS corporate_actions (
        symbol_id    BIGINT       NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
        ex_date      DATE         NOT NULL,
        action_type  VARCHAR(20)  NOT NULL
                     CHECK (action_type IN ('capital_increase', 'bonus', 'dividend')),
        ratio        NUMERIC(12,6) NOT NULL DEFAULT 0,
        dps          NUMERIC(20,2) NOT NULL DEFAULT 0,
        source       VARCHAR(20)  NOT NULL DEFAULT 'manual'
                     CHECK (source IN ('manual', 'codal', 'import')),
        codal_ref    TEXT,
        notes        TEXT,
        created_at   TIMESTAMP    NOT NULL DEFAULT now(),
        PRIMARY KEY (symbol_id, ex_date, action_type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_corp_actions_ex_date ON corporate_actions (ex_date)",
    """
    CREATE TABLE IF NOT EXISTS daily_adjust_factors (
        symbol_id    BIGINT        NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
        trade_date   DATE          NOT NULL,
        adj_factor   NUMERIC(18,10) NOT NULL DEFAULT 1,
        computed_at  TIMESTAMP     NOT NULL DEFAULT now(),
        PRIMARY KEY (symbol_id, trade_date)
    )
    """,
]


def upgrade() -> None:
    for stmt in _DDL:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS daily_adjust_factors")
    op.execute("DROP TABLE IF EXISTS corporate_actions")
