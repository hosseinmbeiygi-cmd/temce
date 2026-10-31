# ممیزی تکمیل مرحلهٔ ۰ — Baseline و وضعیت Git

> این فایل ممیزی **مستقل** از مرحلهٔ ۰ است. نتیجه‌گیری بر پایهٔ بازخوانی فایل گزارش، بازرسی مستقیم کد، snapshot تازهٔ Git و اجرای مجدد تست‌ها انجام شده است؛ نه بر پایهٔ ادعای مرحلهٔ قبل.

| مورد | مقدار |
|---|---|
| تاریخ/زمان ممیزی | ۲۰۲۶-۱۰-۲۸ |
| snapshot ممیزی | `2026-10-28T06:02:36Z` (۰۹:۳۲:۳۶ محلی) |
| ریشهٔ مخزن | `C:/Users/Iran/Desktop/temce` |
| شاخه | `integration/golddesk-fixes` |
| HEAD | `90597e05b9f4328bcd82ee819a31ba5c55413c12` |
| مفسر تست | `venv/Scripts/python.exe` — Python 3.11.9، pytest 9.1.1 |
| Vitest | v4.1.9 |
| درخواست زندهٔ BrsApi | **انجام نشد** (ممنوع) |

---

## ۱. مسیر گزارش نهایی مرحله و تأیید وجود فایل

**گزارش مرحلهٔ ۰:**

```
AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE_run2.md
```

| سنجه | مقدار |
|---|---|
| وجود فایل | ✅ بله (با `ls -la` تأیید شد) |
| اندازه | ۴۵٬۲۹۰ بایت |
| تعداد خطوط | ۶۰۹ |
| mtime | `2026-10-28 09:30:47 +0330` |
| MD5 | `823d4e3aeccb5e3e9e390ee4497db5ab` |
| فایل قبلی `00_BASELINE_AND_GIT_STATE.md` | وجود دارد، ۸٬۳۰۷ بایت، mtime `2026-10-27 22:07:43` — **overwrite نشده** (⚠ محدودیت: MD5 قبل از اجرا ثبت نشده بود؛ تأیید بر پایهٔ mtime و اندازهٔ بدون‌تغییر است) |

ساختار گزارش: هر ۱۶ بخش الزامی موجود است (`## ۰` تا `## ۱۶`) — با `grep -n "^## "` تأیید شد.

**گزارش ممیزی این مرحله:**

```
AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_0.md
```

پیش از نگارش، وجود این فایل بررسی شد: **موجود نبود** → بدون خطر overwrite ایجاد شد.

---

## ۲. فایل‌های بررسی‌شده و بررسی‌نشده

علامت‌ها: ✅ کامل | 🟡 بخشی (با محدودهٔ خط) | ⬜ بررسی‌نشده

### ۲.۱ بررسی‌شده در این ممیزی

| مسیر | خطوط | وضعیت | کار انجام‌شده |
|---|---|---|---|
| `AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE_run2.md` | ۶۰۹ | ✅ | کل گزارش خوانده و با واقعیت تطبیق داده شد |
| `brsapi/repositories/base.py` | ۴۰۴ | 🟡 | خطوط ۱۰۰–۱۱۵ (`needs_sync`) عیناً بازرسی شد |
| `frontend/src/hooks/useMarketData.ts` | ۸۱۵ | 🟡 | خطوط ۲۷۸–۲۹۲ (`isDataFresh`) عیناً بازرسی شد |
| `ingestion/storage/__init__.py` | ۹۲ | 🟡 | خطوط ۸۳–۹۰ (الگوی falsy) |
| `ingestion/parser/library_parsers.py` | ۴۰۷ | 🟡 | خطوط ۹۰–۱۰۰ (`parse` و `except → return []`) |
| `apps/api/router.py` | ۷۳۶ | 🟡 | بررسی conflict + `ast.parse`؛ محتوا خط‌به‌خط نه |
| `tests/unit/repositories/test_sync_log_repository.py` | ۴۲۵ | 🟡 | شمارش و نام ۱۵ تابع تست؛ بدنه نه |
| `frontend/src/__tests__/useMarketData.test.tsx` | ۱۴۸ | 🟡 | شمارش و نام ۱۰ تست |
| `AUDIT_REPORTS/MODULAR_TEMCE/*` (۷ فایل دیگر) | — | 🟡 | فقط فهرست و mtime/اندازه |
| خروجی Git (`status`, `diff`, `ls-files`) | — | ✅ | snapshot کامل در ۰۹:۳۲ |
| خروجی pytest و vitest | — | ✅ | اجرای مجدد کامل |

### ۲.۲ بررسی‌نشده — با دلیل

| دسته | دلیل |
|---|---|
| `ingestion/worker.py` (۱۹۶ خط، ۳۷۷ خط diff) | فقط diffstat دیده شد؛ محتوا خوانده نشد → بخش ۰۲ |
| `brsapi/services/sync_service.py` (۱٬۸۴۳ خط) | فقط hunkهای diff → بخش ۰۲/۰۳ |
| `brsapi/models/base.py` (۱۵۸ خط) | فقط hunkهای diff |
| `brsapi/models/tsetmc.py` | فقط ناحیهٔ `NavRecordModel` با grep |
| `ingestion/parser/tsetmc_parsers.py` (۱۶۴ خط) | فقط diffstat (۶ خط) → بخش ۰۱ |
| `tests/fixtures/*` (۹ فایل JSON) | بررسی نشد → بخش‌های ۱–۳ |
| `tests/gold_desk/*` (۳ فایل، ~۱٬۲۷۴ خط) | بررسی نشد → خارج از دامنه |
| `docs/` (۲۱۸ فایل) و `docs/New folder/` (اکنون ۰ فایل) | محتوا بررسی نشد؛ فقط وجود/تعداد |
| `.env`, `.env.production`, `frontend/.env`, … | **عمداً خوانده نشد** (secret) |
| `symbol_reports/` (۴٬۱۷۴)، `json/` (۱٬۴۵۱)، `reports/` (۲۱۱)، `new_symbol_reports/` (۱۶۹) | تولیدی/data |
| `_FRONTEND_BACKEND_COPY/` (۲٬۲۶۵) | vendor/copy |
| `node_modules/`, `venv/`, `.venv/` | وابستگی خارجی |
| باینری‌ها (۱۵۹ png، ۵۴ ttf، ۴ zip، ۴ exe، ۴ pdb، pdf) | باینری |
| `docs/audits/tools/_ruff_broad.json` (۸۲٬۷۷۸ خط)، `_pattern_findings.json` (۱۳٬۶۹۴ خط) | تولیدی/حجیم |

**هیچ ادعای «همهٔ فایل‌ها بررسی شد» در این ممیزی وجود ندارد.**

---

## ۳. جدول الزامات

### ۳.۱ معیارهای پذیرش مرحلهٔ ۰ (از پرامپت)

| الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| هیچ فایل source/test یا state گیت تغییر نکرده باشد؛ فقط گزارش جدید ایجاد شود | `git diff --cached --shortstat` = `138 files / +115998 / -1447` — **دقیقاً همان مقدار ابتدای مرحله**؛ HEAD = `90597e05` بدون تغییر؛ تنها فایل افزوده `00_..._run2.md` | 🟡 **PARTIAL** | intent برآورده شده (index و HEAD بایت‌ثابت، بدون add/reset/clean/stash/commit)، اما **criterion به‌صورت تحت‌اللفظی قابل تأیید نیست**: در همان بازهٔ زمانی یک فرآیند بیرونی ۸ فایل source را تغییر داد و انتقال `docs/` را برگرداند (I13). |
| گزارش manifest وضعیت اولیهٔ Git و موانع اصلی را مستند کند | بخش‌های ۱ (سه snapshot)، ۳ (inventory)، ۸ (۱۲+۱ ایراد)، ۱۳ (۸ خطر) | ✅ **PASS** | — |
| هیچ ادعای «همهٔ فایل‌ها کامل خوانده شده» بدون manifest و شاهد درج نشود | بخش ۱۶ گزارش: manifest فایل‌به‌فایل با علامت ✅/🟡/⬜ و دلیل؛ صریحاً «هیچ ادعایی… وجود ندارد» | ✅ **PASS** | — |

### ۳.۲ وظایف اختصاصی مرحلهٔ ۰

| الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| شناسایی ریشهٔ checkout | `pwd` = `/c/Users/Iran/Desktop/temce`؛ `git rev-parse --show-toplevel` = `C:/Users/Iran/Desktop/temce` (exit 0) | ✅ PASS | — |
| ثبت HEAD، نام شاخه | `integration/golddesk-fixes`؛ `90597e05b9f4328bcd82ee819a31ba5c55413c12`؛ پیام: `feat(phase0): unify gold engine and ship fail-closed trust labels` | ✅ PASS | — |
| ثبت staged/unstaged/untracked و diffها | snapshot ۱ (۲۸۸ ورودی)، snapshot ۲ (۲۹۱)، snapshot ۳ (۱۴۸)؛ `git diff --shortstat` و `--cached --shortstat` در هر سه | ✅ PASS | — |
| فهرست فایل‌های تغییرکرده | بخش ۱.۳–۱.۵ + جدول تفکیک HEAD/index/worktree در ۱.۶ | ✅ PASS | — |
| برای فایل‌های حساس، تفاوت HEAD/index/worktree جداگانه و بدون افشای secret | جدول بخش ۱.۶: `useMarketData.ts`، `test_sync_log_repository.py`، `brsapi/repositories/base.py`، `brsapi/models/base.py`، فایل‌های env (فقط نام) | ✅ PASS | — |
| inventory با `git ls-files`: زبان/مسیر/نوع/اندازه | `13129` فایل tracked؛ توزیع پسوند (py 5091، md 4975، json 1600، tsx 680، ts 152)؛ توزیع دایرکتوری؛ تفکیک source/test/config/migration/docs/generated/vendor/binary | 🟡 **PARTIAL** | **اندازهٔ تک‌تک فایل‌ها محاسبه نشد** (پرامپت: «در صورت امکان اندازه»). گزارش خودش این را در A6 پذیرفته است. |
| شناسایی آرشیو ZIP/گزارش نشست، بدون اشتباه با checkout | بخش ۴: `docs/SESSION_REPORT_2026-09-16.zip` (۳٬۳۵۰٬۷۵۷ بایت، tracked در index)، `options-platform-architecture-fa.pdf` (۴۲۷٬۵۱۵)؛ تأکید: مبنای بررسی working tree است | ✅ PASS | — |
| گزارش‌های audit قبلی به‌عنوان claim index | بخش ۶: C1–C12 استخراج شد | ✅ PASS | ۶ ادعا (C5, C6, C8, C9, C10, C12) عامدانه تأییدنشده ماندند → بخش‌های ۱–۳ |
| غیبت `AUDIT_BATCH_001..009_FA.md` و `ROOT_CAUSE_VERIFICATION_FA.md` ثبت شود | `find` تا عمق ۳/۴ → هیچ نتیجه‌ای؛ در بخش ۶.۱ صریحاً «غیبت ثبت شد» و «حدس زده نشد» | ✅ PASS | — |
| بررسی نشانگرهای `<<<<<<<` / `>>>>>>>` | این ممیزی مجدداً اجرا کرد: `grep -rlE '^(<<<<<<<\|>>>>>>>)'` روی `apps src tests frontend/src ingestion brsapi services integrations domain core schemas repositories` → **۰ فایل** | ✅ PASS | — |
| بررسی وضعیت `apps/api/router.py` | فایل موجود (۳۱٬۰۲۴ بایت، ۷۳۶ خط، mtime `Oct 26 09:33`)؛ `ast.parse` → `parses OK`؛ `grep -c` نشانگر → `0`؛ در `git status` **غایب** = بدون تغییر | ✅ PASS | — |
| بررسی ادعای «needs_sync تست شده» و «isDataFresh اصلاح شده» — فقط مشاهده | بازرسی مستقیم کد (بخش ۵ این سند)؛ ادعاها تأیید شدند و دو عدد نادرست گزارش قبلی (۱۵ تست needs_sync / ۱۰ از ۱۵ تست فرانت) رد شد | ✅ PASS | — |
| تعیین ترتیب اجرایی بخش‌ها | بخش ۱۴: منبع/پارسر → scheduler/queue → persistence → API/cache → frontend → deployment → data quality → سایر → امنیت → تست نهایی | ✅ PASS | — |
| عدم درخواست زندهٔ BrsApi / عدم دست‌کاری cooldown | هیچ فرمان شبکه‌ای اجرا نشد؛ cooldown دست‌نخورده (لاگ `logs/brsapi_sync_20261027.log`) | ✅ PASS (BLOCKED برای تأیید زنده) | تأیید end-to-end نیازمند رفع محدودیت BrsApi است |
| عدم عملیات مخرب DB | هیچ TRUNCATE/DELETE/reset/migration اجرا نشد | ✅ PASS | — |
| عدم افشای secret | گزارش فقط **نام** فایل‌های env را دارد؛ مقادیر خوانده/چاپ نشد | ✅ PASS | — |
| گزارش در فایل، پاسخ چت کوتاه | فایل ۶۰۹ خطی موجود؛ پاسخ چت کوتاه بود | ✅ PASS | — |

---

## ۴. اصلاحات: مسیر، diff، دلیل، تست

**مرحلهٔ ۰ هیچ اصلاح کدی انجام نداد.** این با شاهد قابل تأیید است:

- `git diff --cached --shortstat` در ابتدا و انتهای مرحله یکسان: `138 files changed, 115998 insertions(+), 1447 deletions(-)`
- HEAD بدون تغییر: `90597e05…`
- هیچ `git add` / `reset` / `checkout` / `stash` / `commit` اجرا نشد
- تنها فایل ایجادشده: `AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE_run2.md`

### ۴.۱ دو تغییر **از پیش موجود** (کار نشست‌های قبلی، حفظ‌شده و دست‌نخورده)

این‌ها توسط مرحلهٔ ۰ ایجاد نشدند؛ فقط بازرسی و مستند شدند. برای رعایت الزام «برای هر اصلاح: مسیر، diff، دلیل، تست»، درج می‌شوند:

**(الف) `frontend/src/hooks/useMarketData.ts` — وضعیت: staged (`M `)، working tree = index**

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
+    // fetched must be a valid past date, not in the future or missing
+    if (fetched == null || fetched > now) return false;
+    return now - fetched <= freshnessThreshold;
+  });
+  return { data: cells, isLive: freshnessThreshold > 0 ? isDataFresh : cells.length > 0, isError, isLoading };
 }
```

- **دلیل:** بدون گارد، `now - fetched_at` برای تاریخ آینده منفی می‌شود و همیشه `<= 300000` است → دادهٔ آینده‌دار «تازه» تلقی می‌شد.
- **تست مرتبط:** `frontend/src/__tests__/useMarketData.test.tsx`
- **نتیجهٔ اجرای مجدد در این ممیزی:** `10 passed (10)`، exit 0

**(ب) `tests/unit/repositories/test_sync_log_repository.py` — وضعیت: staged (`M `)**

- diffstat: `1 file changed, 254 insertions(+), 1 deletion(-)`
- محتوا: ۱۵ تابع تست که **۱۰** تای آن `test_needs_sync_*` است و ۵ تا `test_get_sync_stats_*`
- **تست مرتبط:** خودِ همین فایل
- **نتیجهٔ اجرای مجدد:** `15 passed in 6.03s`، exit 0

### ۴.۲ تغییرات بیرونی (کار مرحلهٔ ۰ نیست — ثبت‌شده)

| فایل | وضعیت | منشأ |
|---|---|---|
| `ingestion/worker.py` | `MM` | فرآیند هم‌زمان بیرونی (mtime ۰۹:۱۷:۵۷) |
| `brsapi/models/base.py` | ` M` | mtime ۰۹:۱۹:۳۶ (`utc_now_naive`) |
| `brsapi/repositories/base.py` | ` M` | mtime ۰۹:۲۰:۲۸ (`delete_where`) |
| `brsapi/services/sync_service.py` | `MM` | mtime ۰۹:۲۱:۵۸ (`replace_filter`, `commit`) |
| `brsapi/services/query_service.py` | ` M` | — |
| `apps/api/endpoints/market.py` | ` M` | — |
| `schemas/common/responses.py` | ` M` | — |
| `docs/` ← `docs/New folder/` | انتقال برگردانده شد | ۲۱۸ → ۰ فایل در `New folder` |

---

## ۵. تأیید مستقل ادعاهای کلیدی (بازرسی مستقیم کد در این ممیزی)

| # | ادعا | شاهد بازرسی‌شده | نتیجه |
|---|---|---|---|
| V1 | شاخه `integration/golddesk-fixes` | `git branch --show-current` | ✅ تأیید |
| V2 | HEAD = `90597e05…` | `git rev-parse HEAD` | ✅ تأیید |
| V3 | `needs_sync()` در `brsapi/repositories/base.py:102` با منطق `elapsed >= interval_seconds` | `sed -n '100,115p'` — تابع در خط ۱۰۲، `return elapsed >= interval_seconds` در خط ۱۱۴ | ✅ تأیید |
| V4 | تست‌های آن فایل پاس می‌شوند | `15 passed in 6.03s`، exit 0 | ✅ تأیید |
| V5 | رفع `isDataFresh` اعمال شده | `sed -n '278,292p'` — گارد `if (fetched == null \|\| fetched > now) return false;` در خط ۲۸۶ | ✅ تأیید |
| V6 | تست فرانت ۱۰/۱۰ پاس (ادعای قبلی «۱۰ از ۱۵» نادرست بود) | `10 passed (10)`، exit 0؛ شمارش `it(` = ۱۰ | ✅ تأیید |
| V7 | `_BaseLibParser` روی خطای JSON بی‌صدا `[]` برمی‌گرداند | `library_parsers.py:97-98` — `logger.exception(...)` + `return []` | ✅ تأیید |
| V8 | الگوی falsy `or data.get(...)` در storage | `ingestion/storage/__init__.py:85-88` | ✅ تأیید |
| V9 | هیچ نشانگر conflict در source/test نیست | `grep -rlE` روی ۱۲ دایرکتوری → ۰ فایل | ✅ تأیید |
| V10 | `apps/api/router.py` تمیز و معتبر است | `ast.parse` → OK؛ ۰ نشانگر؛ غایب در `git status` | ✅ تأیید |
| V11 | اعداد inventory گزارش درست‌اند | بازمحاسبه: tracked ۱۳٬۱۲۹ / py ۵٬۰۹۱ / md ۴٬۹۷۵ / json ۱٬۶۰۰ / tsx ۶۸۰ / ts ۱۵۲ / tests ۵۲۹ / fe tests ۵۵ / migrations ۸۹ / symbol_reports ۴٬۱۷۴ / copy ۲٬۲۶۵ / json_dir ۱٬۴۵۱ | ✅ **همه دقیقاً مطابق** |
| V12 | snapshot سوم (۱۴۸ ورودی، ۱۰۲A/۳۲M/۶??/۴MM/۴ M) | snapshot ممیزی در ۰۹:۳۲: `total=148` و همان توزیع؛ `git diff --shortstat` = `8 files / +402 / -285` | ✅ تأیید و **پایدار مانده** |

---

## ۶. فرمان‌های تست، نتیجهٔ واقعی

| # | فرمان | نتیجه | موفق | ناموفق | اجرانشده | exit |
|---|---|---|---|---|---|---|
| T1 | `python -m pytest tests/unit/repositories/test_sync_log_repository.py -p no:cacheprovider --timeout=120 --timeout-method=thread -q` | `15 passed in 6.03s` | ۱۵ | ۰ | ۰ | **0** |
| T2 | `cd frontend && npx vitest run src/__tests__/useMarketData.test.tsx` | `1 file passed`، `10 passed (10)` | ۱۰ | ۰ | ۰ | **0** |
| T3 | `python -c "import ast; ast.parse(open('apps/api/router.py',...))"` | `parses OK` | ۱ بررسی | ۰ | ۰ | **0** |
| T4 | `grep -rlE '^(<<<<<<<\|>>>>>>>)' <۱۲ دایرکتوری>` | ۰ فایل | بررسی منفی موفق | — | — | **1** (بدون تطابق = انتظار) |
| T5 | بازمحاسبهٔ inventory با `git ls-files` | تمام ۱۲ عدد مطابق گزارش | ✅ | ۰ | ۰ | **0** |

**جمع تست‌های اجراشده در این ممیزی: ۲۵ تست (۱۵ backend + ۱۰ frontend) — ۲۵ موفق، ۰ ناموفق، ۰ skip.**

### ۶.۱ تست‌های اجرانشده — و چرا موفق اعلام نمی‌شوند

| تست | علت | وضعیت |
|---|---|---|
| کل مجموعهٔ `pytest tests/` | خارج از دامنهٔ مرحلهٔ ۰ | NOT RUN |
| تست‌های `-m needs_db` | PostgreSQL روی `localhost:5432` بالا نیست | **BLOCKED** |
| تست یکپارچگی DB (dedup، ON CONFLICT، migration) | همین علت | **BLOCKED** |
| زنجیرهٔ end-to-end (منبع → پارسر → DB → API → فرانت) | BrsApi در cooldown 302 + نبود PostgreSQL/Redis | **BLOCKED** |
| تست صف/worker (`jobs/`, `ingestion/worker.py`) | نیازمند Redis | **BLOCKED** |
| `npm test` کامل فرانت | خارج از دامنه | NOT RUN |
| `next build` / `docker compose` | خارج از دامنه/محیط | NOT RUN |

هیچ‌یک از موارد بالا در این سند «موفق» ثبت نشده است.

---

## ۷. حفظ تغییرات قبلی و staged

| بررسی | شاهد | نتیجه |
|---|---|---|
| index بدون تغییر نسبت به ابتدای مرحله | `138 files changed, 115998 insertions(+), 1447 deletions(-)` در ۰۹:۰۷ و ۰۹:۳۲ — یکسان | ✅ حفظ شد |
| HEAD بدون تغییر | `90597e05…` در تمام snapshotها | ✅ حفظ شد |
| عدم commit خودکار | هیچ `git commit` اجرا نشد | ✅ |
| عدم reset/clean/stash/checkout مخرب | هیچ‌کدام اجرا نشد | ✅ |
| تغییرات کاربر حذف/بازنویسی نشد | تمام ورودی‌های status که توسط این مأموریت ایجاد نشده‌اند، پابرجا هستند | ✅ |
| ⚠ تغییر بیرونی | ۸ فایل source و ساختار `docs/` توسط فرآیند هم‌زمان تغییر کرد | ثبت شد؛ **قابل انتساب به این مأموریت نیست** |

---

## ۸. وضعیت دسترسی خارجی

| سرویس | وضعیت | شاهد |
|---|---|---|
| BrsApi (زنده) | **BLOCKED** | `logs/brsapi_sync_20261027.log`: `BrsApi key in 302-cooldown (430s left…)` — هیچ درخواستی ارسال نشد و cooldown دست‌نخورده است |
| PostgreSQL | **BLOCKED** | `logs/brsapi_sync_20261028.log`: `RuntimeError: Cannot connect to PostgreSQL database … Tried: localhost:5432/market` |
| Redis | تأییدنشده | سرویس محلی در دسترس نیست |
| Docker | NOT RUN | خارج از دامنه |

---

## ۹. نتیجهٔ نهایی ممیزی

# ⛔ PARTIAL

**دلیل:** هستهٔ مرحلهٔ ۰ (ثبت وضعیت Git، inventory، claim index، بررسی conflict/روتر، تأیید مستقل ادعاها، ترتیب اجرایی) انجام و با شاهد کد و خروجی تست تأیید شده است. اما سه معیار به‌طور کامل برآورده نشده‌اند:

1. **A1 (عدم تغییر source/state)** — intent برآورده شده (index و HEAD بایت‌ثابت، فقط گزارش اضافه شد)، ولی چون یک فرآیند بیرونی در همان بازه ۸ فایل source را تغییر داد و انتقال `docs/` را برگرداند، «عدم تغییر» را نمی‌توان به‌صورت مطلق تأیید کرد. تا تثبیت working tree، این معیار PARTIAL است.
2. **inventory با اندازه** — توزیع کامل است ولی اندازهٔ تک‌فایل محاسبه نشد.
3. **۶ ادعای claim index** (C5، C6، C8، C9، C10، C12) عامدانه تأییدنشده ماندند و به بخش‌های ۱–۳ موکول شده‌اند.

مرحله **FAIL** نیست: هیچ آزمونی نقص جدیدی نشان نداد و هیچ تست شکست‌خورده‌ای پنهان نشده است. مرحله **BLOCKED** هم نیست: مانع بیرونی، تکمیل خود مرحلهٔ ۰ را متوقف نکرد؛ فقط تأیید زندهٔ زنجیرهٔ داده را به مراحل بعد می‌سپارد.

---

## ۱۰. فهرست دقیق کارهای باقی‌مانده

### ۱۰.۱ مسدودکننده‌های تثبیت (پیش‌شرط شروع مرحلهٔ ۱)

1. **توقف نویسندهٔ هم‌زمان** روی این checkout (VS Code + نشست عامل دیگر) و گرفتن snapshot تأییدشده پس از توقف.
2. **تصمیم کاربر دربارهٔ ساختار `docs/`**: `docs/` تخت (وضعیت فعلی) یا `docs/New folder/` (وضعیت ابتدای جلسه). سپس تثبیت آن با `git mv` یا commit صریح.
3. **تثبیت index**: بازبینی ۱۰۲ فایل `A ` و ۳۲ فایل `M ` و ساختن یک commit نقطه‌ای (فقط با اجازهٔ صریح کاربر) تا baseline پایدار شود.
4. **پاک‌سازی index از مصنوعات**: `services/market_service.py.bak`، `frontend/src/app/gold/components/SummarySection.tsx.bak`، `z.py.bak`، `apply_fixes.py`، `fix_avg.py`، `fix_function.py`، `fix_sector.py`، `docs/audits/tools/_ruff_broad.json`، `_pattern_findings.json`.
5. **رفع gitlink یتیم `InkGist`** (mode `160000` بدون `.gitmodules`) — تصمیم: حذف از index یا افزودن `.gitmodules`.

### ۱۰.۲ تکمیل‌های این مرحله

6. **محاسبهٔ اندازهٔ فایل‌ها** برای inventory (حداقل برای دایرکتوری‌های اجرایی: `apps/`, `brsapi/`, `ingestion/`, `src/`, `services/`, `domain/`, `core/`, `frontend/src/`) تا معیار «اندازه» کامل شود.
7. **تأیید ۶ ادعای باقی‌ماندهٔ claim index** (C5 تفکیک empty/error، C6 ترتیب dedup، C8 نوع `NavRecordModel.fetched_at`، C9 رفتار Redis-down، C10 auth صف، C12 پروکسی) — در بخش‌های مربوطه.

### ۱۰.۳ مسدودهای محیطی (برای مراحل بعد)

8. **PostgreSQL** بالا بیاید تا تست‌های `needs_db` و یکپارچگی DB اجرا شوند.
9. **Redis** بالا بیاید تا رفتار صف/worker قابل آزمون شود.
10. **BrsApi**: پس از پایان cooldown، تأیید زندهٔ زنجیرهٔ داده — تا آن زمان هر نتیجه در این حوزه **BLOCKED** ثبت می‌شود.

### ۱۰.۴ شروع مرحلهٔ بعد

11. شروع **بخش ۰۱ (منبع و پارسر)** فقط پس از بندهای ۱، ۲ و ۳.
