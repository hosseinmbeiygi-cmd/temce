# مرحلهٔ ۸ — دور دوم: اجرای کارهای باقی‌ماندهٔ ممیزی

> این فایل، دور دوم مرحلهٔ ۸ است. گزارش دور اول
> (`08_NEWS_FUNDS_SYMBOLS_OTHER_INGESTION.md`) **بازنویسی/overwrite نشد** و دست‌نخورده است؛
> این پیوست، کارهای باقی‌مانده‌ای را که ممیزی (`QA_STAGE_8.md`) فهرست کرده بود انجام می‌دهد.

## ۰) فرادادهٔ اجرا

| کلید | مقدار |
|---|---|
| تاریخ/زمان اجرا (Tehran) | ۲۰۲۶-۱۰-۲۹، حدود ۰۰:۰۰–۰۰:۳۰ |
| ریشهٔ مخزن | `C:\Users\Iran\Desktop\temce` |
| شاخه | `integration/golddesk-fixes` |
| `HEAD` | `90597e05` (`90597e05b9f4328bcd82ee819a31ba5c55413c12`) — تغییری نکرد |
| پوسته / Python | Windows PowerShell؛ `venv` محلی؛ `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` |
| Ruff | `0.15.17` |
| PostgreSQL محلی | در دسترس نیست → تست‌های `needs_db` علی‌الحساب skip/دسِلکت می‌شوند |
| BrsApi/TSETMC/RSS زنده | **استفاده نشد** (طبق قواعد ثابت مأموریت) |
| Commit | ایجاد نشد |

## ۱) دامنهٔ این دور

هفت موردی که در ممیزی (`QA_STAGE_8.md`) به‌عنوان کار باقی‌مانده ثبت شده بود:
۸-۳ (کپ ۶ نماد)، ۸-۴ (کد مردهٔ linker)، ۸-۵ (نگاشت مبهم)، ۸-۶ (موفقیت صفر-رکورد RSS)،
۸-۷ (استاب‌های هم‌نام)، ۸-۸ (تست DB-وابستهٔ fail‌شونده) و QA-8-A (ارجاع‌های جابه‌جا در گزارش دور اول).
مورد BLOCKED (اثبات زندهٔ مبهم‌بودن در DB/Redis واقعی) خارج از توان این محیط ماند.

## ۲) جدول اصلاحات این دور

| # | فایل | تغییر (خلاصهٔ diff) | دلیل | تست |
|---|---|---|---|---|
| ۸-۳ | `providers/news/parser.py` (+157/-1) | `extract_symbols` از فهرست hard-code شش‌نمادی به نگاشت مبتنی بر `domain.instruments.symbol_catalog` تغییر کرد: فولد ی/ك/ZWNJ/ارقام، قالب `#نماد`/`$TICKER` برای کل کاتالوگ، تطبیق bare فقط خارج از بخش «صندوق» + مرز توکن (لاتین دو طرف، فارسی سمت چپ) + حذف `کالا`، ترجیح طولانی‌ترین تطبیق، یکسان‌سازی املای عربی/فارسی twins، حذف تکراری‌ها با ترتیب اولین ظهور | این تابع مصرف‌کنندهٔ زندهٔ مسیر ingest است (`services/news_ingestion.py:391`)، پس کپ ۶ نماد یعنی هر خبر مربوط به نمادهای دیگر بی‌تگ و بی‌صدا ذخیره می‌شد | `tests/unit/providers/test_news_symbol_extraction.py` (۹ تست) |
| ۸-۴ | `brsapi/pipelines/news/symbol_linker.py` (+8/-11) | حذف `_known_symbols` (۸ نماد دستی) و واگذاری `extract_symbols` به `NewsParser`؛ مستندسازی «کد مرده، ابزار واقعی همان کاتالوگ است» | دو مسیر متناقض نگاشت؛ اگر دوباره وصل شود، منبع نگاشت غلط/ناقص می‌شود. (حذف فایل طبق قواعد مأموریت ممنوع بود.) | پوشش غیرمستقیم از طریق تست‌های parser |
| ۸-۵ | `services/news_tag_symbol_mapper.py` (+53/-13) | `_PROBE_SQL` + `_probe_sql()`: هر دو probe اکنون `ORDER BY id ... LIMIT 2`؛ `_probe_tables` کم‌ترین `id` را قطعی برمی‌گزیند و در صورت >۱ ردیف، `logger.warning` «Ambiguous news tag mapping» می‌دهد | `LIMIT 1` بدون `ORDER BY` انتخاب را به planner واگذار می‌کرد → احتمال اتصال تگ به ردیف اشتباه، بی‌سروصدا | `TestAmbiguousProbeIsDeterministic` (۲ تست آفلاین با session stub) |
| ۸-۶ | `providers/news/rss/rss_provider.py` (+29/-2) | نبود فید → `Result.fail("no_feeds_configured:…")`؛ شمارش per-source (ok/empty/failed) + یک `logger.info` خلاصهٔ هر اجرا؛ «همهٔ فیدها شکست خورده‌اند» → `Result.fail("all_feeds_failed:…<per-source>")`؛ موفقیت با صفر رکورد واقعی همچنان `ok([])` | تفکیک «پیکربندی غلط/قطع کامل» از «فید سالم ولی خالی»؛ قبلاً هر سه حالت یک `success + 0 records` می‌داد | `tests/unit/providers/test_news_rss_provider_status.py` (۴ تست) |
| ۸-۶b | `services/news_ingestion.py` (+5) | افزودن `stats["fetch_error"]` و `stats["errors"] += 1` در مسیر شکست fetch | خطای منبع در خروجی job و `/news/refresh` اثری نداشت؛ حالا دلیل خطا قابل‌ردیابی است | `test_fetch_failure_is_recorded_instead_of_a_silent_zero` |
| ۸-۷ | `orchestration/news_flow.py`، `jobs/news_sync.py` (+16/-8 و +14/-4) | هر دو استاب از `Result.ok({"status": "completed"})` به `Result.fail("not_implemented: …")` + `logger.error` و docstring ارجاع‌دهنده به `jobs/definitions/news_jobs.py::NewsIngestionJob` تغییر کردند | «completed» برای کاری که هیچ‌وقت اجرا نمی‌شود، ریسک اتصال اشتباه و گزارش موفقیت کاذب است | `tests/unit/test_news_stub_paths.py` (۲ تست) |
| ۸-۸ | `tests/unit/services/test_news_source_health.py` (+1) | افزودن `@pytest.mark.needs_db` به `TestJobWrapper::test_success_when_healthy` | این تست پیش از `NewsSourceHealthService` یک session واقعی می‌گیرد؛ بدون DB به‌جای skip، **fail** می‌شد (تأییدشده در ممیزی با دو اجرای مستقل) | همان تست؛ حالا دسلکت/اسکیپ می‌شود |
| QA-8-A | همین فایل | ثبت اصلاح ارجاع: در دور اول بخش ۶ ردیف ۸-۲b به `domain/instruments/symbol_catalog.py:365` و `sector_summary:451` ارجاع داده بود؛ مقادیر درست **`:366`** (اعمال `_canonical_market_sector`) و **`:472`** (خط fold شدن بخش‌های granular به «سهام» در `sector_summary`؛ تعریف تابع در `:459`) است. متن دور اول دست‌نخورده ماند (بدون بازنویسی تاریخ) | ارجاع یک‌خطی جابه‌جا، ردیابی خواننده را دشوار می‌کرد | — |

**فایل‌های جدید تست:** `tests/unit/providers/test_news_symbol_extraction.py`،
`tests/unit/providers/test_news_rss_provider_status.py`، `tests/unit/test_news_stub_paths.py`.

خلاصهٔ diff این دور (فقط فایل‌های همین دامنه):

```
 brsapi/pipelines/news/symbol_linker.py             |  19 +--
 jobs/news_sync.py                                  |  14 +-
 orchestration/news_flow.py                         |  16 ++-
 providers/news/parser.py                           | 157 ++++++++++++++++++++-
 providers/news/rss/rss_provider.py                 |  29 +++-
 services/news_ingestion.py                         |  47 +++++-
 services/news_tag_symbol_mapper.py                 |  53 ++++++--
 tests/unit/services/test_news_source_health.py     |   1 +
 tests/unit/services/test_news_tag_symbol_mapper.py | 126 +++++++++++++++++
 9 files changed, 424 insertions(+), 38 deletions(-)   (به‌علاوه ۳ فایل تست جدید/untracked)
```

## ۳) طراحی نگاشت نماد (۸-۳) و مرزهای دقت

دادهٔ واقعی کاتالوگ در همین checkout سنجیده شد: **۵۳۴** نماد، **بدون نماد تکراری**،
۱۸۳ نامزد bare (خارج از بخش «صندوق»)، و در بخش «صندوق» ۳۵۰ نماد که عمدتاً واژه‌های
عادی فارسی‌اند (`آتش`، `ارزش`، `آس`). بنابراین:

- نمادهای صندوق **فقط** با قالب صریح `#نام`/`$TICKER` پذیرفته می‌شوند (پیش‌فرض «صندوق قبل از سهام» در DB دست‌نخورده می‌ماند)؛
- تطبیق bare برای واژه‌های عمومی غیرقابل‌اعتماد مسدود است (`کالا` در «بورس کالا»)؛
- نمادهای هم‌شکل: بزرگ‌ترین تطبیق در همان موقعیت برنده است (`کگل2` نه `کگل`)؛
- املای عربی/فارسی یک نماد به یک نتیجه می‌رسد و شکل فارسی‌اش برگردانده می‌شود (`آساميد`+`آسامید` → `آسامید`)؛
- هیچ نمادی ساخته نمی‌شود: خروجی همیشه زیرمجموعهٔ کاتالوگ است (تست اختصاصی).

## ۴) فرمان‌های تست و نتیجهٔ واقعی

همه با `$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"` و `-p no:cacheprovider`.

| # | فرمان | نتیجه | exit |
|---|---|---|---|
| ۱ | `pytest -q … tests/unit/providers/ tests/unit/test_news_stub_paths.py tests/unit/services/test_news_ingestion_skips.py tests/unit/services/test_news_tag_symbol_mapper.py` | `56 passed, 4 skipped in 7.77s` | 0 |
| ۲ | باطری ۱۵ فایلی (باطری ۱۱ فایلی دور اول + `providers/test_news_symbol_extraction.py`, `providers/test_news_rss_provider_status.py`, `test_news_stub_paths.py`, `test_critical_runtime_fixes.py`) | `177 passed, 15 skipped, 3 warnings in 152.63s` | 0 |
| ۳ | `pytest -q … tests/unit/services/test_news_source_health.py tests/unit/api/test_news_tag_map_admin.py tests/unit/api/test_news_date_range_http.py` | `15 passed, 5 skipped, 1 deselected, 8 warnings in 129.19s` (پیش از ۸-۸: `1 failed`) | 0 |
| ۴ | `ruff check` روی ۷ فایل تولیدی + ۴ فایل تست این دور | `All checks passed!` | 0 |
| ۵ | `ruff check` روی `test_news_source_health.py` و `test_news_tag_symbol_mapper.py` | `Found 7 errors` — هر ۷ مورد **پیش‌موجود** (۵ مورد با اجرای ruff روی نسخهٔ `HEAD` بازتولید شد: F821 + ۴×C408؛ ۲×C408 نیز قبلاً روی `HEAD` تأیید شده بود) | 1 |
| ۶ | اسموک import: `import apps.api.main`, `providers.news.parser`, `brsapi.pipelines.news.symbol_linker` + یک فراخوانی واقعی `extract_symbols` | `imports ok` / `smoke: ['شپنا', 'وبملت', 'آگاس']` | 0 |

**تست‌های اجرانشده (و علت):**

- تست‌های DB-وابستهٔ `test_news_tag_symbol_mapper.py` (۴ مورد) و `TestHealthReportDb` → بدون PostgreSQL `skip`.
- `tests/unit/test_symbols_page_size.py` → نیازمند اپ کامل + PostgreSQL.
- اثبات «انتخاب قطعی در DB واقعی با دو ردیف هم‌نماد» → نیازمند PostgreSQL؛ پوشش آفلاین با session stub انجام شد.
- بدل شدن shadow/canary/OOM-500 → نیازمند PostgreSQL/Redis زنده.
- هر تست نیازمند RSS/BrsApi/TSETMC زنده → **BLOCKED** طبق قواعد مأموریت.
- تست‌های frontend → خارج از دامنهٔ مرحله ۸.

## ۵) کنترل رگرسیون و حفظ وضعیت

- هیچ فایل کاربر حذف/بازنویسی نشد؛ فایل‌های staged/untracked و ۳ stash دست‌نخورده ماندند؛ هیچ commit ایجاد نشد.
- تغییرات این دور فقط در دامنهٔ مرحله ۸ است (۹ فایل ویرایش‌شده + ۳ فایل تست جدید)؛
  هیچ schema/مایگریشن/API مشترکی تغییر نکرد.
- خطای `1 failed` گزارش دور اول اکنون برطرف شده و به `1 deselected` تبدیل شد (شاهد: ردیف ۳ جدول بالا).

## ۶) خطرات باقی‌مانده و موارد BLOCKED

1. **BLOCKED:** تأیید انتخاب قطعی نگاشت در DB واقعی (نیازمند دو ردیف هم‌نماد + PostgreSQL).
2. **BLOCKED:** پاریتی مسیر canary/shadow و بازتولید OOM/HTTP-500 (نیازمند PostgreSQL/Redis زنده).
3. **BLOCKED:** هر تأییدی که نیازمند درخواست زندهٔ RSS/BrsApi/TSETMC باشد.
4. ریسک باقی‌ماندهٔ طراحی: تطبیق bare فارسی به‌صورت «پیشوند واژه» انجام می‌شود (تا `فولادمبارکه` از دست نرود)؛ این می‌تواند واژه‌های مشتق
   (`خودرویی`) را نیز به نماد وصل کند. این رفتار آگاهانه و مستند است (کاهش recall به‌جای از‌دست‌رفتن نمادهای اصلی) و قابل تنظیم با `_BARE_DENY`.
5. بدهی lint پیش‌موجود در دو فایل تست (۷ خطا) خارج از دامنهٔ این اصلاح ماند؛ در صورت نیاز مرحلهٔ مستقل.

## ۷) معیارهای پذیرش و وضعیت

| معیار پذیرش | وضعیت | شاهد |
|---|---|---|
| هر مسیر مستقل منبع، دلیل حذف/تغییر رکورد را قابل‌ردیابی کند | **محقق** | `skipped_existing` + لاگ دلیل (`news_ingestion`)، لاگ رد شدن mirror (`news_dual_write`)، `unmapped` در mapper، لاگ per-source فید |
| وضعیت خطا قابل‌ردیابی باشد | **محقق** | `stats["errors"]`/`stats["fetch_error"]`، `all_feeds_failed`/`no_feeds_configured`، استاب‌های fail-closed |
| mapping مبهم پوشش تست داشته باشد | **محقق (آفلاین)** | `TestAmbiguousProbeIsDeterministic` + تست twins/look-alike؛ تأیید روی DB واقعی BLOCKED |
| partial failure در تست‌ها پوشش داده شود | **محقق** | `test_save_failure_is_counted_and_does_not_abort_the_batch`، `test_partial_failure_still_returns_the_healthy_articles` |
| mapping بدون‌نماد به نماد اشتباه وصل نشود | **محقق** | تست‌های unmapped، `کالا`، `کگل2`، زیرمجموعهٔ کاتالوگ |
| فقط همین حوزه اصلاح شود | **محقق** | ۹ فایل ویرایش + ۳ تست جدید؛ بدون تغییر schema/API مشترک |

## ۸) نتیجهٔ این دور

**PASS در دامنهٔ مرحلهٔ ۸** — هر هفت کار باقی‌ماندهٔ ممیزی انجام و با تست آفلاین تثبیت شد
(۱۷۷ + ۱۵ + ۵۶ تست سبز، Ruff سبز روی کد تغییر‌یافته، انتشار: `1 failed` دور اول برطرف شد).
سه مورد تأییدِ وابسته به محیط زنده (DB/Redis/BrsApi) همان‌طور **BLOCKED** و مستند باقی است.
