# قسمت ۰۱ — هسته اجرا و چرخه حیات (Execution Core & Lifespan)

| | |
|---|---|
| **تاریخ** | ۲۰۲۶-۱۱-۱۴ |
| **کامیت مبنا** | `091fdf31` |
| **روش** | خواندن مستقیم تمام فایلهای این قسمت + اسکریپت شمارش فقطخواندنی + تطبیق با `docker-compose.yml` و تستها |
| **محدوده** | `main.py`, `apps/api/app.py`, `apps/api/error_handlers.py`, `apps/api/metrics.py`, `apps/api/openapi_security.py`, `apps/api/endpoints/health.py`, `apps/scheduler/app.py`, `apps/scheduler/__main__.py`, `apps/worker/__main__.py` |
| **انجام نشد** | بوت سرور، اتصال DB/Redis زنده، اجرای تست (تحلیل ایستا) |
| **اعتبار مقابل HEAD** | حین نگارش، HEAD به `9a100a6f` رفت (۱۰ کامیت)، ولی `git diff --name-only 091fdf31..HEAD` نشان داد **هیچ فایلی از فهرست بالا تغییر نکرده** → همه ۱۶ یافته `EX-*` زندهاند. جزئیات در `README.md` |

---

## ۱. ابعاد واقعی

| فایل | خط | نقش |
|---|---:|---|
| `main.py` | ۲۰ | نقطه ورود توسعهدهنده (`uvicorn.run`) |
| `apps/api/app.py` | **۱٬۲۳۸** | app factory + lifespan + ۸ وظیفه پسزمینه + ۸ route درونخطی + ماشین حالت کرون |
| `apps/api/error_handlers.py` | ۱۰۹ | ۵ هندلر استثناء |
| `apps/api/metrics.py` | ۹۶ | `MetricsMiddleware` + singleton exporter |
| `apps/api/openapi_security.py` | ۷۱ | تزریق `security` به OpenAPI |
| `apps/api/endpoints/health.py` | ۱۶۲ | چهار پروب سلامت |
| `apps/api/router.py` | ۷۶۱ | ۸۰ `include_router` (قسمت ۰۲) |
| `apps/api/dependencies.py` | ۵۳۶ | DI و RBAC (قسمت ۰۲) |
| `apps/api/middleware.py` | ۶۲۶ | ۸ کلاس میانافزار (قسمت ۰۲) |

`apps/api/app.py` بهتنهایی ۱٬۲۳۸ خط است: **۳۵٪ کل لایه HTTP**. بیش از نیمی از آن (خطوط ۱۰۰–۸۸۴) منطق کرون/هشدار/قفل است، نه تعریف اپ. این یعنی «app factory» عملاً یک **میکروسرویس زمانبند توکار** را هم حمل میکند — نخستین و مهمترین یافته معماری این قسمت.

---

## ۲. زنجیره بوت، گامبهگام

```
python main.py                                   main.py:9-17
  └─ uvicorn.run("apps.api.app:app", workers=settings.workers, reload=settings.is_development)
       └─ import apps.api.app                     app.py:1-41   ← import-time (بند ۳)
            └─ app = create_app()                 app.py:1238
                 ├─ FastAPI(...)                  app.py:1064-1071
                 ├─ ۹× add_middleware             app.py:1073-1089
                 ├─ register_error_handlers(app)  app.py:1091
                 ├─ ۸× @app.get/post درونخطی      app.py:1093-1229
                 ├─ include_router(Router().setup(), prefix=settings.api_prefix)   :1231-1232
                 └─ install_openapi_security(app)  :1233
       └─ lifespan(app)                           app.py:885-1061  ← بند ۶
```

**نکته ترتیبی:** `create_app()` در **زمان import** اجرا میشود، یعنی `Router().setup()` و import تنبل ۷۵ ماژول endpoint **پیش از** `setup_logging()` (که در خط ۸۸۸ داخل lifespan است) انجام میگیرند. `logger = get_logger(__name__)` در خط ۴۱ و تمام loggerهای ماژولهای endpoint، پیش از پیکربندی لاگینگ ساخته میشوند. معمولاً بیلطری است (loggerها به همان handler بعدی وصلاند)، ولی وابسته به ترتیب import است و با `reload=True` / چند worker میتواند لاگهای بوت را از دست بدهد.

همچنین `main.py` هم `reload=settings.is_development` و هم `workers=settings.workers` میدهد؛ uvicorn هنگام `reload=True` مقدار `workers` را نادیده میگیرد. `Dockerfile.api` اما `uvicorn apps.api.app:app --host 0.0.0.0 --port 8000 --no-access-log` است، بدون `reload` و بدون `workers`. نتیجه: **سه رفتار بوتاسترپ متفاوت** (محلی / `main.py` / کانتینر) برای یک اپ واحد.

---

## ۳. رفتار import-time: دو fail-fast واقعی

**خط ۳۶–۳۹:**
```python
# Fail fast: GoldDesk API-token hashing has no default salt. Importing this
# module raises RuntimeError when GOLD_API_TOKEN_SALT is unset, so the API
# process refuses to boot instead of failing on the first token request.
from src.gold_desk.api_token import SALT as _GOLD_TOKEN_SALT  # noqa: F401
```
این یک تصمیم امنیتی درست است: اگر salt ست نشده باشد، **فرایند اصلاً بالا نمیآید**، نه اینکه اولین درخواست توکن شکست بخورد. `docker-compose.yml:63` هم با `${GOLD_API_TOKEN_SALT:?...}` همان الزام را در لایه استقرار تکرار کرده (دفاع درعمق). کامنت compose صادقانه هشدار میدهد که عوض کردن salt، توکنهای قبلی را باطل میکند.

**خط ۸۹۸–۹۰۸ (درون lifespan):** `settings.validate_production()` — در `production`/`staging` هر خطا `raise` میشود (fail-closed)، در development فقط `logger.warning`. هشت شرط `core/config/__init__.py:488-512`: `SECRET_KEY` پیشفرض، `AUTH_DISABLED`, `CORS_ORIGINS=["*"]`, SQLite، `AUTH_COOKIE_SECURE`, `WS_ALLOW_LEGACY_TOKEN`, `OTLP_ENDPOINT`. Sentry **پیش از** این گیت init میشود (خط ۸۹۱) تا شکست پیکربندی هم ثبت شود — ترتیب هوشمندانهای است.

---

## ۴. `create_app()`: نه میانافزار و ترتیب **واقعی** اجرا

`Starlette.add_middleware` هر لایه را در ابتدای لیست درج میکند و لیست را برعکس میپیچد؛ بنابراین **آخرین اضافهشده، بیرونیترین است**. ترتیب اجرای درخواست:

| # | میانافزار | خط | نقش |
|---|---|---:|---|
| ۱ | `RequestContextMiddleware` | ۱۰۸۹ | بیرونیترین؛ `trace_id` + `X-Trace-Id` |
| ۲ | `RateLimitMiddleware` | ۱۰۸۶ | نرخ IP + سهمیه tier |
| ۳ | `LoggingMiddleware` | ۱۰۸۵ | لاگ درخواست |
| ۴ | `MetricsMiddleware` | ۱۰۸۴ | شمارنده/هیستوگرام |
| ۵ | `TimingMiddleware` | ۱۰۸۳ | `X-Response-Time-Ms` |
| ۶ | `InputSanitizationMiddleware` | ۱۰۸۲ | پاکسازی JSON/query |
| ۷ | `CSRFMiddleware` | ۱۰۸۱ | Origin/Referer + double-submit |
| ۸ | `SecurityMiddleware` | ۱۰۸۰ | هدرهای امنیتی + گارد نوشتن حساس |
| ۹ | `CORSMiddleware` | ۱۰۷۳ | **درونیترین** |

کامنت خط ۱۰۸۷ صریحاً میگوید `RequestContextMiddleware LAST → OUTERMOST` — پس ترتیب قصدشده و مستند است.

**اما پیامد ناخواسته:** چون `CORSMiddleware` درونیترین است، **هر میانافقزاری که بیرون از آن پاسخ را کوتاهکند، هدرهای CORS را اضافه نمیکند**. موارد قطعی:
- `CSRFMiddleware:224` و `:239` → ۴۰۳
- `SecurityMiddleware:146` → ۴۰۱
- `RateLimitMiddleware` → ۴۲۹ (هم نرخ IP و هم سهمیه tier)
- `ServerErrorMiddleware` + `generic_error_handler:101` → ۵۰۰

مرورگر در این حالت بهجای «۴۲۹/۴۰۳/۵۰۰» خطای **CORS** نشان میدهد؛ `frontend/src/lib/api-envelope.ts` هم فقط `data` را میخواند و تشخیص نمیدهد (قسمت ۱۱). هدرهای امنیتی `SecurityMiddleware` نیز چون درونیتر از CSRF/RateLimit است، روی همان پاسخها وجود ندارند.

---

## ۵. هشت route درونخطی (outside the Router)

| خط | مسیر | محافظت | نکته |
|---:|---|---|---|
| ۱۰۹۳ | `GET /` | — | `RedirectResponse("/docs")` |
| ۱۰۹۸ | `GET /metrics` | **هیچ** | `include_in_schema=False` |
| ۱۱۰۷ | `GET /api/v1/orchestrator-cron-status` | `get_current_active_user` | وضعیت بحران + history |
| ۱۱۲۶ | `GET /api/v1/orchestrator-cron-history` | `get_current_active_user` | ۱۰۰ رکورد آخر، شامل `error` |
| ۱۱۳۸ | `POST /api/v1/orchestrator-cron/toggle` | `require_roles("admin")` | تراکنش قفلدار |
| ۱۱۵۳ | `POST /api/v1/orchestrator-cron/run-now` | `require_roles("admin")` | اجرای کامل orchestrator درخواست HTTP |
| ۱۱۸۹ | `GET /api/v1/rate-limits` | `require_roles("admin")` | سهمیه BrsApi |
| ۱۱۹۸ | `GET /api/v1/cache-stats` | `require_roles("admin")` | کلیدها و TTL کش |

شش route آخر **پیشوند `/api/v1` را هاردکد کردهاند**، در حالی که `app.include_router(..., prefix=settings.api_prefix)` (خط ۱۲۳۲) از تنظیمات میخواند. اگر `API_PREFIX` عوض شود، ۷۵ router جابهجا میشوند و این شش مسیر سر جای قدیمی میمانند. همین الگو در `middleware.py` تکرار شده: `_EXEMPT_PATHS` (۵۱)، `_SENSITIVE_WRITE_PREFIXES` (۵۸–۷۰)، exempt CSRF (۲۱۶) و skip نرخ (۵۴۰) همگی `/api/v1` هاردکد دارند — یعنی تغییر پیشوند، علاوه بر جابهجایی مسیر، **گاردهای امنیتی دفاعدرعمق را بیصدا خاموش میکند**.

---

## ۶. جدول کامل startup (lifespan، خطوط ۸۸۵–۱۰۲۸)

| # | خط | عمل | سیاست شکست |
|---:|---:|---|---|
| ۱ | ۸۸۸ | `setup_logging()` | — |
| ۲ | ۸۹۱–۸۹۶ | `init_sentry(settings)` | `except Exception` → warning |
| ۳ | ۸۹۸–۹۰۸ | `validate_production()` | **prod: fatal** / dev: warning |
| ۴ | ۹۱۱–۹۱۴ | `await init_database()` | `logger.exception("... continuing without DB")` → **swallow** |
| ۵ | ۹۱۷–۹۲۰ | `register_all_models()` (۸ مدل) | warning |
| ۶ | ۹۲۳–۹۲۷ | `get_cache().initialize()` | warning + null cache |
| ۷ | ۹۳۰ | `_load_cron_state_from_store()` | بدون try (Redis ناوصل → no-op در داخل) |
| ۸ | ۹۳۳–۹۳۹ | `get_usage_recorder().start()` (flush ۶۰s) | warning |
| ۹ | ۹۴۲–۹۴۸ | `get_accuracy_outcome_queue().start()` (flush ۳۰s) | warning |
| ۱۰ | ۹۵۱–۹۶۲ | rate limiter + `on_threshold(_rate_limit_notify)` | warning |
| ۱۱ | ۹۶۵–۹۷۳ | `SchedulerApp().start()` — **۲۹ جاب APScheduler** | `logger.exception` → «periodic syncs disabled» |
| ۱۲ | ۹۷۶ | `_brsapi_startup_sync()` | وظیفه پسزمینه، ۳ بار retry |
| ۱۳ | ۹۷۹ | `_fetch_news_on_startup()` | وظیفه پسزمینه، ۳ بار retry |
| ۱۴ | ۹۸۲ | `_decision_engine_startup_seed()` | وظیفه پسزمینه، قفلدار |
| ۱۵ | ۹۸۵–۹۹۱ | `RealtimeService.start()` | `logger.exception` → WS broadcast غیرفعال |
| ۱۶ | ۹۹۸–۱۰۰۳ | `get_armor_ws_manager().start_subscriber()` | warning |
| ۱۷ | ۱۰۰۶ | `_orchestrator_hourly_cron()` | **حلقه بینهایت** |
| ۱۸ | ۱۰۱۲–۱۰۱۴ | `warm_signal_cache()` | warning |
| ۱۹ | ۱۰۲۰ | `_fund_sync_cron()` | **حلقه بینهایت** |
| ۲۰ | ۱۰۲۴ | `_ml_model_preload()` | وظیفه یکباره |
| ۲۱ | ۱۰۲۷–۱۰۲۸ | `logger.info("Starting ...")` + `yield` | — |

**مشاهده ساختاری:** گام ۴ شکست DB را قورت میدهد، ولی گامهای ۱۲–۲۰ **بلافاصله و همزمان** آغاز میشوند و همگی به DB نیاز دارند. هشت وظیفه در یک لحظه `create_task` میشوند: یکی `sync_all` تمام endpointهای BrsApi را میگیرد (سهمیه ۱۰٬۰۰۰/روز)، یکی پردازش اخبار با sentiment، یکی seed معماری، یکی گرمایش کش ۶۰ ثانیهای، یکی preload مدل، و دو حلقه بینهایت. خوشبختانه `/health/ready` (بند ۹) در چنین حالتی ۵۰۳ میدهد — ولی **compose برای سرویس `api` هلثچکی تعریف نکرده**، پس در استقرار پیشفرض کسی این ۵۰۳ را نمیخواند.

**تکثر worker:** `settings.workers` پیشفرض ۱ است، ولی `docker compose up --scale worker=N` (کامنت compose خط ۱۳۰) و هر پیکربندی `workers>1`، **تمام ۲۱ گام را بهازای هر worker** تکرار میکند. قفلهای توزیعشده بیشترشان را مهار میکنند (بند ۸)، ولی `RealtimeService`، `Armor subscriber`، `usage_recorder` و `accuracy_outcome_queue` **قفلی ندارند** → N مشترک روی یک کانال Redis pub/sub و N flusher روی یک صف.

---

## ۷. رجیستری وظایف پسزمینه — الگوی درست

```python
_background_tasks: set[asyncio.Task[Any]] = set()          # :47

def _track_background_task(coro, name) -> asyncio.Task:    # :50-71
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)          # strong reference → جلوگیری از GC
    def _done(completed):
        _background_tasks.discard(completed)
        if completed.cancelled(): return
        error = completed.exception()
        if error is not None:
            logger.error("Background task %s failed: %s", name, error,
                         exc_info=(type(error), error, error.__traceback__))
    task.add_done_callback(_done)
    return task

async def _stop_background_tasks():                        # :74-82
    for task in list(_background_tasks): task.cancel()
    tasks = list(_background_tasks)
    await asyncio.gather(*tasks, return_exceptions=True)
    _background_tasks.clear()
```
نگهداری مرجع قوی + لاگ کردن `task.exception()` + `gather(return_exceptions=True)` دقیقاً همان الگویی است که از «شکست خاموش تسک فراموششده» جلوگیری میکند. **نقطه قوت تأییدشده.**

| # | نام تسک | تابع | قفل توزیعشده | retry | بینهایت | هزینه |
|---:|---|---|---|---|---|---|
| ۱ | `brsapi-startup-sync` | `:784` | ✅ `startup:brsapi_sync` | ۳× (۳۰/۶۰/۱۲۰s) | خیر | سهمیه روزانه BrsApi |
| ۲ | `news-startup-ingest` | `:730` | ✅ `startup:news_ingest` | ۳× (۱۵/۳۰/۶۰s) | خیر | RSS + sentiment |
| ۳ | `decision-engine-seed` | `:543` | ✅ `startup:decision_seed` | خیر | خیر | ۵ JSON → جدول |
| ۴ | `orchestrator-hourly-cron` | `:411` | ✅ `orchestrator:hourly_tick` | خیر | ✅ ۳۶۰0s | سیگنال + بازآموزی |
| ۵ | `signal-cache-warmup` | `:1012` | ❌ (idempotent) | خیر | خیر | ~۶۰s pipeline |
| ۶ | `fund-sync-cron` | `:597` | ✅ `fund:sync_cycle` | خیر | ✅ ۱۵ دقیقه | سهمیه BrsApi |
| ۷ | `ml-model-preload` | `:657` | ❌ (read-only) | خیر | خیر | دیسک / LRU |
| — | `RealtimeService`, `Armor subscriber`, `usage_recorder`, `accuracy_flusher`, `SchedulerApp` | `:985-1003`, `:933-948`, `:966` | ❌ | — | ✅ | pub/sub + flush |

---

## ۸. تاکسونومی قفلها

| کلید | TTL | خط | هدف | رفتار در نبود Redis |
|---|---|---:|---|---|
| `startup:{key}` | ۶۰0s | `:494-530` | جلوگیری از اجرای همزمان sync/seed/news توسط رپلیکاها | **prod: fail-closed** (`:515-518`: «refusing to run unlocked»)، dev: fail-open |
| `orchestrator:hourly_tick` | ۹۰0s | `:135`, `:444` | تک اجرای کرون ساعتی | `locker is None` → **بدون قفل اجرا میکند** + `logger.error` (`:440-442`) |
| `fund:sync_cycle` | ۱۸۰0s | `:137`, `:630` | تک سیکل همگامسازی صندوقها | `locker is None` → **بدون قفل اجرا میکند** (`:624-625`) |
| `orchestrator:state_lock` | — | `:130`, `:179` | تراکنش اتمیک load→mutate→save وضعیت کرون | وابسته به `state_transaction` |
| `job:*` (صف) | — | `jobs/locking.py` | exactly-once اجرای جابها | in-memory fallback |

**ناسازگاری سیاست:** startup تسکها در نبود Redis **fail-closed**اند (تصمیم درست، با کامنت صریح در `:512-514` که میگوید اجرای بدون قفل روی جداول فاقد uniqueness guard خطرناک است)، ولی دو **حلقه بینهایت** (`hourly_tick`, `fund:sync_cycle`) در همان شرایط **fail-open** و بدون قفل اجرا میشوند. دقیقاً همان خطر («دو فرایند همزمان سیگنال تولید کنند / NAV یکسان را upsert کنند») در دائمیترین مسیرها پذیرفته شده است.

---

## ۹. ماشین حالت کرون و هشداردهی — عمیقترین بخش

**ذخیرهسازی:** Redis منبع حقیقت است (`core.shared_state.RedisStateDocument`)؛ `_cron_state` (شامل `deque(maxlen=100)`) و `_alert_state` فقط آینه محلی هر workerاند. `_cron_documents()` (`:141`) هر بار داکیومنت تازهای روی دیکشنری زنده میسازد تا تستهایی که `_cron_state` را عوض میکنند بشکنند. هر چرخه read-modify-write از `_cron_state_transaction()` (`:172`) با قفل `orchestrator:state_lock` میگذرد. `_commit_cron_run()` (`:215`) هشدارها را **بعد از** آزاد شدن قفل ارسال میکند تا تماس کند تلگرام قفل را نگه ندارد — طراحی دقیق.

**ترتیب `_plan_cron_alerts()` (`:254-343`):** حداقل ۳ رکورد history → سه شکست متوالی (با cooldown ۶ ساعته) → پیام بازیابی → افت دقت زیر ۵۰٪ (cooldown ۶ ساعته) → پیام بازگشت دقت. چهار نوع هشدار، همگی با `_alert_state` ردیابی وضعیت «ورود/خروج از بحران».

**باگ بالقوه پرتأثیر (`EX-10`):** زنجیره عددی را دنبال کنید:

```python
# :196  _record_cron_run
"accuracy": (accuracy or {}).get("overall", 0),      # دیکشنری خالی → ۰

# services/quant_signal_orchestrator.py::_get_accuracy_snapshot
_MIN_SNAPSHOT_SAMPLES = 20        # بازارهای <۲۰ نمونه حذف میشوند
snapshot = {... for market, v in ... if v["total"] >= 20}   # → {} وقتی نمونهای نباشد

# :297  _plan_cron_alerts
acc = latest.get("accuracy", 100)  # کلید وجود دارد و ۰ است → ۰ (نه ۱۰۰)
if acc < 50: → هشدار بحرانی + _alert_state["was_accuracy_below_50"] = now_ts

# :1117  orchestrator_cron_status
in_crisis = ... or _alert_state["was_accuracy_below_50"] > 0.0
data["health"]["status"] = "in_crisis"
```

یعنی **یک اجرای کاملاً سالم که بهدلیل کمبود نمونه دقتیگزارش نمیکند، بهعنوان «افت دقت به زیر ۵۰٪» هشدار بحرانی میفرستد و داشبورد را تا اطلاع ثانوی در حالت `in_crisis` نگه میدارد.** با توجه به `NUMERIC_AUDIT_2026-11-12.md` (۳٬۷۰۵ رکورد دقت ۱۰۰٪ یتیم و جداول تصمیم خالی)، این سناریو دور از ذهن نیست. مقدار پیشفرض `latest.get("accuracy", 100)` فقط وقتی اثر دارد که کلید اصلاً وجود نداشته باشد، در حالی که `_record_cron_run` همیشه آن را مینویسد.

**سایر ظرائف:**
- `orchestrator_cron_status:1122` فیلد `last_critical_alert_sent` در واقع `max(دو timestamp)` است (عدد خام `time.time()`)، نه رشته تاریخ.
- `_record_cron_run:203` خطا را به ۵۰۰ و `entry["error"]` را به ۲۰۰ نویسه برش میدهد، ولی منبعش `traceback.format_exc()` کامل (`:456`) است؛ `/orchestrator-cron-history` فقط `get_current_active_user` میخواهد (**هر کاربر واردشده**، نه admin) → نشت مسیرهای فایل/استک به سطح کاربر عادی.
- `orchestrator_cron_run_now` (`:1153-1186`) **قفل `hourly_tick` را نمیگیرد**؛ کامنت `:1176` میگوید «همان بخش بحرانی تیک ساعتی» ولی منظورش `_commit_cron_run` (قفل state) است، نه قفل اجرا. اجرای دستی همزمان با تیک ساعتی = دو بار `orchestrator.generate()` = سیگنال دوتایی و ارزیابی دقت دوتایی. ضمن اینکه یک pipeline ~۶۰ ثانیهای بدون timeout داخل handler درخواست HTTP اجرا میشود.
- `_orchestrator_hourly_cron:454-456` در `except Exception` خودش `_commit_cron_run(...)` را صدا میزند؛ اگر علت اصلی شکست، خرابی Redis/قفل state باشد، این فراخوان **دوباره همان استثناء را میدهد و حلقه `while True` برای همیشه میمیرد** — بیآنکه هیچ شکستی گزارش شود (چون داخل `except` رخ داده).

---

## ۱۰. ترتیب shutdown (`:1030-1061`)

`_stop_background_tasks()` ← `Armor WS shutdown` ← `scheduler.shutdown(wait=False)` ← `RealtimeService.stop()` ← `cache.close()` ← `close_client()` ← `usage_recorder.stop()` ← `accuracy_outcome_queue.stop()` ← `close_database()`.

ترتیب **تولیدکننده پیش از وابستگی** رعایت شده (تسکها قبل از بستن DB/Redis). همه مراحل با `with suppress(Exception)` پوشیدهاند تا یک شکست، بقیه را متوقف نکند. دو ظرافت:
- تسکهای startup قفل خود را در `finally` و با یک `await` آزاد میکنند (`:566-567`, `:780-781`, `:878-879`)؛ رها کردن `await` درون `finally` هنگام `CancelledError` شکننده است و به نسخه/زمانبندی asyncio وابسته است.
- `scheduler.shutdown(wait=False)` (`:1039`) یعنی جابهای in-process در حال اجرا، وسط نوشتن رها میشوند. در حالت `JOB_QUEUE_ENABLED=false` این یعنی نوشتن ناتمام روی DB.

---

## ۱۱. پروبهای سلامت — تصحیحگزارش اصلی

`apps/api/endpoints/health.py` **چهار** پروب دارد (نه یک «نقطه پراکنده»):

| خط | مسیر | رفتار |
|---:|---|---|
| ۱۸ | `GET /api/v1/health` | همیشه `status=ok` (فقط زندهبودن فرایند) |
| ۳۰ | `GET /api/v1/health/ready` | DB (`SELECT 1`) + Redis (`ping`) جداگانه؛ خرابی → **HTTP ۵۰۳** |
| ۷۸ | `GET /api/v1/health/live` | همیشه `alive` |
| ۸۳ | `GET /api/v1/health/full` | DB + Redis + BrsApi، همراه latency |

`/ready` **موجود و صحیح است** — ادعای لایه ۱۵۵گزارش ۱۶۰ لایهای («نبود یک `/ready` واحد») اشتباه بود و درجا اصلاح شد. اشکال واقعی دو تاست:

1. **`:85` + `:108`:** `overall = "ok"` فقط در بلوک DB به `"degraded"` تغییر میکند. بلوکهای Redis و BrsApi وضعیت خود را در `checks` مینویسند ولی `overall` را دست نمیزنند. نتیجه: با Redis و BrsApi **هر دو مرده**، پاسخ `{"success": true, "data": {"status": "ok", "checks": {"redis": {"status":"error"}, "brsapi": {"status":"error"}}}}` و **HTTP ۲۰۰** است.
2. `docker-compose.yml` هلثچک برای `timescaledb` (۱۸), `redis` (۳۴), `worker` (۱۲۴), `currency` (۱۵۴) و `frontend` (۱۸۳) دارد، ولی **سرویس `api` (خط ۴۰) هیچ `healthcheck`ای ندارد**. بنابراین `/ready` در استقرار پیشفرض مصرفکنندهای ندارد و `depends_on` سرویسها هم فقط `timescaledb: service_healthy` را چک میکند.

---

## ۱۲. جدول یافتهها

| ID | شدت | خط | یافته | اثر عملی | جهت اصلاح |
|---|---|---:|---|---|---|
| **EX-01** | 🔴 بحرانی | `app.py:1093` + `:1068` | `GET /` همیشه به `/docs` ریدایرکت میکند، ولی در production `docs_url=None` است | در پروداکشن روت دامنه **۴۰۴** میدهد | ریدایرکت شرطی یا صفحه لندینگ |
| **EX-02** | 🔴 بحرانی | `app.py:1098`, `middleware.py:540` | `/metrics` بدون احراز هویت، خارج از schema، و **معاف از نرخگیری** | افشای نام routeها، نرخ خطا و وضعیت canary اخبار + سطح حمله scrape بدون محدودیت | admin/IP allowlist + شبکه داخلی |
| **EX-03** | 🟠 بالا | `app.py:1107-1198`, `middleware.py:51,58-70,216,540` | پیشوند `/api/v1` در ۶ route و ۴ نقطه امنیتی هاردکد شده، در حالی که router از `settings.api_prefix` میخواند | تغییر `API_PREFIX` → ۶ مسیر یتیم + گارد نوشتن حساس و exemptها بیصدا از کار میافتند | ساخت prefix از `settings` |
| **EX-04** | 🟠 بالا | `health.py:85,108,154` | `full_health` فقط خرابی DB را در `overall` لحاظ میکند | Redis/BrsApi مرده → `status=ok`, HTTP ۲۰۰ | `overall` تجمیعی + ۵۰۳ |
| **EX-05** | 🟠 بالا | `docker-compose.yml:40` | سرویس `api` هلثچک ندارد | `/ready` هرگز خوانده نمیشود؛ ترافیک به سرویس نیمهمرده میرود | `healthcheck` روی `/api/v1/health/ready` |
| **EX-06** | 🟠 بالا | `app.py:1073-1089` | CORS درونیترین است؛ CSRF/RateLimit/Security/500 بیرون از آن پاسخ کوتاه میکنند | مرورگر بهجای ۴۰۳/۴۲۹/۵۰۰ خطای CORS میگیرد؛ هدرهای امنیتی هم حذف میشوند | CORS بیرونیترین |
| **EX-07** | 🟠 بالا | `error_handlers.py:73-90` | `safe_error_message`/`safe_error_detail` تعریف شده ولی **چهار هندلر** از `str(exc)` / `exc.message` استفاده میکنند | نشت پیام استثناء داخلی در production (هدف صریح آن دو تابع نقض شده) | عبور همه پیامها از `safe_error_message` |
| **EX-08** | 🟠 بالا | `app.py:1153-1186` | `run-now` قفل `hourly_tick` ندارد و pipeline بلند را بدون timeout در handler اجرا میکند | همپوشانی با تیک ساعتی → سیگنال/ارزیابی دوتایی؛ درخواست معلق | قفل مشترک + اجرا از طریق صف |
| **EX-09** | 🟡 متوسط | `app.py:454-456` | داخل `except`، `_commit_cron_run` میتواند همان استثناء Redis را بازتولید کند | مرگ خاموش و دائمی حلقه ساعتی | `try/except` جدا + `sleep` تضمینی |
| **EX-10** | 🟡 متوسط | `app.py:196,297-325,1117` | دقت `{}` → عدد ۰ → هشدار «زیر ۵۰٪» و `in_crisis` | هشدار کاذب بحرانی هنگام کمبود نمونه (گیت ۲۰ نمونه) | تمایز `None`/ناموجود از `0` |
| **EX-11** | 🟡 متوسط | `app.py:456,1126-1136` | `traceback.format_exc()` در state مشترک و در دسترس هر کاربر واردشده | نشت مسیرها/جزئیات داخلی | admin-only + پیام خلاصه |
| **EX-12** | 🟡 متوسط | `app.py:911-1025` | شکست `init_database` بلعیده میشود و ۸ تسک + ۴ سرویس بیدرنگ آغاز میشوند؛ با `workers>1` چهار سرویس بدون قفل تکثیر میشوند | هجوم retryها، N مشترک pub/sub، N flusher | گیت آمادگی پیش از launch + قفل leader |
| **EX-13** | 🟡 متوسط | `app.py:965-973` + `apps/scheduler/__main__.py` | `SchedulerApp` بیقیدوشرط داخل API استارت میشود؛ `Dockerfile.scheduler` هم سرویس جداگانهای میسازد | اجرای همزمان = ۲۹ تریگر دوتایی (قفل فقط هنگام *اجرا* جلوگیری میکند، نه publish) | پرچم `SCHEDULER_EMBEDDED` |
| **EX-14** | 🟡 متوسط | `main.py:9-17` | `reload` و `workers` همزمان؛ `Dockerfile.api` هیچکدام را ندارد | سه رفتار بوت متفاوت | یک مسیر بوت واحد |
| **EX-15** | 🟢 کم | `app.py:1039,566-567` | `shutdown(wait=False)` + آزادسازی قفل با `await` در `finally` تحت cancel | نوشتن ناتمام / قفل تا TTL باقیمانده | `wait=True` + آزادسازی بیدرنگ |
| **EX-16** | 🟢 کم | `app.py:41` در برابر `:888` | loggerهای ماژولی پیش از `setup_logging()` ساخته میشوند | لاگهای بوت وابسته به ترتیب import | پیکربندی لاگ در import-time |

> **🔄 بهروزرسانی لحظهای (worktree، کامیتنشده):** در حین نگارش همین قسمت، فرایند دیگری در مخزن **EX-04 و EX-05 را اصلاح کرد**: به `apps/api/endpoints/health.py` دو بلوک `if cache_status != "ok": overall = "degraded"` (خط ۱۳۰) و `if brsapi_status != "ok": overall = "degraded"` (خط ۱۵۵) اضافه شد، و به `docker-compose.yml:74` یک `healthcheck` برای سرویس `api` با `urllib.request.urlopen('http://localhost:8000/api/v1/health/ready')` اضافه گردید. این دو مورد در برابر **HEAD کامیتشده (`af9b02be`) همچنان زندهاند** ولی در worktree فعلی بسته شدهاند. ۱۴ یافته دیگر (EX-01/02/03/06–۱۶ بهجز موارد یادشده) تغییری نکردهاند. تفاوت میان HEAD و worktree را هنگام استفاده از این جدول حتماً در نظر بگیرید.

---

## ۱۳. نقاط قوت تأییدشده (برای توازن)

1. `_with_startup_lock` در production **fail-closed** است (`:515-518`) و دلیلش در کامنت نوشته شده: «جداول فاقد uniqueness guard».
2. `_track_background_task` مرجع قوی + `add_done_callback` + لاگ `exc_info` — الگوی کامل ضد «تسک گمشده».
3. `state_transaction` با قفل Redis و ارسال هشدار **خارج** از بخش بحرانی (`:229-239`).
4. `validate_production()` هشت شرط، fail-closed در prod/staging، با Sentry پیش از آن.
5. Fail-fast دوزمنبعهای `GOLD_API_TOKEN_SALT` (import-time + `${VAR:?}` در compose) با هشدار صریح درباره باطل شدن توکنها.
6. `install_openapi_security` درخت وابستگیها را پیمایش میکند؛ بررسی شد که closure `_check` حاصل `require_roles()` شامل `Depends(get_current_user)` است، پس security روی routeهای نقشدار **بهدرستی** اعمال میشود (شک اولیه رد شد).
7. `/health/ready` با ۵۰۳ و تفکیک DB/Redis — پیادهسازی صحیح، فقط بیاستفاده مانده (EX-05).
8. ترتیب shutdown: producers پیش از وابستگیها، با `suppress` برای جلوگیری از توقف زنجیره.

---

## ۱۴. تصحیحات اعمالشده برگزارش ۱۶۰ لایهای

| لایه | ادعای قبلی | اصلاح |
|---|---|---|
| ۱۵۵ | «نبود یک `/ready` واحد» | `/ready` موجود و ۵۰۳ میدهد؛ ایراد واقعی `overall` تکبعدی `full_health` و نبود healthcheck سرویس `api` در compose است |
| ۱۵۹ / بند ۴ نقشه راه | «افزودن `/ready` ترکیبی» | «وصل کردن هلثچک `api` به `/ready` موجود + اصلاح `overall`» |

متن هر دو لایه و بند نقشه road در `DEEP_ANALYSIS_160_LAYERS_2026-11-13.md` درجا ویرایش شد و جدول «تصحیحات» به پیوست اضافه گردید.

---

## ۱۵. مرز روش / گام بعدی

هیچ ادعای زماناجرایی مطرح نشد: سرور بوت نشد، به DB/Redis متصل نشدیم، تستی اجرا نکردیم. یافتههای EX-01 تا EX-16 همگی از خواندن کد، تطبیق با `docker-compose.yml`، `tests/` و تنظیمات استخراج شدهاند. مواردی مانند رفتار واقعی `X-Forwarded-For` پشت پراکسی (قسمت ۰۲) یا مصرف سهمیه BrsApi هنگام startup نیازمند اجرای زندهاند و صریحاً بهعنوان «فرضیه قابلآزمون» علامت خواهند خورد.

**قسمت ۰۲:** `router.py` (۸۰ mount)، `dependencies.py` (۳۹ wrapper در برابر `get_service` generic)، `middleware.py` (۸ کلاس، `_SENSITIVE_WRITE_PREFIXES`، نرخگیری دوبعدی) و `core/security/`.

---
*فقط فایل تحلیلی ساخته شد؛ هیچ کدی تغییر نکرد.*
