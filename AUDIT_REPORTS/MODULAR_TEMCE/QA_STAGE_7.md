# QA — ممیزی مستقل مرحلهٔ ۷ (کیفیت داده، زمان‌ها، تاریخچه‌ها و NAV)

> این فایل، ممیزی مستقل مرحلهٔ ۷ است. هیچ ادعایی از گزارش خودِ مرحله بدون بررسی شاهد کد/تست/Git پذیرفته نشده است.

| مورد | مقدار |
|---|---|
| زمان اجرای ممیزی | `2026-10-28 23:19` تا `23:35` (ساعت محلی ماشین) |
| داور | همان عامل، در نقش ممیز؛ **بر اساس شاهد، نه ادعای قبلی** |
| شاخه | `integration/golddesk-fixes` |
| `HEAD` در زمان ممیزی | `90597e05b9f4328bcd82ee819a31ba5c55413c12` |
| commit ساخته‌شده در این مرحله | **هیچ** (`git log -1` همان `90597e05` است) |
| **وضعیت نهایی** | **PARTIAL** |

---

## ۱) مسیر گزارش نهایی مرحله و وجود فایل

| مورد | مقدار |
|---|---|
| مسیر اعلام‌شده | `AUDIT_REPORTS/MODULAR_TEMCE/07_DATA_QUALITY_TIMESTAMP_HISTORY.md` |
| وجود فایل | **تأیید شد** (`ls -la` → فایل موجود، ۵۰٬۰۰۴ بایت، mtime `2026-10-28 23:12`) |
| تعداد خط | ۴۰۴ خط |
| بخش‌های موجود | ۱۴ سرفصل `##` (شامل همهٔ ۱۲ بخش الزامی بند ۹ پرامپت + سه بخش تکمیلی) |
| overwrite گزارش قبلی | رخ نداد؛ فایل `07_*` از قبل وجود نداشت (فهرست `AUDIT_REPORTS/MODULAR_TEMCE/` در ابتدای مرحله ۰۰–۰۵ و QA_* بود، بدون فایل ۰۷) |
| مسیر QA | `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_7.md` (همین فایل) |

---

## ۲) روش ممیزی (چه چیزی واقعاً بازبینی شد)

1. `git rev-parse HEAD`, `git branch --show-current`, `git log --oneline -3`, `git status --short --branch`, `git diff --cached --stat`, `git diff --stat`, `git status --porcelain --untracked-files=all` — وضعیت فعلی با وضعیت ابتدای مرحله مقایسه شد.
2. `git diff` کامل چهار فایل tracked تغییرکرده خوانده شد (`history_fetch_service.py`, `freshness.py`, `nav_checker.py`, `market_info.py`).
3. وجود و اندازهٔ هفت فایل جدید (ماژول کیفیت، fixture، پنج تست) با `ls -la` تأیید شد.
4. شماره‌خط‌های ارجاع‌داده‌شده در گزارش مرحله به‌صورت نقطه‌ای با `sed -n`/`grep -n` روی فایل واقعی تطبیق داده شد (نتیجه در بخش ۹).
5. تست‌ها **از نو** اجرا شدند (نه نقل از اجرای قبلی) و خروجی خام + exit code ثبت شد.
6. `ruff` روی فایل‌های تغییرکرده؛ برای خطای موجود در `nav_checker.py` نسخهٔ `HEAD` همان فایل جداگانه بررسی شد تا «از قبل موجود بودن» اثبات شود.
7. شمارش تست‌ها با `pytest --collect-only` مستقل تأیید شد.
8. جست‌وجوی SQL مخرب (`DELETE/TRUNCATE/DROP/ALTER`) و فراخوانی شبکه (`requests/httpx/aiohttp/urllib`) در فایل‌های جدید.

---

## ۳) فایل‌های بررسی‌شده و بررسی‌نشده (در این ممیزی)

### ۳.۱ بررسی‌شده در این ممیزی

| فایل | نحوهٔ بررسی |
|---|---|
| `AUDIT_REPORTS/MODULAR_TEMCE/07_DATA_QUALITY_TIMESTAMP_HISTORY.md` | سرفصل‌ها کامل؛ بخش‌های ۲، ۵، ۶، ۷، ۹، ۱۰، ۱۴ خط‌به‌خط در حد ادعاهای قابل‌سنجش؛ بخش‌های تحلیلی (۱، ۳، ۸، ۱۱، ۱۲، ۱۳) بدون تغییر پذیرفته شدند |
| `brsapi/quality.py` | کامل (imports، دکوراتور/امضای توابع، SQL‑ها) |
| `brsapi/services/history_fetch_service.py` | diff کامل + محل `_fetch_history_sync`/`history_daily` |
| `src/gold_desk/freshness.py` | diff کامل |
| `src/gold_desk/nav_checker.py` | diff کامل + شماره‌خط توابع |
| `apps/api/endpoints/market_info.py` | diff کامل |
| `brsapi/models/commodity.py`, `brsapi/models/tsetmc.py`, `brsapi/parsers/tsetmc.py`, `brsapi/services/sync_service.py`, `brsapi/migrations/001_create_brsapi_tables.py` | نقطه‌ای: فقط خطوطی که در گزارش به آن‌ها استناد شده (تطبیق شماره‌خط) |
| `brsapi/jobs/gold_desk_jobs.py`, `services/fund_service.py`, `apps/api/endpoints/funds.py`, `src/gold_desk/phase2.py`, `src/gold_desk/api.py` | نقطه‌ای: تأیید شماره‌خط ادعاها |
| `docs/audits/phase-0/DATA_QUALITY_AUDIT.md` | نقطه‌ای: خطوط ۱۰۳–۱۳۹ (جدول کهنگی و OHLC) |
| پنج فایل تست جدید + `tests/unit/api/test_market_endpoint_contracts.py` | اجرا + شمارش + بازبینی assertion تغییرکرده |
| `tests/unit/repositories/test_sync_log_repository.py`, `frontend/src/__tests__/useMarketData.test.tsx` | اجرای مجدد برای تأیید مستقل ادعای ۱۵/۱۰ |

### ۳.۲ بررسی‌نشده در این ممیزی (و بررسی‌نشده در مرحله)

| فایل/موضوع | دلیل |
|---|---|
| `frontend/src/hooks/useMarketData.ts` (بدنه) | فقط وجود، اندازه و اجرای تست تأیید شد؛ منطق هوک بررسی نشد |
| `brsapi/services/sync_service.py` (کامل، ۱۸۷۲ خط) | فقط بخش‌های تاریخ/NAV/`_to_jalali_date` نقطه‌ای دیده شد |
| `brsapi/models/tsetmc.py` (باقی ۵۴۴ خط) | خارج از دامنه |
| `apps/api/endpoints/funds.py` (۱۸۱۲ خط) | فقط توابع تبدیل/premium |
| `services/fund_nav_engine.py`, `fund_nav_reconciliation.py`, `apps/funds/**` | بررسی نشد؛ موتور NAV «Enterprise» مسیر مستقلی است که در این مرحله ادعایی دربارهٔ آن نشده |
| همهٔ `tests/integration/**` | نیازمند DB؛ اجرا نشد |
| `brsapi/readiness.py`, `brsapi/client.py` | عمداً؛ هیچ درخواست زنده‌ای مجاز نبود |
| `.env*` | عمداً (secret) |
| `algoritm/**`, `reports/runs/**`, `BACKTEST_ALL_CODE.txt`, `gold_complete_bundle.txt` | آرشیو/خروجی تولیدی |

---

## ۴) جدول الزامات پرامپت مرحله

ستون‌ها: الزام · شاهد · نتیجه · کار باقی‌مانده

### ۴.۱ الزامات عمومی مأموریت

| # | الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| R1 | شناسایی ریشه/شاخه/HEAD و ثبت `status`, `diff --stat`, `diff --cached --stat` | گزارش ۰۷ §۲ + بازبینی زندهٔ Git در این ممیزی | **انجام شد** | — |
| R2 | حفظ staged/unstaged/untracked؛ بررسی diff پیش از ویرایش؛ ممنوعیت reset/clean/checkout/stash/commit | `git diff --cached --stat` اکنون **دقیقاً** `138 files, 115998 insertions(+), 1447 deletions(-)` (برابر با ابتدای مرحله)؛ `HEAD` بدون تغییر؛ چهار فایل tracked فقط به‌صورت ` M` (unstaged)؛ هفت فایل جدید `??` | **انجام شد** | — |
| R3 | بدون درخواست زنده به BrsApi/TSETMC؛ بدون دست‌کاری quota/cooldown؛ استفاده از code/log/fixture/تست آفلاین | `brsapi/quality.py` هیچ import شبکه ندارد (`grep -c "requests\|httpx\|aiohttp\|urllib"` = ۰)؛ تست ingestion با patch کردن `fetch_history` اجرا می‌شود؛ هیچ فرمان شبکه‌ای در این مرحله اجرا نشد | **انجام شد** | — |
| R4 | بدون عملیات مخرب DB؛ بدون `TRUNCATE/DELETE`/reset/migration؛ بدون چاپ secret | هیچ اتصال DB برقرار نشد؛ `grep -Ei "DELETE\|TRUNCATE\|DROP\|ALTER"` روی فایل‌های تغییرکرده فقط یک توضیح در docstring است؛ کوئری‌های تشخیصی `SELECT`-only و تست‌شده | **انجام شد** | — |
| R5 | گزارش‌های قدیمی سرنخ باشند؛ تأیید مستقل ادعاهای نشست قبل (۱۵/۱۰، شاخه، فایل هوک) | اجرای مجدد در همین ممیزی: `15 passed in 9.81s` (exit 0) و `Tests 10 passed (10)` (exit 0)؛ شاخه و فایل تأیید شد؛ نبودِ `AUDIT_BATCH_00*_FA.md` و `ROOT_CAUSE_VERIFICATION_FA.md` مستند شد | **انجام شد** | — |
| R6 | خواندن کامل فایل‌ها؛ manifest با سه وضعیت؛ عدم ادعای «کل پروژه» | گزارش ۰۷ §۴ با ۳۸ ردیف و سه نشانه (`کامل/بخشی/بررسی‌نشده`)؛ جملهٔ صریح «ادعای کل پروژه بررسی شد نمی‌شود» | **انجام شد** | — |
| R7 | تغییر کوچک/هدفمند؛ بدون بازنویسی سراسری یا fixer؛ handoff برای خارج از دامنه | diff چهار فایل: ۱۹۲ خط افزوده، ۳۲ خط حذف‌شده در سه فایل + یک تابع جدید در `market_info.py`؛ هیچ فایل بی‌ربطی لمس نشد؛ handoff در §۱۳ گزارش | **انجام شد** | — |
| R8 | نوشتن گزارش در مسیر دقیق؛ عدم overwrite | فایل `07_*` ایجاد شد و پیش‌تر وجود نداشت | **انجام شد** | — |
| R9 | وجود ۱۲ بخش الزامی در گزارش | ۱۴ سرفصل (بخش ۱ تا ۱۴) شامل همهٔ موارد | **انجام شد** | — |
| R10 | انجام واقعی کار و پاسخ کوتاه چت | کد و تست واقعی + گزارش؛ پاسخ چت کوتاه با مسیر و نتیجه | **انجام شد** | — |

### ۴.۲ الزامات اختصاصی این مرحله

| # | الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|---|
| D1 | برای هر جدول مشخص شود کدام فیلد «زمان fetch»، «زمان درج»، «تاریخ معامله/منبع» است؛ میلادی/شمسی؛ محل تولید و conversion با path:line | گزارش ۰۷ §۶ (سه جدول OHLC/NAV + snapshotها)؛ شماره‌خط‌ها در این ممیزی تطبیق و ۶ مورد اصلاح شد (بخش ۹) | **انجام شد** | — |
| D2 | بررسی ادعای کهنگی سه جدول و تازگی fund snapshot **فقط** با دادهٔ محلی/گزارش؛ بدون آمار جدید | گزارش ۰۷ §۵.۳ (S1–S5) + §۶.۳؛ هیچ عدد جدیدی تولید نشد؛ اعداد از `DATA_QUALITY_AUDIT.md:109-115` نقل شده | **انجام شد (محدود به شاهد موجود)** | تأیید عددی روی DB عملیاتی: **BLOCKED** |
| D3 | بررسی `high>=low`، `close` در بازه، قیمت منفی/صفر، gap، تکرار، null؛ مسیر flag/quarantine + metric؛ بدون اصلاح/حذف خودکار | `brsapi/quality.py` (۶ کد ایراد + کوئری‌های تکرار/gap/null)؛ `invalid_count`/`failed_count` در `FetchReport`؛ تست‌ها | **انجام شد** | ستون `quality_flag` در DB و مسیر «نگه‌داشتن با فلگ» پیاده نشد |
| D4 | بررسی اختلاف شمسی/میلادی، timezone، و ذخیرهٔ `gregorian_date`/`shamsi_date` به‌جای trading date | گزارش ۰۷ §۶ + اصلاح `freshness.py`؛ تست `test_no_history_source_is_measured_on_an_ingest_column` | **انجام شد** | تصمیم دربارهٔ حذف/تغییرنام ستون‌های DB عملیاتی |
| D5 | بررسی ادعای ۳۲/۳۲ `nav == price_last` با کد و تست؛ درستی تعریف NAV/قیمت/premium/واحد | ریشهٔ کد در `market_info.py` پیدا و رفع شد؛ تست قرارداد به‌روزرسانی شد؛ تعریف NAV در `nav_checker._resolve_nav` مستند شد؛ واحدها در §۶.۱ | **انجام شد در سطح کد** | بازتولید عددی ۳۲/۳۲ روی DB: **BLOCKED** |
| D6 | fixture + unit test برای همهٔ تغییرات؛ کوئری تشخیصی read-only؛ بدون اصلاح مستقیم dataset | ۵ فایل تست جدید/به‌روز (۷۸ تست در ۵ فایل) + fixture؛ تست `all_queries_are_read_only_selects`؛ هیچ نوشتنی روی داده انجام نشد | **انجام شد** | — |
| D7 | معیار پذیرش: timestampها و معیار کیفیت دقیق؛ ایراد OHLC/NAV قابل‌شناسایی و آزمون‌پذیر؛ هیچ داده واقعی با حدس تغییر نکند | `brsapi/quality.py` + تست‌ها؛ `freshness` با تاریخ معامله؛ `nav` صادق | **برآورده** | — |
| D8 | تأیید پایان: وجود فایل گزارش، اتصال ادعاها به کد/تست، اعلام مسیر و نتیجه واقعی | همین فایل + §۱ + پاسخ چت | **برآورده** | — |

---

## ۵) جدول اصلاحات: فایل، diff، دلیل، تست

| # | فایل | خلاصهٔ diff | دلیل | تست مرتبط |
|---|---|---|---|---|
| C1 | `brsapi/quality.py` (**جدید**، ۱۳٬۴۱۷ بایت) | افزودن `normalize_jalali_date`, `jalali_to_gregorian`, `daily_bar_issues`, `is_valid_daily_bar`, `history_quality_queries` + ثابت‌های `OHLC_HISTORY_TABLES`/`NAV_HISTORY_TABLES` | یک تعریف واحد و تست‌پذیر از «تاریخ معتبر» و «bar معتبر»؛ کوئری‌های تشخیصی read-only | `tests/unit/brsapi/test_history_quality.py` (۴۲ تست) |
| C2 | `brsapi/services/history_fetch_service.py` | +`datetime/UTC`، +import کیفیت، +`invalid_count`/`failed_count` در `FetchReport`، +`_FETCH_TIME_FORMAT`، جایگزینی `contextlib.suppress` با `try/except` شمارشی، نوشتن `fetched_at`، نرمال‌سازی/اعتبارسنجی bar، لاگ متریک | Q-02/Q-03/Q-06: زمان fetch ذخیره نمی‌شد، خطا پنهان می‌شد، bar نامعتبر وارد جدول می‌شد | `tests/unit/brsapi/test_history_fetch_quality.py` (۷ تست) |
| C3 | `src/gold_desk/freshness.py` | +`calendar` در `FreshnessSource`؛ دو منبع تاریخچه از `gregorian_date` به `date` (jalali)؛ +منبع `brsapi_nav_records`؛ `_last_value_sql`/`_last_at`؛ `missing` برای تاریخ غیرقابل‌تبدیل | Q-01/Q-08: تازگی با تاریخ ingestion سنجیده می‌شد و NAV پایش نمی‌شد | `tests/unit/gold_desk/test_freshness_trading_date.py` (۱۲ تست) |
| C4 | `src/gold_desk/nav_checker.py` | +`_date_key(model)=func.replace(date,'/','-')` و استفاده در `_latest_nav`, `_nav_7d_ago`, `_latest_rows_by_symbol`, `_nav_7d_ago_batch` | Q-07: مقایسهٔ رشته‌ای تاریخ شمسی با جداکنندهٔ مختلط | `tests/unit/gold_desk/test_nav_date_normalization.py` (۴ تست) + `tests/gold_desk/test_nav_checker.py` |
| C5 | `apps/api/endpoints/market_info.py` | +`_fund_list_row()` با `nav=None`, `nav_source=None`, `price_last`, `price_close`؛ مرتب‌سازی روی قیمت؛ **حفظ تغییرات قبلی کاربر** (خطای صریح، dedup بر `fetched_at`) | Q-05: `price_last` زیر نام `nav` منتشر می‌شد ⇒ premium ساختاراً صفر (ریشهٔ ادعای ۳۲/۳۲) | `tests/unit/api/test_market_endpoint_contracts.py` (۱۳ تست) |
| T1 | `tests/fixtures/brsapi/history_ohlc_mixed.json` (**جدید**) | ۹ bar: معتبر، اسلش، ارقام فارسی، `high<low`، `close` خارج بازه، `open` خارج بازه، صفر، تاریخ خالی، ماه ۱۳ | fixture برای طبقه‌بندی قطعی | مصرف در دو فایل تست |
| T2 | `tests/unit/api/test_market_endpoint_contracts.py` | assertion قدیمی «`nav == 20`» به «`price_last == 20` + `nav is None` + `nav_source is None` + ترتیب» تغییر کرد | قرارداد غلط را pin می‌کرد | همان فایل |

**بررسی صحت diff:** هر پنج diff در این ممیزی بازخوانی شد؛ هیچ‌کدام فایل بی‌ربط را تغییر نداده و هیچ حذف داده‌ای در آن‌ها نیست. تنها نوشتن DB در C2 همان `INSERT … ON CONFLICT DO UPDATE` قبلی است (فقط ردیف‌های جدید/به‌روزرسانی قیمت همان روز).

---

## ۶) تست‌ها: فرمان، نتیجهٔ واقعی، تعداد موفق/ناموفق/اجرانشده

همه در همین ممیزی از نو اجرا شد.

| # | فرمان | نتیجهٔ خام | موفق | ناموفق | exit |
|---|---|---|---|---|---|
| QA‑T1 | `venv/Scripts/python -m pytest tests/unit/brsapi/test_history_quality.py tests/unit/brsapi/test_history_fetch_quality.py tests/unit/gold_desk/test_freshness_trading_date.py tests/unit/gold_desk/test_nav_date_normalization.py tests/unit/api/test_market_endpoint_contracts.py tests/gold_desk/test_nav_checker.py tests/unit/api/test_golddesk_portfolio_performance.py -q` | `93 passed, 1 warning in 213.87s` | **۹۳** | **۰** | **0** |
| QA‑T2 | `venv/Scripts/python -m pytest tests/unit/repositories/test_sync_log_repository.py -q` | `15 passed in 9.81s` | **۱۵** | **۰** | **0** |
| QA‑T3 | `cd frontend && npx vitest run src/__tests__/useMarketData.test.tsx` | `Test Files 1 passed (1)` / `Tests 10 passed (10)` | **۱۰** | **۰** | **0** |
| QA‑T4 | `ruff check` روی ۵ فایل اصلی تغییرکرده | `quality.py`, `history_fetch_service.py`, `freshness.py`, `market_info.py` → `All checks passed!`؛ `nav_checker.py` → ۱ خطای `I001` | ۴ فایل پاک | ۱ خطای lint | 1 |
| QA‑T5 | `pytest --collect-only -q` روی ۵ فایل تست مرحله | `42 / 7 / 12 / 4 / 13` تست | جمع ۷۸ | ۰ | 0 |
| QA‑T6 | `ruff check --no-cache` روی نسخهٔ `HEAD` فایل `nav_checker.py` | `Found 1 error` (همان I001) | — | — | 1 |

**تحلیل QA‑T4/T6:** خطای lint در `nav_checker.py` **از قبل موجود** است و مستقل از این مرحله. برای جلوگیری از «سبزکردن مصنوعی»، fixer روی مخزن اجرا نشد.

**تست‌های اجرانشده (به‌عنوان موفق گزارش نمی‌شوند):**

| مورد | چرا اجرا نشد | وضعیت |
|---|---|---|
| `tests/integration/**` و هر تست نیازمند PostgreSQL | بدون اتصال/مجوز DB | **BLOCKED** |
| تست واقعی `ON CONFLICT` روی جدول واقعی | نیازمند schema با unique constraint + DB | **BLOCKED** |
| هر تست نیازمند BrsApi | محدودیت دسترسی زنده | **BLOCKED** |
| اجرای کامل `pytest` روی کل مخزن | ۱۰٬۰۰۰+ فایل + ده‌ها تغییر هم‌زمان کاربر؛ قابل تفکیک نبود | اجرا نشد |
| بازرسی چشمی UI | درخواست نشده بود | اجرا نشد |

---

## ۷) وضعیت Git و حفظ تغییرات کاربر

| سنجه | ابتدای مرحله | زمان ممیزی | حکم |
|---|---|---|---|
| `HEAD` | `90597e05b9f4328bcd82ee819a31ba5c55413c12` | همان | بدون commit ✅ |
| staged | `138 files, 115998 insertions(+), 1447 deletions(-)` | **همان اعداد** | دست‌نخورده ✅ |
| unstaged (tracked) | ۱۸ فایل | ۲۶ فایل | ۴ فایل مربوط به این مرحله + ۸ فایل نامرتبط که **فرآیند دیگری** بین `22:59` و `23:02` تغییر داد (`services/news_ingestion.py`, `services/news_dual_write.py`, `domain/instruments/symbol_catalog.py`, `tests/unit/services/test_symbol_catalog.py`, `tests/unit/services/test_news_tag_symbol_mapper.py`, …). این مرحله آن‌ها را نه خوانده و نه تغییر داده. |
| untracked | ۴۴ فایل | ۴۴ فایل | ۷ فایل جدید این مرحله (۶ فایل + fixture) بخشی از همین ۴۴ است؛ هیچ‌کدام stage نشد ✅ |
| فایل‌های تغییرکردهٔ این مرحله | — | ` M` روی `brsapi/services/history_fetch_service.py`, `src/gold_desk/freshness.py`, `src/gold_desk/nav_checker.py`, `apps/api/endpoints/market_info.py` | بدون `git add` ✅ |
| عملیات ممنوعه | — | هیچ `reset --hard`, `clean`, `checkout/restore`, `stash`, `rebase`, `push`, `commit` یا حذف فایل | ✅ |

---

## ۸) موارد BLOCKED (نیازمند دسترسی یا تصمیم بیرونی)

| # | مورد | علت | چه چیزی برای رفع لازم است |
|---|---|---|---|
| B1 | بازتولید عددی «۳۲ از ۳۲ صندوق با `nav == price_last`» | بدون اتصال به DB عملیاتی/محلی مجاز | اجرای کوئری خواندنی روی `funds` + `brsapi_nav_records` توسط مالک داده |
| B2 | تأیید کهنگی واقعی سه جدول و `fund` snapshotها در «الآن» | بدون DB | اجرای `history_quality_queries(...)` روی DB (کوئری‌ها آماده و read-only‌اند) |
| B3 | اعتبارسنجی `ON CONFLICT (symbol, date)` در محیط واقعی | schema مخزن unique constraint ندارد | migration + تصمیم مالک داده (بخش ۱۳ گزارش) |
| B4 | هر تست/بررسی نیازمند BrsApi | محدودیت دسترسی زنده | پس از رفع محدودیت، اجرای ingestion واقعی روی یک نماد |
| B5 | صحت نوع ستون `fetched_at` در DB عملیاتی | inspect نشد | `\d brsapi_gold_coin_history` توسط مالک؛ در صورت timestamp بودن، تغییر نوع نوشتن |

---

## ۹) ایرادهای خودِ گزارش ۰۷ که در این ممیزی پیدا و اصلاح شد

| # | محل | ادعای قبلی | واقعیت | اقدام |
|---|---|---|---|---|
| E1 | §۶.۱ | `history_fetch_service.py:82-101` برای `history_daily` | `_fetch_history_sync` در `:128`، استخراج پاسخ در `:144` | اصلاح به `:128-146` |
| E2 | §۶.۲ | ستون `date` در `tsetmc.py:275` | `date` در `:274` (`:275` = `time`) | اصلاح به `:274` |
| E3 | §۶.۲ | `_resolve_nav` در `nav_checker.py:46-75` | تعریف در `:55-78` | اصلاح شد |
| E4 | §۶.۲/§۷ | نرمال‌سازی NAV در `sync_service.py:651-654` | فراخوانی در `:666` | اصلاح شد |
| E5 | §۵.۲/§۷ | `migrations:661-676` / `nav_checker:107-116,124-133,300-315,340-346` (مخلوط پیش/پس از تغییر) | بلوک migration `:664-677`؛ توابع `:108-120`, `:122-135`, `:291-318`, `:337-347` | اصلاح شد |
| E6 | §۶.۳/§۶.۱/§۵.۳ | `fund_service.py:252`, `funds.py:227-229`, `phase2.py:836-843`/`:809-826`, `api.py:576-584`, `DATA_QUALITY_AUDIT.md:105-112`/`:118-125` | `:253`, `:230`, `:1045`/`:1047` و `:832`, `:576-581`, `:109-115`/`:132-139` | اصلاح شد |

این‌ها خطای استناد بودند، نه تغییر کد؛ متن گزارش ۰۷ پس از اصلاح دوباره ذخیره شد. **درس:** شماره‌خط‌های «نسخهٔ قبل از تغییر» و «نسخهٔ بعد از تغییر» نباید در یک جدول مخلوط شوند.

**ایراد محتوایی که باقی مانده (اصلاح نشد):** گزارش ۰۷ واحد پول ردیف‌های `brsapi_gold_coin_history` را بر پایهٔ «قرارداد مصرف‌کننده» (تومان، `phase2.py:832`) مستند کرده، ولی خودِ جدول ستون `unit` ندارد؛ این یک **قرارداد مستندنشده در schema** است و به تصمیم مالک داده نیاز دارد.

---

## ۱۰) ارزیابی معیارهای پذیرش (خلاصهٔ داوری)

| معیار | داوری ممیز |
|---|---|
| معنای هر timestamp دقیق است | **برآورده** (جدول §۶ گزارش ۰۷ + docstring کد + تست‌ها) |
| ایرادهای OHLC قابل‌شناسایی و آزمون‌پذیرند | **برآورده** (۶ کد ایراد + ۴۲ تست + fixture) |
| NAV/premium تعریف روشن دارد | **برآورده در کد**؛ بازتولید داده‌ای **BLOCKED** |
| هیچ داده واقعی با حدس تغییر نکرد | **برآورده** (هیچ نوشتن/حذف/اصلاح روی داده؛ فقط `SELECT` تشخیصی) |
| مسیر flag/quarantine + metric | **جزئی** — quarantine و metric هست؛ ستون flag در DB نیست |
| کهنگی با معیار درست سنجیده می‌شود | **برآورده** برای سه جدول تاریخچه؛ `gold_fund_nav` **باقی‌مانده** |

---

## ۱۱) نتیجهٔ نهایی

# PARTIAL

**دلیل:** بخش قابل‌توجهی از معیارها با شاهد کد و تست تأیید شد (timestampها، quarantine/metric، freshness مبتنی بر تاریخ معامله، NAV صادق، تست‌های سبز و بدون دادهٔ تغییریافته). اما:

1. دو معیار پذیرش به‌طور کامل قابل تأیید نبودند چون به DB عملیاتی/BrsApi نیاز دارند (**BLOCKED**)،
2. یک الزام صریح (مسیر «flag» برای دادهٔ نامعتبر) فقط با quarantine+metric انجام شد، نه با فلگ در DB،
3. یک بخش از دامنه (تازگی `gold_fund_nav` / snapshotهای صندوق) شناسایی ولی اصلاح نشد،
4. unique constraint لازم برای upsert تاریخچه هنوز ساخته نشده (خارج از اختیار این مرحله).

بنابراین مرحله **کامل** اعلام نمی‌شود.

---

## ۱۲) فهرست دقیق کارهای باقی‌مانده

1. **[BLOCKED → مالک داده]** اجرای کوئری‌های read-only `brsapi.quality.history_quality_queries()` روی DB واقعی برای سه جدول و ثبت آمار واقعی (تعداد `high<low`، `close` خارج بازه، رکورد تکراری، `nav_issue≠nav_redemption`، بازهٔ تاریخ معامله).
2. **[BLOCKED → مالک داده]** تأیید عددی «۳۲/۳۲ صندوق با `nav == price_last`» و اینکه پس از اصلاح، `nav` برای همان صندوق‌ها `NULL` است.
3. **[تصمیم + migration]** ساخت unique index روی `(symbol, replace(date,'/','-'))` برای دو جدول تاریخچه پس از dedup کنترل‌شده، تا `ON CONFLICT` معتبر شود.
4. **[تصمیم]** تعیین تکلیف ستون‌های `gregorian_date`/`shamsi_date` در DB عملیاتی (حذف یا تغییر نام به `ingested_on` + افزودن به مدل).
5. **[کد]** افزودن مسیر «flag» برای دادهٔ نامعتبر (ستون `quality_flag` + migration + نمایش در داشبورد) اگر مالک داده «نگه‌داشتن با فلگ» را به «قرنطینه» ترجیح دهد.
6. **[کد]** اصلاح تازگی `gold_fund_nav` تا سن NAV منبع را نشان دهد، نه زمان اجرای job (Q-09).
7. **[کد]** اعمال همان الگوی «خطای قابل‌مشاهده + نرمال‌سازی تاریخ» روی `sync_crypto_history` (همان `contextlib.suppress`).
8. **[بررسی]** تأیید نوع واقعی ستون `fetched_at` در دو جدول تاریخچه؛ در صورت timestamp بودن، نوشتن مقدار datetime به‌جای رشته.
9. **[مستندسازی]** ثبت قرارداد واحد پول `brsapi_gold_coin_history` (تومان، بدون ستون `unit`) در schema یا مستند داده.
10. **[بررسی]** اجرای مجموعهٔ کامل تست‌های مرتبط پس از پایان تغییرات هم‌زمان کاربر در `services/news_*` و `domain/instruments/symbol_catalog.py` (این مرحله آن فایل‌ها را نخوانده و تغییر نداده است).

---

## ۱۳) دور دوم ممیزی — پس از انجام کارهای باقی‌مانده (`2026-10-28 23:40` … `2026-10-29 00:20`)

### ۱۳.۱ ایراد مهم خود ممیزی که در دور دوم کشف شد (E7)

ممیزی دور اول (و گزارش مرحله) مجموعهٔ migration را از مسیر اشتباهی خوانده بود:

| مورد | مقدار درست |
|---|---|
| مسیر فعال Alembic | `alembic.ini:2` → `script_location = migrations`؛ ۸۵ فایل در `migrations/versions/`؛ head = `0043_gold_holding_soft_delete` |
| مسیر اشتباه که به آن استناد شده بود | `brsapi/migrations/001_create_brsapi_tables.py` (نسخهٔ قدیمی/غیرمرجع) |
| اثر بر یافته‌ها | ادعای «`gregorian_date`/`shamsi_date` در schema نیستند» **غلط** بود؛ افزون بر آن mechanism واقعی پر شدن آن‌ها (migration `0025` + تریگر + `dual_date_columns`) کشف شد |
| ادعایی که همچنان درست است | نبود unique constraint روی `(symbol, date)`؛ مجموعهٔ واقعی (۰۰۰۶، ۰۰۲۵) هم آن را نمی‌سازد |
| ادعایی که تنزل یافت | «`market_info.py` توضیح ساختاری ۳۲/۳۲ است» → فقط یک نمونهٔ کد از همان ضدالگو؛ هیچ مدلی در مخزن `nav` و `price_last` را با هم ندارد ⇒ منشأ عدد نامعلوم |

گزارش ۰۷ در بخش‌های ۵.۲ (Y1)، ۶.۱، ۶.۲، ۷ (Q-04/Q-05)، ۸ و ۱۳.۱ اصلاح شد و بخش ۱۵ به آن افزوده شد.

### ۱۳.۲ کارهایی که در دور دوم انجام شد و اکنون تأیید می‌شوند

| # | کار | شاهد | تست | وضعیت |
|---|---|---|---|---|
| N1 | مسیر کریپتو: حذف پنهان‌سازی خطا + نرمال‌سازی تاریخ + قرنطینه + `fetched_at` | `brsapi/services/history_fetch_service.py` (diff)؛ `import contextlib` حذف شد | ۲ تست جدید (`test_crypto_history_uses_same_quality_and_error_rules`, `test_crypto_insert_failure_is_reported`) | **انجام شد** |
| N2 | معنای تازگی `gold_fund_nav` صریح شد | `src/gold_desk/freshness.py`: فیلد `note` + برچسب «زمان اجرای job» + منبع مستقل `brsapi_nav_records` | ۲ تست جدید | **انجام شد** |
| N3 | قرارداد واحد پول دو جدول تاریخچه در docstring مدل | `brsapi/models/commodity.py` | — (مستند) | **انجام شد** |
| N4 | ابزار pre-flight فقط-خواندنی برای کارهای مسدود | `scripts/history_quality_preflight.py` + ۶ تست | `test_every_executable_statement_is_a_select` و … | **انجام شد** |
| R7 (item 10) | اجرای گسترده‌تر تست‌ها | `tests/unit/brsapi`, `tests/unit/gold_desk`, `tests/gold_desk`, `tests/unit/api` | `9 failed, 823 passed, 6 skipped` — هر ۹ شکست با `RuntimeError: Cannot connect to PostgreSQL database` | **انجام شد با محدودیت محیط** |

### ۱۳.۳ شواهد تست دور دوم (اجرای واقعی، از نو)

| فرمان | نتیجهٔ خام | exit |
|---|---|---|
| `pytest tests/unit/brsapi/test_history_quality_preflight.py tests/unit/gold_desk/test_freshness_trading_date.py -q` | `20 passed in 6.60s` | **0** |
| `pytest tests/unit/brsapi/test_history_fetch_quality.py -q` | `9 passed in 30.47s` | **0** |
| `pytest tests/unit/brsapi tests/unit/gold_desk tests/gold_desk tests/unit/api -q --ignore=tests/unit/brsapi/test_sync_outcomes.py` | `9 failed, 823 passed, 6 skipped in 398.64s` | 1 |
| `ruff check` روی ۶ فایل دور دوم | `All checks passed!` | 0 |
| **اجرای تجمیعی نهایی** روی ۸ فایل تست مرتبط (`test_history_quality`, `test_history_fetch_quality`, `test_history_quality_preflight`, `test_freshness_trading_date`, `test_nav_date_normalization`, `test_market_endpoint_contracts`, `test_nav_checker`, `test_golddesk_portfolio_performance`) | `103 passed, 1 warning in 99.47s` | **0** |
| `pytest tests/unit/brsapi … -q` (بدون ignore) | `ImportError: cannot import name 'BrsApiMalformedResponseError' from 'brsapi.client'` در `tests/unit/brsapi/test_sync_outcomes.py` (فایل untracked دیگری) | 2 |

هیچ‌یک از ۹ شکست در ماژول‌های تغییرکرده نیست؛ علت مشترک نبود PostgreSQL است. خطای collection متعلق به فایل کار-در-جریان دیگری است (تأیید: `hasattr(brsapi.client, 'BrsApiMalformedResponseError')` → `False`).

### ۱۳.۴ وضعیت Git پس از دور دوم

- `HEAD` بدون تغییر: `90597e05b9f4328bcd82ee819a31ba5c55413c12`
- `git diff --cached --stat` بدون تغییر: `138 files changed, 115998 insertions(+), 1447 deletions(-)`
- فایل‌های جدید دور دوم (`scripts/history_quality_preflight.py`, `tests/unit/brsapi/test_history_quality_preflight.py`) و ویرایش‌شده‌ها **unstaged/untracked** باقی ماندند؛ هیچ `git add`/`commit` انجام نشد.

### ۱۳.۵ داوری نهایی دور دوم

**PARTIAL (بدون تغییر)**

کارهای قابل‌انجام در این محیط تمام شد (کریپتو، معنای تازگی صندوق، مستندسازی واحد، ابزار pre-flight، اجرای گستردهٔ تست). آنچه باقی است فقط به **دسترسی به دیتابیس عملیاتی/تصمیم مالک داده** وابسته است:

1. اجرای `scripts/history_quality_preflight.py` روی DB و ثبت آمار واقعی (ابزار آماده، اجرا **BLOCKED**).
2. تأیید عددی ۳۲/۳۲ و شناسایی جدول/ستون مبنا (منشأ نامعلوم + **BLOCKED**).
3. `CREATE UNIQUE INDEX CONCURRENTLY` روی `(symbol, date)` پس از بررسی تکراری‌ها (DDL در خروجی اسکریپت چاپ می‌شود؛ اجرا **BLOCKED/تصمیم**).
4. اصلاح `dual_date_columns.source_column` به `date` + `scripts/backfill_dual_dates.py` (**BLOCKED/تصمیم**).
5. ستون `quality_flag` و مسیر «نگه‌داشتن با فلگ» (فعلاً قرنطینهٔ بدون نوشت).
6. افزودن `nav_as_of` به `gold_fund_nav` (تصمیم محصول).
7. رفع دو ایراد محیطی مستقل: نبود PostgreSQL در محیط تست، و `ImportError` در `tests/unit/brsapi/test_sync_outcomes.py` (کار دیگری).
