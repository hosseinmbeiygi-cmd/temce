# پرامپت مستقل ۸ — خبر، نگاشت نماد، صندوق و سایر مسیرهای ingestion

> این فایل مرجع کامل این مرحله است. پاسخ چت فقط خلاصه است.

## ۰) فرادادهٔ اجرا

| کلید | مقدار |
|---|---|
| تاریخ/زمان اجرا (Tehran) | ۲۰۲۶-۱۰-۲۸، حوالی ۲۳:۰۰–۲۳:۱۰ |
| ریشهٔ مخزن | `C:\Users\Iran\Desktop\temce` (`pwd` + `git rev-parse --show-toplevel`) |
| پوسته/سیستم | Windows / PowerShell |
| Python | `3.11.9` (اجرای تست‌ها با `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`) |
| شاخهٔ فعلی | `integration/golddesk-fixes` (تأییدشده با `git branch --show-current` و `git rev-parse --abbrev-ref HEAD`) |
| `HEAD` | `90597e05b9f4328bcd82ee819a31ba5c55413c12` — `feat(phase0): unify gold engine and ship fail-closed trust labels` (2026-10-26 09:48:51 +0330) |
| ابزارهای Git | `git` در دسترس؛ هشدار بی‌اثر `unable to access 'C:\Users\Iran/.config/git/ignore': Permission denied` در همهٔ فرمان‌ها |
| دسترسی زنده به BrsApi/TSETMC | **استفاده نشد** — همهٔ بررسی‌ها آفلاین روی کد/تست/fixture |
| PostgreSQL محلی | **در دسترس نیست** (`RuntimeError: Cannot connect to PostgreSQL database … Tried: localhost:5432/market`) → تست‌های `needs_db` و تست‌های DB-وابسته skip/خطا شدند (پایین‌تر) |
| Redis | استفاده نشد (ماژول‌های news بدون Redis به in-memory fallback تنزل می‌کنند) |

## ۱) وضعیت اولیهٔ Git (بدون هیچ تغییر مخرب)

```
$ git rev-parse HEAD
90597e05b9f4328bcd82ee819a31ba5c55413c12
$ git branch --show-current
integration/golddesk-fixes
$ git status --short --branch
## integration/golddesk-fixes
… (۱۳۸ فایل staged از قبل + فایل‌های unstaged/untracked کاربر) …
```

- `git diff --stat` (working tree در آغاز): **۱۸ فایل، ۷۲۳ insertions(+)، ۳۷۳ deletions(-)**
  (از جمله `apps/api/endpoints/market.py`, `brsapi/services/query_service.py`, `ingestion/worker.py`, `frontend/src/hooks/useMarketData.ts`, `schemas/common/responses.py`, …)
- `git diff --cached --stat` (index در آغاز): **۱۳۸ فایل، ۱۱۵۹۹۸ insertions(+)، ۱۴۴۷ deletions(-)**
- `git stash list`: ۳ stash قدیمی از قبل موجود (`stash@{0..2}`) — **دست نخورد**.
- هیچ `git reset --hard` / `git clean` / `checkout` / `restore` / `stash` / `rebase` / `commit` اجرا نشد.
- پیش از ویرایش، `git diff` و `git status --short` برای هر فایل مورد ویرایش بررسی شد: هر ۳ فایل تولیدی **تمیز** بودند (`git diff` خالی، بدون staged).

### تأیید مستقل ادعاهای نشست قبلی (بدون فرض)

| ادعا | روش بررسی | نتیجهٔ مستقل |
|---|---|---|
| شاخهٔ `integration/golddesk-fixes` | `git branch -a --list "*golddesk*"` + `git rev-parse --abbrev-ref HEAD` | **تأیید** — شاخه وجود دارد و شاخهٔ فعلی است |
| `tests/unit/repositories/test_sync_log_repository.py` | `git status` + شمارش تست + اجرا | **تأیید** — فایل هست، `M ` (staged، `254 insertions(+), 1 deletion(-)` در index) و **۱۵ تست** دارد |
| «۱۵ از ۱۵» | `python -m pytest -q -p no:cacheprovider tests/unit/repositories/test_sync_log_repository.py` | **تأیید** — `15 passed in 40.31s`، `EXIT=0` (بدون DB) |
| `frontend/src/hooks/useMarketData.ts` | `git status --short` + `git diff --stat` | **تأیید** — هست و هم staged و هم unstaged است (`MM`)، working-tree diff: `47 insertions(+), 19 deletions(-)`؛ فایل تست آن `frontend/src/__tests__/useMarketData.test.tsx` در working tree ` M` است. **اجرا نشد** (تست frontend؛ خارج از دامنهٔ این مرحله) |

### گزارش‌های قدیمی به‌عنوان «سرنخ»

- `AUDIT_BATCH_001_FA.md` … `AUDIT_BATCH_009_FA.md`: **در checkout فعلی یافت نشد** (`git ls-files` و جست‌وجوی `docs/`). تنها فایل مشابه، `docs/audits/ROOT_CAUSE_BATCH10.md` است.
- `ROOT_CAUSE_VERIFICATION_FA.md`: **یافت نشد**.
- **نتیجه:** عدم وجود این گزارش‌ها ثبت می‌شود؛ هیچ ادعایی از آن‌ها به‌عنوان حقیقت پذیرفته نشد. تنها گزارش‌های موجود و مرتبط در `AUDIT_REPORTS/MODULAR_TEMCE/` و `docs/NEWS_READ_CANARY_SHADOW_REPORT_2026-09-20.md` هستند که فقط به‌عنوان سرنخ استفاده شدند و محل ادعای «OOM» و «۳۳۸ خطای ۵۰۰» در `services/news_read_canary.py:258-263` به‌صورت کامنت در کد **مشاهده شد** (شاهد در کد، نه اتکای صرف به گزارش).

## ۲) هدف و مرز دامنه

**هدف:** بررسی مسیرهای دریافت داده‌ای که در مرحلهٔ قیمت/صف جا نیفتاده‌اند: news (provider → pipeline → service → API)، نگاشت نماد/تیکر، صندوق‌ها، و ingestهای دامنه‌ای مستقل؛ سپس رفع باگ‌های کوچک و قابل‌آزمون در همین محدوده.

**در دامنه:** `providers/news/**`, `providers/base/news.py`, `providers/funds/**`, `services/news_*.py`, `services/fund_identity.py`, `services/fund_sync_service.py`, `domain/instruments/symbol_catalog.py`, `domain/instruments/symbol_finglish.py`, `repositories/news_repository.py`, `repositories/news_items_read_repo.py`, `repositories/instrument_repository.py`, `apps/api/endpoints/news.py`, `news_tag_map_admin.py`, `symbol_search.py`, `symbols.py`, `brsapi/pipelines/news/**`, `brsapi/pipelines/funds/**`, `jobs/news_sync.py`, `jobs/definitions/news_jobs.py`, `orchestration/news_flow.py`, `ingestion/sources/**`, `ingestion/library_sources/**`, `ingestion/scanners/all_symbols.py`, `ingestion/symbol_scanner.py`، تست‌های مرتبط.

**خارج از دامنه (handoff):** schema/مایگریشن مشترک، API مشترک بازار، `symbols`/`funds` DB schema، مسیر قیمت/صف، فرمت پاسخ‌های مشترک.

**صریحاً بررسی‌نشده:** درخت `_FRONTEND_BACKEND_COPY/**` (کپی قدیمی، نه درخت زندهٔ اجرا؛ فقط برای مقایسهٔ مسیر فایل کاتالوگ نگاه شد).

## ۳) Manifest فایل‌های خوانده‌شده

علامت‌ها: `کامل` = کامل خوانده شد؛ `بخشی` = بخشی خوانده شد (با دلیل)؛ `خارج` = باینری/تولیدی/وابستگی خارجی.

| فایل | وضعیت |
|---|---|
| `services/news_ingestion.py` | کامل (۱–۴۵۷) + ویرایش |
| `services/news_dual_write.py` | کامل (۱–۱۷۸) + ویرایش |
| `services/news_dedup.py` | کامل (۱–۱۰۸) |
| `services/news_service.py` | کامل (۱–۸۳) |
| `services/news_tag_symbol_mapper.py` | کامل (۱–۳۹۵) |
| `services/news_read_canary.py` | کامل (۱–۳۹۶) |
| `services/news_source_health.py` | بخشی — بازهٔ ۱۰۶–۱۴۰ در خروجی ترمینال truncate شد |
| `services/news_filter.py` | کامل (۱–۱۸۶) |
| `services/news_sentiment_pipeline.py` | کامل (۱–۱۵۰) |
| `services/fund_identity.py` | بخشی (۱–۱۲۰ از ۳۰۰+) |
| `services/fund_sync_service.py` | بخشی (۱–۷۰ + grep روی الگوهای cap/limit) |
| `services/symbol_catalog.py` (facade) | کامل (۱–۳۰) |
| `domain/instruments/symbol_catalog.py` | بخشی — بازهٔ ≈۱۵۱–۲۳۹ (لیست‌های gold/currency/crypto) در ترمینال truncate شد؛ ۱–۱۵۰ و ۲۴۰–۵۲۳ خوانده شد + ویرایش |
| `repositories/news_repository.py` | بخشی (۱–۶۵ از ~۳۰۰) — کافی برای درک مسیر canary read |
| `repositories/news_items_read_repo.py` | بخشی — بازهٔ ۱۰۵–۱۳۸ truncate شد |
| `repositories/instrument_repository.py` | بخشی (۱–۱۴۰ از ~۱۹۰) |
| `apps/api/endpoints/news.py` | بخشی — بازهٔ ۹۸–۱۳۰ truncate شد؛ سایر بخش‌ها (۱–۹۷، ۱۳۱–۵۷۱) خوانده شد |
| `apps/api/endpoints/news_tag_map_admin.py` | بخشی (۱–۱۲۰ از ~۲۰۰) |
| `apps/api/endpoints/symbol_search.py` | کامل (۱–۵۹) |
| `apps/api/endpoints/symbols.py` | بخشی (۱–۱۶۰ از ~۲۰۰) |
| `providers/base/news.py` | کامل |
| `providers/news/parser.py` | کامل (۱–۱۱۲) |
| `providers/news/domestic/mapping.py` | کامل |
| `providers/news/foreign/mapping.py` | کامل |
| `providers/news/domestic/rss_domestic_provider.py` | بخشی — فهرست فیدها (~۱۲۰ خط) truncate شد؛ سر/بدنه دیده شد |
| `providers/news/domestic/economic_news_provider.py` | کامل |
| `providers/news/rss/rss_provider.py` | کامل |
| `providers/news/rss/rss_client.py` | کامل |
| `providers/funds/mapping.py` | بخشی — ابتدای فایل در truncate خورد |
| `providers/funds/parser.py` | کامل |
| `brsapi/pipelines/news/{__init__,harmonization,enrichment,validation,persist,symbol_linker}.py` | harmony/persist/symbol_linker کامل؛ enrichment و validation بخشی (truncate) |
| `brsapi/pipelines/funds/{harmonization,enrichment,validation,persist}.py` | harmonization کامل؛ enrichment/validation بخشی |
| `jobs/news_sync.py`, `jobs/definitions/news_jobs.py` | کامل (۱–۱۳۰ و ۱–۱۰۵) |
| `orchestration/news_flow.py` | کامل (۱–۱۴) |
| `ingestion/sources/base.py`, `ingestion/scanners/all_symbols.py` | کامل |
| `ingestion/symbol_scanner.py` | بخشی (۱–۱۲۰ از ~۳۰۰) |
| `ingestion/sources/tsetmc.py` | بخشی (۱–۴۵) |
| `scripts/selected_symbols.json` | کامل (۱۵ رکورد) |
| `tests/unit/services/test_symbol_catalog.py` | بخشی (بررسی گزیده‌ای + ویرایش/افزودن) |
| `tests/unit/services/test_news_tag_symbol_mapper.py` | بخشی (۱–۱۵۰ + ویرایش/افزودن) |
| `tests/unit/services/test_news_source_health.py` | بخشی (بررسی `TestJobWrapper` و مارکرها) |
| `tests/integration/test_news_ingestion_flow.py` | کامل |
| `tests/unit/test_runtime_patches.py` | بخشی (۱–۶۰) |
| `tests/conftest.py` | بخشی (۱–۸۰) |
| `tests/unit/services/test_news_ingestion_skips.py` | **جدید — ساختهٔ همین مرحله** |
| `all_symbols.json`, `json/brsapi/symbol_details/**` | خارج — دادهٔ حجیم تولیدی |
| `node_modules/**`, `venv/**`, `.venv/**` | خارج — وابستگی خارجی |
| `_FRONTEND_BACKEND_COPY/**` | خارج (کپی قدیمی؛ فقط ۲ مقایسهٔ مسیر) |

## ۴) جدول مسیر: source → fetch → parse/map → dedup → persist → API/consumer

### ۴.۱ خبر (مسیر زندهٔ واقعی)

| مرحله | محل واقعی | وضعیت |
|---|---|---|
| source | `providers/news/domestic/rss_domestic_provider.py:13` (`DOMESTIC_RSS_FEEDS`, چند ده فید) | فقط فهرست ثابت؛ **فراخوانی زنده انجام نشد** |
| fetch | `providers/news/rss/rss_provider.py:44-89` → `rss_client.py:20-39` (retry×3, timeout 15s, per-feed timeout 20s, `asyncio.gather`) | خطای هر فید **منزوی** است: `Result.fail` و ادامهٔ فیدهای دیگر؛ ولی در بازگشت، هیچ شمارندهٔ per-source خطا در خروجی نیست (فقط `logger.warning`) |
| parse | `providers/news/rss/rss_parser.py::parse_feed` | XML خالی/خطا → `[]`؛ «هیچ داده جعلی برنمی‌گرداند» |
| map (نماد) | `providers/news/parser.py:72-79` (`extract_symbols`) | **کپ پنهان: ۶ نماد hard-coded** (`فولاد، فملی، وبانک، کگل، خودرو، شپنا`) |
| dedup (in-memory) | `services/news_dedup.py:48-96` (URL → title-hash → content-prefix, TTL 86400s) | درست و ثبت‌شده (`duplicates_removed`) |
| filter | `services/news_filter.py:87-164` | دلایل حذف **قابل ردیابی** (`stats` داخل فیلتر + log) |
| enrich | `services/news_ingestion.py:279-307` (sentiment + relevance) | خطای sentiment → `neutral` (fail-safe) |
| dedup (DB) | `services/news_ingestion.py:379-382` (`exists_by_url_or_title`) | **ریشهٔ باگ ۸-۱** (پایین) |
| persist (legacy) | `repositories/news_repository.py` (`news_articles`) | مسیر نوشتن اصلی |
| persist (dual-write) | `services/news_dual_write.py:59-133` (`news_items` + `news_tags` + `news_ingestion_sources`) | افزودنی؛ `safe_mirror` هرگز exception را بالا نمی‌دهد |
| read (canary) | `services/news_read_canary.py` + `repositories/news_items_read_repo.py` | حالت `off/shadow/canary/full` + parity + auto-halt (parity و HTTP 5xx) |
| API | `apps/api/endpoints/news.py` (`GET /news`, `/news/search`, `/news/symbol/{symbol}`, `/news/sources/health`, `/news/read-path/status|mode`, `POST /news/refresh`) + `news_tag_map_admin.py` (admin) | مسیرهای عمومی و محافظت‌شده حفظ شده‌اند |
| scheduler/job | `jobs/definitions/news_jobs.py` (`NewsIngestionJob`, `NewsSentimentJob`, `NewsSourceHealthJob`, `NewsReadPathHalterJob`) | متصل به `NewsIngestionService` |

### ۴.۲ نگاشت نماد/تیکر

| مسیر | محل | وضعیت |
|---|---|---|
| تگ خبر → نماد/صندوق (DB) | `services/news_tag_symbol_mapper.py` — ترتیب: `manual` → `exact` (funds سپس symbols) → `arabic_fallback` → `unmapped` | نرمال‌سازی فارسی (ی/ك، ZWNJ، ارقام) + ثبت «بدون‌نگاشت» برای ردیابی؛ **مبهم‌بودن**: `_probe_tables` با `LIMIT 1` و بدون `ORDER BY` (پایین، ریسک) |
| خواندن معکوس | `tag_values_for_symbol`, `explain_symbol` | درست؛ consumer = `NewsItemsReadRepo.get_by_symbol` |
| کاتالوگ ثابت نماد (DB-free) | `domain/instruments/symbol_catalog.py` + facade `services/symbol_catalog.py` | **ریشهٔ باگ ۸-۲** (پایین) |
| Finglish | `domain/instruments/symbol_finglish.py` + `repositories/instrument_repository.py:13-19` | درست؛ consumer = `/instruments/search` و `watchlist` |
| linker قدیمی خبر | `brsapi/pipelines/news/symbol_linker.py:10` (`_known_symbols` = ۸ نماد دستی) | **کد مرده** (هیچ فراخوانی‌کننده‌ای جز import در تست ندارد)؛ ریسک نهفته |

### ۴.۳ صندوق و دارایی

| مسیر | محل | وضعیت |
|---|---|---|
| provider | `providers/funds/{provider,client,parser,mapping}.py` | نگاشت فیلد ساده؛ `parse_nav`/`parse_holdings` با کلیدهای `nav_history`/`holdings` |
| pipeline | `brsapi/pipelines/funds/{harmonization,enrichment,validation,persist}.py` | همین‌طور **بدون فراخوانی‌کننده** (کد pipeline موازی) |
| هویت/alias | `services/fund_identity.py` (اولویت ISIN → National ID → Symbol+Type+Manager، `conflict`) | منطق «تصمیم» side-effect-free و testable |
| sync | `services/fund_sync_service.py` (`KNOWN_FUND_SYMBOLS`, `MAX_CONCURRENT=5`, `DELAY_BETWEEN_SYMBOLS=1.5`) | کپ‌ها **صریح و مستند** هستند (نه پنهان) |
| metadata دارایی | `domain/instruments/symbol_catalog.py` (سهام/طلا/ارز/رمزارز/کامودیتی/بورس کالا/صندوق + فایل غنی‌شده) | **ریشهٔ باگ ۸-۲** |

### ۴.۴ سایر ingestهای دامنه‌ای مستقل

| دامنه | محل | وضعیت |
|---|---|---|
| TSETMC instruments | `ingestion/sources/tsetmc.py` | `DataSource.fetch` → `SourcePayload` خام؛ **خطای HTTP به exception تبدیل نمی‌شود** (بازگشت payload خام) — ریسک «موفقیت کاذب» سطح پایین |
| crypto / derivatives / energy / global_markets / ifb / codal | `ingestion/sources/*.py` | همان الگوی `DataSource`؛ خروجی خالی در چند مورد (`crypto.py:71,81`, `tsetmc.py:58`) |
| library sources | `ingestion/library_sources/{algotik,finpy,pytse_client,sadra,universal_collector}.py` | آداپترهای کتابخانه‌های بیرونی — **بررسی سطحی**، بدون فراخوانی زنده |
| AllSymbols scanner | `ingestion/scanners/all_symbols.py` + `ingestion/symbol_scanner.py` | بازار-محور؛ خروجی صفر با `error` ثبت می‌شود (خوب) |
| news flow (orchestration) | `orchestration/news_flow.py` | **استاب** (`{"status": "completed"}` بدون کار واقعی) |
| `jobs/news_sync.py::NewsSyncJob` | — | **استاب** (`records: 0`) — دو root متفاوت برای «همگام‌سازی خبر» |

## ۵) یافته‌های تأییدشده در برابر فرضیه‌ها

### تأییدشده (با شاهد کد + اجرا)

1. **باگ ۸-۱ — «موفقیت کاذب» در شمارش ذخیرهٔ خبر.** `_save_article` روی تشخیص تکراری‌بودن، `None` برمی‌گرداند ولی حلقهٔ `ingest` هر بازگشت را «ذخیرهٔ موفق» می‌شمارد؛ همچنین `Result.fail` از `NewsService.save` نادیده گرفته می‌شد. شاهد: `services/news_ingestion.py:315-328` و `:358-361` (پیش از اصلاح). بازتولید واقعی: تست جدید → `assert 2 == 1` و `assert 2 == 0` شکست خورد.
2. **باگ ۸-۲ — حذف بی‌صدای کاتالوگ غنی‌شدهٔ نماد.** `_load_selected_symbols` مسیر `Path(__file__).resolve().parents[1] / "scripts" / "selected_symbols.json"` را می‌خواند که از `domain/instruments/` به `domain/scripts/` (ناموجود) اشاره می‌کند. شاهد: `domain/instruments/symbol_catalog.py:335` (پیش از اصلاح). اندازه‌گیری: `all_symbols()` = **۵۱۹**، `<15 → 0` هم‌پوشانی با `scripts/selected_symbols.json`.
3. **کپ پنهان نگاشت نماد خبر.** `providers/news/parser.py:74` فقط ۶ نماد hard-code؛ هر نماد دیگر در متن خبر **بی‌صدا** بی‌تگ می‌ماند. تأیید با خواندن کد + تست موجود `tests/unit/providers/test_news_parser.py`.
4. **کد مردهٔ pipeline خبر.** `brsapi/pipelines/news/*` هیچ فراخوانی‌کننده‌ای ندارد (`git grep` → تنها `tests/unit/test_runtime_patches.py:33` برای import). `NewsSymbolLinker._known_symbols` = ۸ نماد دستی.
5. **دو مسیر موازی برای «sync خبر».** `jobs/definitions/news_jobs.py::NewsIngestionJob` (واقعی) در برابر `jobs/news_sync.py::NewsSyncJob` و `orchestration/news_flow.py::NewsFlow` (استاب). هر سه وجود دارند و متمایزند — تصمیم‌گیری خارج از دامنه.
6. **مبهم‌بودن بالقوهٔ نگاشت.** `services/news_tag_symbol_mapper.py:157-173`: پرس‌وجوی `symbols`/`funds` با `LIMIT 1` و **بدون `ORDER BY`**؛ اگر دو ردیف هم‌نماد وجود داشته باشد انتخاب قطعی نیست. پیش‌فرض صریح «صندوق قبل از سهام» مستند است (`:18-20`) ولی انتخاب بین دو ردیف هم‌نامِ یک جدول مستند نیست.
7. **Authorization حفظ شده:** `/news/read-path/mode` با `require_roles("admin")` (`news.py:543-546`) و کل router ادمین `news_tag_map_admin.py` پشت نقش admin با ثبت `audit_logs` (`:36-64`).

### فرضیه‌هایی که تأیید/رد شدند (نه اتکا)

- *«مشکل OOM/۵۰۰ در news در گزارش قدیمی هست»* → **بخشی تأیید**: گزارش `docs/NEWS_READ_CANARY_SHADOW_REPORT_2026-09-20.md` در checkout هست و **در کد** به آن ارجاع داده شده (`services/news_read_canary.py:258-263`). ولی خود عدد/رخداد در این مرحله بازتولید نشد (نیازمند DB/Redis زنده) → «مسدود».
- *«`AUDIT_BATCH_*.md` سرنخ‌های لازم را دارند»* → **رد**: در checkout فعلی وجود ندارند.

## ۶) جدول ایرادها

| ID | شدت | شاهد `path:line` | روش بازتولید | اثر |
|---|---|---|---|---|
| ۸-۱ (رفع‌شده) | **بالا** | `services/news_ingestion.py:315-328`, `:358-361` | تست `tests/unit/services/test_news_ingestion_skips.py::test_existing_article_is_reported_as_skipped_not_saved` (پیش از اصلاح: `assert 2 == 1` FAIL) | گزارش کاذب موفقیت: `saved` متورم، دلیل حذف رکورد نامعلوم، خروجی job و `/news/refresh` گمراه‌کننده |
| ۸-۱b (رفع‌شده) | متوسط | `services/news_ingestion.py:417-424` (پیش از اصلاح بدون بررسی `save_result.success`) | `test_legacy_save_result_failure_is_not_counted_as_saved` | row در `news_items` mirror می‌شد ولی در `news_articles` نبود → نقض parity مسیر canary |
| ۸-۲ (رفع‌شده) | **بالا** | `domain/instruments/symbol_catalog.py:335` | `python -c "…all_symbols()…"` → ۵۱۹ نماد، هم‌پوشانی ۰ با فایل غنی‌شده | ۱۵ نماد معتبر (شامل صندوق‌های `عیار`، `کیان`) در جست‌وجوی نماد و Finglish و شمارش بخش‌ها **غایب** بودند، بی‌صدای کامل |
| ۸-۲b (رفع‌شده) | متوسط | `domain/instruments/symbol_catalog.py:365` + `sector_summary:451` | تست `test_enriched_fund_rows_are_not_published_as_stocks` | با ورود ردیف‌های غنی‌شده، صندوق‌ها در `سهام` دسته‌بندی می‌شدند (انتساب به دامنهٔ اشتباه) |
| ۸-۳ | متوسط | `providers/news/parser.py:72-79` | خواندن کد + `tests/unit/providers/test_news_parser.py` | پوشش نگاشت خبر→نماد عملاً محدود به ۶ نماد؛ بقیه بی‌صدا بی‌تگ |
| ۸-۴ | پایین | `brsapi/pipelines/news/symbol_linker.py:10-17` | `git grep NewsSymbolLinker` → تنها import در تست | کد مرده با کپ دستی ۸ نماد؛ اگر وصل شود منبع نگاشت غلط/ناقص |
| ۸-۵ | پایین | `services/news_tag_symbol_mapper.py:157-173` | خواندن کد (نیازمند DB برای اثبات قطعی) | انتخاب غیرقطعی بین ردیف‌های هم‌نماد (`LIMIT 1` بدون `ORDER BY`) |
| ۸-۶ | پایین | `providers/news/rss/rss_provider.py:52-54` | خواندن کد | `Result.ok([])` هنگام نبود فید = «موفقیت با صفر رکورد»؛ در مصرف‌کننده با falsy بودن `[]` جبران می‌شود |
| ۸-۷ | پایین | `orchestration/news_flow.py:11-14`, `jobs/news_sync.py:11-14` | خواندن کد | دو استاب هم‌نام با مسیر واقعی؛ ریسک فراخوانی اشتباه در آینده |
| ۸-۸ | پایین | `tests/unit/services/test_news_source_health.py::TestJobWrapper::test_success_when_healthy` | اجرای تست بدون DB → `RuntimeError … localhost:5432/market` | تست off-line-ایمن نیست (مارکر `needs_db` ندارد) → در CI بدون DB به‌جای skip، fail می‌دهد |
| ۸-۹ | پایین (پیش‌موجود) | `tests/unit/services/test_news_tag_symbol_mapper.py:233,240` | `ruff check` روی نسخهٔ `HEAD` هم `C408` می‌دهد | بدهی lint در تست‌های موجود؛ خارج از دامنهٔ این اصلاح |

## ۷) علت ریشه‌ای

- **۸-۱/۸-۱b:** تابع `_save_article` به‌عنوان تابع `None`-بازگشت (void) طراحی شده بود؛ حذف «مسیر تکراری» و «ذخیرهٔ ناموفق» هیچ سیگنالی به حلقه نمی‌داد، پس حلقه ناچار بود هر عدم-exception را موفق بپندارد → شمارندهٔ متورم و از‌دست‌رفتن دلیل حذف.
- **۸-۲:** جابه‌جایی فایل از `services/` به `domain/instruments/` عمق نسبی را یک سطح زیاد کرد ولی `parents[1]` به‌روز نشد. مسیر ناموجود هم به‌صورت «best-effort» صفر برمی‌گرداند بدون exception/لاگ → خرابی کامل و بی‌صدا.
- **۸-۲b:** قرارداد `sector_summary` مبنی بر «هر sector غیر از ۷ مقدار بازار → سهام» با رشته‌های granular فایل غنی‌شده ترکیب می‌شد و صندوق را به سهام تبدیل می‌کرد.
- **۸-۳/۸-۴:** نگاشت خبر→نماد در ابتدا به‌صورت «مجموعهٔ کوچک ثابت» پیاده شده و هرگز به کاتالوگ/DB وصل نشد.
- **۸-۸:** تست jobها از `get_session()` واقعی استفاده می‌کنند و در محیط بدون DB، exception به‌جای skip داده می‌شود.

## ۸) تغییرات کد و دلیل هرکدام

| فایل | تغییر | دلیل |
|---|---|---|
| `services/news_ingestion.py` | `stats["skipped_existing"]`؛ `_save_article` اکنون `"saved"`/`"skipped_existing"` برمی‌گرداند؛ حلقه بر همین اساس می‌شمارد؛ `Result.fail` مسیر legacy به exception تبدیل و به‌عنوان خطا شمرده می‌شود؛ خط لاگ و یک خط خلاصهٔ ترمینال برای «already present» | حذف «موفقیت کاذب» و قابل‌ردیابی‌کردن **دلیل حذف رکورد**؛ حفظ parity مسیر dual-write |
| `services/news_dual_write.py` | یک `logger.debug` هنگام رد شدن mirror به‌دلیل `dedup_hash` موجود | قابل‌ردیابی‌کردن دلیل حذف رکورد در لایهٔ `news_items` |
| `domain/instruments/symbol_catalog.py` | مسیر فایل غنی‌شده از `parents[1]` به `parents[2]` (ریشهٔ مخزن)؛ `logger.debug` در نبود فایل؛ تابع `_canonical_market_sector` برای نگاشت رشته‌های صندوقی به `صندوق` | رفع حذف بی‌صدای ۱۵ نماد + جلوگیری از انتساب صندوق به دامنهٔ «سهام» |
| `tests/unit/services/test_news_ingestion_skips.py` | **جدید** — ۴ تست | پوشش باگ ۸-۱/۸-۱b (شامل partial failure و batch تماماً تکراری) |
| `tests/unit/services/test_symbol_catalog.py` | +۵ تست | پوشش باگ ۸-۲/۸-۲b و نگاشت بخش |
| `tests/unit/services/test_news_tag_symbol_mapper.py` | +۲ تست | پوشش «نبود mapping → ثبت `unmapped` و عدم انتساب به نماد اشتباه» + مسیر `persist=False` |

**بدون تغییر (handoff):** `providers/news/parser.py` (۸-۳) — توسعهٔ پوشش نماد نیازمند منطق مرز-توکن + جهان نماد منتخب است؛ گسترش ساده‌لوحانه به زیررشتهٔ ۵۱۹ نماد باعث false-positive و «اتصال به نماد اشتباه» می‌شود (خارج از دامنهٔ اصلاح کوچک). `services/news_tag_symbol_mapper.py` (۸-۵) — افزودن `ORDER BY` نیازمند تصمیم محصولی دربارهٔ اولویت و migration ایندکس است. `tests/.../test_news_source_health.py` (۸-۸) — افزودن مارکر `needs_db` تغییر تست خارج از دامنهٔ خبر/نماد است.

## ۹) فرمان‌های تست دقیق + نتیجه

همه با `$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"` و `-p no:cacheprovider` اجرا شدند.

**الف) بازتولید باگ پیش از اصلاح (TDD)**
```
python -m pytest -q -p no:cacheprovider tests/unit/services/test_news_ingestion_skips.py
→ 2 failed, 1 passed  (assert 2 == 1 / assert 2 == 0)   EXIT=1
```

**ب) پس از اصلاح**
```
python -m pytest -q -p no:cacheprovider tests/unit/services/test_news_ingestion_skips.py
→ 4 passed                                              EXIT=0

python -m pytest -q -p no:cacheprovider tests/unit/services/test_news_tag_symbol_mapper.py
→ 7 passed, 4 skipped                                   EXIT=0

python -m pytest -q -p no:cacheprovider tests/unit/services/test_symbol_catalog.py
→ 42 passed                                             EXIT=0
```

**ج) باطری درون‌دامنه (۱۱ فایل: news_ingestion_skips، news_dual_write، news_items_read_path، news_read_canary، news_service، news_tag_symbol_mapper، providers/test_news_parser، api/test_news_category، api/test_news_date_range، api/test_news_symbol_meta_http، services/test_symbol_catalog)**
```
python -m pytest -q -p no:cacheprovider <11 files>
→ 144 passed, 15 skipped, 3 warnings in 58.22s           EXIT=0
```

**د) فایل‌های DB-وابسته**
```
python -m pytest -q -p no:cacheprovider tests/unit/services/test_news_source_health.py tests/unit/api/test_news_tag_map_admin.py tests/unit/api/test_news_date_range_http.py
→ 1 failed, 15 passed, 5 skipped                        EXIT=1
   FAILED tests/unit/services/test_news_source_health.py::TestJobWrapper::test_success_when_healthy
   RuntimeError: Cannot connect to PostgreSQL database … Tried: localhost:5432/market

python -m pytest -q -p no:cacheprovider tests/unit/services/test_symbol_catalog.py tests/unit/providers/test_news_parser.py tests/unit/test_symbols_page_size.py
→ 4 failed, 43 passed    (هر ۴ شکست از tests/unit/test_symbols_page_size.py و همگی DB-وابسته)   EXIT=1
```

**ه) تأیید ادعای نشست قبلی**
```
python -m pytest -q -p no:cacheprovider tests/unit/repositories/test_sync_log_repository.py
→ 15 passed in 40.31s                                   EXIT=0
```

**و) Lint**
```
python -m ruff check services/news_ingestion.py services/news_dual_write.py domain/instruments/symbol_catalog.py tests/unit/services/test_news_ingestion_skips.py
→ All checks passed!                                    EXIT=0

python -m ruff check tests/unit/services/test_symbol_catalog.py tests/unit/services/test_news_tag_symbol_mapper.py
→ Found 2 errors (C408) — هر دو در کد موجودِ همان فایل (تأیید با اجرای ruff روی نسخهٔ HEAD)   EXIT=1
```

**ر) بازتولید عددی باگ ۸-۲**
```
# پیش از اصلاح
catalog size 519 ; has فارس2: False ; overlap(selected_symbols) = 0
# پس از اصلاح
catalog size 534 ; missing [] ; عیار/کیان → sector 'صندوق'
sector_summary → صندوق 350 / رمزارز 73 / بورس کالا 36 / سهام 27 / طلا و سکه 19 / ارز 15 / کامودیتی 14  (مجموع 534)
```

> `python -m ruff format --check` روی این فایل‌ها «would reformat» می‌دهد، **اما نسخهٔ `HEAD` همین فایل‌ها هم همین‌طور بود** → مخزن formatter را الزام نکرده؛ برای پرهیز از churn بی‌ربط، فرمت کل فایل بازنویسی نشد.

## ۱۰) تست‌های اجرانشده و علت

| تست | علت |
|---|---|
| تست‌های DB-وابستهٔ `test_news_tag_symbol_mapper.py` (۴ مورد) و `test_news_source_health.py::TestHealthReportDb` | `DATABASE_URL` تنظیم نیست / PostgreSQL محلی در دسترس نیست → `pytest.skip` |
| `tests/unit/test_symbols_page_size.py` (۴ تست) | نیازمند PostgreSQL + اپ کامل |
| `frontend/src/__tests__/useMarketData.test.tsx` و کل تست‌های frontend | خارج از دامنهٔ این مرحله (فقط وضعیت git آن تأیید شد) |
| هر تستی که نیازمند فراخوانی زندهٔ RSS/BrsApi/TSETMC باشد | **مسدود به‌علت نبود دسترسی زنده** (طبق قواعد مأموریت) |
| اثبات عددی OOM/۵۰۰ گزارش ۲۰۲۶-۰۹-۲۰ | نیازمند DB/Redis زنده → **مسدود** |
| اجرای full regression پروژه | خارج از دامنه و نیازمند DB؛ باطری درون‌دامنه اجرا شد |

## ۱۱) خطرات باقی‌مانده و وابستگی‌ها

- **۸-۳ (نگاشت خبر→نماد):** پوشش نماد در خبر همچنان ۶ نماد دستی است. `news_tags` تقریباً برای همهٔ نمادهای غیر از این ۶ خالی می‌ماند؛ بنابراین مسیر canary خواندن با `?symbol=` برای آن نمادها (به‌جز تطبیق spelling در `news_articles`) نتیجهٔ کمتری برمی‌گرداند.
- **۸-۵:** نبود `ORDER BY` در `_probe_tables` ممکن است در DB واقعی (با ردیف‌های هم‌نماد) انتخاب غیرقطعی بدهد؛ بدون DB قابل اثبات نیست.
- **۸-۸:** با نبود PostgreSQL، `test_news_source_health.py::test_success_when_healthy` fail می‌دهد (نه skip) — در CI بدون DB سراسری شدن failure محتمل است.
- **۸-۹:** ۲ مورد `C408` پیش‌موجود در تست mapper.
- **پوشش‌نداشتن** `pipelines/news` و `pipelines/funds` توسط هیچ caller → هرگونه تغییر آینده در `services/news_*` باید این دو را هم‌زمان تعیین تکلیف کند (کد مرده/متناقض).
- **دامنهٔ `_FRONTEND_BACKEND_COPY`** کپی قدیمی است و ممکن است برای خوانندهٔ آینده گمراه‌کننده باشد (مسیر `parents[1]` در آن هم اشتباه است).
- وابستگی‌ها: PostgreSQL و Redis برای اثبات canary/parity و alert؛ BrsApi برای pipeline واقعی خبر.

## ۱۲) معیارهای پذیرش و وضعیت

| معیار پذیرش | وضعیت | شاهد |
|---|---|---|
| هر مسیر مستقل منبع، دلیل حذف/تغییر رکورد را قابل‌ردیابی کند | **محقق (در دامنهٔ خبر)** — `skipped_existing` + لاگ دلیل + لاگ رد شدن mirror + دلایل فیلتر موجود | `services/news_ingestion.py:340-346`، `services/news_dual_write.py:90-94`، تست‌های جدید |
| وضعیت خطا قابل‌ردیابی باشد | **محقق** — `errors` برای exception و برای `Result.fail` مسیر legacy؛ `NewsSourceHealthService` برای منبع مرده | `services/news_ingestion.py:326-336`, `:417-424`; `news_source_health.py` |
| mapping مبهم پوشش تست داشته باشد | **تا حد امکان آفلاین محقق** — «نبود mapping نباید بی‌صدا وصل شود» با تست پوشش یافت؛ مبهم‌بودن بین دو ردیف هم‌نام **مسدود به‌علت نبود DB** | `tests/unit/services/test_news_tag_symbol_mapper.py` (۷ passed، ۴ skipped) |
| partial failure در تست‌ها پوشش داده شود | **محقق** — ذخیرهٔ ناموفق یکی از دو رکورد، batch تماماً تکراری، `Result.fail` مسیر legacy | `tests/unit/services/test_news_ingestion_skips.py` (۴ passed) |
| mapping بدون‌نماد به نماد اشتباه وصل نشود | **محقق** — ردیف‌های صندوقی فایل غنی‌شده روی `صندوق` می‌مانند، نه `سهام` | `test_enriched_fund_rows_are_not_published_as_stocks` |
| صندوق/دارایی بدون‌نماد بی‌صدا حذف نشود | **محقق** — ۱۵ ردیف غنی‌شده اکنون در کاتالوگ هستند | `test_enriched_selected_symbols_are_merged_into_the_catalog`، عدد ۵۱۹→۵۳۴ |
| کپ پنهان / صفحه‌بندی ناقص بررسی شود | **بررسی‌شده و مستند** — کپ‌ها شمرده شدند (۶ نماد news، ۱۰ نماد در `news_sentiment_pipeline:81`، `MAX_UPLOAD_BYTES`، `page_size le=10000`، `limit` clamp در `symbol_catalog.search`) | جدول بخش ۴ و ایراد ۸-۳ |
| فقط این حوزه اصلاح شود و schema/API مشترک handoff شود | **محقق** — هیچ schema/مایگریشن/API مشترکی تغییر نکرد؛ تغییرات محدود به ۳ فایل کد درون‌دامنه + ۳ فایل تست | بخش ۸ |

## ۱۳) وضعیت پاک‌سازی و کارهای کاربر

- هیچ فایل کاربر حذف/بازنویسی نشد؛ فایل‌های staged/untracked دست‌نخورده ماندند.
- فایل‌های ناخواسته/موقت در مخزن ایجاد نشد (فقط ۱ فایل تست جدید + ۱ فایل گزارش).
- `services/market_service.py.bak`, `src/gold_desk/*`, `_8_gate/**`, `_audit_base/**` و … تغییر نکردند.

### فایل‌های تغییرکردهٔ این مرحله

```
 M domain/instruments/symbol_catalog.py        (+26/-? — مسیر + نگاشت بخش)
 M services/news_dual_write.py                 (+5)
 M services/news_ingestion.py                  (+42/-9 حدود)
 M tests/unit/services/test_symbol_catalog.py  (+59)
 M tests/unit/services/test_news_tag_symbol_mapper.py (+63)
?? tests/unit/services/test_news_ingestion_skips.py   (جدید، ۴ تست)
?? AUDIT_REPORTS/MODULAR_TEMCE/08_NEWS_FUNDS_SYMBOLS_OTHER_INGESTION.md (همین گزارش)
```

### موارد مسدود (صریح)

1. اثبات/بازتولید خطای OOM و ۵۰۰ مسیر خبر (نیازمند PostgreSQL/Redis زنده).
2. تست‌های DB-وابستهٔ نگاشت تگ→نماد و health منبع خبر.
3. قطعی‌کردن «انتخاب غیرقطعی در `_probe_tables`» (نیازمند DB با دو ردیف هم‌نماد).
4. هر تأییدی که نیازمند درخواست زنده به RSS/BrsApi/TSETMC باشد.
