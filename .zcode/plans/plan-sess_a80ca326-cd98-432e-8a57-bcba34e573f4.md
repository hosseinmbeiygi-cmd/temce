## گزارش و پلن

### بخش ۱ — گزارش API (توصیفی، بدون تغییر)

**ساختار کلی**
- یک سرویس FastAPI در `apps/api/app.py`، prefix `/api/v1`. ~۵۰ روتر در `apps/api/endpoints/`. داکر: backend روی 8000، nginx بدون rate-limit (تحویل به اپ).
- پکیج `brsapi/` لایه داده‌ای برای BrsApi.ir (client + models + services) است؛ خودش HTTP endpoint ندارد ولی از طریق `/brsapi/...` (همان اپ) در دسترس است.

**لایه‌های Rate-Limit (۳ لایه)**

| لایه | دامنه | پیش‌فرض | فایل |
|---|---|---|---|
| Inbound Middleware | per IP+path, sliding 60s | dict per-endpoint یا 300/min | `apps/api/middleware.py:338` |
| Outbound BrsApi — global daily | Tehran TZ | **4000/day** | `brsapi/rate_limiter.py:43` |
| Outbound BrsApi — global 5min | sliding 300s | **1000/5min** | `brsapi/rate_limiter.py:44` |
| Outbound BrsApi — per category | token-bucket | پیش‌فرض 30/min | `brsapi/rate_limiter.py:101-102` |

مقادیر per-endpoint مهم: `/signals=10`, `/backtests/run=5`, `/ml/train=2`, `/data-import=5`, `/chat=20`, `/funds=30`, `/market*` و `/codal/...` معمولاً 30.

**NAV — فقط صندوق‌ها**
- `GET /api/v1/funds/{symbol}/nav` (`funds.py:950`)، `GET /api/v1/funds/nav-history` (`funds.py:866`)، `GET /api/v1/funds/{symbol}` (`funds.py:966`).
- منابع: `brsapi_nav_records` (NAV صدور/ابطال) + `brsapi_ime_funds` (صندوق‌های کالایی).
- هیچ NAV در crypto/options/stocks وجود ندارد. صفحه `/crypto` فقط قیمت لحظه‌ای از `/brsapi/crypto` می‌گیرد.

**Auth**: در dev اختیاری، در production `X-API-Key` یا Bearer الزامی (در `_SENSITIVE_WRITE_PREFIXES` حتی در dev اجباری است).

---

### بخش ۲ — دو تست شبیه‌سازی (بدون تغییر در کد production)

#### تست ۱ — Outbound BrsApi (`tests/unit/test_brsapi_outbound_simulation.py`)

هدف: ثابت کند اگر مصرف به **500 req/5min** و **10000 req/day** برسد، آیا limiter به‌درستی بلاک می‌کند یا نه. نکته: پلن واقعی 4000/day است (نه 10000)، پس شبیه‌سازی باید نشان دهد که آستانه 10000/day هرگز بلاک نمی‌شود چون پیش‌تر روی 4000 بلاک می‌شود. این خودش یافته گزارش است.

ساختار:
- `RateLimiter` را با `daily_limit=10000, five_min_limit=500` نمونه‌سازی کن (override پیش‌فرض).
- async loop: 500 درخواست در 5 دقیقه تزریق کن با `fake_sleep`، انتظار: 500 ام پس از پنجره بلاک شود. سپس تست کن اگر به 4000 در روز برسیم (کمتر از 10000)، بلاک می‌شویم.
- استفاده از `asyncio.sleep` به جای sleep واقعی برای سرعت.

#### تست ۲ — Inbound API (`tests/unit/test_api_inbound_simulation.py`)

هدف: ثابت کند کاربری که به یک endpoint (مثل `/api/v1/funds` با limit=30/min) بیش از 30 req در 60s می‌زند، 429 می‌گیرد؛ و در 24 ساعت با 300 req/min × 1440 دقیقه = بیش از 10000 در شبانه‌روز، 429 می‌گیرد.

ساختار:
- اپ حداقلی با `RateLimitMiddleware(window_seconds=60)`.
- `TestClient`، 35 درخواست متوالی روی `/api/v1/funds`، انتظار: 30 موفق، 5 تاش 429.
- تست دوم: 1440 چرخه × 35 req روی یک endpoint (sliding window 60s) → 100% بلاک. نمایشگر "exceeded 10000/day" با header.

#### تغییرات production: **هیچ**

فایل‌های جدید:
- `tests/unit/test_brsapi_outbound_simulation.py` (≈۹۰ خط)
- `tests/unit/test_api_inbound_simulation.py` (≈۷۰ خط)

بدون تغییر در `brsapi/rate_limiter.py`، `apps/api/middleware.py`، یا تنظیمات. NAV نیاز به تغییر ندارد (فقط در `/funds` استفاده می‌شود، تأیید شد).

skipped: اضافه کردن endpoint جدید `/api/v1/sim/usage` برای اجرای زنده — این فقط تست واحد می‌ماند. add when: نیاز به دموی داشبورد.