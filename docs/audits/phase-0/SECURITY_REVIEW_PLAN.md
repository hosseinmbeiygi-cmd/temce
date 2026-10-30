# برنامه امنیت و قابلیت اطمینان — فاز صفر

**دامنه:** اپ مونت‌شده با ۷۱۴ route، ۱۰۳ مسیر gold، زیرساخت Docker/K8s/nginx.
**محدودیت:** هیچ تست نفوذ، اسکن فعال، یا عملیات تغییردهنده روی سرویس واقعی انجام نشد. همه موارد زیر یا از کد خوانده شده‌اند یا از اجرای محلی بی‌خطر.

---

## 1. سطح حمله (Attack Surface)

| سطح | تعداد | محافظ فعلی | شاهد |
|---|---|---|---|
| `/api/v1/*` | 714 route | JWT + rate limit + error masking | `apps/api/router.py`, `middleware.py` |
| Gold شخصی (`src/gold_desk/api.py`) | 65 route در router شخصی | `_require_user` در mount | `apps/api/router.py:296` |
| Gold عمومی | `health`, `assistant-rules`, `metrics`, `ws` | فقط خواندن؛ WS توکن داخلی | خروجی `anonymous_router.routes` |
| Gold Analytics | 26 route | **عمومی** (قرارداد: ماشین‌حساب بدون داده حساب) | `apps/api/router.py:267-271` |
| GoldDesk SaaS | `/golddesk/*` | توکن scoped | `apps/api/router.py:264` |
| ادمین | `/jobs`, `/tests`, `/tables` | `_require_admin` | `apps/api/router.py:582,645` |
| WebSocket | `/gold/ws`, `/ws` | بررسی توکن/Origin | `test_ws_origin_and_table_guard.py` |
| فرانت | 472 فایل TS/TSX | middleware + refresh cookie httpOnly | `frontend/src/middleware.ts`, `lib/api.ts` |

---

## 2. چک‌لیست امنیتی

| مورد | وضعیت | شاهد / توضیح |
|---|---|---|
| احراز هویت JWT | **تأییدشده** | `apps/api/auth.py`, `dependencies.py` |
| refresh تک‌پرواز | **تأییدشده** | `api.ts:76-115` (`_refreshPromise`) |
| idempotency خروج ۴۰۱ | **نیازمند بررسی** | `_handle401` گارد ندارد (ISSUE-112) |
| کنترل دسترسی سطح ادمین | **تأییدشده** | `_require_admin` روی jobs/tests/tables |
| دسترسی طلا بدون auth | **تأییدشده (طراحی)** | فقط ۴ مسیر عمومی خواندنی؛ کامنت کهنه ISSUE-108 |
| مدیریت اسرار | **تأییدشده** | `.env` در `.gitignore:19` و track نشده؛ compose با `${VAR:?}` fail-closed (`:13,29,47-59`) |
| salt توکن طلا | **تأییدشده** | بدون `GOLD_API_TOKEN_SALT` اپ بالا نمی‌آید (`api_token.py:35`) |
| اعتبارسنجی production | **تأییدشده** | `core/config/__init__.py:435-455`؛ SECRET_KEY، AUTH_DISABLED، CORS، SQLite، cookie secure |
| AUTH_DISABLED پیش‌فرض | **تأییدشده** | `default=False` (`:122`) و در production ممنوع |
| rate limiting | **تأییدشده در اپ / نیازمند بررسی در edge** | `middleware.py:390-501`؛ در `nginx-golddesk.conf` هیچ `limit_req` پیدا نشد |
| masking خطا | **تأییدشده** | `error_handlers.py:26-50` |
| CORS | **نیازمند بررسی** | `CORS_ORIGINS` در production اعتبارسنجی می‌شود؛ مقدار واقعی env قابل خواندن نیست |
| اسکن اسرار | **تأییدشده (ابزار)** | `.github/workflows/secrets-scan.yml` + `.gitleaks.toml` |
| اسرار در تاریخچه Git | **ریسک باقی‌مانده** | هدر `.gitleaks.toml` صریحاً می‌گوید رمز Redis و توکن صف از compose حذف شده‌اند اما «در تاریخچه و روی origin باقی‌اند» → چرخش (rotation) اجباری |
| health check | **تأییدشده جزئی** | `timescaledb` healthcheck (`compose:18-22`)؛ health اپ `/health` |
| backup/restore | **ابزار موجود، اجرا نشده** | `scripts/backup_postgres.py`, `backup_golddesk.sh`, `test_restore_golddesk.sh` |
| rollback | **نیازمند بررسی** | migration برگشت‌پذیر؟ فقط با بازبینی تک‌تک در فاز ۳ |
| رفتار قطع Redis | **تأییدشده** | null cache + warning (شاهد در لاگ تست) |
| رفتار قطع PostgreSQL | **تأییدشده (خطا)** | لاگ asyncpg در تست‌ها؛ `needs_db` skip |
| افشای اطلاعات در خطا | **تأییدشده** | `safe_error_message` در production |
| ورودی‌های بدون اعتبارسنجی | **نیازمند بررسی** | Pydantic در بیشتر endpointها؛ endpointهای با `dict` خام باید فهرست شوند |
| SQL injection | **نیازمند بررسی** | استفاده از `text()` با نام جدول در `base.py:346`؛ گارد `safe_identifier` در `test_ws_origin_and_table_guard.py` وجود دارد |
| ثبت رویداد امنیتی | **نیازمند بررسی** | rate-limit و middleware لاگ می‌کنند؛ لاگ ورود ناموفق/توکن باطل تأیید نشد |
| observability | **تأییدشده جزئی** | Prometheus/OTLP پیکربندی شده؛ الزام `OTLP_ENDPOINT` در production |

---

## 3. تست‌های مجاز این فاز (و آنچه ممنوع است)

**مجاز:**
- `ruff check` و `grep` ایستا.
- اجرای تست‌های موجود امنیتی: `tests/unit/test_ws_origin_and_table_guard.py`، تست‌های auth.
- `docker compose config` بدون بالا آوردن سرویس (در صورت نصب Docker).
- gitleaks روی working tree (بدون تاریخچه کامل).

**ممنوع:**
- اسکن فعال/نفوذ، ارسال payload مخرب به سرویس در حال اجرا.
- تلاش برای ورود با credential واقعی، ثبت سفارش، تغییر داده.
- `git filter-branch`/پاک‌سازی تاریخچه بدون مجوز کتبی.

---

## 4. مالکیت و معیار پذیرش

| حوزه | مالک | معیار پذیرش فاز ۳ |
|---|---|---|
| auth/session/۴۰۱ | دستیار ۳ (بازبینی) + ۲ (اصلاح) | تست موازی 401: فقط یک logout؛ بدون حلقه redirect |
| rate limit/edge | دستیار ۳ | `limit_req` در nginx یا مستند تصمیم به اتکا به اپ |
| اسرار/چرخش | دستیار ۳ + مالک محصول | فهرست secretهای تاریخی و تاریخ چرخش ثبت شود |
| health/backup/rollback | دستیار ۳ | اجرای آزمایشی restore روی محیط محلی + مستند RTO |
| قرارداد خطا | دستیار ۳ | تست schema برای `{success:false,error}` |
| injection/table guard | دستیار ۱ + ۳ | تست منفی برای `text(table_name)` |
