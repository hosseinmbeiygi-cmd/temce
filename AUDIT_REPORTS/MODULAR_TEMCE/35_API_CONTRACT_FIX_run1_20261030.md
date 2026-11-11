# ۳۵ — اصلاح قرارداد API: operationId و اعلام امنیت — run1، ۳۰ اکتبر ۲۰۲۶

**یافته‌ها:** `AUD-API-01` و `AUD-API-02` — وضعیت **FIXED**.
**دامنه:** فقط متادیتای OpenAPI؛ رفتار runtime تغییر نکرد. تغییرات commit نشده‌اند.

---

## ۱) AUD-API-01 — operationId تکراری

**قبل:** `/api/v1/market/watch` (در `market.py`) و `/api/v1/market-watch`
(در `market_watch.py`) هر دو تابع `market_watch` داشتند و FastAPI برای هر دو
`market_watch_api_v1_market_watch_get` می‌ساخت؛ تولید کلاینت/کدجن با برخورد مواجه می‌شد.

**اصلاح:** `operation_id="market_watch_dashboard"` روی روت `market_watch.py`
(`apps/api/endpoints/market_watch.py:19`).

**اثبات:** `app.openapi()` → ۶۷۱ مسیر، ۷۰۶ عملیات، **۰** operationId تکراری.

---

## ۲) AUD-API-02 — قرارداد بدون طرح امنیتی

**ریشه:** احراز هویت با `Authorization: Header("")` و `Depends(get_current_user)` است؛
FastAPI فقط برای `Security(...)` فیلد `security` تولید می‌کند، بنابراین ۷۰۶/۷۰۶ عملیات
بدون طرح امنیتی بودند.

**اصلاح:** فایل جدید `apps/api/openapi_security.py` که `app.openapi()` را wrap می‌کند:
- `components.securitySchemes.bearerAuth` = `http` / `bearer` / `JWT` را اعلام می‌کند؛
- برای هر روت، درخت dependency را می‌پیماید؛ اگر `get_current_user` /
  `get_current_active_user` / `require_role` باشد، همهٔ متدها و اگر
  `require_user_for_writes` باشد فقط متدهای نوشتن،
  `security: [{bearerAuth: []}]` می‌گیرند.
- در `create_app()` بعد از `include_router` نصب می‌شود.

**اثبات:**
- `security_schemes = ['bearerAuth']`
- `operations_with_security = 551 / 706`
- مسیرهای عمومی همچنان public: `/api/v1/market/watch`، `/api/v1/market-watch`،
  `/api/v1/gold/analytics/feed-health`، `/api/v1/gold/analytics/macro/calendar`
- `verify_api_key` (X-API-Key) در کد استفاده نمی‌شود، پس طرح API-key اعلام نشد.

---

## ۳) تست‌ها

| اجرا | نتیجه |
|---|---|
| `pytest tests/unit/api -q` بدون DSN روی ۱۵۴۳۲ | ۳۷۶ passed / ۸ failed / ۶ skipped — ۷ مورد همان تست‌های gold وابسته به `localhost:5432`، ۱ مورد tier/rate-limit |
| همان ۸ مورد با `DATABASE_URL` روی ۱۵۴۳۲ | **۵۷ passed / ۰ failed** |

نتیجه: تغییر OpenAPI رگرسیون رفتاری نداده؛ شکست‌ها محیطی/ترتیبی بودند. تست tier در
اجرای هدفمند پاس شد.

---

## ۴) فایل‌ها

```
apps/api/endpoints/market_watch.py   + operation_id (۱ خط)
apps/api/openapi_security.py         جدید (~۷۰ خط)
apps/api/app.py                      + import و فراخوانی نصب (۲ خط)
```

## ۵) باقی‌مانده

- احراز هویت همچنان با `Header("")` است؛ لایهٔ جدید فقط قرارداد را درست می‌کند. مهاجرت
  واقعی به `Security(HTTPBearer())` یک slice جداگانه است (بیش از ۱۰۰ نقطه).
- `verify_api_key` کد مرده است؛ یا باید استفاده شود یا حذف.
- تعیین عمومی/خصوصی بودن هر مسیر همچنان به رفتار dependency فعلی وابسته است؛ اگر
  مسیری بعداً عمومی شود، باید از dependency مربوطه خارج شود.

## ۶) وضعیت

| مورد | وضعیت |
|---|---|
| AUD-API-01 | **FIXED** |
| AUD-API-02 | **FIXED** (متادیتا) |
| رگرسیون runtime | **PASS** (۵۷/۵۷ هدفمند) |
| commit | **BLOCKED** (درخت مشترک؛ منتظر دستور) |
