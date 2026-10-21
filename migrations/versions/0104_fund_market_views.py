"""Fund market-data views (read-only, additive).

Revision ID: 0104
Revises: 0103

7 read-only views mapping BrsApi raw tables to fund scope via
fund_symbol_aliases (fallback to funds.symbol):
  1. vw_fund_symbols      <- AllSymbols (brsapi_symbol_snapshots latest per symbol)
  2. vw_fund_intraday     <- Transaction (brsapi_intraday_trades)
  3. vw_fund_history      <- History type=0 (brsapi_historical_daily)
  4. vw_fund_nav          <- Nav (brsapi_nav_records + fund_nav_history union)
  5. vw_fund_codal        <- Announcement (brsapi_codal_announcements)
  6. vw_fund_shareholders <- Shareholder (brsapi_shareholder_records)
  7. vw_fund_candles      <- Candlestick (brsapi_candlesticks)
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0104"
down_revision: str | None = "0103"
branch_labels: str | None = None
depends_on: str | None = None

_ALIAS_SQL = """SELECT DISTINCT fund_id, symbol FROM fund_symbol_aliases WHERE is_active = TRUE
    UNION
    SELECT id AS fund_id, symbol FROM funds"""

_DDL: list[str] = [
    # 1. AllSymbols latest snapshot per fund symbol
    """
    CREATE OR REPLACE VIEW vw_fund_symbols AS
    WITH alias AS (%s),
    ranked AS (
        SELECT s.*, a.fund_id,
               ROW_NUMBER() OVER (PARTITION BY s.symbol ORDER BY s.created_at DESC NULLS LAST, s.id DESC) AS rn
        FROM brsapi_symbol_snapshots s JOIN alias a ON a.symbol = s.symbol
    )
    SELECT * FROM ranked WHERE rn = 1
    """ % _ALIAS_SQL,
    # 2. Transaction / intraday
    """
    CREATE OR REPLACE VIEW vw_fund_intraday AS
    WITH alias AS (%s)
    SELECT a.fund_id, t.* FROM brsapi_intraday_trades t
    JOIN alias a ON a.symbol = t.symbol
    """ % _ALIAS_SQL,
    # 3. History daily
    """
    CREATE OR REPLACE VIEW vw_fund_history AS
    WITH alias AS (%s)
    SELECT a.fund_id, h.* FROM brsapi_historical_daily h
    JOIN alias a ON a.symbol = h.symbol
    """ % _ALIAS_SQL,
    # 4. NAV union (new authoritative + legacy brsapi)
    """
    CREATE OR REPLACE VIEW vw_fund_nav AS
    WITH alias AS (%s)
    SELECT a.fund_id, n.symbol, n.nav_issue, n.nav_redemption, n.date AS nav_date,
           n.gregorian_date, 'brsapi_nav_records' AS src
    FROM brsapi_nav_records n JOIN alias a ON a.symbol = n.symbol
    UNION ALL
    SELECT h.fund_id, NULL AS symbol, h.nav_issue, h.nav_redemption,
           h.nav_date_greg::varchar AS nav_date, h.nav_date_greg AS gregorian_date,
           'fund_nav_history' AS src
    FROM fund_nav_history h
    """ % _ALIAS_SQL,
    # 5. Codal announcements
    """
    CREATE OR REPLACE VIEW vw_fund_codal AS
    WITH alias AS (%s)
    SELECT a.fund_id, c.* FROM brsapi_codal_announcements c
    JOIN alias a ON a.symbol = c.symbol
    """ % _ALIAS_SQL,
    # 6. Shareholders
    """
    CREATE OR REPLACE VIEW vw_fund_shareholders AS
    WITH alias AS (%s)
    SELECT a.fund_id, s.* FROM brsapi_shareholder_records s
    JOIN alias a ON a.symbol = s.symbol
    """ % _ALIAS_SQL,
    # 7. Candlesticks
    """
    CREATE OR REPLACE VIEW vw_fund_candles AS
    WITH alias AS (%s)
    SELECT a.fund_id, c.* FROM brsapi_candlesticks c
    JOIN alias a ON a.symbol = c.symbol
    """ % _ALIAS_SQL,
]


def upgrade() -> None:
    conn = op.get_bind()
    for ddl in _DDL:
        conn.execute(text(ddl))


def downgrade() -> None:
    for v in ["vw_fund_symbols", "vw_fund_intraday", "vw_fund_history",
              "vw_fund_nav", "vw_fund_codal", "vw_fund_shareholders",
              "vw_fund_candles"]:
        op.execute(f"DROP VIEW IF EXISTS {v}")
