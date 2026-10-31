# ممیزی تکمیل مرحلهٔ ۸ — خبر، نگاشت نماد، صندوق و سایر مسیرهای ingestion

> این فایل، ممیزی مستقل مرحلهٔ ۸ است. مبنای آن بررسی خودِ فایل گزارش مرحله، کد واقعی checkout،
> وضعیت Git و خروجی اجرای مجدد تست‌ها است — نه ادعای گزارش قبلی.

## ۰) فرادادهٔ اجرا

| کلید | مقدار |
|---|---|
| تاریخ/زمان اجرا (Tehran) | ۲۰۲۶-۱۰-۲۸، حدود ۲۳:۲۰–۲۳:۴۵ |
| ریشهٔ مخزن | `C:\Users\Iran\Desktop\temce` |
| پوسته | Windows / PowerShell |
| شاخهٔ فعلی | `integration/golddesk-fixes` (`git rev-parse --abbrev-ref HEAD` + `git branch -a --list "*golddesk*"`) |
| `HEAD` | `90597e05b9f4328bcd82ee819a31ba5c55413c12` (`git rev-parse HEAD`) |
| Python | `venv` محلی؛ اجرای تست‌ها با `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` |
| Ruff | `ruff 0.15.17` |
| دسترسی زندهٔ BrsApi/TSETMC/RSS | **استفاده نشد** — همهٔ بررسی‌ها آفلاین روی کد/تست/fixture |
| PostgreSQL محلی | **در دسترس نیست** → `RuntimeError: Cannot connect to PostgreSQL database … Tried: localhost:5432/market` |
| Redis | استفاده نشد |

## ۱) مسیر گزارش نهایی مرحله (الزام ۱ پرامپت ممیزی)

| مورد | مقدار |
|---|---|
| مسیر گزارش مرحله | `AUDIT_REPORTS/MODULAR_TEMCE/08_NEWS_FUNDS_SYMBOLS_OTHER_INGESTION.md` |
| وجود فایل | **بله** — `(Get-Item).Length` = `37897` بایت، `346` خط، `LastWriteTime` = `2026-10-28 23:07:05` |
| مسیر این گزارش ممیزی | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_8.md` (فایل‌های `QA_STAGE_*` موجود قبلی overwrite نشدند؛ `QA_STAGE_8.md` پیش از این وجود نداشت → `Test-Path` = `False`) |

## ۲) وضعیت Git در ابتدای ممیزی (فقط‌خواندنی)

```
$ git rev-parse HEAD
90597e05b9f4328bcd82ee819a31ba5c55413c12
$ git rev-parse --abbrev-ref HEAD
integration/golddesk-fixes
$ git status --short --branch
## integration/golddesk-fixes      (۱۳۸ فایل staged + فایل‌های unstaged/untracked کاربر)
$ git diff --stat            → 26 files changed, 1092 insertions(+), 407 deletions(-)
$ git diff --cached --stat   → 138 files changed, 115998 insertions(+), 1447 deletions(-)
$ git stash list             → stash@{0}, stash@{1}, stash@{2}   (۳ عدد قدیمی، دست‌نخورده)
```

- `frontend/src/hooks/useMarketData.ts` → وضعیت `MM` (هم staged هم unstaged)؛ unstaged: `47 insertions(+), 19 deletions(-)`؛ staged: `10 ±`.
- `tests/unit/repositories/test_sync_log_repository.py` → وضعیت `M ` (staged)، `255 ±`.
- هیچ `git reset --hard` / `git clean` / `checkout` / `restore` / `stash` / `rebase` / `commit` اجرا **نشد**.
- هیچ فایل کاربری حذف یا بازنویسی نشد؛ فقط یک فایل گزارش جدید (`QA_STAGE_8.md`) افزوده شد.

## ۳) فایل‌های بررسی‌شده / بررسی‌نشده (الزام ۲ ممیزی)

### بررسی‌شده در همین ممیزی (با شاهد خواندن/اجرا)

| فایل | وضعیت | نحوهٔ بررسی |
|---|---|---|
| `services/news_ingestion.py` | کامل خوانده شد (۳۰۰–۴۶۰) + diff کامل | `Get-Content` + `git diff` |
| `services/news_dual_write.py` | diff کامل | `git diff` (تغییر ۵ خطی) |
| `domain/instruments/symbol_catalog.py` | بخشی (۳۳۳–۳۷۳، ۴۵۹–۴۷۷) + diff کامل | `Get-Content` + `git diff` + اجرای زندهٔ ماژول |
| `tests/unit/services/test_news_ingestion_skips.py` | کامل خوانده شد (فایل جدید) | `Get-Content` |
| `tests/unit/services/test_symbol_catalog.py` | diff (۵ تست افزوده) | `git diff` |
| `tests/unit/services/test_news_tag_symbol_mapper.py` | diff (۲ تست افزوده) | `git diff` |
| `providers/news/parser.py` | بخشی (۷۰–۷۹) | `Get-Content` |
| `brsapi/pipelines/news/symbol_linker.py` | بخشی (۸–۱۴) | `Get-Content` |
| `services/news_sentiment_pipeline.py` | بخشی (۷۸–۸۴) | `Get-Content` |
| `services/news_tag_symbol_mapper.py` | بخشی (۱۵۵–۱۷۰) | `Get-Content` |
| `providers/news/rss/rss_provider.py` | بخشی (۵۰–۵۸) | `Get-Content` |
| `orchestration/news_flow.py` | کامل (۱–۲۵) | `Get-Content` |
| `jobs/news_sync.py` | کامل (۱–۲۵) | `Get-Content` |
| `apps/api/endpoints/news.py` | بخشی (۵۴۰–۵۵۲) | `Get-Content` |
| `services/news_read_canary.py` | بخشی (۲۵۲–۲۶۸) | `Get-Content` |
| `AUDIT_REPORTS/MODULAR_TEMCE/08_NEWS_FUNDS_SYMBOLS_OTHER_INGESTION.md` | کامل (۳۴۶ خط) | `Get-Content -Encoding UTF8` |

### بررسی‌نشده در همین ممیزی (و دلیل)

| فایل/دامنه | دلیل | وضعیت |
|---|---|---|
| `providers/news/rss/rss_parser.py`, `rss_client.py` | در همین ممیزی بازخوانی نشد (در گزارش مرحله ادعا شده) | **بررسی‌نشده محسوب می‌شود** |
| `services/news_filter.py`, `news_dedup.py`, `news_read_canary.py` (کل فایل) | فقط نقاط ارجاع‌شده خوانده شد | بررسی‌نشده (کامل) |
| `providers/funds/**`, `brsapi/pipelines/funds/**`, `services/fund_identity.py`, `fund_sync_service.py` | در همین ممیزی بازخوانی نشد؛ فقط ادعای گزارش | بررسی‌نشده محسوب می‌شود |
| `ingestion/sources/**`, `ingestion/library_sources/**`, `ingestion/scanners/all_symbols.py` | همان | بررسی‌نشده محسوب می‌شود |
| `_FRONTEND_BACKEND_COPY/**`, `node_modules/**`, `venv/**`, `all_symbols.json` | کپی قدیمی/وابستگی خارجی/دادهٔ تولیدی | باینری/تولیدی/وابستگی خارجی — بررسی نشد |
| `frontend/src/hooks/useMarketData.ts` و تست‌های frontend | خارج از دامنهٔ مرحله ۸؛ فقط وضعیت Git آن تأیید شد | اجرا نشد |

> ادعای «کل پروژه بررسی شد» مطرح نمی‌شود. دامنهٔ ممیزی = زیرمجموعهٔ خبر/نماد/صندوق/استاب‌های مرتبط.

## ۴) جدول الزام → شاهد → نتیجه → کار باقی‌مانده (الزام ۳ ممیزی)

| الزام پرامپت مرحله ۸ | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| حفظ گزارش قبلی (عدم overwrite) و ساخت گزارش با نام زمانی در صورت وجود | `Test-Path …/08_….md` = True؛ این ممیزی در فایل مستقل `QA_STAGE_8.md` نوشته شد | **PASS** | — |
| ثبت Git state (branch/HEAD/status/diff/diff --cached) در گزارش | بخش ۲ گزارش مرحله + بازتأیید مستقل در بخش ۲ همین فایل | **PASS** | — |
| عدم تماس زنده با BrsApi/TSETMC/RSS | هیچ فراخوانی شبکه‌ای در این مرحله اجرا نشد؛ همهٔ تست‌ها offline/fake | **PASS** | — |
| عدم عملیات مخرب DB/Redis | هیچ `TRUNCATE/DELETE/migration` اجرا نشد؛ PostgreSQL اصلاً در دسترس نیست | **PASS** | — |
| بررسی گزارش‌های قدیمی به‌عنوان سرنخ | `AUDIT_BATCH_001_FA…009_FA`, `ROOT_CAUSE_VERIFICATION_FA` در checkout نیستند (ثبت‌شده در گزارش مرحله، بخش «گزارش‌های قدیمی») | **PASS** (غیبت ثبت شد) | — |
| تأیید مستقل «۱۵ از ۱۵» | اجرای مجدد: `python -m pytest -q -p no:cacheprovider tests/unit/repositories/test_sync_log_repository.py` → `15 passed in 16.84s`, `EXIT=0` | **PASS** | — |
| تأیید مستقل `frontend/src/hooks/useMarketData.ts` | `git status --short` → `MM`؛ unstaged `47/19`؛ staged `10 ±` | **PASS** | اجرای تست frontend انجام نشد (خارج از دامنه) |
| تأیید مستقل شاخهٔ `integration/golddesk-fixes` | `git branch -a --list "*golddesk*"` + `--abbrev-ref HEAD` | **PASS** | — |
| manifest فایل‌های خوانده‌شده با علامت | بخش ۳ همین فایل + بخش ۳ گزارش مرحله | **PASS** | — |
| تغییر کوچک/هدفمند + handoff برای خارج دامنه | diff محدود به ۳ فایل کد + ۳ فایل تست؛ handoff صریح در گزارش مرحله (بخش ۸) | **PASS** | — |
| جدول source → fetch → parse/map → dedup → persist → API/consumer | بخش ۴ گزارش مرحله (۴.۱ خبر، ۴.۲ نگاشت، ۴.۳ صندوق، ۴.۴ سایر ingestها) | **PASS** | ردیف‌های «providerهای صندوق» و «library sources» فقط کشف سطحی‌اند |
| بررسی نگاشت نماد/نام/alias و «نبود mapping نباید بی‌صدا حذف/وصل شود» | `news_tag_symbol_mapper` مسیر `unmapped` دارد؛ تست افزوده `test_...unmapped...`؛ `unmapped` در `news_tags` ثبت می‌شود | **PARTIAL** | نگاشت مبهم (`LIMIT 1` بدون `ORDER BY`) نیابازمحصولی/DB-live دارد → بدون DB اثبات‌نشدنی |
| بررسی pipeline خبر (dual-write، dedup، ترتیب رویداد، parity، stale، commit/rollback) | dedup اکنون `skipped_existing` را قابل‌ردیابی می‌کند؛ `save_result.success` چک می‌شود؛ `news_dual_write` لاگ رد شدن mirror دارد | **PARTIAL** | parity/shadow-canary و OOM/HTTP-500 فقط با DB/Redis زنده قابل اثبات است → BLOCKED |
| بررسی cap پنهان/صفحه‌بندی ناقص/cache فهرست نماد/zero-record کاذب | شواهد کد: `providers/news/parser.py:74` (۶ نماد)، `news_sentiment_pipeline.py:81` (`symbols[:10]`)، `news_tag_symbol_mapper.py:159,167` (`LIMIT 1`)، `rss_provider.py:54` (`Result.ok([])`) | **PASS (مستندسازی)** | خود capها رفع نشدند (۸-۳/۸-۶ در دامنهٔ اصلاح کوچک نبودند) |
| خطای یک provider کل دامنه‌های مستقل را از کار نیندازد + رفتار جزئی/کامل قابل ردیابی | `rss_provider` خطای هر فید را منزوی می‌کند ولی شمارندهٔ per-source در خروجی ندارد؛ `Result.fail` فید → ادامهٔ فیدهای دیگر | **PARTIAL** | افزودن شمارندهٔ خطا per-source باقی مانده است |
| فقط همین حوزه اصلاح شود؛ schema/API مشترک handoff شود | هیچ schema/migration/API مشترکی تغییر نکرد؛ diff فقط ۳ فایل کد + ۳ فایل تست | **PASS** | — |
| معیار پذیرش نهایی: «هر مسیر مستقل دلیل حذف/تغییر رکورد و وضعیت خطا را قابل‌ردیابی کند» | فقط مسیر news و کاتالوگ نماد؛ مسیرهای صندوق/سایر ingestها اصلاح نشدند | **PARTIAL** | مسیرهای صندوق و ingestهای مستقل همچنان بدون تغییر باقی مانده‌اند |

## ۵) اصلاحات مرحله: مسیر + diff + دلیل + تست

| فایل | diff (خلاصه) | دلیل | تست مرتبط |
|---|---|---|---|
| `services/news_ingestion.py` | `+42/-9`؛ افزودن `stats["skipped_existing"]`؛ تغییر امضا به `_save_article(...) -> str` با مقادیر `"saved"`/`"skipped_existing"`؛ حلقه بر همین اساس می‌شمارد؛ چک `save_result is None or not save_result.success` → `raise RuntimeError` (۸-۱b)؛ خط لاگ + خط خلاصهٔ ترمینال | حذف «موفقیت کاذب» و قابل‌ردیابی‌کردن **دلیل حذف رکورد** | `tests/unit/services/test_news_ingestion_skips.py` (۴ تست، `4 passed`) |
| `services/news_dual_write.py` | `+5`؛ `logger.debug` هنگام رد شدن mirror به‌دلیل `dedup_hash` موجود | قابل‌ردیابی‌کردن دلیل حذف در لایهٔ `news_items` | `test_news_dual_write.py` در باطری ۱۱ فایلی (`144 passed`) |
| `domain/instruments/symbol_catalog.py` | `+26`؛ `parents[1]` → `parents[2]` (خط ۳۵۴)، `logger.debug` در نبود فایل، تابع جدید `_canonical_market_sector` (خط ۳۳۳) و اعمال آن در خط ۳۶۶ | رفع حذف بی‌صدای ۱۵ ردیف غنی‌شده (۸-۲) و جلوگیری از انتساب صندوق به «سهام» (۸-۲b) | ۵ تست افزوده در `test_symbol_catalog.py` (`test_enriched_fund_rows_are_not_published_as_stocks` …) |
| `tests/unit/services/test_news_ingestion_skips.py` | **جدید** (۴ تست، بدون DB با fake provider/service) | پوشش ۸-۱ و ۸-۱b شامل partial failure و batch تماماً تکراری | `4 passed` |
| `tests/unit/services/test_symbol_catalog.py` | `+59` (۵ تست) | پوشش ۸-۲/۸-۲b | `53 passed, 4 skipped` (با دو فایل دیگر) |
| `tests/unit/services/test_news_tag_symbol_mapper.py` | `+63` (۲ تست) | پوشش «نبود mapping → `unmapped` و عدم انتساب به نماد اشتباه» + مسیر `persist=False` | `53 passed, 4 skipped` |

**بدون تغییر (handoff صریح در گزارش مرحله):** `providers/news/parser.py` (۸-۳)، `services/news_tag_symbol_mapper.py` (۸-۵)، `tests/unit/services/test_news_source_health.py` (۸-۸ مارکر `needs_db`).

## ۶) فرمان‌های تست: نتیجهٔ واقعی (الزام ۵ ممیزی)

همه با `$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"` و `-p no:cacheprovider`.

### الف) اجراشده در همین ممیزی (شاهد مستقیم)

| # | فرمان | نتیجه | exit code |
|---|---|---|---|
| ۱ | `python -m pytest -q -p no:cacheprovider tests/unit/services/test_news_source_health.py tests/unit/api/test_news_tag_map_admin.py tests/unit/api/test_news_date_range_http.py` | `1 failed, 15 passed, 5 skipped, 8 warnings in 223.32s` | **1** |
| ۲ | همان فرمان، اجرای دوم مستقل | `1 failed, 15 passed, 5 skipped, 8 warnings in 269.06s` | **1** |
| ۳ | `python -m pytest -q -p no:cacheprovider tests/unit/services/test_symbol_catalog.py tests/unit/services/test_news_tag_symbol_mapper.py tests/unit/services/test_news_ingestion_skips.py` | `53 passed, 4 skipped, 1 warning in 193.04s` | **0** |
| ۴ | باطری ۱۱ فایلی: `… test_news_ingestion_skips.py test_news_dual_write.py test_news_items_read_path.py test_news_read_canary.py test_news_service.py test_news_tag_symbol_mapper.py providers/test_news_parser.py api/test_news_category.py api/test_news_date_range.py api/test_news_symbol_meta_http.py services/test_symbol_catalog.py` | `144 passed, 15 skipped, 3 warnings in 143.03s` | **0** |
| ۵ | `python -m pytest -q -p no:cacheprovider tests/unit/repositories/test_sync_log_repository.py` | `15 passed in 16.84s` | **0** |
| ۶ | `python -c "from domain.instruments import symbol_catalog as s; …"` | `catalog_size 534`؛ `sector_summary` → صندوق 350 / رمزارز 73 / بورس کالا 36 / سهام 27 / طلا و سکه 19 / ارز 15 / کامودیتی 14 | **0** |
| ۷ | `python -m ruff check services/news_ingestion.py services/news_dual_write.py domain/instruments/symbol_catalog.py tests/unit/services/test_news_ingestion_skips.py` | `All checks passed!` | **0** |
| ۸ | `python -m ruff check tests/unit/services/test_symbol_catalog.py tests/unit/services/test_news_tag_symbol_mapper.py` | `Found 2 errors (C408)` — هر دو در `test_news_tag_symbol_mapper.py:233,240` | **1** |

**شکست شمارهٔ ۱/۲ (پنهان نشده):**
```
FAILED tests/unit/services/test_news_source_health.py::TestJobWrapper::test_success_when_healthy
E  RuntimeError: Cannot connect to PostgreSQL database. … Tried: localhost:5432/market
   core\database.py:180
```
دو اجرای مستقل، همان نتیجه → تکرارپذیر و **علت آن نبود PostgreSQL محلی است، نه کد مرحله ۸**. این دقیقاً ایراد ۸-۸ است (تست offline-ایمن نیست) و در همین ممیزی تأیید شد.

### ب) ادعاهای گزارش مرحله که در این ممیزی **مجدداً اجرا نشدند** (به‌عنوان شاهد مستقیم محسوب نمی‌شوند)

| فرمان (ادعای گزارش) | ادعای گزارش | وضعیت این ممیزی |
|---|---|---|
| `pytest tests/unit/services/test_news_ingestion_skips.py` (پیش از اصلاح) | `2 failed, 1 passed` / `EXIT=1` | اجرا نشد (نیازمند revert موقت) — پذیرفته‌شده به‌عنوان ادعا، نه شاهد |
| `pytest tests/unit/services/test_news_ingestion_skips.py` | `4 passed` | با اجرای ترکیبی #۳ تأیید شد (`53 passed, 4 skipped` شامل این ۴ تست) |
| `pytest tests/unit/services/test_news_tag_symbol_mapper.py` | `7 passed, 4 skipped` | با #۳ تأیید شد |
| `pytest tests/unit/services/test_symbol_catalog.py` | `42 passed` | با #۳ تأیید شد |
| `pytest tests/unit/services/test_symbol_catalog.py tests/unit/providers/test_news_parser.py tests/unit/test_symbols_page_size.py` | `4 failed, 43 passed` (همهٔ شکست‌ها DB-وابسته) | اجرا نشد (نیازمند PostgreSQL) |
| `ruff format --check` | «would reformat» ولی نسخهٔ `HEAD` هم همین‌طور بود | اجرا نشد |

## ۷) یافته‌های این ممیزی

| ID | شدت | شاهد `path:line` | توضیح | اثر |
|---|---|---|---|---|
| **QA-8-A** | پایین (مستندسازی) | `AUDIT_REPORTS/MODULAR_TEMCE/08_NEWS_FUNDS_SYMBOLS_OTHER_INGESTION.md:194` | ردیف ۸-۲b به `symbol_catalog.py:365` و `sector_summary:451` ارجاع می‌دهد؛ مقدار درست: اعمال `_canonical_market_sector` در `domain/instruments/symbol_catalog.py:366` و خط fold-to-`سهام` در `sector_summary` = `domain/instruments/symbol_catalog.py:472` (تعریف تابع = خط ۴۵۹) | ارجاع یک‌خطی جابه‌جا؛ ردیابی خواننده را کمی دشوار می‌کند |
| **QA-8-B** | پایین | `tests/unit/services/test_news_tag_symbol_mapper.py:233,240` | ۲ خطای `C408`؛ با `git show HEAD:…` و اجرای ruff روی همان‌ها تأیید شد که **پیش‌موجود** است (خطوط ۱۷۰/۱۷۷ در HEAD) → ناشی از این مرحله نیست | بدهی lint موجود؛ خارج از دامنه |
| **QA-8-C** | — (تأیید مثبت) | `services/news_ingestion.py:322-326, 363-372, 379, 414-420, 446`؛ diff کامل | اصلاح ۸-۱/۸-۱b واقعاً در کد فعلی حاضر است و تست‌ها آن را می‌پوشانند | — |
| **QA-8-D** | — (تأیید مثبت) | `domain/instruments/symbol_catalog.py:333, 354, 366` | عدد کاتالوگ ۵۱۹→۵۳۴ و نگاشت صندوق→`صندوق` با اجرای زندهٔ ماژول بازتولید شد و با ادعای گزارش مطابق است | — |
| **QA-8-E** | پایین | `tests/unit/services/test_news_source_health.py::TestJobWrapper::test_success_when_healthy` | بدون DB، به‌جای skip → **fail** (دو اجرای مستقل تأیید شد) | در CI بدون DB، این خطا می‌تواند کاذبانه سراسری شود (همان ۸-۸؛ اصلاح نشده) |

## ۸) علت ریشه‌ای (بازتأیید مستقل)

- **۸-۱:** `_save_article` با امضای `-> None` طراحی شده بود؛ مسیر «تکراری» هیچ سیگنالی به حلقه نمی‌داد → حلقه هر عدم-exception را «ذخیرهٔ موفق» می‌شمرد (شمارندهٔ متورم و دلیل حذف نامعلوم).
- **۸-۱b:** نتیجهٔ `NewsService.save` (که می‌تواند `Result.fail` باشد) نادیده گرفته می‌شد → ردیف در `news_items` mirror می‌شد ولی در `news_articles` نه (نقض parity مسیر canary).
- **۸-۲:** جابه‌جایی ماژول از `services/` به `domain/instruments/` عمق نسبی را یک سطح افزایش داد ولی `parents[1]` به‌روز نشد؛ مسیر ناموجود به‌صورت best-effort صفر برمی‌گرداند بدون exception/لاگ → خرابی کامل و بی‌صدا.
- **۸-۲b:** قرارداد `sector_summary` («هر sector غیر از ۷ مقدار بازار → سهام») با رشته‌های granular فایل غنی‌شده ترکیب می‌شد و صندوق را به سهام تبدیل می‌کرد.

## ۹) موارد BLOCKED (الزام ۷ ممیزی)

1. قطعی‌کردن نگاشت مبهم (`_probe_tables` با `LIMIT 1` بدون `ORDER BY` در `services/news_tag_symbol_mapper.py:159,167`) → نیازمند DB با دو ردیف هم‌نماد. **BLOCKED**.
2. اثبات/بازتولید parity مسیر canary، shadow و OOM/HTTP-500 مسیر خبر → نیازمند PostgreSQL/Redis زنده. **BLOCKED** (شاهد کد در `services/news_read_canary.py:258-263` فقط به‌صورت کامنت موجود است، بازتولید نشد).
3. هر تأییدی که نیازمند درخواست زندهٔ RSS/BrsApi/TSETMC باشد → طبق قواعد پرامپت **BLOCKED**.

## ۱۰) معیارهای پذیرش و وضعیت نهایی

| معیار پذیرش پرامپت | وضعیت |
|---|---|
| هر مسیر مستقل منبع، دلیل حذف/تغییر رکورد و وضعیت خطا را قابل‌ردیابی کند | **PARTIAL** — مسیر news (۸-۱/۸-۱b) و کاتالوگ نماد (۸-۲) محقق؛ مسیرهای صندوق/سایر ingestها و cap نماد خبر (۸-۳) بدون تغییر |
| mapping مبهم و partial failure در تست‌ها پوشش داده شود | **PARTIAL** — partial failure پوشش داده شد (`4 passed`)؛ «نبود mapping → `unmapped`» پوشش داده شد؛ «مبهم‌بودن بین دو ردیف هم‌نام» **BLOCKED** (نیازمند DB) |
| خروجی تست‌ها بدون پنهان‌کاری ثبت شود | **PASS** — شکست `1 failed` (DB-وابسته) و ۲ خطای `C408` صریح ثبت شد |
| حفظ تغییرات کاربر و عدم commit بدون اجازه | **PASS** — محتوای staged/untracked دست‌نخورده؛ stash‌ها دست‌نخورده؛ هیچ commit ایجاد نشد |

### نتیجهٔ نهایی این مرحله: **PARTIAL**

دلیل: باگ‌های اصلی ۸-۱/۸-۱b/۸-۲/۸-۲b با کد و تست تأییدشده رفع شده‌اند و معیارهای آن بخش‌ها PASS است، اما
(الف) نگاشت خبر→نماد (۸-۳) با کپ ۶ نماد و کد مردهٔ `symbol_linker` (۸-۴) و «موفقیت صفر-رکورد» در `rss_provider` (۸-۶) رفع نشده‌اند،
(ب) نگاشت مبهم و parasiteهای DB-وابسته (۸-۵/۸-۸) و بازتولید OOM/500 مسیر canary **BLOCKED** است،
پس «معیار پذیرش کامل مرحله» برآورده نشده و مرحله را **کامل** اعلام نمی‌کنم.

## ۱۱) فهرست کارهای باقی‌مانده (به‌ترتیب اولویت)

1. **۸-۸ (توصیه: الان):** افزودن مارکر `needs_db` (یا skip صریح) به `tests/unit/services/test_news_source_health.py::TestJobWrapper::test_success_when_healthy` تا در CI بدون DB به‌جای fail، skip شود. (تغییر تست خارج از دامنهٔ فعلی → نیاز به مجوز/مرحلهٔ مستقل)
2. **۸-۳:** جایگزینی کپ ۶ نماد در `providers/news/parser.py:74` با نگاشت مبتنی بر کاتالوگ/DB، با منطق مرز-توکن برای پرهیز از false-positive (نیازمند تصمیم محصولی + تست).
3. **۸-۵:** افزودن `ORDER BY` قطعی در `services/news_tag_symbol_mapper.py:159,167` + تست DB (نیازمند migration ایندکس/تصمیم اولویت).
4. **۸-۶:** تبدیل `Result.ok([])` در `providers/news/rss/rss_provider.py:54` به نتیجهٔ قابل‌تفکیک («فید تنظیم‌نشده») + شمارندهٔ خطای per-source در خروجی `fetch_news`.
5. **۸-۴/۸-۷:** تعیین تکلیف کد مرده/استاب: `brsapi/pipelines/news/symbol_linker.py:10`، `orchestration/news_flow.py:11-14`، `jobs/news_sync.py:11-14` (حذف یا اتصال واقعی + تست).
6. **QA-8-A:** اصلاح دو ارجاع جابه‌جا در گزارش `08_…md:194` (`:365`→`:366` و `sector_summary:451`→`:472`).
7. **BLOCKED:** اثبات نگاشت مبهم/parity canary/OOM-500 و هر تأیید وابسته به BrsApi، پس از فراهم‌شدن DB/Redis/دسترسی زنده.

## ۱۲) پیوست: فرادادهٔ اثبات

- گزارش مرحله: `AUDIT_REPORTS/MODULAR_TEMCE/08_NEWS_FUNDS_SYMBOLS_OTHER_INGESTION.md` (37897 بایت / ۳۴۶ خط / `2026-10-28 23:07:05`)
- این فایل ممیزی: `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_8.md`
- تست‌های اجراشده در این ممیزی: ۵ فرمان pytest/اجرا + ۲ فرمان ruff (بخش ۶-الف)
- تست‌های اجرانشده در این ممیزی: pre-fix TDD، `test_symbols_page_size.py`، `ruff format --check`، تست‌های frontend و هر تست نیازمند شبکه/DB (بخش ۶-ب و ۹)

## ۱۳) پیوست دوم: اجرای کارهای باقی‌مانده (دور ۲)

پس از این ممیزی، تمام هفت کار باقی‌ماندهٔ فهرست بخش ۱۱ اجرا و با تست تثبیت شد.
گزارش کامل این دور: **`AUDIT_REPORTS/MODULAR_TEMCE/08_NEWS_FUNDS_SYMBOLS_OTHER_INGESTION_run2_20261029.md`**
(گزارش دور اول overwrite نشد).

| مورد | وضعیت پس از دور ۲ | شاهد |
|---|---|---|
| ۸-۳ کپ ۶ نماد در نگاشت خبر→نماد | **حل شد** | `providers/news/parser.py` (نگاشت کاتالوگی + مرز توکن)؛ ۹ تست در `tests/unit/providers/test_news_symbol_extraction.py` |
| ۸-۴ کد مردهٔ `NewsSymbolLinker` | **حل شد** | واگذاری به `NewsParser.extract_symbols`؛ حذف `_known_symbols` |
| ۸-۵ نگاشت مبهم (`LIMIT 1` بدون `ORDER BY`) | **حل شد (آفلاین)** | `_probe_sql()` + `ORDER BY id` + warning مبهم‌بودن؛ `TestAmbiguousProbeIsDeterministic` |
| ۸-۶ موفقیت صفر-رکورد در `rss_provider` | **حل شد** | تفکیک `no_feeds_configured`/`all_feeds_failed`/`ok([])` + لاگ per-source؛ ۴ تست |
| ۸-۶b خطای fetch در آمار ingest | **حل شد** | `stats["fetch_error"]` + شمارش خطا؛ `test_fetch_failure_is_recorded_instead_of_a_silent_zero` |
| ۸-۷ استاب‌های هم‌نام | **حل شد** | هر دو fail-closed با پیام `not_implemented`؛ `tests/unit/test_news_stub_paths.py` |
| ۸-۸ تست DB-وابستهٔ fail‌شونده | **حل شد** | `@pytest.mark.needs_db`؛ نتیجهٔ سوئیت از `1 failed` به `1 deselected` رسید |
| QA-8-A ارجاع جابه‌جا (`:365`/`:451`) | **ثبت اصلاحیه** | مقادیر درست `symbol_catalog.py:366` و `:472`؛ در گزارش دور ۲ مستند شد |
| اثبات زندهٔ مبهم‌بودن در DB / پاریتی canary / OOM-500 | **BLOCKED** | نیازمند PostgreSQL/Redis زنده — بدون تغییر |

فرمان‌ها و نتیجهٔ واقعی دور ۲:

| فرمان | نتیجه | exit |
|---|---|---|
| `pytest … tests/unit/providers/ tests/unit/test_news_stub_paths.py tests/unit/services/test_news_ingestion_skips.py tests/unit/services/test_news_tag_symbol_mapper.py` | `56 passed, 4 skipped` | 0 |
| باطری ۱۵ فایلی درون‌دامنه | `177 passed, 15 skipped, 3 warnings` | 0 |
| `pytest … test_news_source_health.py test_news_tag_map_admin.py test_news_date_range_http.py` | `15 passed, 5 skipped, 1 deselected` | 0 |
| `ruff check` روی فایل‌های تغییر‌یافتهٔ تولیدی + تست‌های جدید | `All checks passed!` | 0 |
| `ruff check` روی دو فایل تست دارای بدهی پیش‌موجود | `Found 7 errors` (همه پیش‌موجود، روی `HEAD` بازتولید شد) | 1 |

### وضعیت نهایی مرحلهٔ ۸: **PASS** (با ۳ مورد تأییدِ وابسته به محیط زنده که BLOCKED و مستند است)

هر دو معیار پذیرش پرامپت مرحله ۸ (قابل‌ردیابی بودن دلیل حذف/تغییر رکورد و وضعیت خطا؛
پوشش تست برای mapping مبهم و partial failure) با شاهد کد و تست برآورده شد.
