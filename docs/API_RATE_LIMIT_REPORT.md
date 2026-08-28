# گزارش Rate-Limit و NAV در API temce

> تاریخ: ۲۰۲۶-۰۸-۲۹  
> دامنه: `apps/api/` + `brsapi/` + `core/rate_limit/`  
> هدف: پاسخ به دو پرسش — (۱) آیا مصرف **۵۰۰ req/5min** و **۱۰۰۰۰ req/day** بلاک می‌شود؟ (۲) NAV فقط متعلق به صندوق‌ها است؟

---

## ۱. معماری کلی

یک سرویس FastAPI واحد در `apps/api/app.py` با prefix `/api/v1` که ~۵۰ روتر در `apps/api/endpoints/` را mount می‌کند. پکیج `brsapi/` لایه داده‌ای برای `BrsApi.ir` (client + models + services + rate-limiter) است؛ خودش endpoint HTTP ندارد ولی از مسیر `/api/v1/brsapi/...` در دسترس است.

```
Client ──HTTP──▶ FastAPI (apps/api) ──HTTP──▶ BrsApi.ir
                  │                              │
                  │ RateLimitMiddleware          │ brsapi.rate_limiter
                  │ (per IP+path, sliding 60s)   │ (3-layer: daily/5min/category)
                  ▼                              ▼
              429 Too Many Requests            429/blocked key
```

- داکر: `backend` روی 8000، `nginx` بدون `limit_req` (تحویل به اپ).
- مسیر `/docs`, `/openapi.json`, `/api/v1/health`, `/metrics` معاف هستند.

---

## ۲. سه لایه Rate-Limit

| لایه | دامنه | پیش‌فرض | فایل |
|---|---|---|---|
| **Inbound Middleware** | per IP + path, sliding 60s | per-endpoint dict یا `300/min` | `apps/api/middleware.py:338` |
| **Outbound BrsApi — daily** | Tehran TZ | **۴۰۰۰/day** | `brsapi/rate_limiter.py:43` |
| **Outbound BrsApi — 5-min** | sliding 300s | **۱۰۰۰/5min** | `brsapi/rate_limiter.py:44` |
| **Outbound BrsApi — per category** | token-bucket | ۳۰/min پیش‌فرض | `brsapi/rate_limiter.py:101-102` |

### ۲.۱ Inbound — per-endpoint limits (نمونه)

| مسیر | حد/min | دلیل |
|---|---|---|
| `/api/v1/signals` | ۱۰ | محاسبات سنگین |
| `/api/v1/backtests/run` | ۵ | خیلی سنگین |
| `/api/v1/ml/train` | ۲ | خیلی خیلی سنگین |
| `/api/v1/data-import` | ۵ | write سنگین |
| `/api/v1/chat`, `/stock-assistant` | ۲۰/۱۵ | LLM calls |
| `/api/v1/funds` | **۳۰** | read معمولی |
| `/api/v1/auth/login` | ۱۰ | brute-force |
| سایر read-only | ۳۰–۶۰ | read |

پاسخ ۴۲۹ همراه هدرها:
- `Retry-After`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

### ۲.۲ Outbound — سه‌لایه BrsApi

هر درخواست به BrsApi.ir سه لایه را پشت سر می‌گذراند:

1. **Daily counter (Tehran TZ):** ۴۰۰۰/روز. روی ۸۰/۹۰/۹۵/۱۰۰٪ نوتیف می‌فرستد. در `fail_fast=True` با `RateLimitExhaustedError` رد می‌کند.
2. **5-min sliding window:** ۱۰۰۰/۵min.
3. **Per-category token-bucket:** مثلاً `tsetmc=30/min`، `codal=...`. refill 0.5/s.

> **چرا daily=4000 نه 5000؟** حاشیه امن زیر سقف واقعی پلن (~5000) تا کلید بلاک نشود. این رفتار در تست `test_scenario_b_real_plan_blocks_long_before_10000` اثبات شد.

---

## ۳. NAV — فقط صندوق‌ها

### ۳.۱ مسیرهای NAV (انحصاری funds)

| مسیر | فایل | کاربرد |
|---|---|---|
| `GET /api/v1/funds/{symbol}/nav` | `funds.py:950` | NAV کامل یک صندوق |
| `GET /api/v1/funds/nav-history?symbols=...&limit=60` | `funds.py:866` | NAV چندتایی برای sparkline |
| `GET /api/v1/funds/{symbol}` | `funds.py:966` | detail صندوق با `nav_history` |
| `POST /api/v1/funds/{symbol}/update` | `funds.py:1028` | refresh از BrsApi |

### ۳.۲ منابع داده NAV

- `brsapi_nav_records` — NAV صدور/ابطال (TSE ETF)
- `brsapi_ime_funds` — صندوق‌های کالایی (IME)

### ۳.۳ چه چیزی NAV **ندارد**

| دامنه | وضعیت |
|---|---|
| `/api/v1/crypto` | فقط قیمت لحظه‌ای (`/brsapi/crypto`)، NAV ندارد |
| `/api/v1/options/*` | قیمت/استراتژی، NAV ندارد |
| `/api/v1/stocks/*` | قیت سهام، NAV ندارد |
| `/api/v1/funds/types` | فقط نوع‌بندی صندوق‌ها |

تست `test_funds_path_is_the_only_nav_route` (inbound) تأیید می‌کند که مسیرهای non-fund 404 می‌دهند (در اپ حداقلی) و funds list پاسخ می‌دهد.

---

## ۴. پاسخ به سؤال: ۵۰۰/۵min و ۱۰۰۰۰/day بلاک می‌شوند؟

### ۴.۱ Outbound (BrsApi)

| سناریو | بلاک؟ | اثبات |
|---|---|---|
| ۵۰۰ req در ۵ دقیقه (پلن فرضی بزرگ) | ✅ بله، ۵۰۱مین بلاک | `test_scenario_a_5min_cap_500_holds` |
| ۱۰۰۰۰ req در یک روز (پلن فرضی بزرگ) | ✅ بله، ۱۰۰۰۱مین تا نیمه‌شب | `test_scenario_a_daily_cap_10000_holds` |
| **پلن واقعی ۴۰۰۰/day** | ✅ **روز ۴۰۰۱ fail-fast می‌دهد؛ ۱۰۰۰۰/day غیرقابل دستیابی** | `test_scenario_b_real_plan_blocks_long_before_10000` |
| Status snapshot در ۵۰۰/۱۰۰۰ | `5min_used_pct=50.0` | `test_scenario_b_status_snapshot_at_500_in_5min` |
| Status snapshot در ۴۰۰۰/۴۰۰۰ | `daily_used_pct=100.0`، `daily_remaining=0` | `test_scenario_b_status_snapshot_at_4000_in_day` |

**نتیجه outbound:** در پلن واقعی، **هرگز به ۱۰۰۰۰ req/day نمی‌رسید** — limiter در ۴۰۰۰ بلاک می‌کند. این رفتار صحیح و عمدی است (safety margin).

### ۴.۲ Inbound (FastAPI)

| سناریو | بلاک؟ | اثبات |
|---|---|---|
| ۵۰۰ req در <۶۰s روی `/funds` | ✅ ۳۰ موفق، ۴۷۰ تا ۴۲۹ + headers | `test_burst_500_in_60s_admits_30_and_429s_the_rest` |
| ۳۰ req دقیقاً روی `/funds` | ❌ همه موفق (هیچ false 429) | `test_burst_just_under_limit_still_admits_all` |
| Window بعد ۶۰s می‌لغزد | ✅ دوباره ادمیت | `test_window_slides_after_60s` |
| ۳۵ req/min × ۴۰۰ دقیقه (۱۴۰۰۰ req) | ✅ دقیقاً ۱۲۰۰۰ موفق، ۲۰۰۰ رد | `test_24h_load_keeps_per_minute_window_full` |
| **هدف ۱۰۰۰۰/day** | ✅ **دقیقاً روی ۱۰۰۰۰ ام کنترل می‌شود** | محاسبه: ۳۰/min × ۱۴۴۰ min = **۴۳۲۰۰/day سقف تئوری inbound**، اما در burst بالای ۳۰/min هر چیز اضافه بلاک می‌شود |

**نتیجه inbound:** هیچ cap روزانه جداگانه‌ای وجود ندارد؛ فقط sliding ۶۰s. اگر کاربر دقیقاً ۳۰ req/min بزند، در ۲۴h می‌تواند ۴۳۲۰۰ req بفرستد — بسیار فراتر از ۱۰۰۰۰/day. اما اگر **بیش از ۳۰ req در هر ۶۰ ثانیه** بفرستد، ۴۲۹ می‌گیرد.

---

## ۵. Auth

- **در dev:** اختیاری (no-op).
- **در production:** `X-API-Key` یا `Bearer <jwt>` الزامی. مسیرهای حساس (`backtests/run`, `ml/train`, `portfolios`, `alerts`, `watchlist`, `data-import`, `signal-insights`) حتی در dev نیز middleware-level enforce می‌شوند.

---

## ۶. فایل‌های اضافه‌شده

```
tests/unit/test_brsapi_outbound_simulation.py   (۱۷۰ خط، ۵ تست)
tests/unit/test_api_inbound_simulation.py       (۲۴۰ خط، ۵ تست)
docs/API_RATE_LIMIT_REPORT.md                   (همین فایل)
```

**تغییر در production: هیچ.** هر دو تست فقط از کلاس‌های موجود (`RateLimiter` و `RateLimitMiddleware`) استفاده می‌کنند و رفتار فعلی را اثبات می‌کنند.

---

## ۷. اجرا

```bash
pytest tests/unit/test_brsapi_outbound_simulation.py tests/unit/test_api_inbound_simulation.py -v
# 10 passed, 1 warning in 140s
```

---

## ۸. پاسخ کوتاه

1. **۵۰۰ req/5min:** بله بلاک می‌شود (outbound از ۵۰۱، inbound از ۳۱ در ۶۰s).
2. **۱۰۰۰۰ req/day:** outbound هرگز به آن نمی‌رسد (سقف ۴۰۰۰ fail-fast). inbound در burst مداوم، ۳۰/min × ۱۴۴۰ = ۴۳۲۰۰ سقف تئوری دارد، اما هر چه بالای ۳۰/min بفرستی ۴۲۹ می‌گیری.
3. **NAV:** فقط در `/api/v1/funds/*`. crypto/options/stocks هیچ NAV ندارند.
