# 📡 apps/api/ — لایه API (REST + WebSocket)

> **آخرین به‌روزرسانی:** ۲۰۲۶-۰۸-۰۱ — فاز ۵

لایه API سیستم بازار سرمایه ایران — ۴۵ endpoint روی FastAPI با معماری lazy-import،
میان‌افزارهای امنیتی/rate-limit و taskهای پس‌زمینه.

---

## 🏗️ معماری

```
apps/api/
├── app.py              # create_app() — lifespan, middleware, startup tasks
├── router.py           # Router.setup() — lazy imports + include_router برای همه endpoint ها
├── main.py             # entry-point
├── dependencies.py     # همه dependency های FastAPI (get_current_user, get_market_service, ...)
├── middleware.py        # Timing, Logging, Security, RateLimit middleware
├── error_handlers.py   # ثبت handlerهای خطای عمومی
├── pagination.py        # PaginationParams, PaginatedResult (pydantic)
├── README.md           # همین فایل
└── endpoints/          # ۴۵ فایل endpoint (هر کدام یک APIRouter)
    ├── auth.py         # ورود، ثبت‌نام، مدیریت کاربران
    ├── market.py       # overview, indices, heatmap, OHLCV, sparklines
    ├── signals.py      # سیگنال‌های معاملاتی
    ├── screener.py     # screener V1 (پنج‌فازی)
    ├── screener_v2.py  # screener V2 (تحلیل پیشرفته)
    ├── brsapi.py       # کالا، ارز، طلا، سکه، رمزارز
    ├── funds.py        # صندوق‌های سرمایه‌گذاری
    ├── health.py       # health/ready/live/full probes
    ├── market_dashboard.py  # داده‌های داشبورد اصلی
    ├── market_watch.py # دیده‌بان بازار
    ├── market_info.py  # صنایع و صندوق‌ها (namespace: /market-info)
    ├── market_insights.py  # صف‌های تقلبی، accumulation, fear-greed
    ├── smart_money.py  # پول هوشمند
    ├── analysis.py     # تحلیل تکنیکال و sentiment
    ├── anomalies.py    # تشخیص آنومالی قیمت/حجم
    ├── portfolios.py   # مدیریت پرتفوی
    ├── quotes.py       # قیمت‌های لحظه‌ای و تاریخی
    ├── orderbooks.py   # مظنه‌ها
    ├── trades.py       # تاریخچه معاملات
    ├── indicators.py   # اندیکاتورهای تکنیکال
    ├── codal.py        # اطلاعیه‌های کدال
    ├── backtests.py    # بک‌تست استراتژی
    ├── ml.py           # مدل‌های یادگیری ماشین
    ├── recommendations.py  # پیشنهادات خرید/فروش
    ├── news.py         # اخبار بازار
    ├── macro.py        # شاخص‌های کلان اقتصادی
    ├── fundamental.py  # تحلیل بنیادی
    ├── economic_calendar.py  # تقویم اقتصادی
    ├── alpha.py        # استراتژی‌های آلفا
    ├── risk.py         # مدیریت ریسک
    ├── alerts.py       # هشدارهای قیمت/اندیکاتور
    ├── chat.py         # چت‌بات هوش مصنوعی
    ├── assistant.py    # دستیار یکپارچه
    ├── stock_assistant.py  # دستیار سهام
    ├── data_import.py  # ورود داده CSV
    ├── jobs.py         # مدیریت jobهای زمان‌بندی
    ├── saved_filters.py    # فیلترهای ذخیره‌شده کاربر
    ├── screener110.py  # screener ۱۱۰ ستونی CANSLIM
    ├── decision_engine.py  # معماری تصمیم‌یار
    ├── queue_analysis.py  # تحلیل صف‌ها
    ├── signal_insights.py  # تحلیل دقت سیگنال‌ها
    ├── multi_market_signals.py  # سیگنال‌های چندبازاری
    ├── compose.py      # ترکیب استراتژی
    ├── symbol_search.py    # جستجوی نماد (بدون DB)
    ├── symbols.py      # مدیریت نمادها
    ├── tables.py       # مرورگر جداول
    ├── tabdeal.py      # صرافی تبدیل
    ├── tests_runner.py # اجرای تست‌ها
    └── websocket.py    # WebSocket داده‌های لحظه‌ای
```

---

## 🚀 Lazy Import Architecture

`Router.setup()` همه ۴۵ файл endpoint را **داخل متد** import میکند
(نه در سطح module) تا import کلاس `Router` (~۳۰۰ms) کل endpointها را
بارگذاری نکند (~۴۵s cumulative). این الگو در `apps/api/endpoints/__init__.py`
مستند شده:

```python
# apps/api/endpoints/__init__.py
"""
API endpoint routers.

Each endpoint module is imported lazily by Router.setup() —
never at module level — to keep import times under 1 second.
"""
__all__ = [
    "alerts_router",
    "alpha_router",
    ...
]
```

---

## 🛣️ Route Structure

همه endpoint ها زیر prefix `/api/v1` (از `settings.api_prefix`) نصب می‌شوند:

| Prefix | Endpoint | Auth | توضیح |
|--------|----------|------|-------|
| `/health` | Health | ❌ | health/ready/live/full |
| `/auth` | Auth | ❌ | login, register, refresh, logout, profile |
| `/market` | Market | اختیاری | overview, indices, heatmap, OHLCV |
| `/market-dashboard` | Market Dashboard | اختیاری | داده‌های تجمیعی داشبورد |
| `/market-watch` | Market Watch | اختیاری | دیده‌بان بازار |
| `/market-info` | Market Info | اختیاری | صنایع و صندوق‌ها |
| `/instruments` | Symbols | اختیاری | مدیریت نمادها |
| `/symbols` | Symbol Search | اختیاری | جستجوی نماد (بدون DB) |
| `/quotes` | Quotes | اختیاری | قیمت‌های لحظه‌ای |
| `/orderbooks` | Orderbooks | اختیاری | مظنه‌ها |
| `/trades` | Trades | اختیاری | تاریخچه معاملات |
| `/signals` | Signals | کاربر+ | سیگنال‌های معاملاتی |
| `/recommendations` | Recommendations | اختیاری | پیشنهادات |
| `/indicators` | Indicators | اختیاری | اندیکاتورهای تکنیکال |
| `/chat` | Chat | اختیاری | چت‌بات |
| `/codal` | Codal | اختیاری | اطلاعیه‌های کدال |
| `/data-import` | Data Import | ادمین | ورود CSV |
| `/economic-calendar` | Economic Calendar | اختیاری | تقویم اقتصادی |
| `/news` | News | اختیاری | اخبار بازار |
| `/jobs` | Jobs | ادمین | زمان‌بندی jobها |
| `/macro` | Macro | اختیاری | شاخص‌های کلان |
| `/fundamental` | Fundamental | اختیاری | تحلیل بنیادی |
| `/backtests` | Backtests | تحلیلگر+ | بک‌تست استراتژی |
| `/ml` | ML | تحلیلگر+ | مدل‌های ML |
| `/multi-market-signals` | Multi-Market Signals | اختیاری | سیگنال‌های چندبازاری |
| `/reports` | Reports | اختیاری | گزارش‌های تولیدشده |
| `/smart-money` | Smart Money | اختیاری | پول هوشمند |
| `/analysis` | Analysis | اختیاری | تحلیل تکنیکال |
| `/anomalies` | Anomalies | اختیاری | آنومالی‌ها |
| `/alpha` | Alpha | اختیاری | استراتژی‌های آلفا |
| `/risk` | Risk | اختیاری | مدیریت ریسک |
| `/funds` | Funds | اختیاری | صندوق‌های سرمایه‌گذاری |
| `/saved-filters` | Saved Filters | اختیاری | فیلترهای ذخیره‌شده |
| `/screener` | Screener | اختیاری | اسکرینر هوشمند |
| `/screener110` | Screener110 | اختیاری | اسکرینر CANSLIM |
| `/screener-v2` | Smart Screener V2 | اختیاری | اسکرینر پیشرفته |
| `/stock-assistant` | Stock Assistant | اختیاری | دستیار سهام |
| `/assistant` | Unified Assistant | اختیاری | دستیار یکپارچه |
| `/tests` | Tests | اختیاری | اجرای تست‌ها |
| `/portfolios` | Portfolios | کاربر+ | مدیریت پرتفوی |
| `/watchlist` | Watchlist | اختیاری | لیست‌های دیده‌بان |
| `/dashboard` | Admin Dashboard | ادمین | پنل مدیریت |
| `/brsapi` | BrsApi | اختیاری | کالا، ارز، طلا |
| `/tabdeal` | Tabdeal | اختیاری | صرافی تبدیل |
| `/tables` | Tables | اختیاری | مرورگر جداول |
| `/compose` | Strategy Composition | اختیاری | ترکیب استراتژی |
| `/market-insights` | Market Insights | اختیاری | صف‌های تقلبی، accumulation |
| `/signal-insights` | Signal Insights | تحلیلگر+ | تحلیل دقت سیگنال‌ها |
| `/decision-engine` | Decision Engine | اختیاری | معماری تصمیم‌یار |
| `/queue-analysis` | Queue Analysis | اختیاری | تحلیل صف‌ها |
| `/ws` | WebSocket | ❌ | داده‌های لحظه‌ای |

---

## 🛡️ Middleware Stack

Middlewareها به ترتیب زیر در `create_app()` ثبت می‌شوند:

```python
app.add_middleware(CORSMiddleware, ...)  # از core.config
app.add_middleware(SecurityMiddleware)   # هدرهای امنیتی + اعتبارسنجی write-sensitive
app.add_middleware(TimingMiddleware)     # X-Response-Time-Ms
app.add_middleware(LoggingMiddleware)    # لاگ درخواست/پاسخ
app.add_middleware(RateLimitMiddleware)  # محدودیت نرخ sliding-window
```

### SecurityMiddleware
- اضافه کردن هدرهای امنیتی به همه پاسخ‌ها (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, ...)
- اعتبارسنجی token در سطح middleware برای endpointهای write-sensitive (دفاع در عمق)

### RateLimitMiddleware
- محدودیت نرخ sliding-window با الگوریتم `core.rate_limit.RateLimiter`
- هر `{client_ip}:{path}` کلید جداگانه دارد
- `has_limit(key)` + `set_limit(key, ...)` در اولین درخواست → `allow(key)` برای درخواست‌های بعدی
- هدرهای `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- تنظیم limits در `core.config.settings.endpoint_rate_limits`

---

## 🔄 Lifespan & Background Tasks

در `@asynccontextmanager lifespan()` ترتیب راه‌اندازی:

1. **setup_logging()**
2. **init_database()** — resilient (خطا → ادامه بدون DB)
3. **register_all_models()** — ML modelها (اختیاری)
4. **Cache.initialize()** — Redis (اختیاری)
5. **BrsApi rate limiter** — ثبت callback هشدار
6. **SchedulerApp.start()** — jobهای زمان‌بندی
7. **asyncio.create_task(_brsapi_startup_sync())** — همگام‌سازی اولیه BrsApi
8. **asyncio.create_task(_fetch_news_on_startup())** — دریافت اخبار RSS
9. **asyncio.create_task(_decision_engine_startup_seed())** — seed معماری
10. **RealtimeService.start()** — WebSocket broadcasting
11. **asyncio.create_task(_orchestrator_hourly_cron())** — تولید سیگنال ساعتی
12. **asyncio.create_task(_fund_sync_cron())** — همگام‌سازی صندوق‌ها (هر ۱۵ دقیقه)

هنگام shutdown:
- `RealtimeService.stop()`
- `cache.close()`
- `close_database()`

---

## 🐛 اشکالات رفع‌شده در فاز ۵

### 🔴 بحرانی — باگ Rate Limit در auth.py

**مشکل:** `_limiter.set_limit("auth:login", rate=5/60, burst=5)` کلید بدون IP
(`"auth:login"`) را ثبت میکرد، اما `_rate_limit_auth` کلید با IP
(`"auth:login:{client_ip}"`) را بررسی میکرد. چون `RateLimiter.allow()` برای
کلیدهای ثبت‌نشده `True` برمی‌گرداند، **محدودیت نرخ هرگز فعال نمیشد** —
محافظت در برابر brute-force عملاً وجود نداشت.

**رفع:** ثبت lazy به ازای هر IP در `_rate_limit_auth` با الگوی
`has_limit(key)` + `set_limit(key, ...)` — دقیقاً مانند `RateLimitMiddleware`:

```python
_AUTH_LIMITS = {
    "login": (5 / 60.0, 5),
    "register": (3 / 60.0, 3),
    "change_password": (3 / 60.0, 3),
}

def _rate_limit_auth(request, endpoint):
    key = f"auth:{endpoint}:{client_ip}"
    rate, burst = _AUTH_LIMITS[endpoint]
    if not _limiter.has_limit(key):
        _limiter.set_limit(key, rate=rate, burst=burst)
    if not _limiter.allow(key):
        raise HTTPException(429, ...)
```

**تست رگرسیون:** `tests/unit/test_auth_rate_limit.py` — ۶ تست تأیید می‌کنند:
- ۵ درخواست مجاز → ششم ۴۲۹
- IPهای متفاوت مستقل هستند (همان باگ اصلی)
- endpointهای مختلف سطل جداگانه دارند
- بازنشانی پنجره بعد از ۶۰ ثانیه
- fallback به `"unknown"` برای درخواست بدون client

### 🟡 تداخل Route در market_info

**مشکل:** `market_info_router` بدون prefix نصب میشد → مسیرهای `/funds` و
`/industries` در ریشه `/api/v1`. مسیر `/funds` با `funds_router` (نصب‌شده
در `/funds`) تداخل داشت.

**رفع:** نصب با prefix `/market-info` → مسیرها: `/api/v1/market-info/industries`
و `/api/v1/market-info/funds`.

### 🟡 ناسازگاری total_pages=0

**مشکل:** پاسخ‌های خطا/خالی در ۵ فایل endpoint از `total_pages=0` استفاده
میکردند در حالی که پاسخ‌های موفق `total_pages=1` داشتند. `PaginatedResult`
در `core/typing` یک dataclass ذخیره‌ای است — `total_pages=0` محاسبات
`has_next`/`has_prev` را تحت تأثیر قرار نمیداد ولی ناسازگار بود.

**رفع:** نرمال‌سازی به `total_pages=1` در:
- `signals.py` (۲ مورد)
- `news.py` (۳ مورد)
- `codal.py` (۱ مورد)
- `macro.py` (۲ مورد)
- `brsapi.py` (۳ مورد)

### 🟢 ارتقا — یکپارچه‌سازی Rate Limiter در screener

**مشکل:** `screener.py` و `screener_v2.py` هر کدام پیاده‌سازی sliding-window
مخصوص خود را با `_rate_limits: dict[str, list[float]]` داشتند — کد تکراری
و ناسازگار با `RateLimiter` مشترک.

**رفع:** جایگزینی با `core.rate_limit.RateLimiter` مشترک با کلیدهای
`screener:{ip}` و `screener-v2:{ip}` — همان سیاست ۳۰ درخواست/۶۰ ثانیه
با کد کمتر و بدون دیکشنری در حال رشد.

---

## 🧪 تست‌ها

| فایل تست | تعداد | توضیح |
|----------|-------|-------|
| `tests/unit/test_rate_limit_middleware.py` | ۳۰ | sliding window، prefix match، 429 headers، exempt paths |
| `tests/unit/test_auth_rate_limit.py` | ۷ | رگرسیون باگ بحرانی auth rate-limit |
| `tests/unit/test_endpoints.py` | ۱۷ | تست endpointها |
| `tests/unit/test_security_middleware.py` | — | اعتبارسنجی امنیتی |
| `tests/unit/test_backend_api.py` | — | تست‌های یکپارچگی API |

> **فاز ۵:** ۵۴ تست پاس (rate-limit + middleware + endpoints) ✅

---

## ⚙️ Dependency Injection

همه سرویس‌ها از طریق `apps/api/dependencies.py` با `Depends` تزریق می‌شوند:

```python
def get_market_service(
    session = Depends(get_db_session),
    brsapi = Depends(get_brsapi_query_service),
    client = Depends(get_brsapi_client),
):
    return MarketService(session, brsapi, client)
```

دسترسی‌ها:
- `get_current_user` — احراز هویت اجباری (۴۰۱ در صورت عدم وجود)
- `get_optional_user` — احراز هویت اختیاری (None در صورت عدم وجود)
- `require_roles(*roles)` — کنترل دسترسی مبتنی بر نقش (admin, analyst, user)

---

## 📝 نکات طراحی

1. **Lazy imports** — `Router.setup()` همه endpointها را در زمان اجرا import
   میکند (نه در سطح module) برای زمان راه‌اندازی زیر ۱ ثانیه.
2. **همه endpointها `ApiResponse[T]` برمی‌گردانند** — ساختار یکسان
   `{success, data, error}`.
3. **rate limit در middleware و endpointها** — middleware برای مسیرهای API
   عمومی، endpointها (auth, screener) برای محدودیت‌های خاص.
4. **taskهای پس‌زمینه با `asyncio.create_task`** — بدون blocking راه‌اندازی.
5. **resilient startup** — خطا در DB/Cache/ML باعث crash کل app نمیشود.
