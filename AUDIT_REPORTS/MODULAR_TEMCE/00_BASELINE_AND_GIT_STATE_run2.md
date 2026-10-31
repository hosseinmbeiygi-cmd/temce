# گزارش ۰۰ (اجرای دوم) — وضعیت واقعی Git، موجودی پروژه و برنامهٔ اجرای بخش‌ها

> این فایل نسخهٔ **اجرای دوم** است. فایل قبلی `AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE.md` overwrite **نشده** و دست‌نخورده باقی مانده است.

---

## ۰. شناسنامهٔ اجرا

| مورد | مقدار |
|---|---|
| تاریخ اجرا | ۲۰۲۶-۱۰-۲۸ (2026-10-28) |
| زمان شروع بررسی | حدود ۰۹:۰۵ محلی (+۰۳:۳۰) |
| زمان snapshot پایانی | `2026-10-28T05:57:58Z` = ۰۹:۵۷:۵۸ محلی (سه snapshot ثبت شد؛ بخش ۱.۵) |
| سیستم عامل | win32 (bash / Git Bash) |
| مفسر پایتون مورد استفاده | `C:\Users\Iran\Desktop\temce\venv\Scripts\python.exe` — Python 3.11.9، pytest 9.1.1 |
| مفسر جایگزین موجود | `.venv/Scripts/python.exe` — **pytest نصب ندارد** |
| Node / Vitest | Vitest v4.1.9 در `frontend/` |
| ابزارهای بررسی | git، pytest، vitest، grep، ast (بدون اتصال شبکه) |
| درخواست زندهٔ BrsApi | **انجام نشد** (ممنوع) |
| عملیات مخرب Git/DB | **انجام نشد** (هیچ reset/clean/stash/checkout/TRUNCATE/DELETE) |

---

## ۱. ریشه، شاخه، کامیت و وضعیت اولیهٔ Git

### ۱.۱ ریشهٔ checkout

```
$ pwd
/c/Users/Iran/Desktop/temce

$ git rev-parse --show-toplevel
C:/Users/Iran/Desktop/temce
```

ریشهٔ مخزن: `C:/Users/Iran/Desktop/temce` — تنها یک مخزن Git فعال است (`git rev-parse` موفق، exit 0).

### ۱.۲ branch / HEAD

| مورد | مقدار |
|---|---|
| شاخهٔ فعلی | `integration/golddesk-fixes` |
| HEAD کامل | `90597e05b9f4328bcd82ee819a31ba5c55413c12` |
| پیام HEAD | `feat(phase0): unify gold engine and ship fail-closed trust labels` |
| reflog (۵ مورد آخر) | `90597e05` → `77e58e1f` → `c18b616b` → `dc4a6f79` → `a1602747` |

**تأیید مستقل ادعای نشست قبلی دربارهٔ شاخه: درست است.** شاخه واقعاً `integration/golddesk-fixes` است و HEAD همان کامیت ادعاشده است.

### ۱.۳ snapshot اولیه (حدود ۰۹:۰۷)

`git status --short --branch` → `## integration/golddesk-fixes`

شمارش status (۲۸۸ ورودی):

| کد | تعداد | معنا |
|---|---|---|
| ` D` (space+D) | ۱۴۷ | حذف‌شده در working tree، بدون stage |
| `AD` | ۶۰ | در index اضافه شده، در working tree حذف شده |
| `A ` | ۴۲ | فایل جدید stage‌شده |
| `M ` | ۳۴ | تغییر stage‌شده، working tree برابر index |
| `MD` | ۲ | در index تغییر کرده، در working tree حذف شده |
| `??` | ۲ | پوشه‌های untracked سطح‌بالا |
| ` m` | ۱ | gitlink با محتوای تغییریافته (`InkGist`) |

diffها:

```
git diff --shortstat          → 210 files changed, 146566 deletions(-)
git diff --cached --shortstat → 138 files changed, 115998 insertions(+), 1447 deletions(-)
```

untracked: **۲۱۵** فایل → `209` در `docs/New folder/` + `6` در `AUDIT_REPORTS/MODULAR_TEMCE/`.
(به‌علاوه ۹ فایل `__pycache__/*.pyc` داخل `docs/New folder/` که ignored هستند.)

### ۱.۴ snapshot دوم (۰۹:۲۲:۳۴) — و کشف مهم: working tree پایدار نیست

```
## integration/golddesk-fixes
HEAD = 90597e05b9f4328bcd82ee819a31ba5c55413c12   (بدون تغییر)

291 entries:
  147  D
   60 AD
   42  A
   31 M
    3 MM      ← جدید نسبت به snapshot اولیه
    4  M      ← جدید نسبت به snapshot اولیه (قبلاً فقط ۱ بود)
    2 MD
    2 ??

git diff --shortstat          → 216 files changed, 283 insertions(+), 146767 deletions(-)
git diff --cached --shortstat → 138 files changed, 115998 insertions(+), 1447 deletions(-)   (بدون تغییر)
```

**در طول همین جلسه، فایل‌های source در working tree توسط فرآیندی بیرونی تغییر کردند.** شاهد قطعی — mtime فایل‌ها:

| فایل | mtime |
|---|---|
| `ingestion/worker.py` | 2026-10-28 **09:17:57** |
| `brsapi/models/base.py` | 2026-10-28 **09:19:36** |
| `brsapi/repositories/base.py` | 2026-10-28 **09:20:28** |
| `brsapi/services/sync_service.py` | 2026-10-28 **09:21:58** |

این زمان‌ها **داخل بازهٔ اجرای این مأموریت** (۰۹:۰۵ تا ۰۹:۲۲) هستند. محتوای diff هم کد واقعی و جدید است، نه تغییر line-ending:

- `brsapi/models/base.py`: اضافه‌شدن `from core.time import utc_now_naive` و جایگزینی `default=datetime.now` با `default=utc_now_naive` در `RawPayloadModel.fetched_at` و `SyncLogModel.started_at`.
- `brsapi/repositories/base.py`: اضافه‌شدن متد جدید `delete_where(column, value)` به `BulkUpsertRepository`، پارامتر `fetched_at=` صریح در `RawPayloadRepository`، و لاگ `rowcount`.
- `brsapi/services/sync_service.py`: پارامتر جدید `replace_filter`، دو فراخوانی `await sess.commit()`، و جایگزینی `repo.truncate()` با `repo.delete_where()` در حالت فیلترشده.
- `ingestion/worker.py`: ۳۷۷ خط تغییر بین index و working tree.

فرآیندهای مرتبط روی ماشین: VS Code با `copilot-runtime.exe` و چند `OpenConsole.exe` فعال (خروجی `ps -W`). یعنی یک نشست/عامل دیگر هم‌زمان روی همین checkout کار می‌کند.

> **نتیجهٔ عملی برای بخش‌های بعدی:** هر snapshot از این checkout حداکثر چند دقیقه اعتبار دارد. قبل از هر اصلاح، باید دوباره `git status` گرفته شود و diff همان فایل در همان لحظه بررسی شود. این گزارش «حقیقت لحظه‌ای» است، نه وضعیت پایدار.

### ۱.۵ snapshot سوم (۰۹:۵۷:۵۸) — فرآیند بیرونی انتقال `docs/` را **بازگرداند**

در فاصلهٔ بین ۰۹:۲۷ و ۰۹:۵۸، همان نویسندهٔ هم‌زمان تغییر بزرگ دیگری در working tree ایجاد کرد:

| سنجه | snapshot دوم (۰۹:۲۲) | snapshot سوم (۰۹:۵۷) |
|---|---|---|
| کل ورودی‌های status | ۲۹۱ | **۱۴۸** |
| ` D` (حذف‌های `docs/`) | ۱۴۷ | **۰** |
| `AD` | ۶۰ | **۰** |
| `A ` | ۴۲ | **۱۰۲** |
| `M ` | ۳۱ | ۳۲ |
| ` M` | ۴ | ۴ |
| `MM` | ۳ | ۴ |
| `??` | ۲ | ۶ |
| untracked | ۲۱۵ | **۱۳** |
| `git diff --shortstat` (worktree) | ۲۱۶ فایل / ۱۴۶٬۷۶۷ حذف | **۸ فایل / ۴۰۲ درج / ۲۸۵ حذف** |
| `git diff --cached --shortstat` | ۱۳۸ / ۱۱۵٬۹۹۸ / ۱٬۴۴۷ | **۱۳۸ / ۱۱۵٬۹۹۸ / ۱٬۴۴۷ (بدون تغییر)** |

**آنچه روی دیسک اتفاق افتاد:**

- `docs/New folder/` از **۲۱۸ فایل به ۰ فایل** رسید (پوشه خالی مانده).
- فایل‌های اصلی `docs/` **بازگشتند**: ۱۰۰ فایل در سطح اول، ۲۱۸ فایل در کل درخت `docs/`.
- یعنی جابه‌جایی `docs/` → `docs/New folder/` که در snapshot اولیه وجود داشت، توسط همان فرآیند بیرونی **لغو/برگردانده شد**.
- ۶۰ فایل `AD` اکنون `A ` هستند (نسخهٔ worktree دوباره موجود است).
- فایل جدید `AUDIT_REPORTS/MODULAR_TEMCE/04_BACKEND_API_AGGREGATION_CACHE.md` در **۰۹:۲۷:۲۱** ساخته شد — مدرک دیگری بر فعال بودن یک عامل/نشست دیگر.
- فایل‌های جدیداً drift‌شده: `apps/api/endpoints/market.py`, `schemas/common/responses.py`.

**این تغییر توسط این مأموریت انجام نشد.** تمام فرمان‌های این جلسه read-only بودند (`git status`, `git diff`, `ls`, `find`, `grep`, `wc`, `md5sum`, `pytest`, `vitest`, `ast.parse`) و هیچ‌کدام فایل جابه‌جا یا حذف نمی‌کنند.

> **هشدار برای کاربر:** سازمان‌دهی `docs/` که در ابتدای این جلسه در working tree وجود داشت، در پایان جلسه روی دیسک نیست. محتوای فایل‌ها از بین نرفته (در `docs/` بازگشته‌اند)، اما ساختار موردنظر شما بازگردانده شده است. پیش از شروع بخش ۰۱ باید مشخص کنید کدام ساختار (`docs/` مسطح یا `docs/New folder/`) مطلوب است.

### ۱.۶ تفکیک HEAD / index / working-tree برای فایل‌های حساس

| فایل | HEAD | index | working tree | جمع‌بندی |
|---|---|---|---|---|
| `frontend/src/hooks/useMarketData.ts` | نسخهٔ باگ‌دار | **حاوی رفع باگ** | برابر index | تغییر فقط در index (stage شده) |
| `tests/unit/repositories/test_sync_log_repository.py` | نسخهٔ قدیمی | ۱۵ تست | برابر index | تغییر فقط در index |
| `brsapi/repositories/base.py` | نسخهٔ HEAD | برابر HEAD | **تغییر جدید بیرونی** | تغییر فقط در working tree |
| `brsapi/models/base.py` | نسخهٔ HEAD | برابر HEAD | **تغییر جدید بیرونی** | تغییر فقط در working tree |
| `.env`, `.env.production`, `frontend/.env` | tracked نیست | — | موجود، ignored | **محتوا خوانده نشد** (فقط نام) |

secret/token/کلید در این گزارش چاپ نشده است؛ فقط **نام** متغیرها و **وجود/نبود** آن‌ها ثبت شده. فایل‌های env روی دیسک (با نام): `.env`, `.env.bak.1790980646`, `.env.production`, `frontend/.env`, `iran_market_data/.env`, `_FRONTEND_BACKEND_COPY/frontend/.env`, `frontend/.next/standalone/frontend/.env`. تنها فایل‌های env tracked: `.env.example` و `frontend/.env.sentry.example` (template، بدون اعتبارنامه).

---

## ۲. هدف و مرز دامنه

**هدف:** ثبت وضعیت واقعی مخزن پیش از هر اصلاح، تا کارهای قبلی کاربر گم نشود و بخش‌های بعدی روی نسخهٔ درست بنا شوند.

**در دامنه:** شناسایی ریشه/branch/HEAD؛ ثبت staged/unstaged/untracked؛ diffst؛ inventory فایل‌ها؛ شناسایی آرشیوها؛ خواندن گزارش‌های audit قبلی به‌عنوان claim index؛ بررسی نشانگرهای merge conflict؛ بررسی `apps/api/router.py`؛ تأیید مستقل چهار ادعای نشست قبلی؛ تعیین ترتیب اجرای بخش‌ها.

**خارج از دامنه (طبق پرامپت):** هیچ اصلاح کد، هیچ رفع باگ، هیچ تغییر در تست یا state گیت، هیچ درخواست زندهٔ BrsApi، هیچ عملیات DB، هیچ reset cooldown.

**نتیجه:** تنها فایل ایجادشده توسط این مأموریت همین گزارش است. هیچ فایل source/test/config تغییر نکرد.

---

## ۳. موجودی پروژه (inventory)

### ۳.۱ اعداد کلی

| سنجه | مقدار |
|---|---|
| فایل‌های tracked (`git ls-files`) | **۱۳٬۱۲۹** |
| فایل‌های untracked (بدون ignored) | ۲۱۵ |
| فایل تست پایتون زیر `tests/` | ۵۲۹ |
| فایل تست فرانت (`*.test.tsx?`) | ۵۵ |
| فایل migration | ۸۹ |

### ۳.۲ توزیع بر اساس پسوند (tracked)

| پسوند | تعداد | نوع غالب |
|---|---|---|
| `.py` | ۵٬۰۹۱ | source / test |
| `.md` | ۴٬۹۷۵ | docs / generated reports |
| `.json` | ۱٬۶۰۰ | config / data / generated |
| `.tsx` | ۶۸۰ | source فرانت |
| `.png` | ۱۵۹ | binary (تصویر) |
| `.ts` | ۱۵۲ | source / type |
| `.txt` | ۱۲۴ | docs / evidence |
| `.ttf` / `.woff2` | ۵۴ / ۱۶ | binary (فونت) |
| `.yaml` / `.yml` | ۳۲ / ۱۵ | config |
| `.csv` | ۱۹ | data |
| `.zip` | ۴ | binary (آرشیو) |
| `.exe` / `.pdb` | ۴ / ۴ | binary |
| `.bak` | ۷ | **بقایای پشتیبان — باید از commit دور بماند** |

### ۳.۳ توزیع بر اساس دایرکتوری سطح‌بالا (tracked)

| دایرکتوری | تعداد | نوع |
|---|---|---|
| `symbol_reports/` | ۴٬۱۷۴ | **generated** (گزارش‌های تولیدی) |
| `_FRONTEND_BACKEND_COPY/` | ۲٬۲۶۵ | **vendor/copy** — کپی کل backend+frontend |
| `json/` | ۱٬۴۵۱ | **generated/data** |
| `tests/` | ۵۷۶ | test |
| `.agents/` | ۵۳۶ | tooling/config (skills) |
| `frontend/` | ۵۳۵ | source فرانت |
| `scripts/` | ۳۰۹ | tooling |
| `backtesting/` | ۲۹۲ | source |
| `services/` | ۲۷۲ | source |
| `providers/` | ۲۴۵ | source |
| `domain/` | ۲۲۰ | source |
| `reports/` | ۲۱۱ | **generated** |
| `docs/` | ۲۰۹ | docs (اکنون به `docs/New folder/` منتقل شده) |
| `apps/` | ۱۸۱ | source (API) |
| `new_symbol_reports/` | ۱۶۹ | **generated** |
| `core/` | ۱۶۹ | source |
| `(root)` | ۱۴۶ | config/docs/اسکریپت |

**تفکیک اجرایی از غیراجرایی:**
- **منطق اجرایی پروژه:** `apps/`, `brsapi/`, `ingestion/`, `src/gold_desk/`, `services/`, `domain/`, `core/`, `providers/`, `repositories/`, `schemas/`, `jobs/`, `integrations/`, `frontend/src/`.
- **تولیدی/غیراجرایی (باید از تحلیل و از commit دور بماند):** `symbol_reports/`, `new_symbol_reports/`, `reports/`, `json/`, `analysis_outputs*/`, `test_results/`, `audit_out/`, `code_dump/`, `_audit_out/`, `_base_wt*/`, `_7c_gate/`, `_7d_gate/`, `_8_gate/`, `docs/audits/tools/_pattern_findings.json`, `docs/audits/tools/_ruff_broad.json`.
- **vendor/copy:** `_FRONTEND_BACKEND_COPY/` یک کپی کامل از backend و frontend است؛ **نباید** با source اصلی اشتباه گرفته شود.

---

## ۴. آرشیو ZIP و نسخهٔ تحت بررسی

**نسخهٔ تحت بررسی:** working tree همین checkout در `C:/Users/Iran/Desktop/temce` روی شاخهٔ `integration/golddesk-fixes` با HEAD `90597e05`.

**آرشیوهای موجود (فقط شناسایی، بدون باز کردن/جایگزینی checkout):**

| مسیر | وضعیت | اندازه |
|---|---|---|
| `docs/SESSION_REPORT_2026-09-16.zip` | tracked در index (`100644 146d63eb`)، در working tree حذف شده (چون `docs/` منتقل شده) | ۳٬۳۵۰٬۷۵۷ بایت (~3.2MB) |
| `docs/New folder/SESSION_REPORT_2026-09-16.zip` | در snapshot اولیه کپی روی دیسک بود؛ **در snapshot سوم `docs/New folder/` خالی است** | ۳٬۳۵۰٬۷۵۷ بایت |
| `docs/options-platform-architecture-fa.pdf` | tracked، حذف‌شده در working tree | ۴۲۷٬۵۱۵ بایت |

این آرشیوها **مبنای بررسی نیستند**. مبنای بررسی صرفاً working tree است. گزارش‌های ZIP فقط به‌عنوان «سرنخ» در claim index آمده‌اند.

---

## ۵. بررسی merge conflict و وضعیت `apps/api/router.py`

### ۵.۱ نشانگرهای conflict

اسکن `^(<<<<<<<|>>>>>>>)` روی `apps/ src/ tests/ frontend/src/ ingestion/ brsapi/ services/ integrations/`:

```
grep -rlE '^(<<<<<<<|>>>>>>>)' ...  →  خروجی خالی
grep_exit=1        (۱ = هیچ تطابقی پیدا نشد)
تعداد فایل دارای نشانگر: 0
```

**نتیجه: هیچ نشانگر merge conflict در هیچ فایل source/test وجود ندارد.** بررسی اولیه روی کل درخت (شامل `docs/`, `node_modules`, `.venv`) به‌دلیل حجم، timeout شد؛ ولی روی دامنهٔ اجرایی کامل انجام و منفی بود.

### ۵.۲ وضعیت `apps/api/router.py`

| سنجه | مقدار |
|---|---|
| وجود فایل | بله — `apps/api/router.py`، ۷۳۶ خط، ۳۱٬۰۲۴ بایت |
| در `git status` | **حاضر نیست** → فایل در index و working tree با HEAD یکسان است |
| نشانگر conflict | ندارد |
| بررسی صحت syntax | `ast.parse(...)` → `router.py parses OK` |

**نتیجه: `apps/api/router.py` تمیز است، conflict ندارد، و هیچ تغییری روی آن در جریان نیست.** در این مرحله تغییری روی آن اعمال نشد.

---

## ۶. Claim index — ادعاهای گزارش‌های audit قبلی

### ۶.۱ وضعیت دسترسی به گزارش‌های نشست‌های قدیمی

| فایل | در checkout موجود است؟ |
|---|---|
| `AUDIT_BATCH_001_FA.md` … `AUDIT_BATCH_009_FA.md` | **خیر** — با `find` تا عمق ۳/۴ پیدا نشد |
| `ROOT_CAUSE_VERIFICATION_FA.md` | **خیر** — پیدا نشد |
| `AUDIT_*_FA.md` | **خیر** — هیچ موردی پیدا نشد |

**غیبت ثبت شد.** برای پیدا کردنشان حدس زده نشد و جست‌وجوی خارج از پروژه انجام نشد. (فایل `DATA_500_PROBLEMS_REPORT.md` در root و `AUDIT_REPORTS/MODULAR_TEMCE/*` موجودند.)

گزارش‌های audit موجود که به‌عنوان claim index خوانده شدند:
`00_BASELINE_AND_GIT_STATE.md`، `01_MARKET_SOURCE_AND_PARSERS.md`، `02_SCHEDULER_WORKERS_QUEUES.md`، `03_DATABASE_STORAGE_REPOSITORIES.md` (فهرست سرفصل‌ها)، `03_..._run2.md` (فهرست سرفصل‌ها)، `QA_STAGE_3.md`.

### ۶.۲ ادعاهای مرتبط با «دریافت داده» (استخراج‌شده، بدون اثبات کامل در این مرحله)

| # | ادعا | منبع |
|---|---|---|
| C1 | `needs_sync()` در `brsapi/repositories/base.py:102` درست است و ۱۵ تست دارد | 00, 03_r2 |
| C2 | رفع باگ `isDataFresh` (رد کردن تاریخ آینده) در `useMarketData.ts` اعمال شده | 00, QA_3 |
| C3 | BrsApi در cooldown 302 است و هیچ درخواست زنده‌ای انجام نشده | 00, 01, 03_r2 |
| C4 | `_BaseLibParser` روی خطای JSON بی‌صدا `[]` برمی‌گرداند و خطا را منتشر نمی‌کند | 01, 02 |
| C5 | «موفق ولی خالی» از «خطا» قابل تفکیک نیست → `success=True, items_count=0` | 01, 02 |
| C6 | dedup در `ingestion/worker.py` **بعد** از نوشتن موفق علامت می‌خورد | 02 |
| C7 | الگوی falsy در `ingestion/storage/__init__.py`: `first_price or open` قیمت صفر را دور می‌زند | 03_r2, QA_3 |
| C8 | `NavRecordModel.fetched_at` از نوع String است نه DateTime | 03_r2, QA_3 |
| C9 | اگر Redis پایین باشد، job اجرا نمی‌شود و scheduler فقط in-memory کار می‌کند | 02 |
| C10 | اگر `job_queue_token` تنظیم نشده باشد، بررسی auth روی پیام‌های صف رد می‌شود | 02 |
| C11 | جدول inventory: «~۲۴۳ فایل کامل خوانده شد از ~۳۱۰» | 00 |
| C12 | کلاینت‌های HTTP پروکسی را bypass می‌کنند (اتصال مستقیم) | 02 (بر پایهٔ لاگ) |

در این مرحله C1، C2، C3 و بخشی از C4/C7/C8 بررسی شد (بخش ۷). سپس **هر شش ادعای باقی‌مانده (C5، C6، C8، C9، C10، C12) در پیوست ب (بخش ۱۸) تأیید یا رد شدند.**

---

## ۷. یافته‌های تأییدشده در برابر فرضیه‌ها

### ۷.۱ تأییدشده (با شاهد `path:line` و فرمان اجراشده)

| مورد | ادعا | نتیجه | شاهد |
|---|---|---|---|
| V1 | شاخه `integration/golddesk-fixes` است | ✅ تأیید | `git branch --show-current` |
| V2 | HEAD = `90597e05…` | ✅ تأیید | `git rev-parse HEAD` |
| V3 | `needs_sync()` در `brsapi/repositories/base.py:102` وجود دارد و منطق `elapsed >= interval_seconds` دارد | ✅ تأیید | `brsapi/repositories/base.py:102-112` |
| V4 | فایل تست `tests/unit/repositories/test_sync_log_repository.py` تغییر کرده و stage شده | ✅ تأیید | `git status` → `M `؛ `git diff --cached --stat` → `255 +-` |
| V5 | تست‌های آن فایل پاس می‌شوند | ✅ تأیید | `15 passed in 13.94s`، exit 0 |
| V6 | رفع `isDataFresh` در `useMarketData.ts` اعمال شده | ✅ تأیید | `useMarketData.ts:281-289` |
| V7 | BrsApi در cooldown 302 است | ✅ تأیید از لاگ | `logs/brsapi_sync_20261027.log`: `BrsApi key in 302-cooldown (430s left…)` |
| V8 | `_BaseLibParser` روی خطای parse بی‌صدا `[]` برمی‌گرداند | ✅ تأیید | `ingestion/parser/library_parsers.py:97-98` |
| V9 | الگوی falsy `or data.get(...)` در storage وجود دارد | ✅ تأیید | `ingestion/storage/__init__.py:85-88` |
| V10 | `apps/api/router.py` conflict ندارد و معتبر است | ✅ تأیید | `ast.parse` → OK؛ ۷۳۶ خط |
| V11 | هیچ نشانگر `<<<<<<<` در source/test نیست | ✅ تأیید | `grep -rlE` → صفر فایل |
| V12 | `docs/` به `docs/New folder/` منتقل شده بود و در لحظهٔ بررسی هیچ محتوایی از دست نرفته بود | ✅ تأیید در snapshot اولیه/دوم، سپس **لغو شد** | ۱۴۷ + ۶۰ فایل بررسی شد؛ `MISSING=0` در ۰۹:۲۲. سپس `docs/New folder/` به ۰ فایل رسید و `docs/` بازگشت (بخش ۱.۵) |

### ۷.۲ ردشده (ادعای قبلی نادرست بود)

| مورد | ادعای قبلی | واقعیت |
|---|---|---|
| R1 | «`useMarketData.test.tsx` — ۱۰ از ۱۵ تست پاس می‌شود؛ اجرای کامل محدود به مشکل محیط» | فایل **فقط ۱۰ تست** دارد و **هر ۱۰ تست پاس می‌شوند** (`10 passed`, exit 0). عدد «۱۵» وجود ندارد. |
| R2 | «۱۵ تست `needs_sync()` اضافه شد» | در فایل **۱۵ تست کل** هست، که **۱۰** تای آن `needs_sync` است و **۵** تا `get_sync_stats`. عبارت «۱۵ تست needs_sync» دقیق نیست. |
| R3 | «~۲۴۳ فایل از ~۳۱۰ فایل کامل خوانده شد» (جدول inventory گزارش 00) | با ۱۳٬۱۲۹ فایل tracked و بدون manifest فایل‌به‌فایل، این ادعا **قابل اثبات نیست**. در همین گزارش هیچ ادعای «همه‌چیز خوانده شد» مطرح نمی‌شود. |
| R4 | «`useMarketData.ts` تغییر working-tree است» (گزارش 00، بخش Git Status Summary) | این تغییر **staged** است (`M `)، نه unstaged. |

### ۷.۳ تأییدنشده / نیازمند بررسی در بخش‌های بعدی

**به‌روزرسانی (پیوست ب / بخش ۱۸):** C5، C6، C8، C9، C10 و C12 اکنون بررسی شده‌اند — پنج مورد تأیید و C9 بخشاً رد شد (ایراد جدید I16).

تنها مورد باقی‌مانده: **C11** (ادعای «~۲۴۳ فایل از ~۳۱۰ کامل خوانده شد») و صحت ادعای «همهٔ تست‌ها با `-v` اجرا شدند» — قابل بازسازی نیستند و همچنان تأییدنشده می‌مانند.

---

## ۸. جدول ایرادها (وضعیت baseline)

| # | شدت | ایراد | شاهد | روش بازتولید | اثر |
|---|---|---|---|---|---|
| I1 | **بحرانی** | یک نویسندهٔ هم‌زمان در حال تغییر working tree است | mtime: `brsapi/models/base.py` ۰۹:۱۹:۳۶، `brsapi/repositories/base.py` ۰۹:۲۰:۲۸، `brsapi/services/sync_service.py` ۰۹:۲۱:۵۸، `ingestion/worker.py` ۰۹:۱۷:۵۷ | `git status --porcelain` دو بار با فاصلهٔ ۱۵ دقیقه | هر تحلیل/اصلاح ممکن است روی نسخهٔ قدیمی انجام شود؛ احتمال از دست رفتن یا تداخل تغییرات |
| I2 | بالا | `InkGist` یک gitlink بدون `.gitmodules` است | `git ls-files -s InkGist` → `160000 cc8166…`؛ `git submodule status` → `fatal: no submodule mapping found`؛ `.gitmodules` وجود ندارد | `git submodule status` | checkout/clone تازه نمی‌تواند این مسیر را بازسازی کند؛ status همیشه ` m` می‌ماند |
| I3 | بالا | انتقال `docs/` به `docs/New folder/` در snapshot اولیه در Git به‌صورت حذف+untracked دیده می‌شد، نه rename — و سپس توسط فرآیند بیرونی **لغو شد** | snapshot اول: `git status` → ۱۴۷ ` D` + ۲۰۹ untracked؛ snapshot سوم: `find "docs/New folder" -type f` → ۰ | `git status --short` و `find docs` در دو زمان مختلف | ساختار موردنظر کاربر روی دیسک نیست؛ خطر commit اشتباه که docs را از مخزن پاک کند (کمتر شده چون فایل‌ها اکنون در جای اصلی هستند) |
| I4 | متوسط | در snapshot دوم، ۶۰ فایل `AD` فقط در index و در کپی `docs/New folder/` بودند | `git status` → ۶۰ `AD`؛ کپی‌ها تأیید شد (`MISSING=0`) | حلقهٔ بررسی وجود کپی | **در snapshot سوم رفع شد:** فایل‌ها دوباره در worktree حاضرند و `AD` به `A ` تبدیل شده؛ ولی خطر در صورت بازنویسی index باقی است |
| I13 | **بحرانی** | سازمان‌دهی `docs/` که در ابتدای جلسه در working tree بود، توسط فرآیند بیرونی برگردانده شد | `find "docs/New folder" -type f` → ۰ (قبلاً ۲۱۸)؛ `find docs -maxdepth 1 -type f` → ۱۰۰ (قبلاً ۰)؛ mtime عوض‌شده | مقایسهٔ `ls docs` در ۰۹:۰۷ و ۰۹:۵۸ | کار قبلی کاربر در working tree از بین رفت (محتوا نه، ساختار بله) |
| I5 | متوسط | فایل‌های پشتیبان `.bak` stage شده‌اند و آمادهٔ commit هستند | `git ls-files --cached \| grep '\.bak$'` → `services/market_service.py.bak`، `frontend/src/app/gold/components/SummarySection.tsx.bak`، `z.py.bak`، ۴ مورد در `_FRONTEND_BACKEND_COPY/` | همان فرمان | آلودگی مخزن با کد مرده/تکراری |
| I6 | متوسط | اسکریپت‌های وصلهٔ موردی در root stage شده‌اند | `apply_fixes.py` (۸٬۴۷۴ بایت)، `fix_avg.py`، `fix_function.py`، `fix_sector.py` — همه `A ` | `git status --short` | کد یک‌بارمصرف وارد تاریخچه می‌شود |
| I7 | متوسط | مصنوعات بزرگ/تولیدی stage شده‌اند | `docs/audits/tools/_ruff_broad.json` (۸۲٬۷۷۸ خط)، `_pattern_findings.json` (۱۳٬۶۹۴ خط)، `docs/SESSION_REPORT_2026-09-16.zip` (۳٫۲MB باینری)، `docs/mermaid-preview.html` (۳٬۷۲۲ خط)، `docs/dep_graph.json` (۳٬۵۸۰ خط) | `git diff --cached --stat` | حجم زیاد مخزن، diff غیرقابل‌مرور |
| I8 | متوسط | PostgreSQL بالا نیست؛ sync روزانه fail می‌شود | `logs/brsapi_sync_20261028.log`: `RuntimeError: Cannot connect to PostgreSQL database … Tried: localhost:5432/market`، `exit=1` | خواندن لاگ | هیچ تست DB/یکپارچگی داده در این محیط اجرا نمی‌شود |
| I9 | متوسط | BrsApi در cooldown 302 است | `logs/brsapi_sync_20261027.log` | خواندن لاگ | مسیر end-to-end قابل تأیید نیست |
| I10 | پایین | دو مفسر پایتون با قابلیت‌های متفاوت روی مخزن هست | `.venv/Scripts/python.exe` → `No module named pytest` (exit 1)؛ `venv/Scripts/python.exe` → pytest 9.1.1 | اجرای pytest با هر دو | اجرای تست با مفسر اشتباه، نتیجهٔ گمراه‌کننده |
| I11 | پایین | `--reporter=basic` در Vitest 4 حذف شده | خطای `Failed to load custom Reporter from basic`، exit 1 | `npx vitest run … --reporter=basic` | دستورهای قدیمی مستندشده کار نمی‌کنند |
| I12 | پایین | ادعاهای عددی گزارش‌های قبلی دقیق نیستند | R1، R2، R3، R4 در بخش ۷.۲ | مقایسهٔ گزارش با فایل واقعی | تصمیم‌گیری بر پایهٔ اعداد نادرست |

---

## ۹. علت ریشه‌ای

1. **ناپایداری baseline (I1):** یک عامل/نشست دیگر هم‌زمان روی همین checkout کار می‌کند و فایل‌های source را مستقیم ویرایش می‌کند. علت ریشه‌ای: نبود قفل/انحصار روی checkout مشترک و نبود مرحلهٔ commit پیش از شروع ممیزی. اثرش این است که «وضعیت اولیه» مفهوم ثابتی ندارد.

2. **انتقال docs بدون ثبت در Git (I3/I4):** در snapshot اولیه، پوشهٔ `docs/` با ابزار فایل‌سیستم (نه `git mv`) به `docs/New folder/` منتقل شده بود. Git این را rename تشخیص نمی‌دهد چون فایل‌های مقصد هنوز tracked نشده‌اند. علت ریشه‌ای: جابه‌جایی دستی خارج از Git. سپس همین انتقال توسط فرآیند هم‌زمان برگردانده شد (I13) — یعنی حتی این تصمیم هم پایدار نبود.

3. **Stage شدن مصنوعات (I5/I6/I7):** در نشست‌های قبلی از `git add` گسترده (مثل `git add -A`) استفاده شده که `.bak`، اسکریپت‌های وصله و JSONهای تولیدی را هم وارد index کرده. علت ریشه‌ای: نبود `.gitignore` برای `*.bak` و نبود بازبینی index پیش از commit.

4. **محیط ناتوان برای تأیید end-to-end (I8/I9):** PostgreSQL خاموش و BrsApi در cooldown. علت ریشه‌ای: محیط محلی بدون سرویس‌های وابسته. این مانع، تأیید زنجیرهٔ «منبع → پارسر → ذخیره → API → فرانت» را به بخش‌های بعدی و به محیط CI موکول می‌کند.

5. **عدم دقت گزارش‌های قبلی (I12):** خلاصه‌سازی بدون اجرای مجدد و بدون شمارش دقیق تست‌ها. علت ریشه‌ای: تکیه بر حافظه/خلاصه به‌جای خروجی فرمان.

---

## ۱۰. تغییرات کد

**هیچ.** طبق مرز دامنه، این مرحله فقط بررسی و گزارش است:

- هیچ فایل source تغییر نکرد.
- هیچ فایل test تغییر نکرد.
- هیچ state گیت تغییر نکرد (بدون `add`، `reset`، `checkout`، `stash`، `commit`).
- هیچ تنظیم cooldown/سهمیه پاک یا دست‌کاری نشد.
- هیچ عملیات DB انجام نشد.

تنها فایل ایجادشده: همین گزارش (`AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE_run2.md`).

> توجه: تغییراتی که در بخش‌های ۱.۴ و ۱.۵ به آن‌ها اشاره شد (فایل‌های `brsapi/*`، `ingestion/worker.py`، `apps/api/endpoints/market.py`، `schemas/common/responses.py` و بازگردانی `docs/`) **کار این مأموریت نیستند**؛ توسط فرآیند هم‌زمان بیرونی ایجاد شده‌اند و ثبت شده‌اند تا در بخش‌های بعدی با آن‌ها اشتباه گرفته نشوند.

---

## ۱۱. فرمان‌های تست، نتیجه و exit code

### T1 — تست repository (تأیید مستقل ادعای «۱۵ تست»)

```bash
cd /c/Users/Iran/Desktop/temce
python -m pytest tests/unit/repositories/test_sync_log_repository.py \
  -p no:cacheprovider --timeout=120 --timeout-method=thread -q
```

```
...............                                        [100%]
15 passed in 13.94s
PYTEST_EXIT=0
```

**نتیجه: PASS — ۱۵ تست، ۰ خطا، exit code = 0.** (`python` به `venv/Scripts/python.exe` اشاره می‌کند.)

### T2 — همان تست با مفسر `.venv` (شکست ابزاری، نه شکست تست)

```bash
.venv/Scripts/python.exe -m pytest tests/unit/repositories/test_sync_log_repository.py -q
```

```
C:\Users\Iran\Desktop\temce\.venv\Scripts\python.exe: No module named pytest
PYTEST_EXIT=1
```

**نتیجه: FAIL (محیط).** `.venv` است وابستگی‌های تست را ندارد. این شکست، شکست کد نیست.

### T3 — تست فرانت (تأیید مستقل ادعای «۱۰/۱۵»)

```bash
cd /c/Users/Iran/Desktop/temce/frontend
npx vitest run src/__tests__/useMarketData.test.tsx
```

```
 ✓ src/__tests__/useMarketData.test.tsx (10 tests) 190ms

 Test Files  1 passed (1)
      Tests  10 passed (10)
VITEST_EXIT=0
```

**نتیجه: PASS — ۱۰ تست، همه پاس، exit code = 0.** ادعای «۱۰ از ۱۵» رد شد؛ فایل ۱۰ تست دارد.

### T4 — تلاش اولیهٔ Vitest با reporter قدیمی (شکست ابزاری)

```bash
npx vitest run src/__tests__/useMarketData.test.tsx --reporter=basic
```

```
Error: Failed to load custom Reporter from basic  … ERR_LOAD_URL
VITEST_EXIT=1
```

**نتیجه: FAIL (ابزار).** در Vitest 4 reporter `basic` وجود ندارد.

### T5 — اعتبارسنجی syntax روتر

```bash
python -c "import ast; ast.parse(open('apps/api/router.py',encoding='utf-8').read()); print('OK')"
```

```
router.py parses OK
```

**نتیجه: PASS.**

### T6 — شمارش فایل تست (ایستا، بدون اجرا)

```bash
grep -c "def test_" tests/unit/repositories/test_sync_log_repository.py   → 15
grep -c "def test_needs_sync" tests/unit/repositories/test_sync_log_repository.py → 10
grep -c "  it(\|  test(" frontend/src/__tests__/useMarketData.test.tsx    → 10
```

**نتیجه: ۱۰ تست `needs_sync` + ۵ تست `get_sync_stats` = ۱۵؛ فرانت ۱۰ تست.**

---

## ۱۲. تست‌های اجرانشده و علت

| تست / بررسی | علت اجرانشده |
|---|---|
| کل مجموعهٔ pytest (`pytest tests/`) | خارج از دامنهٔ این مرحله؛ زمان‌بر و برای baseline لازم نیست |
| تست‌های نیازمند PostgreSQL (`-m needs_db`) | PostgreSQL روی `localhost:5432` بالا نیست (شاهد: `logs/brsapi_sync_20261028.log`) |
| تست‌های یکپارچگی DB (dedup، ON CONFLICT، migration) | نیازمند DB محلی؛ ممنوعیت عملیات مخرب و نبود سرویس |
| زنجیرهٔ end-to-end (منبع → پارسر → lake → DB → API → فرانت) | BrsApi در cooldown 302 + نبود PostgreSQL + نبود Redis |
| تست‌های صف/worker (`jobs/`, `ingestion/worker.py`) | نیازمند Redis؛ در این مرحله خارج از دامنه |
| تست فرانت به‌صورت کامل (`npm test`) | فقط فایل مرتبط با ادعای قبلی اجرا شد؛ اجرای کامل خارج از دامنه |
| `docker compose` / استقرار | نیازمند Docker؛ خارج از دامنه و محیط |
| build فرانت (`next build`) | خارج از دامنه (تغییر کدی انجام نشده) |

---

## ۱۳. خطرات باقی‌مانده و وابستگی‌ها

| # | خطر | وابستگی |
|---|---|---|
| K1 | تغییر هم‌زمان working tree توسط عامل دیگر، تحلیل‌ها را بی‌اعتبار می‌کند — و در همین جلسه سازمان‌دهی `docs/` را برگرداند | نیاز به هماهنگی/توقف نویسندهٔ دیگر یا commit نقطه‌ای پیش از شروع بخش ۰۱ |
| K2 | در snapshot اولیه، commit ناخواستهٔ ۱۴۷ حذف `docs/` می‌توانست مستندات را از مخزن پاک کند (اکنون `docs/` بازگشته، ولی ساختار مقصد از بین رفته) | تأیید ساختار مطلوب `docs/` توسط کاربر پیش از هر commit |
| K3 | ۶۰ فایل که قبلاً `AD` بودند، اکنون به worktree بازگشته‌اند؛ وضعیت index ممکن است ناپایدار باشد | بازبینی index در بخش پایانی |
| K4 | `.bak`، `z.py.bak` و اسکریپت‌های وصله در صف commit هستند | پاک‌سازی index در بخش پایانی |
| K5 | مسیر داده زنده قابل تأیید نیست (cooldown + DB خاموش) | رفع cooldown BrsApi و بالا آمدن PostgreSQL/Redis |
| K6 | `InkGist` gitlink یتیم | تصمیم کاربر: حذف از index یا افزودن `.gitmodules` |
| K7 | یکپارچگی داده، dedup، و timestamps تأییدنشده‌اند (C5/C6/C7/C8) | بخش ۰۳ |
| K8 | رفتار صف/worker و auth صف تأییدنشده است (C9/C10) | بخش ۰۲ |

---

## ۱۴. ترتیب اجرایی پیشنهادی بخش‌ها (برای مراحل بعد)

1. **منبع و پارسر** — `ingestion/sources/`, `ingestion/parser/*`, `ingestion/http_client.py`, `brsapi/parsers/`
2. **Scheduler / worker / queue** — `ingestion/scheduler.py`, `ingestion/worker.py`, `jobs/`, `brsapi/jobs/`
3. **Persistence** — `ingestion/storage/`, `brsapi/repositories/`, `brsapi/models/`, `migrations/`
4. **API و cache** — `apps/api/`, `brsapi/services/query_service.py`, `ingestion/cache.py`
5. **Frontend** — `frontend/src/hooks/`, `frontend/src/lib/`, `frontend/src/app/gold/`
6. **Deployment** — `deploy/`, `k8s/`, `docker-compose*`, `.github/`
7. **Data quality** — `raw_validation.py`, `validation.py`, `ingestion/validator`
8. **حوزه‌های دیگر** — `src/gold_desk/`, `domain/options/`, `backtesting/`, `ml/`
9. **امنیت** — secrets، auth، `apps/api/auth.py`, `.gitleaks.toml`
10. **تست نهایی** — مجموعهٔ کامل + یکپارچگی

> پیش‌شرط شروع بخش ۰۱: تثبیت working tree (توقف نویسندهٔ هم‌زمان) و گرفتن snapshot تازه.

---

## ۱۵. معیارهای پذیرش و وضعیت

| # | معیار | وضعیت | شاهد |
|---|---|---|---|
| A1 | هیچ فایل source/test یا state گیت **توسط این مأموریت** تغییر نکرده باشد؛ فقط گزارش جدید ایجاد شود | ✅ PASS | تنها فایل ایجادشده توسط این جلسه همین گزارش است؛ HEAD بدون تغییر `90597e05`؛ بدون add/reset/clean/commit/stash. (تغییرات بیرونی در بخش‌های ۱.۴ و ۱.۵ مستند شده‌اند.) |
| A2 | گزارش manifest وضعیت اولیهٔ Git و موانع اصلی را مستند کند | ✅ PASS | بخش‌های ۱، ۳، ۸، ۱۳ |
| A3 | هیچ ادعای «همهٔ فایل‌ها کامل خوانده شده» بدون manifest و شاهد درج نشود | ✅ PASS | بخش ۱۶ — manifest صریح و محافظه‌کارانه؛ ادعای کلی مطرح نشده |
| A4 | ریشه/branch/HEAD/status/diff ثبت شده باشد | ✅ PASS | بخش ۱ |
| A5 | staging / unstaged / untracked تفکیک شده باشد | ✅ PASS | بخش ۱.۳ و ۱.۵ |
| A6 | inventory با زبان/مسیر/نوع/اندازه ساخته شده باشد | ✅ **PASS** | بخش ۳ (توزیع) + **بخش ۱۷ (اندازه)** — ۱۳٬۱۲۹ فایل، ۲۴۶٫۱۳ MB، تفکیک دایرکتوری/پسوند/بزرگ‌ترین‌ها |
| A7 | آرشیو ZIP شناسایی و از checkout تفکیک شده باشد | ✅ PASS | بخش ۴ |
| A8 | claim index از گزارش‌های قبلی استخراج شده باشد | ✅ PASS | بخش ۶ (C1–C12) |
| A9 | نشانگرهای conflict و وضعیت `apps/api/router.py` بررسی شده باشد | ✅ PASS | بخش ۵ — هیچ نشانگری یافت نشد؛ روتر تمیز و معتبر |
| A10 | ادعاهای نشست قبلی دربارهٔ `test_sync_log_repository.py`، `useMarketData.ts`، شاخه و «۱۵/۱۰ تست» مستقلاً تأیید شده باشد | ✅ PASS | V1، V4–V6، T1، T3؛ نادرستی «۱۰/۱۵» در R1 ثبت شد |
| A11 | هیچ درخواست زندهٔ BrsApi و هیچ عملیات مخرب DB/Git انجام نشده باشد | ✅ PASS | بدون شبکه؛ cooldown دست‌نخورده؛ بدون TRUNCATE/DELETE/reset |
| A12 | secret چاپ نشده باشد | ✅ PASS | فقط نام فایل‌های env؛ مقادیر خوانده/چاپ نشد |
| A13 | ترتیب اجرایی بخش‌ها مشخص شده باشد | ✅ PASS | بخش ۱۴ |
| A14 | گزارش در فایل نوشته شده باشد و پاسخ چت کوتاه باشد | ✅ PASS | همین فایل |

**وضعیت کلی: PASS برای دامنهٔ این مرحله.** محدودیت‌ها (A6 اندازهٔ تک‌فایل، I8/I9 محیط) صریحاً ثبت شده‌اند.

---

## ۱۶. Manifest فایل‌های خوانده‌شده

علامت‌ها: ✅ کامل خوانده شد | 🟡 بخشی خوانده شد | ⬜ بررسی نشد (با دلیل)

### ۱۶.۱ گزارش‌های audit

| مسیر | خطوط | وضعیت | توضیح |
|---|---|---|---|
| `AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE.md` | ۱۷۲ | ✅ | کل فایل خوانده شد (منبع claimهای R1–R4) |
| `AUDIT_REPORTS/MODULAR_TEMCE/01_MARKET_SOURCE_AND_PARSERS.md` | ۲۸۷ | 🟡 | خطوط ۱۱۰–۲۳۹ + فهرست سرفصل‌ها؛ بخش‌های ۱–۳ و ۹–۱۲ خوانده نشد |
| `AUDIT_REPORTS/MODULAR_TEMCE/02_SCHEDULER_WORKERS_QUEUES.md` | ۳۹۶ | 🟡 | خطوط ۲۳۶–۳۲۵ + فهرست سرفصل‌ها |
| `AUDIT_REPORTS/MODULAR_TEMCE/03_DATABASE_STORAGE_REPOSITORIES.md` | ۴۳۴ | 🟡 | فقط فهرست سرفصل‌ها |
| `AUDIT_REPORTS/MODULAR_TEMCE/03_DATABASE_STORAGE_REPOSITORIES_run2.md` | ۴۰۲ | 🟡 | فقط فهرست سرفصل‌ها |
| `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_3.md` | ۱۵۳ | 🟡 | خطوط ۱–۱۵۰ |

### ۱۶.۲ کد منبع

| مسیر | خطوط | وضعیت | توضیح |
|---|---|---|---|
| `brsapi/repositories/base.py` | ۴۰۴ | 🟡 | خطوط ۸۰–۱۳۰ (`last_sync`, `needs_sync`) + hunkهای diff (`delete_where`, `rowcount`) |
| `brsapi/models/base.py` | ۱۵۸ | 🟡 | فقط hunkهای diff (`utc_now_naive`) |
| `brsapi/services/sync_service.py` | ۱٬۸۴۳ | 🟡 | فقط hunkهای diff (`replace_filter`, `commit`) |
| `ingestion/worker.py` | ۱۹۶ | 🟡 | فقط `git diff --stat` (۳۷۷ خط تغییر) — محتوا کامل خوانده نشد |
| `ingestion/storage/__init__.py` | ۹۲ | 🟡 | خطوط ۸۵–۸۸ (الگوی falsy) + grep |
| `ingestion/parser/library_parsers.py` | ۴۰۷ | 🟡 | خطوط ۹۰–۱۰۴ (`_BaseLibParser.parse`) |
| `ingestion/parser/tsetmc_parsers.py` | ۱۶۴ | ⬜ | فقط `--stat` diff (۶ خط)؛ محتوا بررسی نشد — بخش ۰۱ |
| `apps/api/router.py` | ۷۳۶ | 🟡 | بررسی conflict + `ast.parse`؛ محتوا خط‌به‌خط خوانده نشد |
| `brsapi/models/tsetmc.py` | — | 🟡 | فقط ناحیهٔ `NavRecordModel` (خط ۲۶۱) |
| `frontend/src/hooks/useMarketData.ts` | ۸۱۵ | 🟡 | خطوط ۲۷۸–۲۹۰ + diff کامل همان ناحیه |

### ۱۶.۳ تست‌ها

| مسیر | خطوط | وضعیت | توضیح |
|---|---|---|---|
| `tests/unit/repositories/test_sync_log_repository.py` | ۴۲۵ | 🟡 | فهرست کامل ۱۵ تابع تست + نام‌ها با شمارهٔ خط؛ بدنهٔ تست‌ها خط‌به‌خط خوانده نشد |
| `frontend/src/__tests__/useMarketData.test.tsx` | ۱۴۸ | 🟡 | فهرست کامل ۱۰ تست با شمارهٔ خط |
| `tests/fixtures/*` (۹ فایل JSON جدید) | — | ⬜ | بررسی نشد — بخش‌های ۱–۳ |
| `tests/gold_desk/test_phase1_terminal.py` و بقیه | — | ⬜ | بررسی نشد — خارج از دامنهٔ این مرحله |

### ۱۶.۴ لاگ‌ها (خواندن، بدون درخواست شبکه)

| مسیر | وضعیت | توضیح |
|---|---|---|
| `logs/brsapi_sync_20261027.log` | 🟡 | خطوط مربوط به cooldown 302 |
| `logs/brsapi_sync_20261028.log` | ✅ (۲۵ خط آخر) | خطای اتصال PostgreSQL و `exit=1` |
| `logs/brsapi_sync_2026101{6,7,8,9}.log` و `2026102{0,1,5,6}` | ⬜ | فقط نام و اندازه فهرست شد |

### ۱۶.۵ بررسی‌نشده — با دلیل

| دسته | دلیل |
|---|---|
| `node_modules/`، `venv/`، `.venv/`، `frontend/node_modules/` | وابستگی خارجی؛ ده‌ها هزار فایل |
| `symbol_reports/` (۴٬۱۷۴)، `new_symbol_reports/` (۱۶۹)، `reports/` (۲۱۱)، `json/` (۱٬۴۵۱) | تولیدی/data؛ خارج از منطق اجرایی |
| `_FRONTEND_BACKEND_COPY/` (۲٬۲۶۵) | vendor/copy؛ نسخهٔ تکراری |
| `*.png` (۱۵۹)، `*.ttf`/`*.woff2`، `*.exe`/`*.pdb`، `*.zip` (۴)، `*.pdf` | باینری |
| `docs/audits/tools/_ruff_broad.json` (۸۲٬۷۷۸ خط)، `_pattern_findings.json` (۱۳٬۶۹۴ خط) | تولیدی/حجیم |
| `docs/New folder/` (۲۰۹ فایل) | فقط وجود و کپی‌بودن بررسی شد، محتوا نه |
| `.env`, `.env.production`, `frontend/.env`, … | محتوای secret — عمداً خوانده نشد |
| بقیهٔ ۱۳٬۱۲۹ فایل tracked | خارج از دامنهٔ مرحلهٔ ۰ |

**هیچ ادعایی مبنی بر «کل پروژه بررسی شد» در این گزارش وجود ندارد.**

---

## ۱۷. پیوست الف — موجودی با اندازه (بستن شکاف A6)

**فرمان:** اسکریپت پایتون read-only روی خروجی `git ls-files -z` با `os.path.getsize`.

```python
out = subprocess.run(['git','ls-files','-z'], capture_output=True).stdout
files = [f for f in out.decode('utf-8','surrogateescape').split('\0') if f]
# for each: os.path.getsize(f) → aggregate by top-level dir / extension
```

| سنجه | مقدار |
|---|---|
| فایل‌های tracked | ۱۳٬۱۲۹ |
| فایل‌های غایب روی دیسک | **۰** |
| حجم کل tracked | **۲۴۶٫۱۳ MB** |

### ۱۷.۱ حجم بر اساس دایرکتوری سطح‌بالا

| دایرکتوری | فایل | حجم | نوع |
|---|---|---|---|
| `symbol_reports/` | ۴٬۱۷۴ | ۸۴٫۲۵ MB | **generated** |
| `(root)` | ۱۴۶ | ۳۴٫۵۷ MB | config/داده/مصنوعات |
| `Redis/` | ۱۵ | ۲۶٫۴۱ MB | **vendor باینری** |
| `reports/` | ۲۱۱ | ۱۷٫۷۲ MB | **generated** |
| `docs/` | ۲۰۹ | ۱۷٫۴۱ MB | docs |
| `_FRONTEND_BACKEND_COPY/` | ۲٬۲۶۵ | ۱۴٫۸۷ MB | **vendor/copy** |
| `json/` | ۱٬۴۵۱ | ۹٫۸۲ MB | **generated/data** |
| `.agents/` | ۵۳۶ | ۹٫۳۷ MB | tooling |
| `frontend/` | ۵۳۵ | ۷٫۹۰ MB | **source** |
| `tests/` | ۵۷۶ | ۴٫۶۵ MB | **test** |
| `services/` | ۲۷۲ | ۳٫۵۲ MB | **source** |
| `audit_out/` | ۱۰۱ | ۲٫۴۶ MB | **generated** |
| `scripts/` | ۳۰۹ | ۱٫۹۲ MB | tooling |
| `new_symbol_reports/` | ۱۶۹ | ۱٫۶۵ MB | **generated** |
| `apps/` | ۱۸۱ | ۱٫۴۸ MB | **source** |
| `backtesting/` | ۲۹۲ | ۱٫۰۴ MB | source |
| `brsapi/` | ۷۷ | ۰٫۶۳ MB | **source** |
| `src/` | ۷۴ | ۰٫۶۲ MB | **source** |
| `core/` | ۱۶۹ | ۰٫۵۴ MB | **source** |
| `domain/` | ۲۲۰ | ۰٫۴۹ MB | source |
| `providers/` | ۲۴۵ | ۰٫۳۴ MB | source |
| `migrations/` | ۸۹ | ۰٫۳۳ MB | **migration** |
| `ingestion/` | ۵۸ | ۰٫۲۴ MB | **source** |

**نکتهٔ کلیدی:** کل کد اجرایی (`apps` + `brsapi` + `ingestion` + `src` + `services` + `domain` + `core` + `providers` ≈ **۸٫۳ MB**) در برابر **۱۷۹ MB** تولیدی/vendor قرار دارد. یعنی بیش از ۷۰٪ حجم مخزن، مصنوعات بازتولیدشدنی است.

### ۱۷.۲ حجم بر اساس پسوند

| پسوند | تعداد | حجم |
|---|---|---|
| `.md` | ۴٬۹۷۵ | ۷۹٫۰۲ MB |
| `.py` | ۵٬۰۹۱ | ۲۵٫۲۴ MB |
| `.db-wal` | ۱ | **۲۵٫۱۰ MB** |
| `.json` | ۱٬۶۰۰ | ۲۰٫۹۰ MB |
| `.pdb` | ۴ | ۱۸٫۵۹ MB |
| `.txt` | ۱۲۴ | ۱۷٫۷۱ MB |
| `.jsonl` | ۱۰ | ۱۳٫۰۲ MB |
| `.png` | ۱۵۹ | ۹٫۶۱ MB |
| `.zip` | ۴ | ۸٫۷۹ MB |
| `.tsx` | ۶۸۰ | ۷٫۳۰ MB |
| `.ttf` | ۵۴ | ۵٫۱۶ MB |
| `.js` | ۱۳ | ۳٫۹۹ MB |
| `.html` | ۹ | ۳٫۴۵ MB |
| `.exe` | ۴ | ۲٫۷۰ MB |
| `.ts` | ۱۵۲ | ۱٫۳۰ MB |

### ۱۷.۳ بزرگ‌ترین ۱۰ فایل tracked

| حجم | مسیر | ارزیابی |
|---|---|---|
| ۲۵٫۱۰ MB | `transactions.db-wal` | **بحرانی — فایل WAL دیتابیس SQLite در Git** |
| ۷٫۴۰ MB | `json/brsapi/symbol_details.json` | generated |
| ۶٫۷۵ MB | `Redis/redis-server.pdb` | vendor باینری |
| ۴٫۹۸ MB | `Redis/Redis.zip` | vendor باینری |
| ۴٫۷۳ MB | `gold_complete_bundle.txt` | مصنوع تولیدی |
| ۳٫۳۳ MB | `symbol_reports/dashboard.md` | generated |
| ۳٫۲۶ MB | `docs/mermaid-preview.html` | مصنوع |
| ۳٫۲۰ MB | `docs/SESSION_REPORT_2026-09-16.zip` | آرشیو (طبق بخش ۴) |
| ۳٫۱۸ MB | `docs/assets/mermaid.min.js` | vendor |
| ۲٫۱۴ MB | `docs/audits/tools/_ruff_broad.json` | generated |

### ۱۷.۴ ایراد جدید کشف‌شده در جریان اندازه‌گیری

| # | شدت | ایراد | شاهد | اثر |
|---|---|---|---|---|
| **I14** | **بالا** | فایل WAL دیتابیس SQLite در مخزن tracked است | `git ls-files transactions.db-wal` → موجود؛ ۲۵٬۱۰۰٬۰۰۰+ بایت، بزرگ‌ترین فایل tracked | دادهٔ تراکنشی/موقت دیتابیس در تاریخچهٔ Git؛ خطر نشت داده و تورم دائمی مخزن |
| **I15** | متوسط | باینری‌های Redis در مخزن نگهداری می‌شوند | `Redis/` → ۲۶٫۴۱ MB شامل `redis-server.exe`, `redis-server.pdb`, `Redis.zip` | مخزن سنگین؛ وابستگی اجرایی وابسته به پلتفرم (win32) |

---

## ۱۸. پیوست ب — تأیید ۶ ادعای باقی‌ماندهٔ claim index

ادعاهای C5، C6، C8، C9، C10، C12 در مرحلهٔ ۰ تأییدنشده مانده بودند. اکنون با بازرسی مستقیم کد بررسی شدند.

### C5 — «موفق ولی خالی» از «خطا» تفکیک نمی‌شود → ✅ **تأیید شد**

شاهد: `brsapi/services/sync_service.py:441-457`

```python
if not records:
    elapsed_ms = (time.monotonic() - start) * 1000
    await sync_log.record(
        endpoint=endpoint.path, ...,
        status="success",
        items_count=0, ...
    )
    await sess.commit()
    return SyncReport(
        endpoint=endpoint.path,
        success=True,
        items_count=0, ...
    )
```

- پاسخ خالی/فیلترشده → `success=True, items_count=0`.
- **مهم:** خطای parse **استثنا** نتیجه می‌دهد (`success=False`, خط ۴۲۶)؛ ولی چون `_BaseLibParser` استثنا را می‌بلعد و `[]` برمی‌گرداند (C4)، همان خطا به مسیر «موفق و خالی» می‌افتد. پس زنجیرهٔ ادعا معتبر است.
- موارد مشابه: خطوط ۳۹۵/۴۰۳، ۶۳۸-۶۳۹، ۷۲۱-۷۲۲، ۷۸۲-۷۸۳، ۱۳۳۴-۱۳۳۵.

### C6 — dedup بعد از نوشتن موفق → ✅ **تأیید شد، با یک ضعف**

شاهد: `ingestion/worker.py:153, 186-191`

```python
payload_written_all = True
for event in events:
    ...
    except Exception:
        logger.exception("Failed to write event for %s", ins_id)
        payload_written_all = False
        continue
    written += 1

# Only after the whole payload was written successfully.
if self._dedup is not None and payload_written_all:
    await self._dedup.mark_seen(payload.source, payload.raw_data)
```

- ادعا **درست** است و حتی قوی‌تر از گزارش قبلی: علامت‌گذاری بعد از **کل payload** انجام می‌شود، نه هر رویداد.
- **ضعف کشف‌شده:** رویدادهایی که `instrument_id` آن‌ها resolve نمی‌شود با `continue` رد می‌شوند (خط ۱۶۹) **بدون** اینکه `payload_written_all = False` شود. همچنین اگر `self._identity` یا `self._storage` نباشد، حلقه هیچ نوشتنی انجام نمی‌دهد و پرچم `True` می‌ماند. در هر دو حالت payload «دیده‌شده» علامت می‌خورد بدون اینکه داده‌اش ذخیره شده باشد → **ریسک از دست رفتن خاموش داده**.

### C7-تکمیلی (C8) — `NavRecordModel.fetched_at` رشته است → ✅ **تأیید شد**

شاهد: `brsapi/models/tsetmc.py:276`

```python
fetched_at: Mapped[str | None] = mapped_column(String(30))
```

- برخلاف `RawPayloadModel.fetched_at` و `SyncLogModel.started_at` (که `DateTime` هستند)، این ستون **رشته** است و **ایندکس هم ندارد** (تنها ایندکس: `idx_nav_symbol_date` روی `symbol, date`). پرس‌وجوهای بازه‌ای زمانی روی آن قابل اتکا نیست.

### C9 — رفتار در نبود Redis → 🟡 **بخشی تأیید، بخشی رد شد**

**رد شد برای jobهای عمومی:** `apps/scheduler/app.py:36-47`

```python
async def _execute(self, job_name: str) -> None:
    if self._queue_enabled:
        published = await self._get_publisher().publish(job_name)
        if published is not None:
            return
        logger.warning("Scheduler could not enqueue %s — falling back to in-process dispatch", job_name)
    await job_dispatcher.dispatch(job_name)
```

و `jobs/queue_publisher.py:96-104` وقتی Redis نیست `None` برمی‌گرداند. پس **fallback درون‌فرآیندی وجود دارد** و ادعای «هیچ jobی اجرا نمی‌شود» نادرست است.

**تأیید شد برای jobهای BrsApi:** `brsapi/jobs/registry.py:503-508`

```python
async def _run(job_name: str = job.name) -> None:
    if self._run_handler is not None:
        await self._run_handler(job_name)   # ← مقدار بازگشتی None نادیده گرفته می‌شود
    else:
        await self.run_job(job_name)
```

و `apps/scheduler/app.py:69`: `brsapi_registry.run_handler = lambda name: self._get_publisher().publish(name)`.

**نتیجه:** در حالت queue-mode، اگر Redis پایین باشد، jobهای BrsApi **بی‌صدا اجرا نمی‌شوند** (publish → `None`، و `_run` مقدار را بررسی نمی‌کند، پس fallback هم رخ نمی‌دهد). این یک **ایراد واقعی جدید** است:

| # | شدت | ایراد | شاهد | اثر |
|---|---|---|---|---|
| **I16** | **بالا** | عدم تقارن fallback: jobهای عمومی fallback دارند، jobهای BrsApi ندارند | `apps/scheduler/app.py:36-47` vs `brsapi/jobs/registry.py:503-508` + `apps/scheduler/app.py:69` | وقتی Redis در دسترس نیست، همگام‌سازی BrsApi در حالت queue بی‌صدا متوقف می‌شود و هیچ هشداری در سطح job ثبت نمی‌شود |

### C10 — بدون token، auth صف رد می‌شود → ✅ **تأیید شد**

شاهد: `jobs/queue_consumer.py:72, 234`

```python
self._token = token if token is not None else settings.job_queue_token   # خط ۷۲
...
if self._token and payload.get("token") != self._token:                    # خط ۲۳۴
    ...
    return
```

- `core/config/__init__.py:273`: `job_queue_token: str = Field(default="", alias="JOB_QUEUE_TOKEN")` → پیش‌فرض خالی.
- docstring خودِ کلاس (خط ۶۰) صریحاً می‌گوید: `empty means *no auth* — dev only`.
- خط ۱۱۹ وضعیت را لاگ می‌کند: `"on" if self._token else "OFF"`.
- **نکتهٔ تکمیلی:** publisher در نبود token یک توکن تصادفی per-process می‌سازد (`jobs/queue_publisher.py:64`)، ولی چون consumer با token خالی **هیچ بررسی‌ای** نمی‌کند، هر پیامی پذیرفته می‌شود.

### C12 — پروکسی bypass و اتصال مستقیم → ✅ **تأیید شد**

شاهد: `core/fix_network.py:44, 76`

```python
_set_env("NO_PROXY", "*")
...
logger.info("Network proxy bypass active — all HTTP clients use direct connections.")
```

- همین پیام عیناً در `logs/brsapi_sync_20261028.log` خط ۲ دیده می‌شود → مسیر اجرایی واقعاً فعال است.

### جمع‌بندی بخش ۱۸

| ادعا | نتیجه |
|---|---|
| C5 | ✅ تأیید |
| C6 | ✅ تأیید (با ضعف در skip بدون علامت‌گذاری) |
| C8 | ✅ تأیید |
| C9 | 🟡 بخشی — برای jobهای عمومی **رد**، برای jobهای BrsApi **تأیید** → ایراد جدید I16 |
| C10 | ✅ تأیید |
| C12 | ✅ تأیید |

**دو ایراد جدید:** I14 (فایل WAL در Git)، I15 (باینری Redis)، I16 (عدم تقارن fallback صف).

> هیچ‌یک از این بررسی‌ها تغییر کد ایجاد نکرد؛ همه read-only بودند.
