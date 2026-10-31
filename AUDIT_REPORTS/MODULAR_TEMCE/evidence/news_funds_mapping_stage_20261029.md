# مرحلهٔ ۹ — خبر/صندوق/نگاشت: شاهد اجرا (۲۹ اکتبر ۲۰۲۶)

دامنه: DS-09 (نگاشت مبهم)، parity اصلی/mirror، شمارندهٔ خطای per-source، cap نمادها.
هیچ DB/شبکهٔ زنده لمس نشد؛ تست‌های DB-محور خبر با skip اجرا شدند (PostgreSQL auth نامعتبر).

## ۱) DS-09 — نگاشت مبهم tag → fund/symbol

در working tree توسط کار هم‌زمان رفع شده بود و بازتأیید شد:
`services/news_tag_symbol_mapper.py::_probe_tables` ابتدا `funds` و سپس `symbols` را probe
می‌کند، `LIMIT 2` + `ORDER BY id` دارد و تطابق چندردیفی را log می‌کند (به‌جای انتخاب خاموش
با LIMIT 1). `tests/unit/services/test_news_tag_symbol_mapper.py` (۹ passed، ۴ skip برای DB)
سبز است. ادعای مالکیت نیست.

## ۲) پاریتی اصلی/mirror

**یافتهٔ جدید (NEWS-03):** ستون یکتای `news_items.legacy_article_id` (migration 0054) توسط
backfill یک‌باره پر می‌شد، اما **dual-write زنده آن را هرگز نمی‌نوشت**؛ یعنی ردیف‌های تازه
فقط با تطبیق fuzzy (title+url) قابل وصل بودند و join دقیق ممکن نبود.

- `services/news_dual_write.py`: پارامتر `legacy_article_id`، درج در INSERT، و dedup
  fast-path روی `dedup_hash` **یا** `legacy_article_id` (هم‌راستا با `scripts/backfill_news_items.py`).
- `services/news_ingestion.py`: `legacy_article_id=item.id` (id سمت کلاینت پیش از flush معلوم است).

**ابزار پاریتی (read-only):** `services/news_parity.py::news_parity_report(session, days=7)` —
شمارش کل/اخیر هر دو جدول، `legacy_missing_mirror`، `mirror_missing_legacy`،
`linked_rows`، `linked_missing_time` و نمونهٔ ردیف‌های جاافتاده. هیچ INSERT/UPDATE/DELETE
ندارد (گارد تست). اجرا: `python scripts/news_parity_report.py --days 7 [--json]` با
exit code 1 در ناسازگاری.
**BLOCKED:** اجرای واقعی روی DB (PostgreSQL auth نامعتبر). تست‌ها با session جعلی:
`tests/unit/services/test_news_parity.py` (۷) و `test_news_mirror_link.py` (۴).

## ۳) شمارندهٔ خطای per-source (NEWS-01)

`Result` فقط یک رشتهٔ خطا دارد؛ بنابراین `RSSDomesticProvider` شکست هر فید را فقط log می‌کرد.
اکنون `provider.last_feed_report = {"ok": [...], "empty": [...], "failed": {name: reason}}`
(در هر فراخوانی reset می‌شود) و `NewsIngestionService.ingest` آن را در
`stats["source_report"]` می‌گذارد؛ خلاصهٔ چاپی هم «Failed sources» را با دلیل نشان می‌دهد.
تست: `test_per_source_report_is_exposed_for_the_ingest_stats`، `test_report_is_reset_between_runs`،
`test_per_source_outcome_reaches_the_ingest_stats`.

**باقی‌مانده:** این گزارش در `news_ingestion_sources` (منبع alert فید مرده) نوشته نمی‌شود؛
فقط stats اجرا را دقیق می‌کند.

## ۴) cap نمادها (NEWS-02)

`providers/news/parser.py`: `MAX_SYMBOLS_PER_ARTICLE = 8` — استخراج کاتالوگ‌محور (کار
هم‌زمان) می‌توانست برای یک گزارش بازار ده‌ها تیکر برگرداند و هر کدام یک ردیف `news_tags`
(و نوتیفیکیشن بعدی) بسازد. اکنون ۸ مورد اول به ترتیب ظهور نگه داشته می‌شود.
تست: `test_symbols_per_article_are_capped` (۱۲ تست این فایل سبز).

**باقی‌مانده:** backfill قدیمی `news_tags` را از ستون قدیمی می‌خواند و سقف ندارد (دادهٔ تاریخی
بازنویسی نمی‌شود).

## ۵) اجرای تست

| مجموعه | نتیجه |
|---|---|
| `test_news_mirror_link.py` + `test_news_parity.py` | ۱۱ passed |
| `test_news_ingestion_skips.py` | ۸ passed |
| `test_news_rss_provider_status.py` + `test_news_symbol_extraction.py` | ۱۹ passed |
| `tests/unit/providers` + news services/jobs/api (۷ فایل) | ۱۲۵ passed، ۱۴ skipped (DB) |
| `test_news_tag_symbol_mapper.py` (DS-09) | ۹ passed، ۴ skipped |
| ruff روی فایل‌های تغییریافته | پاک |

**محدودیت‌ها:** پاریتی واقعی روی DB اجرا نشد؛ تست‌های DB-محور dual-write/canary با skip
اجرا شدند (پیش از این برش هم همین‌طور بودند)؛ سناریوی فید مرده → alert جدید ساخته نشد.
