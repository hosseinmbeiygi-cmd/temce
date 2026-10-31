# ممیزی مرحلهٔ ۰ — اجرای دوم (پس از بستن شکاف‌ها)

> ممیزی مستقل. مبنای نتیجه‌گیری: بازخوانی فایل گزارش، بازرسی مستقیم کد، snapshot تازهٔ Git و اجرای مجدد تست‌ها. هیچ ادعای مرحلهٔ قبل بدون بازبینی پذیرفته نشده است.
>
> این فایل **جایگزین** `QA_STAGE_0.md` نیست و آن را بازنویسی نمی‌کند؛ ممیزی دوم پس از بستن شکاف‌های مجاز (اندازهٔ inventory و ۶ ادعای claim index) است.

| مورد | مقدار |
|---|---|
| تاریخ/زمان ممیزی | ۲۰۲۶-۱۰-۲۸ |
| snapshot | `2026-10-28T06:33:05Z` (۰۹:۳۳:۰۵ محلی) |
| ریشهٔ مخزن | `C:/Users/Iran/Desktop/temce` |
| شاخه | `integration/golddesk-fixes` |
| HEAD | `90597e05b9f4328bcd82ee819a31ba5c55413c12` |
| مفسر تست | `venv/Scripts/python.exe` — Python 3.11.9، pytest 9.1.1 |
| Vitest | v4.1.9 |
| درخواست زندهٔ BrsApi | **انجام نشد** |

---

## ۱. مسیر گزارش نهایی مرحله و تأیید وجود فایل

### ۱.۱ گزارش مرحلهٔ ۰ (مرجع)

```
AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE_run2.md
```

| سنجه | مقدار |
|---|---|
| وجود فایل | ✅ تأیید با `ls -la` و `wc -l -c` |
| تعداد خطوط | **۸۴۱** (قبلاً ۶۰۹ — دو پیوست ۱۷ و ۱۸ اضافه شد) |
| اندازه | **۵۷٬۴۴۴ بایت** (قبلاً ۴۵٬۲۹۰ بایت) |
| MD5 | `f5a849186a105f11b961a1685fd92fe1` |
| بخش‌ها | ۱۸ بخش (`## ۰` تا `## ۱۸`) — تأیید با `grep -n "^## "` |
| پیوست الف | خط ۶۱۵ — «موجودی با اندازه» |
| پیوست ب | خط ۷۰۵ — «تأیید ۶ ادعای باقی‌مانده» |

### ۱.۲ گزارش‌های ممیزی

| مسیر | خطوط | وضعیت |
|---|---|---|
| `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_0.md` | ۲۹۱ | ممیزی اول؛ **دست‌نخورده** (mtime ۰۹:۳۶، بازنویسی نشد) |
| `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_0_run2.md` | همین فایل | ممیزی دوم |

### ۱.۳ گزارش‌های قبلی مرحلهٔ ۰ که overwrite نشدند

| مسیر | اندازه | mtime |
|---|---|---|
| `00_BASELINE_AND_GIT_STATE.md` | ۸٬۳۰۷ بایت | 2026-10-27 22:07 |
| `01_MARKET_SOURCE_AND_PARSERS.md` | ۱۳٬۵۳۴ بایت | 2026-10-27 22:11 |
| `02_SCHEDULER_WORKERS_QUEUES.md` | ۱۸٬۱۳۵ بایت | 2026-10-27 22:12 |
| `03_DATABASE_STORAGE_REPOSITORIES.md` | ۱۸٬۸۶۲ بایت | 2026-10-27 22:14 |

---

## ۲. فایل‌های بررسی‌شده و بررسی‌نشده

### ۲.۱ بررسی‌شده در این ممیزی

| مسیر | خطوط | وضعیت | کار انجام‌شده |
|---|---|---|---|
| `AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE_run2.md` | ۸۴۱ | ✅ | کل گزارش، شامل پیوست‌های ۱۷ و ۱۸ |
| `brsapi/repositories/base.py` | ۴۰۴ | 🟡 | خطوط ۱۰۰–۱۱۵ (`needs_sync`) |
| `brsapi/services/sync_service.py` | ۱٬۸۴۳ | 🟡 | خطوط ۳۹۰–۴۶۰ (مسیر «خالی → success») + `grep` روی `items_count=` |
| `brsapi/models/tsetmc.py` | — | 🟡 | خطوط ۲۶۱–۲۸۵ (`NavRecordModel`) |
| `brsapi/jobs/registry.py` | — | 🟡 | خطوط ۳۴۸–۳۶۳ و ۴۹۹–۵۱۶ (`run_handler`, `_run`) |
| `ingestion/worker.py` | ۱۹۶ | 🟡 | خطوط ۱۵۰–۲۰۰ (ترتیب dedup) |
| `ingestion/storage/__init__.py` | ۹۲ | 🟡 | خطوط ۸۳–۹۰ |
| `ingestion/parser/library_parsers.py` | ۴۰۷ | 🟡 | خطوط ۹۰–۱۰۰ |
| `jobs/queue_consumer.py` | — | 🟡 | خطوط ۵۲–۱۰۵ و ۲۳۴–۲۴۰ (token/auth) |
| `jobs/queue_publisher.py` | — | 🟡 | خطوط ۸۴–۱۳۵ (`publish`, `is_available`) |
| `jobs/scheduler.py` | ۱۲۴ | 🟡 | ساختار کلی — **هیچ ارجاعی به queue ندارد** |
| `apps/scheduler/app.py` | ۳۲۹ | 🟡 | خطوط ۱–۹۰ (`_execute`, `run_handler`) |
| `core/fix_network.py` | — | 🟡 | خطوط ۴۴ و ۷۶ (پروکسی bypass) |
| `core/config/__init__.py` | — | 🟡 | خط ۲۷۳ (`job_queue_token`) |
| `frontend/src/hooks/useMarketData.ts` | ۸۱۵ | 🟡 | خطوط ۲۷۸–۲۹۲ |
| `apps/api/router.py` | ۷۳۶ | 🟡 | conflict + `ast.parse` |
| `tests/unit/repositories/test_sync_log_repository.py` | ۴۲۵ | 🟡 | شمارش/نام ۱۵ تست |
| `frontend/src/__tests__/useMarketData.test.tsx` | ۱۴۸ | 🟡 | شمارش/نام ۱۰ تست |
| خروجی Git و اسکریپت اندازه‌گیری | — | ✅ | snapshot کامل + محاسبهٔ حجم ۱۳٬۱۲۹ فایل |

### ۲.۲ بررسی‌نشده — با دلیل

| دسته | دلیل |
|---|---|
| `tests/unit/repositories/test_bulk_upsert_repository.py`، `test_clock_semantics.py`، `tests/unit/api/test_market_aggregate_cache.py` | **تازه توسط فرآیند بیرونی ساخته شده‌اند** (untracked، پس از snapshot قبلی)؛ محتوا بررسی نشد |
| `docs/` (۲۱۸ فایل) | محتوا بررسی نشد؛ فقط وجود/تعداد |
| `symbol_reports/`، `json/`، `reports/`، `new_symbol_reports/`، `audit_out/` | تولیدی/data |
| `_FRONTEND_BACKEND_COPY/` (۲٬۲۶۵) | vendor/copy |
| `Redis/` (باینری‌ها) | باینری |
| `node_modules/`، `venv/`، `.venv/` | وابستگی خارجی |
| `.env`, `.env.production`, `frontend/.env` | **عمداً خوانده نشد** (secret) |
| `ml/`، `backtesting/`، `providers/` (محتوا) | خارج از دامنهٔ مرحلهٔ ۰ |
| باینری‌ها (png/ttf/exe/pdb/zip/pdf) | باینری |

**هیچ ادعای «همهٔ فایل‌ها بررسی شد» مطرح نیست.**

---

## ۳. جدول الزامات

### ۳.۱ معیارهای پذیرش مرحلهٔ ۰

| الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| هیچ فایل source/test یا state گیت تغییر نکرده باشد؛ فقط گزارش جدید ایجاد شود | `git diff --cached --shortstat` = `138 / +115998 / -1447` — **در سه نوبت (۰۹:۰۷، ۰۹:۳۲، ۰۹:۳۳) یکسان**؛ HEAD بدون تغییر `90597e05` | 🟡 **PARTIAL** | intent برآورده شد، ولی criterion مطلق قابل تأیید نیست: فرآیند بیرونی **۳ فایل تست جدید** و تغییرات source اضافه کرد (بخش ۷) |
| گزارش manifest وضعیت اولیهٔ Git و موانع را مستند کند | بخش‌های ۱ (سه snapshot)، ۳، ۸، ۱۳، ۱۷، ۱۸ | ✅ **PASS** | — |
| هیچ ادعای «همهٔ فایل‌ها کامل خوانده شده» بدون manifest و شاهد نباشد | بخش ۱۶ گزارش + بخش ۲ همین سند | ✅ **PASS** | — |

### ۳.۲ وظایف اختصاصی مرحلهٔ ۰

| الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| شناسایی ریشهٔ checkout | `git rev-parse --show-toplevel` → `C:/Users/Iran/Desktop/temce` (exit 0) | ✅ PASS | — |
| ثبت HEAD و نام شاخه | `integration/golddesk-fixes` / `90597e05…` | ✅ PASS | — |
| ثبت staged/unstaged/untracked و diffها | سه snapshot + `--shortstat` هر دو سمت | ✅ PASS | — |
| فهرست فایل‌های تغییرکرده | بخش ۱.۳–۱.۵ گزارش + جدول تفکیک ۱.۶ | ✅ PASS | — |
| تفکیک HEAD/index/working-tree برای فایل‌های حساس بدون افشای secret | جدول بخش ۱.۶؛ فقط نام فایل‌های env | ✅ PASS | — |
| inventory با `git ls-files`: زبان/مسیر/نوع/**اندازه** | **بخش ۱۷:** ۱۳٬۱۲۹ فایل، ۰ غایب، ۲۴۶٫۱۳ MB؛ تفکیک ۲۸ دایرکتوری + ۱۶ پسوند + ۱۰ فایل بزرگ + تفکیک source/generated/vendor/binary | ✅ **PASS** (شکاف A6 بسته شد) | — |
| شناسایی آرشیوها بدون اشتباه با checkout | بخش ۴ گزارش؛ ZIP ۳٬۳۵۰٬۷۵۷ بایت؛ تصریح «مبنای بررسی working tree است» | ✅ PASS | — |
| گزارش‌های audit قبلی به‌عنوان claim index | بخش ۶ گزارش: C1–C12 | ✅ PASS | — |
| غیبت `AUDIT_BATCH_001..009_FA.md` و `ROOT_CAUSE_VERIFICATION_FA.md` ثبت شود | بخش ۶.۱: «غیبت ثبت شد»، بدون حدس | ✅ PASS | — |
| بررسی نشانگرهای `<<<<<<<` / `>>>>>>>` | `grep -rlE` روی ۱۲ دایرکتوری → **۰ فایل** | ✅ PASS | — |
| بررسی وضعیت `apps/api/router.py` | ۷۳۶ خط؛ `ast.parse` → OK؛ ۰ نشانگر؛ غایب در `git status` | ✅ PASS | — |
| بررسی ادعای «needs_sync تست شده» / «isDataFresh اصلاح شده» (فقط مشاهده) | بازرسی مستقیم (بخش ۵) | ✅ PASS | — |
| ترتیب اجرایی بخش‌ها | بخش ۱۴ گزارش | ✅ PASS | — |
| عدم درخواست زندهٔ BrsApi / عدم دست‌کاری cooldown | هیچ فرمان شبکه‌ای؛ cooldown دست‌نخورده | ✅ PASS (تأیید زنده **BLOCKED**) | رفع cooldown لازم است |
| عدم عملیات مخرب DB | هیچ TRUNCATE/DELETE/reset/migration | ✅ PASS | — |
| عدم افشای secret | فقط نام فایل‌های env | ✅ PASS | — |
| گزارش در فایل، پاسخ چت کوتاه | گزارش ۸۴۱ خطی؛ پاسخ کوتاه | ✅ PASS | — |

### ۳.۳ شکاف‌های بسته‌شده در این اجرا

| شکاف قبلی | اقدام | شاهد | نتیجه |
|---|---|---|---|
| inventory بدون اندازه | محاسبهٔ حجم ۱۳٬۱۲۹ فایل tracked | بخش ۱۷ گزارش؛ `MISSING_ON_DISK=0`؛ کل ۲۴۶٫۱۳ MB | ✅ بسته شد |
| C5، C6، C8، C9، C10، C12 تأییدنشده | بازرسی مستقیم ۶ ادعا با `path:line` | بخش ۱۸ گزارش | ✅ بسته شد (۵ تأیید + ۱ نقض جزئی) |
| C11 تأییدنشده | قابل بازسازی نیست (ادعای عددی در گزارش قبلی، بدون manifest) | — | ❌ باز باقی ماند |

---

## ۴. اصلاحات: مسیر، diff، دلیل، تست

**مرحلهٔ ۰ هیچ اصلاح کدی انجام نداد.** شاهد:

- `git diff --cached --shortstat` در ۰۹:۰۷، ۰۹:۳۲ و ۰۹:۳۳ **یکسان**: `138 files changed, 115998 insertions(+), 1447 deletions(-)`
- `HEAD` در تمام snapshotها: `90597e05b9f4328bcd82ee819a31ba5c55413c12`
- هیچ `git add` / `reset` / `checkout` / `stash` / `commit` اجرا نشد
- فایل‌های ایجادشده: `00_..._run2.md` (گسترش‌یافته با append)، `QA_STAGE_0.md`، `QA_STAGE_0_run2.md`

### ۴.۱ دو تغییر **از پیش موجود** (حفظ‌شده، بازرسی‌شده)

**(الف) `frontend/src/hooks/useMarketData.ts`** — وضعیت `M ` (staged)، working tree = index

```diff
@@ -278,7 +278,15 @@ function useEnrichedHeatmap(): LiveDataResult<HeatmapCell[]> {
     retry: 1,
   });
   const cells = data ?? [];
-  return { data: cells, isLive: cells.length > 0, isError, isLoading };
+  const now = Date.now();
+  const freshnessThreshold = 5 * 60 * 1000; // 5 minutes
+  const isDataFresh = cells.length > 0 && cells.every((c: any) => {
+    const fetched = c.fetched_at ? new Date(c.fetched_at).getTime() : null;
+    if (fetched == null || fetched > now) return false;
+    return now - fetched <= freshnessThreshold;
+  });
+  return { data: cells, isLive: freshnessThreshold > 0 ? isDataFresh : cells.length > 0, isError, isLoading };
 }
```

- **دلیل:** `now - fetched_at` برای تاریخ آینده منفی و همیشه `<= threshold` بود.
- **تست:** `frontend/src/__tests__/useMarketData.test.tsx` → `10 passed`

**(ب) `tests/unit/repositories/test_sync_log_repository.py`** — وضعیت `M ` (staged)، `+254 / -1`
- ۱۵ تست: ۱۰ × `test_needs_sync_*` + ۵ × `test_get_sync_stats_*`
- **تست:** خود فایل → `15 passed`

### ۴.۲ تغییرات بیرونی (کار مرحلهٔ ۰ نیست)

| فایل | وضعیت | شاهد |
|---|---|---|
| `brsapi/models/base.py` | ` M` | mtime ۰۹:۱۹:۳۶ |
| `brsapi/repositories/base.py` | ` M` | mtime ۰۹:۲۰:۲۸ |
| `brsapi/services/sync_service.py` | `MM` | mtime ۰۹:۲۱:۵۸ |
| `brsapi/services/query_service.py` | ` M` | — |
| `ingestion/worker.py` | `MM` | mtime ۰۹:۱۷:۵۷ |
| `apps/api/endpoints/market.py` | ` M` | — |
| `schemas/common/responses.py` | ` M` | — |
| `tests/unit/api/test_market_aggregate_cache.py` | `??` **جدید** | untracked |
| `tests/unit/repositories/test_bulk_upsert_repository.py` | `??` **جدید** | untracked |
| `tests/unit/repositories/test_clock_semantics.py` | `??` **جدید** | untracked |

---

## ۵. فرمان‌های تست — نتیجهٔ واقعی

| # | فرمان | نتیجه | موفق | ناموفق | اجرانشده | exit |
|---|---|---|---|---|---|---|
| T1 | `python -m pytest tests/unit/repositories/test_sync_log_repository.py -p no:cacheprovider --timeout=120 --timeout-method=thread -q` | `15 passed in 6.03s` | ۱۵ | ۰ | ۰ | **0** |
| T2 | `cd frontend && npx vitest run src/__tests__/useMarketData.test.tsx` | `Test Files 1 passed (1)` / `Tests 10 passed (10)` | ۱۰ | ۰ | ۰ | **0** |
| T3 | `python -c "import ast; ast.parse(open('apps/api/router.py',encoding='utf-8').read()); print('parses OK')"` | `parses OK` | ۱ | ۰ | ۰ | **0** |
| T4 | `grep -rlE '^(<<<<<<<\|>>>>>>>)' <۱۲ دایرکتوری>` | ۰ فایل | بررسی منفی | — | — | **1** (بدون تطابق = انتظار) |
| T5 | اسکریپت خواندن `os.path.getsize` روی `git ls-files -z` | ۱۳٬۱۲۹ فایل، ۰ غایب، ۲۴۶٫۱۳ MB | ✅ | ۰ | ۰ | **0** |
| T6 | `grep -c "def test_"` / `grep -c "def test_needs_sync"` / `grep -c "it("` | ۱۵ / ۱۰ / ۱۰ | ✅ | ۰ | ۰ | **0** |

**جمع: ۲۵ تست اجراشده — ۲۵ موفق، ۰ ناموفق، ۰ skip.**

> نکتهٔ صداقت: در اجرای ممیزی قبلی، `.venv/Scripts/python.exe` به‌دلیل نبود pytest شکست خورد (exit 1). این شکست **ابزاری** است، نه شکست تست، و در این سند به‌عنوان موفق ثبت نمی‌شود.

### ۵.۱ تست‌های اجرانشده

| تست | علت | وضعیت |
|---|---|---|
| کل `pytest tests/` | خارج از دامنهٔ مرحلهٔ ۰ | NOT RUN |
| `-m needs_db` | PostgreSQL روی `localhost:5432` بالا نیست | **BLOCKED** |
| تست یکپارچگی DB (dedup/ON CONFLICT/migration) | همان علت | **BLOCKED** |
| زنجیرهٔ end-to-end | BrsApi cooldown + نبود PostgreSQL/Redis | **BLOCKED** |
| تست صف/worker | نیازمند Redis | **BLOCKED** |
| **۳ فایل تست جدید** (`test_bulk_upsert_repository.py`، `test_clock_semantics.py`، `test_market_aggregate_cache.py`) | تازه ساخته شده‌اند؛ در دامنهٔ مرحلهٔ ۰ نیستند | NOT RUN |
| `npm test` کامل / `next build` / `docker compose` | خارج از دامنه/محیط | NOT RUN |

---

## ۶. حفظ تغییرات قبلی و staged

| بررسی | شاهد | نتیجه |
|---|---|---|
| index بدون تغییر | `138 / +115998 / -1447` در سه نوبت | ✅ حفظ شد |
| HEAD بدون تغییر | `90597e05…` | ✅ حفظ شد |
| عدم commit | هیچ `git commit` | ✅ |
| عدم reset/clean/stash/checkout | هیچ‌کدام | ✅ |
| عدم حذف تغییرات کاربر | تمام ورودی‌های status پابرجا | ✅ |
| ⚠ تغییر بیرونی | ۸ فایل source + ۳ فایل تست جدید | ثبت شد؛ منتسب به این مأموریت نیست |

---

## ۷. وضعیت Git در snapshot ممیزی و رانش مشاهده‌شده

| سنجه | ۰۹:۰۷ | ۰۹:۲۲ | ۰۹:۵۷ | **۰۹:۳۳ (ممیزی)** |
|---|---|---|---|---|
| کل status | ۲۸۸ | ۲۹۱ | ۱۴۸ | **۱۵۳** |
| `A ` | ۴۲ | ۴۲ | ۱۰۲ | ۱۰۲ |
| `M ` | ۳۴ | ۳۱ | ۳۲ | ۳۲ |
| `MM` | ۰ | ۳ | ۴ | ۴ |
| ` M` | ۱ | ۴ | ۴ | **۵** |
| `??` | ۲ | ۲ | ۶ | **۱۰** |
| untracked فایل | ۲۱۵ | ۲۱۵ | ۱۳ | **۱۳** |
| `git diff --cached` | ۱۳۸/۱۱۵۹۹۸/۱۴۴۷ | همان | همان | **همان** |
| HEAD | ۹۰۵۹۷e۰۵ | همان | همان | **همان** |

**تفسیر:** index و HEAD در تمام جلسه بایت‌ثابت مانده‌اند. رانش فقط در working tree رخ داده و منشأ آن فرآیند بیرونی است. افزوده‌شدن **۳ فایل تست جدید** نشان می‌دهد آن فرآیند اکنون در حال توسعهٔ فعال (به‌نظر مرحلهٔ ۰۴) است و baseline همچنان ناپایدار می‌ماند.

---

## ۸. دسترسی خارجی

| سرویس | وضعیت | شاهد |
|---|---|---|
| BrsApi (زنده) | **BLOCKED** | `logs/brsapi_sync_20261027.log`: `BrsApi key in 302-cooldown (430s left…)` |
| PostgreSQL | **BLOCKED** | `logs/brsapi_sync_20261028.log`: `Cannot connect to PostgreSQL database … localhost:5432/market` |
| Redis | تأییدنشده | سرویس محلی در دسترس نیست |
| Docker | NOT RUN | خارج از دامنه |

هیچ درخواست زندهٔ BrsApi ارسال نشد و cooldown/شمارنده دست‌کاری نشد.

---

## ۹. یافته‌های جدید این اجرا

| # | شدت | یافته | شاهد |
|---|---|---|---|
| **I14** | **بالا** | فایل WAL دیتابیس SQLite در Git tracked است (۲۵٫۱۰ MB — بزرگ‌ترین فایل مخزن) | `git ls-files transactions.db-wal` |
| **I15** | متوسط | باینری‌های Redis در مخزن (۲۶٫۴۱ MB) | `Redis/` |
| **I16** | **بالا** | عدم تقارن fallback در صف: jobهای عمومی fallback دارند، jobهای BrsApi ندارند | `apps/scheduler/app.py:36-47` vs `brsapi/jobs/registry.py:503-508` + `apps/scheduler/app.py:69` |
| **I17** | متوسط | در `ingestion/worker.py` رویدادهای resolve‌نشده `continue` می‌شوند بدون `payload_written_all=False` → payload «دیده‌شده» علامت می‌خورد بدون ذخیره | `ingestion/worker.py:167-189` |
| **I18** | پایین | `NavRecordModel.fetched_at` رشته (`String(30)`) بدون ایندکس، برخلاف سایر مدل‌ها | `brsapi/models/tsetmc.py:276` |

### ۹.۱ ادعای C9 که نقض شد

ادعای قبلی: «اگر Redis پایین باشد، scheduler هنوز fire می‌کند ولی پیام‌ها صف نمی‌شوند و workerها بیکار می‌مانند → هیچ jobی اجرا نمی‌شود.»

- برای **jobهای عمومی**: نادرست — `_execute` مقدار `None` را می‌بیند و به `job_dispatcher.dispatch` برمی‌گردد.
- برای **jobهای BrsApi**: درست — `_run` مقدار بازگشتی `run_handler` را نادیده می‌گیرد.

این تفکیک در پیوست ب گزارش مرحله (بخش ۱۸) ثبت شد.

---

## ۱۰. نتیجهٔ نهایی

# ⛔ PARTIAL

**دلیل:** الزامات مستندسازی (A2، A3) و تمام وظایف اختصاصی مرحلهٔ ۰ با شاهد کد/فرمان تأیید شده‌اند؛ دو شکاف قبلی (اندازهٔ inventory و ۶ ادعای claim index) بسته شدند. اما معیار A1 به‌صورت مطلق برآورده نشده است: در همان بازهٔ زمانی یک فرآیند بیرونی ۸ فایل source را تغییر داد و **۳ فایل تست جدید** ساخت، پس «عدم تغییر source/test» را نمی‌توان برای کل بازه تأیید کرد — هرچند index و HEAD بایت‌ثابت مانده‌اند و هیچ تغییری به این مأموریت منتسب نیست.

**FAIL نیست:** هیچ تست شکست‌خورده‌ای وجود ندارد (۲۵/۲۵ موفق) و هیچ نقصی پنهان نشده است.
**BLOCKED نیست:** مانع بیرونی، تکمیل مستندسازی مرحلهٔ ۰ را متوقف نکرد؛ فقط تأیید زندهٔ زنجیرهٔ داده را به مراحل بعد می‌سپارد.

> بر پایهٔ قاعدهٔ «تا زمانی که معیارهای پذیرش برآورده نشده‌اند، مرحله را کامل اعلام نکن» — **مرحلهٔ ۰ کامل اعلام نمی‌شود.**

---

## ۱۱. فهرست دقیق کارهای باقی‌مانده

### ۱۱.۱ مسدودکنندهٔ تثبیت (پیش‌شرط مرحلهٔ ۱)

1. **توقف نویسندهٔ هم‌زمان** روی این checkout (VS Code + Copilot runtime + نشست عامل دیگر).
2. **تصمیم دربارهٔ ساختار `docs/`** — `docs/` تخت (وضعیت فعلی، ۲۱۸ فایل) یا `docs/New folder/` (وضعیت ابتدای جلسه، اکنون ۰ فایل روی دیسک).
3. **تثبیت index** — بازبینی ۱۰۲ فایل `A ` و ۳۲ فایل `M ` و commit نقطه‌ای (فقط با اجازهٔ صریح).
4. **پاک‌سازی index از مصنوعات** — `services/market_service.py.bak`، `frontend/src/app/gold/components/SummarySection.tsx.bak`، `z.py.bak`، `apply_fixes.py`، `fix_avg.py`، `fix_function.py`، `fix_sector.py`، `docs/audits/tools/_ruff_broad.json`، `_pattern_findings.json`.
5. **حذف artefacts جدید از مخزن** — `transactions.db-wal` (۲۵ MB، I14) و باینری‌های `Redis/` (I15).
6. **رفع gitlink یتیم `InkGist`** (mode `160000` بدون `.gitmodules`).

### ۱۱.۲ تکمیل‌های این مرحله

7. **تأیید C11** — قابل بازسازی نیست مگر گزارش قبلی manifest فایل‌به‌فایل داشته باشد؛ در غیر این صورت باید به‌عنوان «ادعای غیرقابل‌تأیید» بسته شود.
8. **تأیید ادعای «۱۵ تست با `-v`»** در گزارش قبلی — قابل بازسازی نیست؛ همین سند فقط نتیجهٔ اجرای `-q` را تأیید می‌کند.

### ۱۱.۳ ایرادهای کد که برای رفع به بخش‌های بعد موکول شد

9. **I16** — افزودن fallback برای jobهای BrsApi در `brsapi/jobs/registry.py` (بخش ۰۲).
10. **I17** — علامت‌گذاری درست `payload_written_all` برای رویدادهای skip‌شده (بخش ۰۲).
11. **I18** — تبدیل `NavRecordModel.fetched_at` به `DateTime` + ایندکس (بخش ۰۳، نیازمند migration).
12. **C5** — تفکیک «موفق و خالی» از «خطای بلعیده‌شده» (بخش ۰۱/۰۲).

### ۱۱.۴ مسدودهای محیطی

13. **PostgreSQL** بالا بیاید → تست‌های `needs_db` و یکپارچگی DB.
14. **Redis** بالا بیاید → آزمون رفتار صف/worker و I16.
15. **BrsApi** پس از پایان cooldown → تأیید زندهٔ زنجیرهٔ داده. تا آن زمان هر نتیجه در این حوزه **BLOCKED** ثبت می‌شود.
