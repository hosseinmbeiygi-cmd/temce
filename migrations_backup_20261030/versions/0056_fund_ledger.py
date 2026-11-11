"""Fund Double-Entry Ledger + Unit Movements API + Outbox (Additive-Only).

Revision ID: 0056
Revises: 0055
Create Date: 2026-09-18

هدف (فاز ۲ و ۶ معماری NAV — `docs/funds/NAV_ARCHITECTURE_V5.md`):
  - ``chart_of_accounts`` : کدینگ حساب‌های استاندارد صندوق.
  - ``journal_entries``   : سند مالی دوطرفه (وضعیت، منبع، برگشت، idempotency).
  - ``journal_lines``     : خطوط بدهکار/بستانکار + مقدار + قید علامت.
  - تریگر تعویق‌شده توازن: SUM(debit)=SUM(credit) برای هر سند در commit.
  - ``fund_nav_outbox``   : Outbox رویدادها در هم‌تراکنش با دفتر (at-least-once).

هیچ جدول/ستون موجودی حذف یا تغییر نوع نمی‌شود. اجرای دوباره idempotent است.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | None = None
depends_on: str | None = None

_DDL: list[str] = [
    # ── ۱. کدینگ حساب‌ها ──
    """
    CREATE TABLE IF NOT EXISTS chart_of_accounts (
        account_code VARCHAR(32) PRIMARY KEY,
        account_name VARCHAR(120) NOT NULL,
        account_type VARCHAR(24) NOT NULL,   -- ASSET|LIABILITY|EQUITY|INCOME|EXPENSE
        normal_side  VARCHAR(8)  NOT NULL,   -- DEBIT|CREDIT
        is_active    BOOLEAN NOT NULL DEFAULT TRUE
    )
    """,
    # ── ۲. سند مالی ──
    """
    CREATE TABLE IF NOT EXISTS journal_entries (
        id                BIGSERIAL PRIMARY KEY,
        fund_id           VARCHAR(50) NOT NULL,
        event_type        VARCHAR(32) NOT NULL,
        status            VARCHAR(16) NOT NULL DEFAULT 'POSTED',  -- POSTED|REVERSED
        effective_at      TIMESTAMP NOT NULL DEFAULT now(),
        recorded_at       TIMESTAMP NOT NULL DEFAULT now(),
        source_system     VARCHAR(32),
        source_ref_id     VARCHAR(128),
        reverses_entry_id BIGINT REFERENCES journal_entries(id),
        idempotency_key   VARCHAR(160) NOT NULL,
        memo              VARCHAR(300),
        CONSTRAINT uq_journal_idem UNIQUE (idempotency_key),
        CONSTRAINT uq_journal_source UNIQUE (source_system, source_ref_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_journal_entries_fund ON journal_entries (fund_id, effective_at DESC)",
    # ── ۳. خطوط سند ──
    """
    CREATE TABLE IF NOT EXISTS journal_lines (
        id               BIGSERIAL PRIMARY KEY,
        entry_id         BIGINT NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
        fund_id          VARCHAR(50) NOT NULL,
        account_code     VARCHAR(32) NOT NULL REFERENCES chart_of_accounts(account_code),
        instrument_symbol VARCHAR(80),
        currency_code    CHAR(3) NOT NULL DEFAULT 'IRR',
        debit_amount     NUMERIC(28,2) NOT NULL DEFAULT 0,
        credit_amount    NUMERIC(28,2) NOT NULL DEFAULT 0,
        quantity_delta   NUMERIC(24,6) NOT NULL DEFAULT 0,
        memo             VARCHAR(300),
        CONSTRAINT chk_journal_line_amount CHECK (
            debit_amount >= 0 AND credit_amount >= 0
            AND NOT (debit_amount > 0 AND credit_amount > 0)
        )
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_journal_lines_entry ON journal_lines (entry_id)",
    "CREATE INDEX IF NOT EXISTS ix_journal_lines_account ON journal_lines (fund_id, account_code)",
    # ── ۴. تریگر توازن (تعویق‌شده تا commit) ──
    """
    CREATE OR REPLACE FUNCTION assert_journal_entry_balanced() RETURNS trigger AS $$
    DECLARE
        total_debit  NUMERIC;
        total_credit NUMERIC;
        eid          BIGINT;
    BEGIN
        eid := COALESCE(NEW.entry_id, OLD.entry_id);
        SELECT COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0)
          INTO total_debit, total_credit
          FROM journal_lines WHERE entry_id = eid;
        IF total_debit <> total_credit THEN
            RAISE EXCEPTION 'journal entry % not balanced: debit=% credit=%', eid, total_debit, total_credit;
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    DROP TRIGGER IF EXISTS trg_journal_balanced ON journal_lines
    """,
    """
    CREATE CONSTRAINT TRIGGER trg_journal_balanced
    AFTER INSERT OR UPDATE OR DELETE ON journal_lines
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_journal_entry_balanced()
    """,
    # ── ۵. Outbox رویدادها ──
    """
    CREATE TABLE IF NOT EXISTS fund_nav_outbox (
        id           BIGSERIAL PRIMARY KEY,
        event_type   VARCHAR(48) NOT NULL,
        fund_id      VARCHAR(50),
        payload_json TEXT NOT NULL,
        status       VARCHAR(16) NOT NULL DEFAULT 'PENDING',  -- PENDING|PUBLISHED|FAILED
        attempts     INTEGER NOT NULL DEFAULT 0,
        last_error   VARCHAR(500),
        created_at   TIMESTAMP NOT NULL DEFAULT now(),
        published_at TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fund_outbox_status ON fund_nav_outbox (status, created_at)",
    # ── ۶. کدینگ پایه (idempotent) ──
    """
    INSERT INTO chart_of_accounts (account_code, account_name, account_type, normal_side) VALUES
        ('CASH',                'نقد و بانک',                     'ASSET',     'DEBIT'),
        ('RECEIVABLE_BROKER',   'دریافتنی از کارگزار',            'ASSET',     'DEBIT'),
        ('RECEIVABLE_DIVIDEND', 'دریافتنی سود سهام',              'ASSET',     'DEBIT'),
        ('INVESTMENT',          'سرمایه‌گذاری‌ها',                 'ASSET',     'DEBIT'),
        ('DEPOSIT',             'سپرده بانکی',                    'ASSET',     'DEBIT'),
        ('MARGIN',              'وجه تضمین',                      'ASSET',     'DEBIT'),
        ('PAYABLE_BROKER',      'پرداختنی به کارگزار',            'LIABILITY', 'CREDIT'),
        ('FEE_PAYABLE',         'کارمزد پرداختنی',                'LIABILITY', 'CREDIT'),
        ('DISTRIBUTION_PAYABLE','سود تقسیمی پرداختنی',            'LIABILITY', 'CREDIT'),
        ('UNITS_LIABILITY',     'سرمایه واحدهای سرمایه‌گذاری',     'EQUITY',    'CREDIT'),
        ('RETAINED_EARNINGS',   'سود (زیان) انباشته',             'EQUITY',    'CREDIT'),
        ('FEE_EXPENSE',         'هزینه کارمزد ارکان',             'EXPENSE',   'DEBIT'),
        ('IMPAIRMENT_EXPENSE',  'هزینه کاهش ارزش',                'EXPENSE',   'DEBIT'),
        ('INCOME',              'درآمد سرمایه‌گذاری',             'INCOME',    'CREDIT'),
        ('FX_REVAL',            'تفاوت تسعیر ارز',                'INCOME',    'CREDIT')
    ON CONFLICT (account_code) DO NOTHING
    """,
]


def upgrade() -> None:
    conn = op.get_bind()
    for ddl in _DDL:
        conn.execute(text(ddl))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_journal_balanced ON journal_lines")
    op.execute("DROP FUNCTION IF EXISTS assert_journal_entry_balanced()")
    op.execute("DROP TABLE IF EXISTS fund_nav_outbox CASCADE")
    op.execute("DROP TABLE IF EXISTS journal_lines CASCADE")
    op.execute("DROP TABLE IF EXISTS journal_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS chart_of_accounts CASCADE")
