"""News Module Foundation: news_items + news_tags + news_ingestion_sources (Additive-Only).

Revision ID: 0054
Revises: 0053
Create Date: 2026-09-18

هدف (ماژول اخبار — docs/NEWS_MODULE_SPEC_FILLED_2026-09-16.md، تصمیم‌های #۱ و #۲):

  - ``news_items`` : جدول جدید ماژول اخبار (مبنای کد جدید). ``published_at``
    از روز اول TIMESTAMP است (تصمیم #۱) — برخلاف ``news_articles.published_at``
    که String(40) است. ``legacy_article_id`` پیوند یک‌طرفه به رکورد legacy
    برای sync می‌دهد.
  - ``news_tags`` : تگ‌سازی ساخت‌یافته (نماد/دارایی/کالا) با confidence —
    جایگزین ستون TEXT ``news_articles.symbols``.
  - ``news_ingestion_sources`` : ثبت منابع ingest (کلید فید RSS) برای
    monitoring و آستانه هشدار منبع مرده.

تصمیم‌های آگاهانه:

  * هیچ FK سخت به ``news_articles`` گذاشته نمی‌شود: CREATE TABLE آن جدول در
    هیچ migrationای نیست (schema زنده تأییدنشده) و یک FK روی DB تازه یا
    محیطی که جدول legacy ندارد می‌شکند. پیوند فقط ستون + ایندکس است.
  * ``category`` مقادیر کانونی جمع (market/companies/economic/political/
    international) را می‌پذیرد — هم‌سو با فیکس VALID_CATEGORIES (کامیت
    1bd0f9e2) و واقعیت داده فعلی (۳٬۲۳۳ ردیف ``companies`` در legacy).
  * ``dedup_hash`` با unique index جزئی (partial) — تکراری‌شدن خلاصه‌های
    یکسان از فیدهای مختلف را در لایه DB قفل می‌کند (dedup فعلی in-memory
    و ناپایدار است).
  * sync داده از ``news_articles`` به این جدول عمداً در همین migration
    نیست: روی DB تازه جدول legacy ممکن است هنوز وجود نداشته باشد. سینک
    idempotent جداگانه در سرویس ingestion پیاده می‌شود.

هیچ جدول/ستون موجودی حذف یا تغییر نوع نمی‌شود. اجرای دوباره idempotent است.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | None = None
depends_on: str | None = None

_DDL: list[str] = [
    # ── ۱. جدول اصلی ماژول اخبار (تصمیم #۲: news_items جدید، legacy دست‌نخورده) ──
    """
    CREATE TABLE IF NOT EXISTS news_items (
        id                BIGSERIAL PRIMARY KEY,
        legacy_article_id VARCHAR(50),
        title             TEXT         NOT NULL,
        body              TEXT,
        source            VARCHAR(100),
        source_url        TEXT,
        published_at      TIMESTAMP,
        category          VARCHAR(50),
        is_breaking       BOOLEAN      NOT NULL DEFAULT FALSE,
        dedup_hash        VARCHAR(64),
        created_at        TIMESTAMP    NOT NULL DEFAULT now(),
        CONSTRAINT uq_news_items_legacy UNIQUE (legacy_article_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_news_published ON news_items (published_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_news_category ON news_items (category)",
    "CREATE INDEX IF NOT EXISTS idx_news_source ON news_items (source)",
    # dedup در لایه DB: فقط وقتی hash موجود است یکتاست (rowهای بدون hash آزادند)
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_dedup ON news_items (dedup_hash) WHERE dedup_hash IS NOT NULL",
    # ── ۲. تگ‌سازی ساخت‌یافته با confidence ──
    """
    CREATE TABLE IF NOT EXISTS news_tags (
        id         BIGSERIAL PRIMARY KEY,
        news_id    BIGINT      NOT NULL REFERENCES news_items (id) ON DELETE CASCADE,
        tag_type   VARCHAR(20),
        tag_value  VARCHAR(50),
        confidence NUMERIC,
        created_at TIMESTAMP   NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_news_tags_value ON news_tags (tag_type, tag_value)",
    "CREATE INDEX IF NOT EXISTS idx_news_tags_news ON news_tags (news_id)",
    # ── ۳. منابع ingestion (کلید فید RSS؛ مثال واقعی: isna_bourse) ──
    """
    CREATE TABLE IF NOT EXISTS news_ingestion_sources (
        id              BIGSERIAL PRIMARY KEY,
        source_name     VARCHAR(100) NOT NULL,
        source_type     VARCHAR(20)  NOT NULL DEFAULT 'rss',
        endpoint_url    TEXT,
        is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
        last_fetched_at TIMESTAMP,
        created_at      TIMESTAMP    NOT NULL DEFAULT now(),
        CONSTRAINT uq_news_source_name UNIQUE (source_name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_news_sources_active ON news_ingestion_sources (is_active)",
]


def upgrade() -> None:
    conn = op.get_bind()
    for ddl in _DDL:
        conn.execute(text(ddl))


def downgrade() -> None:
    # ترتیب مهم: ابتدا فرزند (FK)، سپس والد.
    op.execute("DROP TABLE IF EXISTS news_tags CASCADE")
    op.execute("DROP TABLE IF EXISTS news_items CASCADE")
    op.execute("DROP TABLE IF EXISTS news_ingestion_sources CASCADE")
