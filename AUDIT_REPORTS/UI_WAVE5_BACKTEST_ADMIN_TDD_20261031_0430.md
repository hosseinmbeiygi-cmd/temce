# موج ۵ — Backtest/Admin/Data Import + اصلاح TDD (F1)

- تاریخ: 2026-10-31 04:30 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- دامنه: تأیید محیط، `/health` و `/health/ready`، نمونه‌برداری Backtest/Admin/Data Import در محیط تستی، و اصلاح کم‌ریسک F1 با TDD.
- **تنها تغییر محصول: F1** (`auth-context.tsx` + تست). سایر یافته‌ها اصلاح نشدند (ریسک/نیاز به تأیید/فایل دارای تغییر کاربر).

---

## ۱) وضعیت شروع و محیط

| مورد | نتیجه |
|---|---|
| DB تستی | `tse_quant_verify` روی `15432` — Alembic **0120**، ۲۱۸ relation، ۰ کاربر |
| API | `scripts/ui_test_server.py` روی `:8000` |
| Redis | `tse_redis` روی `:16379`؛ رمز از `docker inspect` بدون چاپ |
| Frontend | Next dev؛ ابتدا Turbopack، سپس به‌دلیل کرش حافظه با **webpack** بالا آمد |
| `/api/v1/health` | **200** — status ok |
| `/api/v1/health/ready` | **200** — `database: ok`، `redis: ok` |
| `/api/v1/ready`, `/health`, `/ready` | 404 (مسیرهای درست همان دو مورد اول هستند) |
| کاربران تستی | `audit_ui_admin_20261030_a1` (admin) و `audit_ui_user_20261030_u1` (user) — هر دو پس از تست حذف شدند |

**محدودیت نام کاربری:** schema فقط `^[a-zA-Z0-9_]+$` را می‌پذیرد (`schemas/api/auth.py:10`)، بنابراین پیشوند پیشنهادی `audit-ui-20261030-` با خط تیره **معتبر نیست**؛ از underscore استفاده شد. رکوردها همچنان با `AUD-UI-...` نام‌گذاری شدند.

---

## ۲) نتیجهٔ سلامت و آمادگی

- `/api/v1/health` → 200، `status: ok`.
- `/api/v1/health/ready` → 200، چک DB و Redis هر دو ok.
- این دو مورد **PASS** هستند.

---

## ۳) Backtest — نمونه‌برداری (بدون اجرای job)

| مسیر | نتیجه | شاهد |
|---|---|---|
| `/backtest` | **PASS (بارگذاری)** — ۱۰ دکمه، ۱۱ ورودی، ۳ select، ۶ نمودار؛ بدون خطا | heading «بک‌تست استراتژی»؛ `hydrateWaitSec=2` |
| `/backtest/engine` | **PASS (بارگذاری)** — ۱۰ دکمه، ۴ ورودی؛ بدون خطا | heading «موتور کشف استراتژی» |
| `/backtest/walk-forward` | **PASS (بارگذاری)** — ۱ دکمه، ۳ ورودی، ۱ select؛ در حین بارگذاری یک `500 /auth/refresh` دیده شد | heading «بهینه‌سازی Walk-Forward» |
| ۸ مسیر باقی‌مانده | **NOT RUN** | زمان/ناپایداری dev server؛ هیچ کنترلی اجرا نشد |
| اجرای واقعی بک‌تست | **NOT RUN** | نیاز به نماد دارای تاریخچه و job؛ در DB تست موجود نیست |

هیچ job/بک‌تستی اجرا نشد و هیچ داده‌ای نوشته نشد. فقط فرم‌ها و صفحات بارگذاری/هیدریت شدند.

---

## ۴) Admin / Data Import — با session معتبر ادمین

| مسیر | نتیجه | شاهد |
|---|---|---|
| `/admin` (admin) | **PASS (بارگذاری)** — heading «پنل مدیریت»، کوکی `im_refresh` httpOnly، بدون redirect | login 200 → `/` → `/admin` |
| `/admin` (کاربر عادی) | **PARTIAL / یافتهٔ امنیتی** — صفحه با ۲۰۰ لود می‌شود؛ `/dashboard` و `/jobs/scheduler` با ۴۰۳ رد می‌شوند، اما `/brsapi/sync-status` با **۲۰۰** داده می‌دهد | `W5-01` |
| `/admin/users` (admin) | **PARTIAL** — heading «مدیریت کاربران» لود شد، اما هیچ جدول/ورودی/دکمه‌ای در snapshot نبود (احتمالاً empty state یا بارگذاری ناقص) | بدون API قابل‌شناسایی |
| `/data-import` (admin) | **PARTIAL (فقط بارگذاری)** — heading «ورود داده»، ۱ ورودی، ۴ دکمه؛ Import واقعی اجرا نشد | `NOT RUN` برای آپلود/نوشتن |
| `/sync-manager` (admin) | **PARTIAL** — heading «مدیریت همگام‌سازی»، ۲۴ دکمه؛ API قابل‌شناسایی در ۷ ثانیه دیده نشد | بارگذاری فقط |

**Data Import واقعی:** عمداً اجرا نشد؛ نیازمند فایل fixture صریح و تأیید محدودهٔ نوشتن است. فقط بارگذاری صفحه و کنترل‌ها ثبت شد.

---

## ۵) یافته‌ها

### W5-01 — صفحهٔ ادمین gate نقش ندارد و `/brsapi/sync-status` برای کاربر عادی ۲۰۰ می‌دهد (Medium — UI authorization)

**شواهد:**
- کاربر عادی با نقش `user` وارد شد (`login 200`، کوکی `im_refresh` موجود)، سپس `/admin` با **200** لود شد و heading «پنل مدیریت» دیده شد.
- فراخوانی مستقیم API با توکن همان کاربر:
  - `/api/v1/dashboard` → **403**
  - `/api/v1/jobs/scheduler` → **403**
  - `/api/v1/brsapi/sync-status` → **200** با ۱۰ بخش (symbols/commodities/gold_coin/currency/…) شامل `record_count`, `last_fetched`, `status`.
- `frontend/src/app/admin/page.tsx:123-135` هیچ `useAuth().hasRole("admin")` یا gate معادلی ندارد؛ فقط queryها را صدا می‌زند. middleware هم `/admin` را فقط با **وجود کوکی** می‌بندد و نقش را چک نمی‌کند (`middleware.ts:85-109`).
- `/brsapi/sync-status` در `apps/api/endpoints/brsapi.py:2702-2775` dependency نقش ندارد، اما کل `brsapi_router` در `apps/api/router.py:649-654` با `_require_user` mount شده است؛ پس دسترسی هر کاربر **احرازشده** به آن احتمالاً by design است، نه یک دور زدن نقش. مسئلهٔ اصلی، نبود gate نقش در خود صفحهٔ `/admin` است.

**اثر:** کاربر عادی می‌تواند پوستهٔ پنل مدیریت و دادهٔ عملیاتی sync (نام جدول‌ها/تعداد رکورد/تازگی) را ببیند؛ `/dashboard` و `/jobs/scheduler` ۴۰۳ هستند، پس نشت دادهٔ مدیریتی کامل تأیید نشد. اگر sync-status عمداً برای همهٔ کاربران است، فقط باید UI ادمین gate شود؛ اگر ادمین‌-only است، endpoint هم باید نقش بگیرد.

**اصلاح پیشنهادی (اجرا نشد):** gate نقش در صفحهٔ `/admin` (و در صورت تصمیم، `require_roles("admin")` روی `/brsapi/sync-status` و `/sync-history`)؛ تست ۲۰۰ برای admin و ۴۰۳ برای user.

---

### W5-02 — پیشوند کاربر با خط تیره مجاز نیست (Medium، محدودیت محیط)

schema نام کاربری `^[a-zA-Z0-9_]+$` است (`schemas/api/auth.py:10`)؛ `audit-ui-20261030-*` رد می‌شود. کاربران با `audit_ui_...` ساخته شدند. اگر پیشوند خط‌تیره الزامی است، باید schema/سیاست نام‌گذاری تغییر کند (تغییر محصول، نیازمند تأیید)؛ در غیر این صورت از underscore استفاده شود.

---

### W5-03 — Turbopack با خطای تخصیص حافظه کرش کرد (Medium، محیط تست)

- بعد از کامپایل `/admin/users` (۴۲s)، dev server با `memory allocation of 1606584 bytes failed` (Rust allocator) کرش کرد؛ `:3000` به 000 رفت و تست معلق شد.
- با `NODE_OPTIONS=--max-old-space-size=6144 npm run dev -- --webpack` پایدار شد و صفحات Admin/Data Import لود شدند.
- این **باگ محصول نیست**؛ محدودیت محیط dev است. برای تست‌های بعدی از webpack یا heap بالاتر استفاده شود.

---

### W5-04 — یک `500 /auth/refresh` گذرا (Low/نیازمند تثبیت)

در بارگذاری `/backtest/walk-forward` یک `500 POST /api/v1/auth/refresh` ثبت شد؛ در تست‌های قبلی نیز ۴۰۱های زنجیره‌ای refresh دیده شده بود. با یک نمونه نمی‌توان «باگ refresh» نامید؛ به‌عنوان ریسک پایداری session ثبت می‌شود و نیاز به تست هدفمند چرخش refresh دارد.

---

## ۶) اصلاح F1 با TDD (تنها تغییر محصول)

**یافتهٔ تأییدشده:** ورود با رمز اشتباه، به‌جای پیام سرور، «Login failed: missing access token» نشان می‌داد.

**تست اول (قرمز):**
- تست جدید در `frontend/src/__tests__/auth-context.test.tsx` برای پاسخ HTTP 200 با `success:false` و `error.message="Invalid username or password"`.
- اجرا: **۱ failed / ۱۲ passed**؛ پیام دریافتی `Login failed: missing access token`.

**اصلاح (کم‌ریسک، فقط frontend):**
- در `frontend/src/lib/auth-context.tsx` بعد از `res.json()`، بررسی `json.success === false` و پرتاب `error.message` (سازگار با `error` رشته‌ای/آبجکتی و `message`).
- مسیر MFA و موفقیت دست‌نخورده ماند.

**تست بعد (سبز):**
- `vitest run src/__tests__/auth-context.test.tsx` → **۱۳ passed / ۰ failed**.
- `eslint` روی هر دو فایل → **exit 0**.
- تأیید UI واقعی: رمز اشتباه → «Invalid username or password» و بدون «missing access token».

**فایل‌های تغییرکرده:** `frontend/src/lib/auth-context.tsx` (+۱۷)، `frontend/src/__tests__/auth-context.test.tsx` (+۳۰). هیچ فایل دیگری تغییر نکرد. (فایل‌های Portfolio/Alerts/Tokens/Layout/Silver که تغییر کاربر دارند، دست نخوردند.)

---

## ۷) پاک‌سازی

- هر دو کاربر تستی (`usr_3f966...`, `usr_2e09...`) پس از تأیید صفر بودن ۱۵ جدول user-scoped حذف شدند؛ `users=0`.
- در این موج هیچ holding/trade/DCA/alert/token/event ساخته نشد؛ هیچ `AUD-UI-*` جدیدی ثبت نشد.
- هیچ داده یا فایل محصولی حذف/تغییر نکرد (به‌جز اصلاح F1).

---

## ۸) جمع‌بندی وضعیت

| مورد | حکم |
|---|---|
| تأیید DB/کاربر/رکوردها | **PASS** (محدودیت خط تیره در نام کاربری) |
| `/health` و `/health/ready` | **PASS** |
| Auth F1 | **PASS (اصلاح TDD)** |
| Backtest (۳ مسیر) | **PASS (بارگذاری)**؛ ۸ مسیر **NOT RUN**؛ اجرای job **NOT RUN** |
| Admin (admin) | **PASS (بارگذاری)** |
| Admin (user) | **PARTIAL — یافتهٔ W5-01** |
| Admin/Users، Data Import، Sync Manager | **PARTIAL** (بارگذاری فقط) |
| Data Import واقعی | **NOT RUN** |
| هیچ صفحه‌ای PASS کامل نیست | — |

---

## ۹) اقدامات بعدی

1. **W5-01:** gate نقش در `/admin` + ۴۰۳ برای `/brsapi/sync-status` و `/sync-history`؛ تست role.
2. **W4-03:** رفع حلقهٔ SW؛ سپس ادامهٔ ۱۹ صفحهٔ Gold.
3. **W4-01:** کاهش موجودی در فروش + فروش چندردیفی (مالی، نیازمند طراحی/تأیید).
4. **W4-02:** اتصال واقعی توکن‌ها یا اصلاح UI/مستندات.
5. ادامهٔ Backtest (۸ مسیر) و Data Import با fixture ساختگی و تأیید نوشتن.
6. Cross-cutting (loading/error/offline/mobile) روی ۵ صفحهٔ Partial.

**شاهدها:** `audit_out/_tmp/wave5_smoke_admin.json`، `wave5_smoke_progress.jsonl`، `admin_auth_probe.json`، `normal_user_admin_probe.js`، `admin_pages_probe2.jsonl`، و گزارش‌های موج ۱/۲/۴.
