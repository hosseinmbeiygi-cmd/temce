"""News Module Foundation: news_items + news_tags + news_ingestion_sources (Additive-Only).

Revision ID: 0054
Revises: 0053
Create Date: 2026-09-18

هدف (ماژول اخبار — docs/NEWS_MODULE_SPEC_FILLED_2026-09-16.md، تصمیم‌های #۱ و #۲):

  - ``news_items`` : جدول جدید ماژول اخبار (مبنای کد جدید). ``published_at``
    از روز اول TIMESTAMP است (تصمیم #۱) — برخلاف ``news_articles.published_at``
    که String(40) است. ``legacy_article_id`` پیوند یک‌طرفه به رکورد legacy
    برای sync می‌دهد.
  - ``news_articles.published_at_ts`` : ستون TIMESTAMP افزودنی روی جدول legacy
    (تصمیم #۱، گزینه «الف») + backfill یک‌باره از رشته ISO/UTC + ایندکس —
    ستون رشته‌ای قدیمی دست‌نخورده می‌ماند تا همه خواننده‌های فعلی نشکنند.
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

نکته backfill ``published_at_ts``:

  * فرمت رشته legacy عملاً ISO 8601 یکنواخت با آفست ``+00:00`` است (۱۵٬۵۸۱/۱۵٬۵۸۱
    ردیف قابل cast روی DB محلی هنگام نوشتن این migration). با این حال cast با
    regex-guard انجام می‌شود: هر مقداری که ISO کامل نباشد (مثلاً در محیطی که
    داده از منبع دیگری آمده) NULL می‌ماند به‌جای شکستن migration.
  * مقادیر آفست‌دار به UTC تبدیل و tzinfo حذف می‌شود تا با ستون‌های
    ``timestamp without time zone`` بقیه اسکیما هم‌خوان بماند.
  * backfill در ``upgrade()`` اجرا می‌شود و idempotent است (فقط ردیف‌های
    ``published_at_ts IS NULL`` را پر می‌کند).

هیچ جدول/ستون موجودی حذف یا تغییر نوع نمی‌شود. اجرای دوباره idempotent است.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | None = None
depends_on: str | None = None

# Backfill تصمیم #۱: رشته ISO 8601 (اختیاری-آفست) → TIMESTAMP (UTC، بدون tzinfo).
#
# گارد regex قبل از cast: فقط رشته‌هایی که کامل ISO هستند تبدیل می‌شوند؛
# هر چیز دیگری NULL می‌ماند (fail-open) تا migration وسط داده بد نشکند.
# Raw-string عمداً: backslashهای regex بدون escape دوباره پایتون خوانا می‌مانند.
#
# نتایج اجرا روی DB محلی هنگام نوشتن این migration: ۱۵٬۵۸۱/۱۵٬۵۸۱ ردیف
# (۱۰۰٪) قابل تبدیل — فرمت legacy یکنواخت ISO با +00:00 است.
#
# فرم‌ها: ۱) با T و آفست/Z  ·  ۲) با T بدون آفست (UTC فرض — هم‌سو با
# _parse_rss_date که tzinfo غایب را UTC می‌گیرد)  ·  ۳/۴) فاصله به‌جای T
_BACKFILL_PUBLISHED_AT_TS = r"""
UPDATE news_articles
SET published_at_ts = CASE
    WHEN btrim(published_at) ~
         '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$'
    THEN (btrim(published_at) :: timestamptz) AT TIME ZONE 'UTC'
    WHEN btrim(published_at) ~
         '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$'
    THEN btrim(published_at) :: timestamp
    WHEN btrim(published_at) ~
         '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$'
    THEN (replace(btrim(published_at), ' ', 'T') :: timestamptz) AT TIME ZONE 'UTC'
    WHEN btrim(published_at) ~
         '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$'
    THEN replace(btrim(published_at), ' ', 'T') :: timestamp
    ELSE NULL
END
WHERE published_at_ts IS NULL
"""

_DDL: list[str] = [
    # ── ۰. تصمیم #۱ (گزینه الف): ستون TIMESTAMP افزودنی روی legacy + backfill ──
    """
    ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS published_at_ts TIMESTAMP
    """,
    "CREATE INDEX IF NOT EXISTS idx_news_articles_published_ts ON news_articles (published_at_ts DESC)",
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

    # ── Backfill published_at_ts (تصمیم #۱) — idempotent, regex-guarded ──
    # فقط ردیف‌های هنوز-NULL پر می‌شوند؛ مقادیر غیر-ISO به NULL می‌مانند
    # (fail-open) تا یک رشته بد در محیطی دیگر migration را نشکند.
    conn.execute(text(_BACKFILL_PUBLISHED_AT_TS))


def downgrade() -> None:
    # ستون افزودنی legacy هم برداشته می‌شود؛ ستون رشته‌ای اصلی دست‌نخورده است.
    op.execute("DROP INDEX IF EXISTS idx_news_articles_published_ts")
    op.execute("ALTER TABLE news_articles DROP COLUMN IF EXISTS published_at_ts")
    # ترتیب مهم: ابتدا فرزند (FK)، سپس والد.
    op.execute("DROP TABLE IF EXISTS news_tags CASCADE")
    op.execute("DROP TABLE IF EXISTS news_items CASCADE")
    op.execute("DROP TABLE IF EXISTS news_ingestion_sources CASCADE")
