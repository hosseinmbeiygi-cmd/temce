# گزارش مستقل ۷ — کیفیت داده، زمان‌ها، تاریخچه‌ها و NAV

> این فایل مرجع کامل این مرحله است. پاسخ چت فقط خلاصه است.

---

## ۱) تاریخ و زمان اجرا

| مورد | مقدار |
|---|---|
| زمان شروع بررسی | `2026-10-28 22:44` (ساعت محلی ماشین، `IST` طبق `date` سیستم) |
| زمان آخرین تأیید وضعیت Git | `2026-10-28 23:08:13 IST` |
| ابزار اجرا | bash روی Windows (Git Bash)، `venv/Scripts/python` (pytest 9.1.1)، Node/vitest 4.1.9 برای فرانت |

---

## ۲) ریشه، شاخه، commit و وضعیت اولیهٔ Git

| مورد | مقدار |
|---|---|
| ریشهٔ مخزن (`git rev-parse --show-toplevel`) | `C:/Users/Iran/Desktop/temce` |
| `branch` | `integration/golddesk-fixes` (تأیید شد که وجود دارد) |
| `HEAD` | `90597e05b9f4328bcd82ee819a31ba5c55413c12` |
| `git status --short --branch` (ابتدای کار) | `## integration/golddesk-fixes` + ده‌ها ردیف `A ` (staged)، `M ` (index)، `MM`، ` M` (working tree) و ` m InkGist` (submodule) |
| `git diff --stat` (ابتدای کار) | ۱۸ فایل، `725 insertions(+), 375 deletions(-)` |
| `git diff --cached --stat` (ابتدای کار) | ۱۳۸ فایل، `115998 insertions(+), 1447 deletions(-)` |

**هیچ عملیات مخربی انجام نشد:** نه `git reset --hard`، نه `git clean`، نه `checkout/restore` برای دور ریختن تغییرات، نه `stash`، نه `commit`، نه `push/rebase`، نه حذف فایل. تغییرات staged کاربر دست‌نخورده ماند.

### نکتهٔ مهم: working tree در طول این نشست توسط فرآیندی دیگر تغییر کرد

در پایان کار `git diff --stat` شده است **۲۶ فایل / ۱۰۹۲ insertion**، در حالی که در ابتدا ۱۸ فایل بود. فایل‌های اضافه‌شده با `mtime` بین `22:59` و `23:02` تغییر کرده‌اند و **هیچ‌کدام توسط این مأموریت لمس نشده‌اند**:

- `services/news_ingestion.py` (22:59)
- `domain/instruments/symbol_catalog.py` و `tests/unit/services/test_symbol_catalog.py` (23:00)
- `services/news_dual_write.py` و `tests/unit/services/test_news_tag_symbol_mapper.py` (23:02)

همچنین `frontend/src/hooks/useMarketData.ts` و `frontend/src/__tests__/useMarketData.test.tsx` در همین بازه اندازهٔ diff متفاوتی نسبت به ابتدای نشست دارند. این تغییرات از این مأموریت نیست و طبق قاعدهٔ «حفظ تغییرات کاربر» دست‌نخورده باقی ماند. تنها فایل‌هایی که این مأموریت تغییر داده در بخش ۸ فهرست شده‌اند.

---

## ۳) هدف و مرز دامنه

**هدف:** جداکردن «کیفیت و تازگی داده» از «اشکال fetch/storage»، با تمرکز روی:

1. معنای دقیق هر timestamp (زمان fetch، زمان درج، تاریخ معامله/منبع، میلادی/شمسی) در جدول‌های تاریخچهٔ طلا/سکه/ارز، NAV و snapshot صندوق.
2. بررسی ادعاهای کهنگی (`brsapi_gold_currency_pro_daily_history`, `brsapi_gold_coin_history`, `brsapi_nav_records`) و تازگی fund snapshotها — **فقط** بر پایهٔ دادهٔ محلی/گزارش موجود.
3. قواعد اعتبار تاریخی OHLC (`high >= low`، `close` در بازه، قیمت منفی/صفر، gap، تکرار، null) و مسیر flag/quarantine + metric.
4. اختلاف تاریخ شمسی/میلادی، timezone، و ذخیرهٔ `gregorian_date`/`shamsi_date` به‌جای trading date.
5. ادعای «۳۲/۳۲ صندوق با `nav == price_last`» و درستی تعریف NAV/قیمت آخر/premium-discount/واحدها.

**خارج از دامنه (عمداً انجام نشد):** درخواست زنده به BrsApi/TSETMC، هر نوشتن/حذف/`TRUNCATE`/migration روی دیتابیس، پاک‌کردن cooldown یا شمارندهٔ سهمیه، بازنویسی یا dedup دادهٔ موجود، تغییر قرارداد فرانت، بازآرایی (refactor) ماژول‌های خارج از این بخش.

**محدودیت دسترسی:** هیچ اتصال زنده به DB عملیاتی و هیچ درخواست به BrsApi استفاده نشد. همهٔ ادعاهای داده‌ای به `docs/audits/phase-0/DATA_QUALITY_AUDIT.md`، `docs/audits/phase-0/ISSUE_REGISTRY.md`، لاگ‌های موجود در `audit_out/_logs/` و README ارجاع داده شده‌اند و به‌عنوان «شاهد موجود» نقل شده‌اند، نه آمار جدید. آمار جدیدی تولید نشد.

---

## ۴) Manifest فایل‌های خوانده‌شده

علامت‌ها: ✅ کامل خوانده شد · ◐ بخشی خوانده شد · ⛔ بررسی نشد.

| # | فایل | وضعیت | توضیح |
|---|---|---|---|
| 1 | `brsapi/models/commodity.py` | ✅ | همهٔ مدل‌های طلا/ارز/کالا |
| 2 | `brsapi/models/tsetmc.py` | ◐ | فقط `NavRecordModel` و محدودهٔ مدل‌ها (خط ۲۴۰–۳۶۰)؛ بقیهٔ ۵۴۴ خط مدل‌های دیگر |
| 3 | `brsapi/models/base.py` | ✅ | `InstrumentRefMixin`, `RawPayloadModel` (market_time/receive_time), `SyncLogModel` |
| 4 | `brsapi/services/history_fetch_service.py` | ✅ | مسیر واقعی ingestion تاریخچهٔ طلا/سکه/ارز |
| 5 | `brsapi/services/sync_service.py` | ◐ | خط ۶۰–۱۵۰ (تبدیل تاریخ) و ۶۰۰–۷۲۰ (`sync_nav`) |
| 6 | `brsapi/parsers/tsetmc.py` | ◐ | خط ۲۴۰–۲۹۰ (`parse_nav`) و ۴۵۰–۵۶۴ (`parse_candlesticks`, `_jalali_to_gregorian`) |
| 7 | `brsapi/migrations/001_create_brsapi_tables.py` | ◐ | خط ۲۱۰–۲۷۰ (`brsapi_nav_records`)، ۶۵۵–۶۹۴ (`brsapi_gold_coin_history`)، ۸۲۰–۸۵۵ (downgrade) |
| 8 | `brsapi/quality.py` | ✅ | فایل جدید این مأموریت |
| 9 | `src/gold_desk/nav_checker.py` | ✅ | NAV، P/NAV، BPR، تازگی real/legal |
| 10 | `src/gold_desk/freshness.py` | ✅ | داشبورد سلامت داده |
| 11 | `src/gold_desk/dates.py` | ✅ | `jalali_days_ago` |
| 12 | `src/gold_desk/portfolio_history.py` | ◐ | خط ۳۰–۸۹ (کامنت و SQL بنچمارک) |
| 13 | `src/gold_desk/phase2.py` | ◐ | خط ۷۴۰–۹۴۰ (`_history_window`, `_series_from_rows`, لودرهای طلا/ارز/شاخص) |
| 14 | `src/gold_desk/models.py` | ◐ | خط ۶۴–۱۰۰ (`GoldFundNAVModel`) |
| 15 | `brsapi/jobs/gold_desk_jobs.py` | ◐ | خط ۲۰۵–۲۶۴ (`_persist_fund_nav`) |
| 16 | `apps/api/endpoints/market_info.py` | ✅ | کل فایل (endpoint `/market-info/funds`) |
| 17 | `apps/api/endpoints/funds.py` | ◐ | خط ۱۹۵–۲۷۴ (`_ime_fund_to_dict`, `_snapshot_to_dict`) و ۱۷۰۰–۱۷۴۹ (محاسبهٔ premium) |
| 18 | `apps/api/endpoints/brsapi.py` | ◐ | خط ۲۷۹۰–۲۸۸۹ (`/nav-sync-status`) |
| 19 | `services/fund_service.py` | ◐ | خط ۱۵۰–۲۷۹ (`update_from_brsapi`: fallback قیمت به NAV + `nav_basis`) |
| 20 | `services/gold/calculator.py` | ◐ | خط ۲۰–۹۴ (`calculate_nav_premium`) |
| 21 | `services/gold/feature_source.py` | ◐ | خط ۶۵۰–۶۹۴ (شاخهٔ P/NAV و حذف ردیف‌های placeholder) |
| 22 | `services/fund_scoring.py` | ◐ | فقط `_calc_bubble` (خط ۴۵۲–۴۵۵) با grep |
| 23 | `ingestion/validation.py` | ◐ | ۶۰ خط اول (الگوی report/flag) |
| 24 | `ingestion/raw_validation.py` | ◐ | ۵۰ خط اول (الگوی گزارش رد ردیف) |
| 25 | `ingestion/fx/quality_gate.py` | ✅ | الگوی quality gate موجود در پروژه |
| 26 | `tests/unit/ingestion/test_fx_quality_gate.py` | ✅ | سبک تست quality gate |
| 27 | `tests/unit/api/test_market_endpoint_contracts.py` | ✅ | ۱۳۰ خط اول (شامل تستی که قرارداد قدیمی NAV را pin کرده بود) |
| 28 | `tests/unit/api/test_golddesk_portfolio_performance.py` | ◐ | خط ۱۰۰–۱۲۰ (قرارداد `/gold/freshness`) |
| 29 | `docs/audits/phase-0/DATA_QUALITY_AUDIT.md` | ◐ | خط ۹۰–۱۴۶ (پروفایل داده و ISSUE-127/128) |
| 30 | `docs/audits/phase-0/ISSUE_REGISTRY.md` | ◐ | خط ۲۸۵–۳۶۴ (ISSUE-126…129 و ماتریس اولویت) |
| 31 | `docs/audits/phase-0/MASTER_READINESS_REPORT.md` | ◐ | فقط از طریق جست‌وجو (خط ۲۰ و ۹۱: ادعای ۳۲/۳۲) |
| 32 | `tests/unit/repositories/test_sync_log_repository.py` | ◐ | فقط شمارش تست‌ها و اجرای آن (بدنه خوانده نشد) |
| 33 | `frontend/src/hooks/useMarketData.ts` | ⛔ | بدنه خوانده نشد؛ فقط وجود فایل (۲۹٬۳۹۳ بایت، mtime 22:43) و اجرای تست آن تأیید شد |
| 34 | `frontend/src/__tests__/useMarketData.test.tsx` | ⛔ | بدنه خوانده نشد؛ فقط اجرای تست (۱۰ تست) |
| 35 | `docs/DATABASE_README.md`، `docs/phase2-market-coverage.md`، `docs/analysis/01_engine.md`، `README.md` | ◐ | فقط خطوط مرتبط از طریق جست‌وجو (نوع ستون‌ها، واحد ریال/تومان، ادعای کهنگی) |
| 36 | `audit_out/**`، `reports/runs/**`، `BACKTEST_ALL_CODE.txt` | ⛔ | خروجی تولیدی/آرشیوی؛ فقط چند خط به‌عنوان سرنخ از طریق جست‌وجو دیده شد، محتوای آن‌ها به‌عنوان حقیقت استفاده نشد |
| 37 | `.env`, `.env.production`, `.env.bak.*` | ⛔ | عمداً باز نشد (secret). فقط وجود متغیرها لازم نشد. |
| 38 | `algoritm/all_in_one/**`, `dsh-our-free-model/**`, `gold_complete_bundle.txt` | ⛔ | بسته‌های آرشیوی/کپی دیگر پروژه‌ها؛ خارج از دامنه |

**ادعای «کل پروژه بررسی شد» نمی‌شود.** فقط فایل‌های جدول بالا دیده شدند.

---

## ۵) یافته‌های تأییدشده در برابر فرضیه‌ها

### ۵.۱ تأیید مستقل ادعاهای نشست قبلی (بدون فرض)

| ادعا | نتیجهٔ بررسی مستقل | شاهد |
|---|---|---|
| شاخهٔ `integration/golddesk-fixes` وجود دارد | **تأیید** | `git branch --show-current` = `integration/golddesk-fixes` |
| `tests/unit/repositories/test_sync_log_repository.py` ۱۵ تست دارد | **تأیید** | `grep -c "def test_"` = ۱۵ و اجرا: `15 passed in 5.08s` (`exit 0`) |
| `frontend/src/hooks/useMarketData.ts` وجود دارد | **تأیید** | فایل ۲۹٬۳۹۳ بایت، mtime `22:43` |
| تست‌های فرانت ۱۰ عددند | **تأیید** | `npx vitest run src/__tests__/useMarketData.test.tsx` → `Tests 10 passed (10)` (`exit 0`) |
| فایل‌های `AUDIT_BATCH_001_FA.md` … `AUDIT_BATCH_009_FA.md` و `ROOT_CAUSE_VERIFICATION_FA.md` | **در دسترس نیستند** | `ls AUDIT_BATCH_00*_FA.md ROOT_CAUSE_VERIFICATION_FA.md` → `No such file or directory`؛ `find . -maxdepth 3 -name "AUDIT_BATCH_*" -o -name "ROOT_CAUSE_VERIFICATION*"` → خروجی خالی. **غیبتشان ثبت می‌شود؛ برای پیدا کردنشان حدس زده نشد.** |

### ۵.۲ یافته‌های تأییدشده (کد + تست)

| # | یافته | شاهد کد | روش تأیید |
|---|---|---|---|
| Y1 | ستون‌های `gregorian_date`/`shamsi_date` در مدل ORM این جدول‌ها نیستند و مقدارشان **تاریخ درج/دریافت** است، نه تاریخ معامله | `brsapi/models/commodity.py:50-63` و `:216-241` (بدون این ستون‌ها)؛ منبع واقعی schema: `migrations/versions/0025_add_dual_date_columns.py` که به **همهٔ** جدول‌ها این دو ستون + تریگر `trg_dual_dates` را اضافه می‌کند و ستون منبع را با `_PRIORITY` (خط ۵۲–۸۰) انتخاب می‌کند — در آن لیست `fetched_at`/`created_at`/`updated_at` **قبل از** `date` هستند، پس برای این جدول‌ها تاریخ ingestion انتخاب شده است (بخش ۸) | خواندن `0025_add_dual_date_columns.py:105-160` (`_pick_source`) و `scripts/install_dual_dates.py:186-236` (متن تریگر) |
| Y2 | داشبورد تازگی، تازگی تاریخچه را با `gregorian_date` می‌سنجید | `src/gold_desk/freshness.py` (نسخهٔ پیش از اصلاح، منابع `brsapi_gold_coin_history`/`brsapi_gold_currency_pro_daily_history` با `column="gregorian_date"`) | تست جدید `test_history_sources_are_jalali_and_use_the_trade_date_column` روی نسخهٔ اصلاح‌شده سبز است و تست `test_stale_history_is_stale_even_when_ingested_now` نشان می‌دهد تاریخ معاملهٔ `1405-06-23` = `2026-09-14` → `stale` می‌شود |
| Y3 | `fetched_at` در مسیر ingestion تاریخچهٔ طلا/ارز هرگز پر نمی‌شد | `brsapi/services/history_fetch_service.py:283-295` (نسخهٔ پیش از اصلاح: ستون‌های INSERT فقط `symbol, date, price_open/…/close` بودند) | تست `test_fetched_at_is_written_and_differs_in_kind_from_date` |
| Y4 | خطای درج در ingestion تاریخچه بی‌صدا خورده می‌شد (`contextlib.suppress(Exception)`) و گزارش «موفق با صفر ردیف» می‌داد | `brsapi/services/history_fetch_service.py` نسخهٔ پیش از اصلاح، بلوک `with contextlib.suppress(Exception):` داخل `sync_gold_currency_history` | تست `test_insert_failure_is_reported_not_hidden` → `success=False`, `failed_count=1`, `error` حاوی نام خطا |
| Y5 | `ON CONFLICT (symbol, date)` در این مسیر، در schema مخزنunique constraint ندارد | `brsapi/services/history_fetch_service.py:325-333` (ON CONFLICT)؛ `brsapi/migrations/001_create_brsapi_tables.py:678` و `:694` فقط `op.create_index(...)` غیریکتا می‌سازند؛ grep `UniqueConstraint` در کل migration فقط یک مورد (خط ۳۹۴، برای `brsapi_candlesticks`) | بازبینی migration؛ **این مورد اصلاح نشد** (نیازمند migration + پاک‌سازی داده) و در بخش ۱۱ به‌عنوان handoff ثبت شده |
| Y6 | جدول NAV هیچ `fetched_at`/`created_at` شیفت‌شده ندارد؛ `fetched_at` رشتهٔ UTC از پارسر و `date` تاریخ شمسی منبع است | `brsapi/parsers/tsetmc.py:257-266` (ساخت `now` و `date`)، `brsapi/models/tsetmc.py:271-280` | خواندن کد + `brsapi/services/sync_service.py:645-656` (نرمال‌سازی `date` با `_normalize_codal_date`) |
| Y7 | `nav` صندوق در endpoint «market-info» از `price_last` ساخته می‌شد (بدون هیچ ستون NAV) | `apps/api/endpoints/market_info.py` نسخهٔ پیش از اصلاح، ساخت `items` (خط ۶۰ در diff اولیه) | تست به‌روزشدهٔ `test_market_info_funds_keep_latest_fetched_at_not_last_row` + تست جدید در همان فایل |
| Y8 | `brsapi_nav_records` هیچ منبعی در داشبورد تازگی نداشت | `src/gold_desk/freshness.py` نسخهٔ پیش از اصلاح (`FRESHNESS_SOURCES` فاقد این جدول) | تست `test_nav_records_are_monitored` |
| Y9 | مقایسه/مرتب‌سازی تاریخ شمسی در `nav_checker` رشته‌ای و خام بود؛ `'/'` (0x2F) > `'-'` (0x2D) ⇒ `MAX(date)` می‌تواند ردیف قدیمی‌تر را «آخرین» ببیند و `date <= cutoff` ردیف‌های اسلش‌دار را حذف کند | `src/gold_desk/nav_checker.py` نسخهٔ پیش از اصلاح: `order_by(desc(NavRecordModel.date))` و `NavRecordModel.date <= cutoff` در `_latest_nav`/`_nav_7d_ago`/`_latest_rows_by_symbol`/`_nav_7d_ago_batch` | تست `tests/unit/gold_desk/test_nav_date_normalization.py` (کوئری‌های تولیدشده باید `replace(...)` داشته باشند) |

### ۵.۳ فرضیه‌هایی که تأیید یا رد نشدند (به‌عنوان باگ قطعی گزارش نمی‌شوند)

| # | فرضیه | وضعیت |
|---|---|---|
| S1 | در دیتابیس عملیاتی، `brsapi_gold_coin_history`/`brsapi_gold_currency_pro_daily_history` ستون‌های `gregorian_date`/`shamsi_date` دارند و مقدارشان تاریخ ingestion است | **از گزارش قبلی نقل شده** (`docs/audits/phase-0/DATA_QUALITY_AUDIT.md:109-115` و `audit_out/_logs/gold_silver_funds_db6.out:3` برای NAV). در این مأموریت دسترسی زنده به DB نبود ⇒ «تأییدنشده در این نشست»؛ ولی کد در هر دو حالت اصلاح شده: چه ستون باشد چه نباشد، تازگی از `date` خوانده می‌شود. |
| S2 | `brsapi_gold_coin_history` واقعاً unique constraint دارد (برخلاف migration) | **تأیید نشد**؛ در schema مخزن وجود ندارد. |
| S3 | ردیف‌های `brsapi_nav_records` با دو جداکننده ذخیره شده‌اند | **تأیید نشد**؛ اصلاح `replace()` در هر دو حالت بی‌خطر است (no-op برای دادهٔ یکدست). |
| S4 | نرخ واقعی خطای OHLC در دادهٔ فعلی (`high<low` = ۷۴ و …) | **بازتولید نشد**؛ فقط از `DATA_QUALITY_AUDIT.md:132-139` نقل شده است. این مأموریت هیچ آماری تولید نکرد. |
| S5 | قدیمی‌ترین/جدیدترین تاریخ واقعی هر جدول در DB | **بررسی نشد** (نیازمند اتصال DB). |

---

## ۶) معنای هر timestamp به‌ازای هر جدول (کار اصلی بند ۱ دستور)

### ۶.۱ جدول‌های OHLC تاریخچه

| جدول | فیلد | معنا | محل تولید | تقویم/واحد |
|---|---|---|---|---|
| `brsapi_gold_currency_pro_daily_history` | `date` | **تاریخ معامله/منبع** (نه زمان درج؛ `gregorian_date`/`shamsi_date` توسط تریگر ۰۰۲۵ از ستون ingestion پر می‌شوند — بخش ۸) | از `history_daily[].date` در `brsapi/services/history_fetch_service.py:128-146` (استخراج پاسخ در `:144`)؛ نرمال‌سازی و اعتبارسنجی در `:305-313` با `brsapi.quality.normalize_jalali_date` | **شمسی** `YYYY-MM-DD` (`String(20)`, `brsapi/models/commodity.py:225`) |
| | `price_open/high/low/close` | قیمت روز معامله | `history_fetch_service.py:314-317` از فیلدهای `open/high/low/close` پاسخ | **ریال** از پیش تبدیل‌شده برای ارز؛ **دلار** فقط برای XAU/USD (`src/gold_desk/phase2.py:1045` با `unit="rial"` و `:1047` با `unit="usd"`؛ `column unit` پیش‌فرض `IRR` در `commodity.py:220`) |
| | `fetched_at` | **زمان دریافت پاسخ HTTP** (ساعت کلاینت) | **قبلاً هرگز نوشته نمی‌شد**؛ اکنون `history_fetch_service.py:300` و در INSERT `:322-336`. در `ON CONFLICT DO UPDATE` عمداً **بازنویسی نمی‌شود** ⇒ «نخستین زمان دریافت این ردیف» | میلادی، رشتهٔ `YYYY-MM-DD HH:MM:SS` (`String(30)`, `commodity.py:230`)، UTC |
| | `created_at` | **زمان درج در DB** (ساعت سرور) | `server_default=func.now()` — `commodity.py:232` | timestamp بدون timezone |
| | `gregorian_date`/`shamsi_date` | در مدل ORM نیستند، ولی بخشی از **schema واقعی** (migration `0025` روی همهٔ جدول‌ها)؛ تریگر `sync_dual_dates_fn` آن‌ها را از ستون منبع `dual_date_columns.source_column` پر می‌کند و برای این جدول‌ها `fetched_at`/`created_at` (زمان ingestion) انتخاب شده ⇒ **تاریخ معامله نیست** | `migrations/versions/0025_add_dual_date_columns.py:105-160` + `scripts/install_dual_dates.py:186-236` | — |
| `brsapi_gold_coin_history` | `date` | **تاریخ معامله/منبع** | همان مسیر؛ `history_fetch_service.py:277` انتخاب جدول، `:305` نرمال‌سازی | **شمسی**، `nullable=False` (`commodity.py:54`) |
| | `price_*` | قیمت روز | همان | **تومان** (بدون ستون `unit`) و مصرف‌کننده آن را با `phase1._toman_to_rial` تبدیل می‌کند (`phase2.py:832` با `unit="toman"`) |
| | `fetched_at` / `created_at` | همان معناها | همان | همان |

**نتیجه‌گیری:** «زمان fetch» و «زمان درج» و «تاریخ معامله» سه چیز متفاوت‌اند. تنها معیار درست برای «چقدر داده تاریخچه تازه است» ستون `date` است (پس از تبدیل شمسی→میلادی). `gregorian_date`/`shamsi_date` این جدول‌ها به‌هیچ‌وجه معیار تازگی نیستند.

### ۶.۲ `brsapi_nav_records`

| فیلد | معنا | محل تولید | تقویم |
|---|---|---|---|
| `date` | **تاریخ انتشار/معامله NAV از منبع** | `TsetmcParser.parse_nav` → `data["date"]` (`brsapi/parsers/tsetmc.py:264`) و نرمال‌سازی با `_normalize_codal_date` در `sync_service.py:666` (تعریف در `:118-130`: ارقام فارسی/عربی → ASCII، `/` → `-`) | **شمسی** `String(20)` (`tsetmc.py:274`) |
| `time` | ساعت انتشار در پاسخ منبع | `tsetmc.py:265` | رشتهٔ منبع |
| `fetched_at` | **زمان دریافت پاسخ** | `datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")` — `tsetmc.py:259` | میلادی، UTC، `String(30)` |
| `created_at` | زمان درج در DB | `server_default=func.now()` — `tsetmc.py:278` | timestamp |
| `nav_issue` / `nav_redemption` | NAV صدور / NAV ابطال (نه یک ستون `nav`) | `psubtran` / `predtran` — `tsetmc.py:262-263` | ریال per unit |
| `gregorian_date`/`shamsi_date` | خارج از مدل، ولی بخشی از schema واقعی (migration `0025`)؛ مقدارشان از تریگر و بر اساس `dual_date_columns` می‌آید — برای این جدول `fetched_at` (زمان دریافت) انتخاب شده، نه `date` | `migrations/versions/0025_add_dual_date_columns.py:105-160`؛ تأیید مشاهده‌ای در لاگ `audit_out/_logs/gold_silver_funds_db6.out:3` | — |

**تعریف NAV در این کد بی‌ابهام است:** `_resolve_nav` (`src/gold_desk/nav_checker.py:55-78`) فقط `nav_issue` را مرجع می‌گیرد، `nav_redemption` را فقط برای هشدار اختلاف ≥۱٪ استفاده می‌کند و در نبود `nav_issue` به `nav_redemption` برمی‌گردد؛ انتخاب «اولین مقدار truthy» حذف شده است.

### ۶.۳ snapshotهای صندوق

| جدول | فیلد زمان | معنا |
|---|---|---|
| `funds` (`apps/funds/models.py:40-62`) | `created_at`, `updated_at` | زمان ایجاد/به‌روزرسانی ردیف؛ **هیچ فیلد تاریخ بازار ندارد**. `extra` یک JSON رشته‌ای است و `snapshot_date` در آن با `now_tehran().strftime("%Y-%m-%d")` نوشته می‌شود (`services/fund_service.py:253`) — یعنی **تاریخ میلادی زمان اجرا**، نه تاریخ معامله. |
| `gold_fund_nav` (`src/gold_desk/models.py:64-84`) | `date` | روزی که snapshot گرفته شده: `datetime(when.year, when.month, when.day)` از `snap.snapshot_at` (`brsapi/jobs/gold_desk_jobs.py:214-215`) |
| | `snapshot_at` | زمان درج snapshot (`server_default=func.now()`) |
| `fund_market_quotes_cache` | `quoted_at` | زمان نقل‌قول قیمت (`services/fund_read_through.py:626-645`) |
| `fund_metrics` (`apps/funds/models.py:82+`) | `ts` | زمان مشاهدهٔ متریک |

**نکتهٔ کیفیت:** NAV ذخیره‌شده در `gold_fund_nav.nav_per_unit` از `nav_checker` می‌آید که «آخرین رکورد NAV ≤ اکنون» را می‌خواند (`nav_checker.py:108-120`)؛ پس `snapshot_at` امروز به‌معنای «NAV امروز» نیست. به همین دلیل منبع مستقل `brsapi_nav_records` به داشبورد تازگی اضافه شد تا سن خودِ NAV دیده شود.

---

## ۷) جدول ایرادها

| ID | شدت | شاهد `path:line` | روش بازتولید (این نشست) | اثر |
|---|---|---|---|---|
| Q-01 | **بالا** | `src/gold_desk/freshness.py` (نسخهٔ قبل): منابع تاریخچه با `column="gregorian_date"`؛ Y1/Y2 | تست جدید `test_stale_history_is_stale_even_when_ingested_now` + `test_no_history_source_is_measured_on_an_ingest_column` | تاریخچهٔ کهنه «تازه» گزارش می‌شد؛ `/gold/freshness` و health check (`src/gold_desk/api.py:576-581`) سبز می‌شدند در حالی که داده ۴۲ روز عقب بود |
| Q-02 | **بالا** | `brsapi/services/history_fetch_service.py:300-337` (نسخهٔ قبل: بدون `fetched_at`) | تست `test_fetched_at_is_written_and_differs_in_kind_from_date` | «زمان fetch» برای دو جدول تاریخچه برای همیشه NULL بود و از `created_at` قابل تفکیک نبود |
| Q-03 | **بالا** | `brsapi/services/history_fetch_service.py` بلوک `contextlib.suppress(Exception)` (نسخهٔ قبل) | تست `test_insert_failure_is_reported_not_hidden` | خطای ذخیره‌سازی به «موفق، صفر ردیف» تبدیل می‌شد؛ ناسازگاری schema/quota بی‌صدا می‌ماند |
| Q-04 | **بالا** | `brsapi/services/history_fetch_service.py` (INSERT … `ON CONFLICT (symbol, date)`) + `migrations/versions/0006_add_missing_updated_at.py` و `0025_add_dual_date_columns.py` تنها migrationهای مرتبط با این دو جدول‌اند و هیچ‌کدام unique constraint نمی‌سازند (grep `uq_`/`unique` روی `migrations/versions/`) | بازبینی مجموعهٔ واقعی migrationها (۸۵ فایل، head = `0043_gold_holding_soft_delete`) | در schema مخزن این upsert معتبر نیست؛ در DB عملیاتی «اثر آن» با نبود dedup در گزارش قبلی (۱۶۰٬۲۹۳ ردیف با `/` و ۱۶۰٬۲۹۳ با `-`) هم‌خوان است. **اصلاح نشد؛ handoff** |
| Q-05 | **بالا** | `apps/api/endpoints/market_info.py:60` (نسخهٔ قبل) — اکنون `:16-38` | تست `test_market_info_funds_keep_latest_fetched_at_not_last_row` | `nav` = `price_last` منتشر می‌شد ⇒ هر مصرف‌کنندهٔ `price/nav-1` صفر می‌گرفت. **نکتهٔ صحت:** این یک نمونهٔ کد از همان الگوی ضدالگو است؛ **منشأ دقیق عدد ۳۲/۳۲ ثابت نشد** (جدول `funds` مورد استناد، ستون `nav`+`price_last` را در هیچ‌یک از مدل‌های مخزن ندارد) — بخش ۱۵.۲ |
| Q-06 | **بالا** | `brsapi/services/history_fetch_service.py` (نسخهٔ قبل): `str(r.get("date","")).replace("/","-")` | بازبینی + تست fixture (ارقام فارسی/اسلش) | ورودی بدون تاریخ به تاریخ خالی/نامعتبر تبدیل می‌شد و قواعد OHLC بررسی نمی‌شد؛ ردیف‌های `high<low`/`close` خارج بازه وارد جدول می‌شدند |
| Q-07 | **متوسط** | `src/gold_desk/nav_checker.py:108-120` (`_latest_nav`)، `:122-135` (`_nav_7d_ago`)، `:291-318` (`_latest_rows_by_symbol`)، `:337-347` (`_nav_7d_ago_batch`) | تست `tests/unit/gold_desk/test_nav_date_normalization.py` | سری زمانی NAV: انتخاب «آخرین NAV» و مبنای «NAV ۷ روز پیش» می‌توانست ردیف قدیمی‌تر اسلش‌دار را بگیرد یا ردیف‌های همان بازه را حذف کند |
| Q-08 | **متوسط** | `src/gold_desk/freshness.py` (نسخهٔ قبل): `FRESHNESS_SOURCES` فاقد `brsapi_nav_records` | تست `test_nav_records_are_monitored` | کهنگی NAV صندوق‌ها در داشبورد سلامت دیده نمی‌شد |
| Q-09 | **متوسط** | `src/gold_desk/freshness.py` (نسخهٔ قبل) — `gold_fund_nav` با `snapshot_at` | بازبینی `brsapi/jobs/gold_desk_jobs.py:205-245` + `nav_checker.py:108-120` | تازگی «NAV صندوق» در واقع تازگی اجرای job بود، نه سن NAV منبع. **اصلاح نشد** (پایین‌ریسک ولی نیازمند تصمیم محصول) |
| Q-10 | **پایین** | `brsapi/models/commodity.py:59` و `:230` vs `brsapi/migrations/001_create_brsapi_tables.py:672` | مقایسهٔ مدل با migration | مدل و migration هم‌خوان‌اند (`String(30)`)، اما DB عملیاتی طبق `README.md:1500` هم varchar است؛ اگر جایی ستون timestamp شده باشد، درج جدید (که اکنون `fetched_at` می‌فرستد) با `DataError` شکست می‌خورد — که این بار **گزارش می‌شود** نه پنهان |

**جمع: ۱۰ ایراد ثبت‌شده (Q-01 … Q-10).**

**ایرادهای خارج از دامنه که فقط ثبت می‌شوند (بدون تغییر):**

- `brsapi/services/history_fetch_service.py:223` — همان `contextlib.suppress(Exception)` در مسیر **کریپتو** (`sync_crypto_history`) باقی ماند؛ خارج از دامنهٔ این مأموریت، عیناً همان الگوی Q-03.
- `apps/api/endpoints/funds.py:211` و `:262` و `:1729` — `nav` از `price_close`/`price_last` ساخته می‌شود؛ این مسیر برخلاف `market_info.py` حداقل `nav_source: "price_proxy"` را در پاسخ می‌گذارد (`funds.py:230`).
- سه پیاده‌سازی مستقل premium با گاردهای متفاوت: `services/gold/calculator.py:61-80` (nav≤0 → `ValueError`)، `services/fund_scoring.py:452-455` (nav≤0 → `None`)، `services/gold/feature_source.py:668-683` (`price == nav` → placeholder، حذف از سری).

---

## ۸) علت ریشه‌ای

**ریشهٔ اصلی: یک ستون «تاریخ» چند معنا داشت و هیچ‌جا نوشته نشده بود کدام کدام است.**

1. **معنای مبهم تاریخ در تاریخچه.** جدول‌ها هم `date` (شمسی، تاریخ بازار) دارند و هم `gregorian_date`/`shamsi_date` که migration `0025` روی **همهٔ** جدول‌ها ساخته و تریگر `sync_dual_dates_fn` پر می‌کند. ستون منبع در `dual_date_columns` ذخیره می‌شود و `_pick_source` آن را با `_PRIORITY` انتخاب می‌کند؛ در آن لیست `fetched_at`, `created_at`, `updated_at` **قبل از** `date` هستند و چون وقت اجرای ۰۰۲۵ مقدار `fetched_at` این جدول‌ها NULL بود، `created_at` (ساعت درج) انتخاب شد. نتیجه: یک ستون با نام «تاریخ میلادی» عملاً تاریخ ingestion را نگه می‌دارد. کد monitoring (`freshness.py`) و برخی خواننده‌ها به همان ستون تکیه کردند ⇒ «کهنگی داده» با «تازگی اجرا» سنجیده شد و health check دروغ گفت. (این مکانیزم در دور دوم ممیزی کشف و مستند شد — بخش ۱۵.)
2. **نبود یک تعریف واحد از «bar معتبر».** اعتبارسنجی OHLC در مسیر تاریخچه فقط `close is None or close <= 0` بود؛ `high<low`، `close` خارج بازه، `open` خارج بازه و `NaN` وارد جدول می‌شدند. ماژول `brsapi/quality.py` اکنون تنها مرجع این قواعد است.
3. **پنهان‌سازی خطا.** `contextlib.suppress(Exception)` دور INSERT باعث شد نبود unique constraint (Q-04)، ناسازگاری نوع ستون و timeout ذخیره‌سازی همگی به «۰ ردیف با موفقیت» تبدیل شوند. خطا باید شمارش و گزارش شود، نه سرکوب.
4. **قرارداد NAV در لایهٔ API تحریف شده بود.** `brsapi_ime_funds` ستون NAV ندارد؛ endpoint به‌جای اعلام «NAV ناموجود»، `price_last` را زیر کلید `nav` منتشر کرد. چون همیشه `nav == price_last` بود، premium/discount ساختاراً صفر شد — این یک نقص نمایش/قرارداد است، نه خطای فرمول.
5. **مقایسهٔ رشته‌ای تاریخ شمسی.** جداکننده‌های متفاوت (`/` و `-`) در ترتیب لغوی ASCII معنی‌دار نیستند (`'/'` > `'-'`)، پس `MAX(date)` و `date <= cutoff` روی دادهٔ مختلط نتیجهٔ غلط می‌دهند.

---

## ۹) تغییرات کد و دلیل هرکدام

### ۹.۰ فایل جدید: `brsapi/quality.py`

مرجع واحد برای:

- `normalize_jalali_date()` — پذیرش `1405-06-23`، `1405/05/01`، `۱۴۰۵/۰۶/۲۳`، `١٤٠٥-٠٦-٢٣`، `1405.6.3`؛ اعتبارسنجی سال ۱۲۰۰–۱۵۹۹ و ماه/روز؛ **هیچ fallback به «امروز»** برای تاریخ ناموجود.
- `jalali_to_gregorian()` — تبدیل قطعی؛ روز غیرممکن → `None`.
- `daily_bar_issues()` / `is_valid_daily_bar()` — قواعد ثابت: `missing_close`، `non_finite`، `non_positive`، `high_below_low`، `close_outside_range`، `open_outside_range`. **هیچ اصلاح یا حذفی انجام نمی‌دهد؛ فقط گزارش می‌کند.**
- `history_quality_queries(table)` — کوئری‌های تشخیصی **فقط `SELECT`** با whitelist جدول؛ برای `brsapi_gold_coin_history`، `brsapi_gold_currency_pro_daily_history` و `brsapi_nav_records`. جدول ناشناس → `ValueError`.

**دلیل:** بدون یک تعریف تست‌شده و مشترک، هر مصرف‌کننده (ingestion، freshness، dashboard) نسخهٔ خودش را داشت.

### ۹.۱ `brsapi/services/history_fetch_service.py`

| تغییر | دلیل |
|---|---|
| `FetchReport` دو فیلد گرفت: `invalid_count`, `failed_count` | «رد شد به‌خاطر کیفیت» و «خطای ذخیره‌سازی» دو پدیدهٔ متفاوت‌اند و هر دو قبلاً نامرئی بودند |
| `_FETCH_TIME_FORMAT` + نوشتن `fetched_at` در INSERT | پر کردن «زمان fetch» که هیچ‌وقت ذخیره نمی‌شد (Q-02). روی `ON CONFLICT DO UPDATE` عمداً ست نمی‌شود تا معنایش «نخستین دریافت» بماند |
| نرمال‌سازی تاریخ با `normalize_jalali_date` | یکسان‌سازی `1405/05/01`/ارقام فارسی؛ تاریخ نامعتبر **quarantine** می‌شود (نه اینکه با «امروز» پر شود) |
| اعتبارسنجی کامل bar با `daily_bar_issues` | جلوگیری از ورود `high<low`/`close` خارج بازه به سری تاریخی؛ ردیف نامعتبر درج نمی‌شود ولی شمرده و لاگ می‌شود |
| حذف `contextlib.suppress(Exception)` دور INSERT و `try/except` صریح با شمارش | خطا دیگر پنهان نمی‌شود؛ `success = failed == 0` و `error` پر می‌شود |
| پیام لاگ پایان هر نماد شامل تعداد درج/قرنطینه/خطا | مشاهده‌پذیری واقعی metric بدون داشبورد جدید |

مسیر کریپتو در همین فایل دست‌نخورده ماند (خارج از دامنه).

### ۹.۲ `src/gold_desk/freshness.py`

| تغییر | دلیل |
|---|---|
| فیلد `calendar` روی `FreshnessSource` (`"gregorian"` پیش‌فرض، `"jalali"`) | یک منبع می‌تواند تاریخ شمسی داشته باشد؛ رفتار منابع قبلی تغییر نمی‌کند |
| منابع `brsapi_gold_coin_history` و `brsapi_gold_currency_pro_daily_history`: `gregorian_date` → `date` + `calendar="jalali"` | **هستهٔ اصلاح Q-01** |
| کوئری probe برای شمسی: `MAX(REPLACE(TRANSLATE(date, …), '/', '-'))` سپس تبدیل به میلادی | MAX روی رشتهٔ نرمال‌شده تا اسلش و خط تیره و ارقام فارسی یکسان مقایسه شوند؛ بدون نوشتن در DB |
| تاریخ غیرقابل‌تبدیل → وضعیت `missing` با `detail` | «تازه» جعل نمی‌شود؛ رفتار fail-safe همان الگوی قبلی فایل |
| افزودن منبع `brsapi_nav_records` (jalali، ۲۸۸۰ دقیقه) | Q-08 — سن NAV صندوق‌ها دیده می‌شود |
| کلید `calendar` در خروجی هر منبع | مصرف‌کنندهٔ داشبورد می‌داند عدد از کدام تقویم آمده |

### ۹.۳ `src/gold_desk/nav_checker.py`

| تغییر | دلیل |
|---|---|
| تابع `_date_key(model)` = `func.replace(model.date, "/", "-")` | مقایسه/مرتب‌سازی تاریخ شمسی مستقل از جداکننده، بدون بازنویسی داده |
| `_latest_nav`: `order_by(desc(_date_key(...)))` | «آخرین NAV» دیگر ردیف قدیمی‌تر اسلش‌دار را انتخاب نمی‌کند |
| `_nav_7d_ago`: شرط `_date_key(...) <= cutoff` | ردیف‌های همان بازه حذف نمی‌شوند |
| `_latest_rows_by_symbol`: `func.max(date_key)` و join روی همان کلید | رفع ناسازگاری `MAX` با `join` برای ردیف‌های اسلش‌دار (هم برای NAV و هم برای `historical_real_legal` که همان قالب تاریخ را دارد) |
| `_nav_7d_ago_batch`: `extra_where=_date_key(...) <= …` | همان اصلاح در مسیر batch |

### ۹.۴ `apps/api/endpoints/market_info.py`

| تغییر | دلیل |
|---|---|
| تابع جدید `_fund_list_row()`: `nav = None`, `nav_source = None`, `price_last`, `price_close` | **قرارداد صادقانه**: این جدول NAV ندارد. «NAV ناموجود» ≠ «حباب صفر» (رویکرد مورد انتظار ISSUE-128) |
| مرتب‌سازی روی `price_last or price_close or 0` | حفظ رفتار قبلیِ ترتیب فهرست بدون استفادهٔ دوباره از نام `nav` |
| تغییرات قبلی کاربر (خطا به‌جای `success=True` خالی، dedup بر اساس `fetched_at`) دست‌نخورده ماند | قاعدهٔ حفظ تغییرات کاربر |

**این یک تغییر قرارداد API است:** مصرف‌کننده‌ای که قبلاً `nav` را عدد می‌گرفت، اکنون `null` می‌گیرد و باید `price_last` را بخواند. در `frontend/src` هیچ مصرف‌کننده‌ای برای `/market-info/funds` پیدا نشد (`grep "market-info"` روی `frontend/src` فقط یک رشتهٔ متنی نامرتبط داد)، ولی این ریسک در بخش ۱۱ ثبت شده است.

### ۹.۵ تست‌ها و fixture (جدید/به‌روزشده)

| فایل | نوع |
|---|---|
| `tests/fixtures/brsapi/history_ohlc_mixed.json` | **جدید** — ۹ bar با ترکیب معتبر/نامعتبر؛ صریحاً «شکل پاسخ» است نه دادهٔ زنده |
| `tests/unit/brsapi/test_history_quality.py` | **جدید** — ۴۲ تست (normalize/convert/OHLC/fixture/read-only) |
| `tests/unit/brsapi/test_history_fetch_quality.py` | **جدید** — ۷ تست با session جعلی و `fetch_history` patch‌شده (بدون شبکه) |
| `tests/unit/gold_desk/test_freshness_trading_date.py` | **جدید** — ۱۲ تست تازگی بر مبنای تاریخ معامله |
| `tests/unit/gold_desk/test_nav_date_normalization.py` | **جدید** — ۴ تست نرمال‌سازی تاریخ در کوئری‌های NAV |
| `tests/unit/api/test_market_endpoint_contracts.py` | **به‌روزشده (فایل untracked کاربر)** — assertion قدیمی «`nav == price`» به قرارداد جدید تغییر کرد و assertionهای `price_last`/`nav_source`/ترتیب افزوده شد |

هیچ assertionای حذف یا ضعیف نشد؛ assertion قبلی که رفتار غلط را pin می‌کرد با سه assertion دقیق‌تر جایگزین شد.

---

## ۱۰) فرمان‌های تست، نتیجه و exit code

همه با `venv/Scripts/python` (pytest 9.1.1) و `set -o pipefail` اجرا شدند.

| # | فرمان | نتیجه | exit |
|---|---|---|---|
| T1 | `venv/Scripts/python -m pytest tests/unit/brsapi/test_history_quality.py tests/unit/brsapi/test_history_fetch_quality.py tests/unit/gold_desk/test_freshness_trading_date.py tests/unit/api/test_market_endpoint_contracts.py -q` | `74 passed, 1 warning in 58.40s` | **0** |
| T2 | `venv/Scripts/python -m pytest tests/unit/gold_desk/test_nav_date_normalization.py tests/gold_desk/test_nav_checker.py -q` | `15 passed in 7.40s` | **0** |
| T3 | `venv/Scripts/python -m pytest tests/gold_desk/test_phase0_snapshot_provenance.py tests/unit/test_gold_silver_funds_critical_regressions.py -q` | `23 passed in 6.25s` | **0** |
| T4 | `venv/Scripts/python -m pytest tests/unit/api/test_golddesk_portfolio_performance.py tests/unit/test_brsapi_history_backfill_manual.py -q` | `15 passed, 1 warning in 9.59s` | **0** |
| T5 | `venv/Scripts/python -m pytest tests/unit/test_brsapi_quota.py -q` | `7 passed in 3.50s` | **0** |
| T6 | `venv/Scripts/python -m pytest tests/unit/repositories/test_sync_log_repository.py -q` | `15 passed in 5.08s` | **0** |
| T7 | `cd frontend && npx vitest run src/__tests__/useMarketData.test.tsx` | `Test Files 1 passed (1)` / `Tests 10 passed (10)` | **0** |
| T8 | `venv/Scripts/python -m ruff check` روی ۸ فایل تغییر‌یافته/جدید این مأموریت | `All checks passed!` | **0** |
| T9 | `venv/Scripts/python -m ruff check src/gold_desk/nav_checker.py` | `Found 1 error` (I001 ترتیب import) | 1 |
| T10 | اجرای تجمیعی نهایی: `pytest` روی ۵ فایل جدید/به‌روزشده + `tests/gold_desk/test_nav_checker.py` + `tests/unit/api/test_golddesk_portfolio_performance.py` | `93 passed, 1 warning in 42.18s` | **0** |

**دربارهٔ T9:** این خطا **از قبل وجود داشت** و مربوط به این مأموریت نیست. برای اثبات، نسخهٔ `HEAD` همان فایل جداگانه بررسی شد: `git show HEAD:src/gold_desk/nav_checker.py > /tmp/nav_head.py && ruff check /tmp/nav_head.py` → همان یک خطای I001. طبق قاعدهٔ «بدون اجرای خودکار fixer روی مخزن»، اصلاح نشد.

**دربارهٔ warning در T1/T4:** یک `PydanticDeprecatedSince20` از `pydantic` در محیط نصب‌شده است، نه از کد این مأموریت.

هیچ تست شکست‌خورده‌ای پنهان نشد. هیچ تست موفقی به‌عنوان دلیل موفقیت رفتاری بدون اجرای واقعی گزارش نشد.

---

## ۱۱) تست‌های اجرانشده و علت

| مورد | علت |
|---|---|
| هر تست نیازمند DB (integration/`tests/integration/**`) | بدون اتصال زنده/مجوز به DB عملیاتی؛ طبق دستور مأموریت هیچ اتصالی برقرار نشد |
| هر تست نیازمند BrsApi | محدودیت دسترسی BrsApi؛ هیچ درخواست زنده‌ای زده نشد (شامل `brsapi/readiness.py::probe_key`) |
| تست idempotency دو بار ingestion روی DB واقعی (معیار پذیرش ISSUE-127) | نیازمند DB و unique constraint؛ فقط با fake session تست شد |
| تست واقعی `ON CONFLICT` در PostgreSQL | نیازمند schema با unique constraint که در migration مخزن نیست |
| `tests/gold_desk/test_phase3_adapters.py` (طبق ISSUE-129 قرمز است) | خارج از دامنهٔ این بخش و وابسته به کار در جریان |
| اجرای کامل `pytest` روی کل مخزن | مخزن ۱۰٬۰۰۰+ فایل و ده‌ها تغییر هم‌زمانِ کاربر دارد؛ اجرای کامل نه در دامنه بود و نه قابل تفکیک از تغییرات دیگران |
| بررسی چشمی UI / اسکرین‌شات | درخواست نشده بود |

---

## ۱۲) معیارهای پذیرش و وضعیت هرکدام

| # | معیار | وضعیت | شاهد |
|---|---|---|---|
| A1 | معنای هر timestamp دقیق و مستند باشد | **برآورده** | بخش ۶؛ docstring `brsapi/quality.py` (سه مفهوم) و `FetchReport` |
| A2 | ایراد OHLC قابل شناسایی و آزمون‌پذیر باشد | **برآورده** | `daily_bar_issues` + ۱۲ تست OHLC + fixture ۹ ردیفی |
| A3 | مسیر flag/quarantine + metric برای داده نامعتبر پیاده شود | **برآورده (محدود)** | quarantine در ingestion + `invalid_count`/`failed_count`؛ **بدون ستون flag در DB** (نیازمند migration، handoff) |
| A4 | هیچ داده واقعی با حدس تغییر نکند | **برآورده** | هیچ UPDATE/DELETE/TRUNCATE؛ کوئری‌های تشخیصی `SELECT`-only و تست‌شده؛ اصلاحات فقط روی رکوردهای جدید |
| A5 | کهنگی تاریخچه با معیار درست سنجیده شود | **برآورده** | `freshness.py` با `date` شمسی؛ ۱۲ تست |
| A6 | ادعای ۳۲/۳۲ با کد توضیح و تست شود | **برآورده (در سطح کد)** | `market_info.py` ریشه بود؛ تست قرارداد جدید. بازتولید عددی ۳۲/۳۲ نیازمند DB ⇒ مسدود |
| A7 | تعریف NAV/قیمت/premium و واحدها روشن باشد | **برآورده** | بخش ۶.۲/۶.۳ + تست بازار + `${nav_basis}` در `fund_service.py:220` |
| A8 | هیچ ادعای داده‌ای بدون شاهد | **برآورده** | بخش ۵.۳ (S1–S5) |
| A9 | گزارش فایل در مسیر تعیین‌شده | **برآورده** | همین فایل |
| A10 | تست‌های ۱۵/۱۰ مستقل تأیید شوند | **برآورده** | T6 و T7 |

---

## ۱۳) خطرات باقی‌مانده، وابستگی‌ها و handoff

### ۱۳.۱ handoff اجباری (خارج از اختیار این بخش)

1. **unique constraint روی `(symbol, date)`** برای `brsapi_gold_coin_history` و `brsapi_gold_currency_pro_daily_history` وجود ندارد، در حالی که هر دو مسیر ingestion به `ON CONFLICT (symbol, date)` تکیه می‌کنند.
   اقدام پیشنهادی (تصمیم و اجرا با مالک داده): یک migration که ابتدا ردیف‌های تکراری نرمال‌شده را شناسایی/آرشیو کند، سپس `date` را یکدست کند و بعد:
   ```sql
   CREATE UNIQUE INDEX CONCURRENTLY uq_gold_coin_hist_symbol_date
     ON brsapi_gold_coin_history (symbol, replace(date, '/', '-'));
   CREATE UNIQUE INDEX CONCURRENTLY uq_pro_daily_hist_symbol_date
     ON brsapi_gold_currency_pro_daily_history (symbol, replace(date, '/', '-'));
   ```
   ⚠️ روی جدول ۳۲۱٬۷۳۶ ردیفی نیازمند پنجرهٔ نگهداری و بررسی قبلی تکراری‌ها است. **در این مأموریت اجرا نشد.**
2. **نگاشت اشتباه `dual_date_columns`** (کشف دور دوم): برای این سه جدول، `source_column` باید `date` باشد ولی `fetched_at`/`created_at` است. اصلاح — **اجرا نشد، تصمیم مالک داده**:
   ```sql
   -- 1) پیش‌بررسی (read-only): مقدار فعلی
   SELECT table_name, source_column FROM dual_date_columns
    WHERE table_name IN ('brsapi_gold_coin_history',
                         'brsapi_gold_currency_pro_daily_history',
                         'brsapi_nav_records');
   -- 2) اصلاح نگاشت
   UPDATE dual_date_columns SET source_column = 'date'
    WHERE table_name IN ('brsapi_gold_coin_history',
                         'brsapi_gold_currency_pro_daily_history',
                         'brsapi_nav_records');
   -- 3) اتصال‌ها را refresh کنید (تریگر منبع را per-session کش می‌کند)
   -- 4) بازمحاسبهٔ دادهٔ موجود: python scripts/backfill_dual_dates.py
   ```
   تا وقتی این کار انجام شود، `gregorian_date` این جدول‌ها تاریخ ingestion است؛ به همین دلیل کد این مرحله دیگر به آن تکیه نمی‌کند.
3. **درج `fetched_at`** فرض می‌کند ستون varchar است (مدل `String(30)`، migration همان، و `README.md:1500` هم varchar می‌گوید). اگر جایی این ستون timestamp باشد، اکنون خطا **گزارش** می‌شود (`failed_count`) ولی ingestion آن نماد داده‌ای ذخیره نمی‌کند. بررسی نوع ستون در محیط عملیاتی لازم است.
4. **`gold_fund_nav` تازگی** با `snapshot_at` سنجیده می‌شود (Q-09): اجرای امروز job با NAV سه‌هفته‌کهنه «تازه» است. تصمیم محصول لازم است (سنجش با `date` یا افزودن `nav_as_of`).
5. **قرارداد `/market-info/funds`** تغییر کرد (`nav` = `null`). اگر مصرف‌کننده‌ای خارج از این مخزن (اپ موبایل/اسکریپت) روی `nav` حساب می‌کند، باید به `price_last` سوییچ کند.
6. ~~**مسیر کریپتو** همان `contextlib.suppress` را دارد~~ — **در دور دوم برطرف شد** (بخش ۱۵).

### ۱۳.۲ خطرات فنی باقی‌مانده

- **کارایی probe تازگی:** `MAX(REPLACE(TRANSLATE(date,…)))` روی جدول ۳۲۱٬۷۳۶ ردیفی بدون index، اسکن کامل است. برای endpoint سلامت داده (`/gold/freshness`) قابل قبول است ولی اگر این endpoint در مسیر پرترافیک قرار گیرد باید materialize شود.
- **`REPLACE`/`TRANSLATE` فقط برای Db PostgreSQL معتبرند** (پروژه PostgreSQL است). تست‌های SQL متنی هستند و روی DB واقعی اجرا نشدند.
- **قواعد کیفیت به‌صورت «رد درج» اعمال می‌شوند، نه flag.** ردیف نامعتبر وارد جدول نمی‌شود؛ یعنی داده در دسترس تحلیل نیست، ولی trace آن در لاگ+`invalid_count` هست. اگر مالک داده «نگه‌داشتن با flag» بخواهد، نیازمند ستون `quality_flag` و migration است.
- **`phase2._load_gold_history`/`_load_pro_history`** از `date >= "1405"` (سال شمسی) به‌عنوان پیش‌فیلتر استفاده می‌کنند و بعد در پایتون با cutoff میلادی فیلتر می‌کنند — این مسیر درست است و تغییر نکرد، ولی روی ردیف‌های اسلش‌دار به مقایسهٔ رشته‌ای سال تکیه دارد که برای `1405/...` هم درست کار می‌کند (چون سال در ابتداست).
- **تغییرات هم‌زمان کاربر** در `services/news_*` و `domain/instruments/symbol_catalog.py` در طول این نشست (بخش ۲) بررسی نشد و ممکن است تست‌های کامل مخزن را تحت تأثیر بگذارد؛ ارتباطی با این بخش ندارد.

### ۱۳.۳ وابستگی‌ها

- `jdatetime` (موجود در محیط؛ برای تبدیل شمسی/میلادی)
- SQLAlchemy (موجود)
- PostgreSQL 18 (برای `TRANSALTE/REPLACE` و `ON CONFLICT`)

---

## ۱۴) فهرست نهایی فایل‌های تغییرکرده توسط این مأموریت

| فایل | وضعیت |
|---|---|
| `brsapi/quality.py` | **جدید** |
| `brsapi/services/history_fetch_service.py` | اصلاح |
| `src/gold_desk/freshness.py` | اصلاح |
| `src/gold_desk/nav_checker.py` | اصلاح |
| `apps/api/endpoints/market_info.py` | اصلاح (تغییرات قبلی کاربر حفظ شد) |
| `tests/fixtures/brsapi/history_ohlc_mixed.json` | **جدید** |
| `tests/unit/brsapi/test_history_quality.py` | **جدید** |
| `tests/unit/brsapi/test_history_fetch_quality.py` | **جدید** |
| `tests/unit/gold_desk/test_freshness_trading_date.py` | **جدید** |
| `tests/unit/gold_desk/test_nav_date_normalization.py` | **جدید** |
| `tests/unit/api/test_market_endpoint_contracts.py` | به‌روزرسانی assertionهای NAV (فایل از قبل untracked بود) |

هیچ فایل دیگری توسط این مأموریت نوشته، حذف یا بازنویسی نشد. هیچ commit، stage، stash یا push انجام نشد.

---

## ۱۵) به‌روزرسانی دور دوم — تکمیل کارهای باقی‌مانده

زمان: `2026-10-28 23:40` تا `2026-10-29 00:20`.

### ۱۵.۱ کشف مهم: مجموعهٔ migration واقعی

مجموعهٔ فعال Alembic مسیر `migrations/versions/` است (۸۵ فایل، head = `0043_gold_holding_soft_delete`، `alembic.ini:2` → `script_location = migrations`)، **نه** `brsapi/migrations/001_create_brsapi_tables.py` که یک نسخهٔ قدیمی و غیرمرجع است. بازبینی مجدد روی مجموعهٔ درست این است:

| ادعا | دور اول (روی migration قدیمی) | دور دوم (روی مجموعهٔ واقعی) |
|---|---|---|
| `gregorian_date`/`shamsi_date` بخشی از schema هستند | «در migration وجود ندارند» ❌ | **وجود دارند**: `migrations/versions/0025_add_dual_date_columns.py` به همهٔ جدول‌ها اضافه می‌کند + تریگر `trg_dual_dates` |
| منبع مقدار آن‌ها | «هیچ کد مخزن آن‌ها را نمی‌نویسد» ❌ | تریگر `sync_dual_dates_fn` از `dual_date_columns.source_column` پر می‌کند (`scripts/install_dual_dates.py:186-236`) |
| چرا تاریخ ingestion است | توضیح نداشت | `_pick_source` (`0025:105-160`) با `_PRIORITY` که `fetched_at`/`created_at`/`updated_at` را **قبل از** `date` می‌آورد؛ در زمان اجرا `fetched_at` NULL بود ⇒ `created_at` انتخاب شد |
| unique constraint روی `(symbol, date)` | «migration ندارد» ✅ | **همچنان درست**: تنها migrationهای مرتبط `0006` (افزودن `updated_at`) و `0025` هستند و هیچ‌کدام unique نمی‌سازند |
| Q-05 (۳۲/۳۲) | «توضیح ساختاری» ⚠️ | **تنزل یافت**: هیچ مدل مخزن ستون‌های `nav`+`price_last` را با هم ندارد (FundModel در `apps/funds/models.py:40` ستون nav ندارد، `BubbleSnapshot.nav` جداست، `iran_market_data` `price_last` ندارد) ⇒ منشأ عدد ۳۲/۳۲ **تأییدنشده** است و `market_info.py` فقط یک نمونهٔ کد از همان ضدالگو و به‌طور مستقل آزمون‌پذیر است |

### ۱۵.۲ کارهای انجام‌شده در دور دوم

| # | کار | فایل | تست |
|---|---|---|---|
| N1 | بهترین‌سازی مسیر **کریپتو**: حذف `contextlib.suppress`، شمارش `invalid_count`/`failed_count`، نرمال‌سازی تاریخ شمسی، قرنطینهٔ bar نامعتبر، نوشتن `fetched_at` | `brsapi/services/history_fetch_service.py` | ۲ تست جدید در `test_history_fetch_quality.py` |
| N2 | روشن‌کردن معنای تازگی `gold_fund_nav` (زمان job ≠ سن NAV) با فیلد جدید `note` در `FreshnessSource` + خروجی گزارش | `src/gold_desk/freshness.py` | ۲ تست جدید در `test_freshness_trading_date.py` |
| N3 | مستندسازی قرارداد واحد پول دو جدول تاریخچه در docstring مدل (تومان در برابر ریال/دلار) | `brsapi/models/commodity.py` | — (مستند) |
| N4 | اسکریپت pre-flight **فقط-خواندنی** برای تولید آمار مسدودشده: چک‌های کیفیت + نوع ستون‌ها + `dual_date_columns` + ایندکس‌ها + DDL پیشنهادی فقط چاپ می‌شود | `scripts/history_quality_preflight.py` | `tests/unit/brsapi/test_history_quality_preflight.py` (۶ تست) |

### ۱۵.۳ خروجی تست دور دوم

| فرمان | نتیجهٔ خام | exit |
|---|---|---|
| `venv/Scripts/python -m pytest tests/unit/brsapi/test_history_quality_preflight.py tests/unit/gold_desk/test_freshness_trading_date.py -q` | `20 passed in 6.60s` | **0** |
| `pytest tests/unit/brsapi/test_history_fetch_quality.py -q` | `9 passed in 30.47s` | **0** |
| `pytest tests/unit/brsapi tests/unit/gold_desk tests/gold_desk tests/unit/api -q --ignore=tests/unit/brsapi/test_sync_outcomes.py` | `9 failed, 823 passed, 6 skipped in 398.64s` | 1 |
| `ruff check` روی ۶ فایل دور دوم | `All checks passed!` | 0 |
| **اجرای تجمیعی نهایی دور دوم** روی ۸ فایل تست مرتبط | `103 passed, 1 warning in 99.47s` | **0** |

**دربارهٔ ۹ شکست در اجرای گسترده:** هر ۹ مورد به `RuntimeError: Cannot connect to PostgreSQL database … localhost:5432/market` می‌خورند (فایل: `tests/gold_desk/test_phase0_snapshot_integration.py` ۲، `tests/unit/api/test_gold_derivatives_endpoints.py` ۲، `tests/unit/api/test_gold_personal_surface_auth.py` ۵). هیچ‌کدام به ماژول‌های تغییرکردهٔ این مرحله مربوط نیست؛ علت مشترک نبود PostgreSQL است.

**و یک خطای collection مستقل از این مرحله:** `tests/unit/brsapi/test_sync_outcomes.py` (فایل untracked کار در جریان) در import با `ImportError: cannot import name 'BrsApiMalformedResponseError' from 'brsapi.client'` می‌شکند — تأیید شد که این نام در `brsapi/client.py` وجود ندارد (`hasattr` → `False`). این فایل توسط این مأموریت ساخته یا تغییر داده نشده است.

### ۱۵.۴ کارهای باقی‌مانده پس از دور دوم

| # | کار | وضعیت |
|---|---|---|
| 1 | اجرای `scripts/history_quality_preflight.py` روی DB عملیاتی و ثبت آمار | **BLOCKED** (بدون DB) — ابزار آماده است |
| 2 | تأیید عددی ۳۲/۳۲ و شناسایی جدول مبنا | **BLOCKED** + منشأ نامعلوم |
| 3 | `CREATE UNIQUE INDEX CONCURRENTLY` روی `(symbol, date)` پس از بررسی تکراری‌ها | **BLOCKED/تصمیم** — DDL پیشنهادی در خروجی اسکریپت چاپ می‌شود |
| 4 | اصلاح نگاشت `dual_date_columns` به `date` + backfill | **BLOCKED/تصمیم** — SQL در بخش ۱۳.۱ آورده شده |
| 5 | ستون `quality_flag` برای داده‌ی نامعتبر | انجام نشد (نیازمند تصمیم محصول؛ فعلاً قرنطینهٔ بدون نوشتن) |
| 6 | بازرسی نوع ستون `fetched_at` در DB | **BLOCKED** — اسکریپت pre-flight نوع ستون‌ها را چاپ می‌کند |
| 7 | مسیر کریپتو | **انجام شد (N1)** |
| 8 | تازگی `gold_fund_nav` | **انجام شد در سطح معنا/برچسب (N2)**؛ `nav_as_of` در DB نیازمند تصمیم |

### ۱۵.۵ فایل‌های جدید/تغییرکردهٔ دور دوم

- جدید: `scripts/history_quality_preflight.py`، `tests/unit/brsapi/test_history_quality_preflight.py`
- تغییر: `brsapi/services/history_fetch_service.py`، `src/gold_desk/freshness.py`، `brsapi/models/commodity.py`، `tests/unit/brsapi/test_history_fetch_quality.py`، `tests/unit/gold_desk/test_freshness_trading_date.py`
- هیچ فایل غیرمرتبطی لمس نشد و هیچ تغییر کاربر حذف/بازنویسی نشد.
