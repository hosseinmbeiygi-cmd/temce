# وضعیت نهایی اجرای ترتیب موج‌ها (Auth/Gold → Storage → Backtest/Admin → TDD)

- تاریخ: 2026-10-31 04:39 (Asia/Tehran)
- Branch: `backup/db02-baseline-20261030` — HEAD: `54c6a6eb`
- این فایل گزارش نهایی این دور است؛ گزارش‌های تفصیلی قبلی دست‌نخورده‌اند.
- **تنها تغییر محصول در این دور: F1** (`auth-context.tsx` + تست). هیچ فایل دیگری تغییر نکرد.

---

## ۱) وضعیت اقدامات به ترتیب درخواست

| # | اقدام | وضعیت | جزئیات |
|---|---|---|---|
| 1 | تأیید DB/کاربر/رکوردهای آزمایشی | **PASS** | `tse_quant_verify` (Alembic 0120، ۲۱۸ relation)؛ دو کاربر admin/user ساخته و پاک شدند. پیشوند خط‌تیرهٔ `audit-ui-...` طبق schema مجاز نیست (`^[a-zA-Z0-9_]+$`)؛ از underscore استفاده شد. رکوردها `AUD-UI-*`. |
| 2 | Backend تستی + `/health` و `/ready` | **PASS** | `/api/v1/health` → 200؛ `/api/v1/health/ready` → 200 با `database: ok`, `redis: ok`. |
| 3 | Auth + Gold به‌عنوان موج اول | **PARTIAL/BLOCKED** | Auth (login/logout/refresh/redirect) قبلاً PASS و F1 اصلاح شد. Gold فقط Portfolio/Alerts/Tokens (۳ صفحه Partial)؛ تلاش برای ۲۲ صفحه **با OOM خود dev server متوقف شد**؛ ۱۹ صفحه NOT RUN. |
| 4 | Silver + Portfolio/Alerts/Tokens + persistence | **PASS (قبلی)** | در موج ۲/۴ اجرا و با GET/refresh/خروج-ورود تأیید شد؛ در این دور تکرار نشد. شواهد: گزارش‌های موج ۲ و ۴. |
| 5 | Backtest/Admin/Data import در محدودهٔ تستی | **PARTIAL** | ۳ مسیر Backtest لود شد؛ ۸ مسیر NOT RUN؛ Admin (admin) PASS بارگذاری؛ Admin (user) Partial/W5-01؛ Data Import واقعی NOT RUN. |
| 6 | اصلاح فقط تأییدشده و کم‌ریسک با TDD | **PASS (F1)** | تست قرمز→سبز؛ ۱۳/۱۳؛ lint پاک؛ UI واقعی تأیید شد. سایر موارد پرریسک یا در فایل‌های دارای تغییر کاربر بودند و دست نخوردند. |

---

## ۲) جزئیات موج Auth + Gold

### Auth
- ورود صحیح، logout (از داشبورد)، refresh پس از reload، redirect مسیر محافظت‌شده قبلاً PASS.
- **F1 اصلاح شد:** رمز اشتباه حالا پیام سرور (`Invalid username or password`) را نشان می‌دهد، نه `missing access token`.
- تست‌های جدید/قدیمی: **۱۳ passed / ۰ failed**؛ `eslint` روی دو فایل تغییرکرده exit 0.

### Gold
- اجراشده (از موج‌های قبلی): `/gold/portfolio` (افزودن/فروش/DCA)، `/gold/alerts` (create/toggle/delete/seed/ack)، `/gold/tokens` (create/copy/revoke).
- تلاش این دور برای ۲۲ صفحه:
  - login موفق ثبت شد؛ سپس `/gold` با `ERR_CONNECTION_RESET` و `chrome-error://chromewebdata` مواجه شد، چون dev server کرش کرده بود.
  - **۱۹ صفحه NOT RUN** (همه به‌جز ۳ صفحهٔ بالا).
- دو مانع مستقل:
  1. **W4-03 (محصول):** با Service Worker فعال، reload صفحات `/gold` حلقه می‌زند (۱۰۲ ناوبری/۱۵s). برای تست SW را مسدود کردیم.
  2. **W5-03 (محیط):** dev server با OOM کرش می‌کند: Turbopack → `memory allocation ... failed`؛ webpack → `FATAL ERROR: Zone Allocation failed — process out of memory` بعد از ۶۰۲ ثانیه کامپایل `/gold`. `:3000` → 000. این باگ محصول نیست، اما تست پایدار Gold را فعلاً مسدود کرده است.

---

## ۳) Backtest / Admin / Data Import

| مسیر | وضعیت | شاهد |
|---|---|---|
| `/backtest` | PASS (بارگذاری) | ۱۰ دکمه، ۱۱ ورودی، ۳ select، ۶ نمودار؛ بدون خطا |
| `/backtest/engine` | PASS (بارگذاری) | ۱۰ دکمه، ۴ ورودی |
| `/backtest/walk-forward` | PASS (بارگذاری) | ۱ دکمه، ۳ ورودی، ۱ select؛ یک `500 /auth/refresh` گذرا |
| ۸ مسیر Backtest دیگر | NOT RUN | زمان/OOM محیط |
| `/admin` (admin) | PASS (بارگذاری) | کوکی httpOnly، پنل لود شد |
| `/admin` (user) | PARTIAL — W5-01 | پوسته لود؛ `/dashboard` و `/jobs/scheduler` ۴۰۳؛ `/brsapi/sync-status` ۲۰۰ |
| `/admin/users` | PARTIAL | heading لود؛ جدول/کنترل در snapshot نبود |
| `/data-import` | PARTIAL (بارگذاری) | ۱ ورودی، ۴ دکمه؛ **Import واقعی NOT RUN** |
| `/sync-manager` | PARTIAL | heading، ۲۴ دکمه؛ عملیات اجرا نشد |

**W5-01 (Medium — UI authorization):** صفحهٔ `/admin` gate نقش ندارد؛ کاربر عادی پوسته را می‌بیند. `brsapi_router` با `_require_user` mount شده، پس `/brsapi/sync-status` برای هر کاربر احرازشده by design است؛ اگر ادمین‌only است، باید نقش بگیرد. `/dashboard` و `/jobs/scheduler` با ۴۰۳ محافظت می‌شوند.

**W5-04 (Low):** یک `500 /auth/refresh` گذرا؛ نیاز به تست چرخش refresh، فعلاً تأییدشده نیست.

---

## ۴) اصلاح TDD (F1)

**قرمز:** تست جدید برای پاسخ HTTP 200 با `success:false` و `error.message="Invalid username or password"` → **FAIL** با پیام `missing access token`.

**اصلاح:** در `frontend/src/lib/auth-context.tsx` بعد از `res.json()` بررسی `json.success === false` و پرتاب پیام خطای سرور (پشتیبانی از `error` آبجکت/رشته و `message`).

**سبز:** `vitest run src/__tests__/auth-context.test.tsx` → **۱۳ passed**؛ `eslint` → 0؛ UI واقعی → پیام درست.

**فایل‌ها:** `frontend/src/lib/auth-context.tsx` (+۱۷)، `frontend/src/__tests__/auth-context.test.tsx` (+۳۰). هیچ فایل دیگری تغییر نکرد.

**موارد اصلاح‌نشده و دلیل:**
- W4-01 (فروش موجودی)، W4-02 (توکن‌ها)، W4-03 (SW)، SIL-01 (schema): پرریسک/نیازمند طراحی و تأیید.
- SIL-02 (`funds.py`)، W4-04 (portfolio)، W4-05/06 (alerts/tokens)، W4-07 (layout)، SIL-05 (silver): فایل‌های هدف تغییرات کاربر دارند؛ طبق قاعده دست نخوردند.
- W5-01: تغییر امنیتی؛ نیازمند تصمیم (ادمین‌only بودن sync-status) و تست ۴۰۳.

---

## ۵) ماتریس پوشش (وضعیت فعلی)

| وضعیت | تعداد |
|---|---:|
| PASS کامل | **0** |
| PARTIAL | **12** |
| FAIL کامل | 0 |
| BLOCKED | 0 |
| NOT RUN | **140** |
| کل صفحه | 152 |

- ۱۲ Partial: Auth/Login، Portfolio، Alerts، Tokens، Silver + ۳ Backtest + Admin + Admin/Users + Data Import + Sync Manager.
- Gold: ۳ Partial (Portfolio/Alerts/Tokens)، ۱۹ NOT RUN.
- ۷۶ اکشن قبلی (۷۳ موفق، ۳ ناموفق) بدون تغییر؛ در این دور کنترل تعاملی جدیدی کامل اجرا نشد (فقط ورود/رمز اشتباه و بارگذاری صفحات).

---

## ۶) پاک‌سازی

- کاربران `audit_ui_admin_20261030_a1`، `audit_ui_user_20261030_u1`، `audit_ui_admin_20261031_b1` حذف شدند؛ همهٔ ۱۵ جدول user-scoped صفر؛ `users=0`.
- هیچ رکورد `AUD-UI-*` جدیدی باقی نماند؛ هیچ داده واقعی تغییر نکرد.
- dev server پس از OOM خاموش شد و سپس با **webpack + heap 1536MB** دوباره بالا آمد؛ `/`, `/auth/login`, `/backtest` = 200. API تستی روی `:8000` و DB/Redis (Docker) بالا هستند. حافظهٔ آزاد حدود **۰.۵GB** است؛ کامپایل `/gold` همچنان ریسک OOM دارد.

---

## ۷) جمع‌بندی و اقدامات بعدی

**انجام‌شده:** تأیید محیط، health/ready، اصلاح F1 با TDD، smoke سه مسیر Backtest، بارگذاری Admin/Data Import/Sync Manager، کشف W5-01 و محدودیت OOM.

**مسدود/انجام‌نشده:** ۱۹ صفحهٔ Gold (OOM + SW)، ۸ مسیر Backtest، Import واقعی، Data Import write، Cross-cutting و mobile.

**اولویت بعدی:**
1. W5-01: gate نقش `/admin` + تصمیم دربارهٔ نقش `/brsapi/sync-status`؛ تست ۲۰۰/۴۰۳.
2. W4-03: رفع حلقهٔ SW؛ سپس Gold با dev پایدار.
3. W4-01: کاهش موجودی فروش (مالی).
4. W4-02: توکن‌ها.
5. حل OOM محیط (heap/webpack/production build یا ماشین تست با RAM بیشتر) و سپس ۱۹ صفحهٔ Gold + ۸ مسیر Backtest + Import با fixture.

**شاهدها:** `audit_out/_tmp/gold_all_smoke.jsonl`، `wave5_smoke_admin.json`، `wave5_smoke_progress.jsonl`، `admin_auth_probe.json`، `admin_pages_probe2.jsonl`، `ui_test_frontend_webpack.log` (OOM)، و گزارش‌های موج ۱/۲/۴/۵.

---

## ۸) اجرای برنامه و اصلاح امنیتی SEC-09 (04:40–04:58)

### وضعیت اجرا
- Docker Desktop خاموش بود؛ روشن شد و containerهای `tse_timescaledb` و `tse_redis` بالا آمدند.
- Frontend: `http://127.0.0.1:3000` — `/`، `/auth/login`، `/backtest` = **200** (webpack، heap 1536MB).
- API: `http://127.0.0.1:8000/api/v1/health` و `/health/ready` = **200** (`database: ok`, `redis: ok`).
- DB: `tse_quant_verify`، Alembic 0120، `users=0`.
- حافظهٔ آزاد ~**۰.۵GB**؛ کامپایل صفحات سنگین Gold ممکن است OOM کند.

### اصلاح SEC-09 — لو رفتن رمز Redis در لاگ
- **یافته:** لاگ‌های تست URL کامل Redis شامل رمز را چاپ می‌کردند (سه نقطه: `core/cache.py:107`، `core/cache_manager.py:137`، `integrations/cache/redis_client.py:65`).
- **TDD:**
  - تست جدید `tests/unit/test_redis_url_redaction.py` (۵ حالت: password-only، user/password، IPv6/TLS، بدون credential، malformed) ابتدا **FAIL** (ماژول نبود).
  - helper جدید `core/security/redaction.py` (`redact_redis_url`) و اتصال به هر سه log site.
  - اجرا: **۵ passed**؛ `py_compile` هر چهار فایل OK.
- **شاهد redaction:** لاگ جدید API خط `Connected to Redis at redis://:***@127.0.0.1:16379/0` را ثبت می‌کند؛ اسکن همهٔ لاگ‌های `audit_out` هیچ segment رمزِ غیر `***` پیدا نکرد.
- **فایل‌های تغییرکرده:** `core/security/redaction.py` (جدید)، `core/cache.py`، `core/cache_manager.py`، `integrations/cache/redis_client.py`، `tests/unit/test_redis_url_redaction.py` (جدید). هیچ migration/داده تغییر نکرد.
- نکته: ردیف SEC-09 در `MASTER_AUDIT_AND_REMEDIATION_PLAN_run1.md` هنوز «باز» است؛ این گزارش وضعیت fixed را ثبت می‌کند و آن فایل (که تغییر کاربر دارد) دست نخورد.

### جمع‌بندی این افزوده
- دو اصلاح محصول در این دور: **F1** (پیام login) و **SEC-09** (redaction لاگ Redis).
- پوشش UI بدون تغییر: ۰ PASS کامل، ۱۲ PARTIAL، ۱۴۰ NOT RUN (Gold همچنان به‌دلیل OOM/SW مسدود).
- کاربر تست باقی نمانده؛ `users=0`.
