# 📘 راهنمای کامل پروژه — Iran Market Data & Analytics Platform

> **نسخه مستند:** 1.0 — آخرین بهروزرسانی: مرداد ۱۴۰۵
> این مستند نمای کامل و ریزجزئیات معماری، سرویسها، API، دیتابیس، jobها، فرانتاند و زیرساخت پروژه است.

---

## فهرست مطالب

1. [معرفی و نمای کلی](#۱-معرفی-و-نمای-کلی)
2. [معماری سیستم](#۲-معماری-سیستم)
3. [استک تکنولوژی](#۳-استک-تکنولوژی)
4. [ساختار پروژه (دایرکتوریها)](#۴-ساختار-پروژه)
5. [لایه داده و یکپارچهسازی BrsApi](#۵-لایه-داده-و-برسپی)
6. [دیتابیس و مهاجرتها](#۶-دیتابیس-و-مهاجرتها)
7. [زیرسیستم API (Backend)](#۷-زیرسیستم-api)
8. [زمانبند و Jobها](#۸-زمانبند-و-jobها)
9. [موتور سیگنال و تصمیمگیری](#۹-موتور-سیگنال-و-تصمیمگیری)
10. [زیرسیستم ML](#۱۰-زیرسیستم-ml)
11. [موتور بکتست](#۱۱-موتور-بکتست)
12. [فرانتاند Next.js](#۱۲-فرانتاند-nextjs)
13. [زیرساخت Docker](#۱۳-زیرساخت-docker)
14. [امنیت](#۱۴-امنیت)
15. [اسکریپتهای عملیاتی](#۱۵-اسکریپتهای-عملیاتی)
16. [تست و CI](#۱۶-تست-و-ci)
17. [راهاندازی](#۱۷-راهاندازی)
18. [عیبیابی](#۱۸-عیبیابی)

---

## ۱. معرفی و نمای کلی

پلتفرم جامع **داده و تحلیل بازار سرمایه ایران** — یک سیستم یکپارچه برای:

- 📥 **جمعآوری داده**: لحظهای و تاریخی از TSETMC / BrsApi.ir (قیمت، حجم، حقیقی-حقوقی، کندلاستیک، سهامداران، NAV، CODAL، طلا/ارز/کالا/کریپتو)
- 📊 **تحلیل**: تکنیکال (۱۰+ اندیکاتور)، بنیادی، احساسات (اخبار)، نقدشوندگی، صفها
- 🤖 **سیگنال**: موتور چندبازاری با رأیگیری و ML
- 🧪 **بکتست**: شبیهساز با قوانین بازار ایران (دامنه نوسان، تیک، صف)
- 🧠 **یادگیری ماشین**: آموزش مدل، رژیم بازار، وزندهی پویا، پیشبینی
- 💼 **پرتفوی و هشدار**: مدیریت سبد، هشدار قیمت/حجم/RSI
- 🖥️ **فرانتاند**: بیش از ۶۰ صفحه Next.js با پشتیبانی کامل RTL و فارسی

**نکته کلیدی دامنه**: تمام دادهها از سرویس **BrsApi.ir** (درگاه دادههای TSETMC و سایر بازارها) میآیند. کلاینت اختصاصی با مدیریت بودجه روزانه ساخته شده تا کلید API هرگز مسدود نشود.

---

## ۲. معماری سیستم

```
┌─────────────────────────────────────────────────────────────┐
│                      مرورگر (Frontend)                        │
│              Next.js 16 — ۶۰+ صفحه — RTL فارسی               │
│              Rewrite Proxy: /api/v1/* → backend:8000          │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    Backend (FastAPI)                          │
│  • apps/api     → REST API (۶۰+ ماژول endpoint)               │
│  • apps/admin   → پنل مدیریت (پورت 8001)                      │
│  • apps/scheduler → APScheduler (زمانبند)                     │
│  • apps/cli     → رابط خط فرمان                               │
│  Middleware: CORS, Security, CSRF, Sanitize, Timing,          │
│              Metrics, Logging, RateLimit                      │
└──────┬────────────────┬──────────────────┬───────────────────┘
       │                │                  │
┌──────▼──────┐  ┌──────▼──────┐   ┌───────▼──────────┐
│ PostgreSQL   │  │  Redis 7    │   │  BrsApi.ir API   │
│ (TimescaleDB)│  │ Cache+Queue │   │  (دیتای TSETMC)  │
└─────────────┘  └──────┬──────┘   └──────┬───────────┘
                        │                 │
              ┌─────────▼─────┐   ┌───────▼──────────┐
              │  Worker(s)    │   │  Rate Limiter    │
              │  Queue مصرفکننده│  │  (۴۰۰۰/روز،     │
              │  Redis Streams │   │  ۱۰۰۰/۵دقیقه)   │
              └───────────────┘   └──────────────────┘
```

**اجزای اصلی پشت صحنه:**

| مؤلفه | مسیر | مسئولیت |
|---|---|---|
| **BrsApiClient** | `brsapi/client.py` | HTTP client با pooling, retry, circuit breaker, rate limit, کش |
| **BrsApiSyncService** | `brsapi/services/sync_service.py` | هماهنگسازی fetch → parse → ذخیره → لاگ |
| **RateLimiter** | `brsapi/rate_limiter.py` | ۳ لایه محدودیت: روزانه/۵دقیقهای/دستهای |
| **BrsApiQueryService** | `brsapi/services/query_service.py` | **لایه خواندن فقط از دیتابیس** (DB-first) |
| **JobDispatcher** | `jobs/job_dispatcher.py` | اجرای jobها با قفل توزیعشده و dedup |
| **SchedulerApp** | `apps/scheduler/app.py` | زمانبندی همه jobها با APScheduler |
| **ModelLoader** | `ml/model_loader.py` | Lazy-loading مدلهای ML با LRU cache |
| **SignalDecisionEngine** | `services/signal_decision_engine.py` | دروازههای تصمیمگیری با Overrideهای Rule-Based |
| **FeatureEngine** | `services/feature_engine.py` | محاسبه ۱۱۵+ ویژگی (۸ بلوک) |

---

## ۳. استک تکنولوژی

### Backend
| تکنولوژی | کاربرد |
|---|---|
| **Python 3.11+** | زبان اصلی |
| **FastAPI** | REST API (async) |
| **SQLAlchemy 2.0 (async)** | ORM با AsyncSession/asyncpg |
| **Alembic** | ۳۸ مهاجرت دیتابیس |
| **Pydantic v2** | اعتبارسنجی و schemaها |
| **APScheduler** | زمانبندی jobها |
| **httpx** | HTTP client ناهمزمان |
| **Redis (redis.asyncio)** | کش، صف jobها، قفل توزیعشده |
| **OpenTelemetry / Prometheus** | متریک و مانیتورینگ |
| **jdatetime** | تبدیل تاریخ شمسی/میلادی |

### ML
| تکنولوژی | کاربرد |
|---|---|
| **PyTorch** | مدلهای یادگیری عمیق |
| **scikit-learn** | Ridge/طبقهبندها (رژیم بازار، وزندهی) |
| **pandas / numpy** | پردازش داده |
| **pandas_ta** | اندیکاتورهای تکنیکال |

### Frontend
| تکنولوژی | کاربرد |
|---|---|
| **Next.js 16** | فریمورک React (App Router) |
| **Tailwind CSS v4** | استایلبندی |
| **Recharts** | نمودارها (Area, Bar, Pie, Candle سفارشی) |
| **TanStack Query** | مدیریت state سمت کلاینت |

### زیرساخت
| سرویس | نقش |
|---|---|
| **TimescaleDB (PostgreSQL 16)** | دیتابیس اصلی |
| **Redis 7** | کش + صف job + قفل |
| **Docker Compose / Swarm** | اجرای سرویسها |

---

## ۴. ساختار پروژه

```
temce/
├── apps/
│   ├── api/                 # FastAPI اصلی (پورت 8000)
│   │   ├── app.py           # lifespan, middleware, روتر، cron orchestrator
│   │   ├── router.py        # تجمیع همه endpointها
│   │   ├── dependencies.py  # تزریق وابستگیها
│   │   └── endpoints/       # ۶۳ فایل endpoint
│   ├── admin/               # پنل مدیریت (پورت 8001)
│   ├── cli/                 # رابط خط فرمان
│   └── scheduler/           # APScheduler
│
├── backtesting/             # موتور بکتست
│   ├── engine/              # simulator, broker, replay
│   ├── strategies/          # استراتژیهای rule-based
│   ├── metrics/             # Sharpe, Sortino, Drawdown, ...
│   ├── microstructure/      # صف، ایمپکت، حراج
│   ├── risk/                # StopLoss, TakeProfit
│   └── alpha/               # مولدهای آلفا
│
├── brsapi/                  # یکپارچهسازی BrsApi.ir
│   ├── client.py            # HTTP client + kill switch
│   ├── config.py            # endpointها و تنظیمات
│   ├── rate_limiter.py      # لیمیتر ۳ لایه
│   ├── readiness.py         # پراب ساعتی آمادگی کلید
│   ├── parsers/             # TsetmcParser, CodalParser, ...
│   ├── repositories/        # BulkUpsert, SyncLog
│   ├── models/              # مدلهای SQLAlchemy (۱۲+ جدول)
│   ├── services/            # sync, query, history_fetch
│   └── jobs/                # رجیستری jobهای sync
│
├── core/                    # ابزارهای زیرساختی
│   ├── database.py          # engine + AsyncSession
│   ├── cache.py             # کش Redis
│   ├── cache_manager.py     # کش ۳ لایه (LRU→Redis→DB)
│   ├── circuit_breaker.py   # قطعکننده مدار
│   ├── security/            # tokens, password, MFA
│   ├── config/              # تنظیمات Pydantic-Settings
│   └── ...                  # logging, ids, paths, result, ...
│
├── domain/                  # موجودیتهای دامنه (dataclass)
│   ├── analytics/           # Signal, Alpha
│   ├── instruments/         # Instrument
│   ├── market_data/         # Quote, OrderBook
│   ├── portfolios/          # Portfolio, Position
│   └── common/              # enumها
│
├── frontend/                # Next.js (۶۰+ صفحه)
│   └── src/app/             # مسیرها (dashboard, screener, ...)
│
├── integrations/            # سرویسهای خارجی
│   ├── notifications/       # Telegram, Email, SMS, Webhook
│   └── observability/       # OTEL, log aggregation
│
├── jobs/                    # سیستم job
│   ├── job_registry.py      # ثبت کلاسهای job
│   ├── job_dispatcher.py    # اجرا با قفل + dedup
│   ├── locking.py           # قفل توزیعشده Redis
│   ├── queue_publisher.py   # ارسال job به Redis Stream
│   ├── queue_consumer.py    # مصرف از صف در Worker
│   └── definitions/         # ۱۹ فایل تعریف job
│
├── ml/                      # یادگیری ماشین
│   ├── model_loader.py      # Lazy Loader + LRU cache
│   ├── train_weight_optimizer.py  # وزندهی رژیمی
│   ├── training/            # Trainer
│   ├── features/            # اندیکاتورها
│   ├── models/              # رجیستری مدلها
│   └── artifacts/           # فایلهای مدل آموزشدیده
│
├── migrations/versions/     # ۳۸ مهاجرت Alembic
│
├── models/                  # مدلهای SQLAlchemy (برنامه اصلی)
├── repositories/            # لایه دسترسی داده
├── schemas/                 # Pydantic schemaها
├── scripts/                 # اسکریپتهای عملیاتی (۳۰+)
├── services/                # سرویسهای کسبوکار (۱۰۰+ فایل)
├── tests/                   # تستهای unit/integration/e2e
├── json/brsapi/             # فایلهای runtime (state، لاگ، baseline)
│
├── docker-compose.yml
├── pyproject.toml
├── main.py                  # نقطه ورود API
└── Makefile
```

---

## ۵. لایه داده و برسپی

### ۵.۱ BrsApiClient — کلاینت HTTP

`brsapi/client.py` یک کلاینت async کامل است:

| ویژگی | توضیح |
|---|---|
| **Connection pooling** | `httpx.Limits` با پیکربندی `connection_pool_size` |
| **Retry با backoff** | ۵۰۲/۵۰۴/۴۲۹ و Timeout دوباره تلاش میشوند؛ ۴۰۱/۳۰۲ نه |
| **Circuit breaker** | بعد از ۵ خطای متوالی، ۳۰ ثانیه مدار باز |
| **کش Redis** | پاسخها با TTL هر endpoint کش میشوند |
| **Kill switch** | `BRSAPI_ENABLED=false` → حالت DB-only، صفر درخواست HTTP |
| **تشخیص 302** | ریدایرکت به فایل حجیم = مسدودی → fail-fast با پیام واضح |

### ۵.۲ RateLimiter — ۳ لایه محدودیت

`brsapi/rate_limiter.py` برای **هر** درخواست اعمال میشود:

| لایه | سقف پیشفرض | توضیح |
|---|---|---|
| **روزانه (Daily)** | ۴,۰۰۰/روز | با حاشیه زیر سقف واقعی پلن (~۵,۰۰۰) تا کلید مسدود نشود |
| **۵ دقیقهای** | ۱,۰۰۰/۵دقیقه | پنجره لغزان |
| **دستهای (Category)** | per-endpoint | token bucket (مثلاً tsetmc=60/min) |

**Fail-fast**: وقتی بودجه روزانه تمام شد، بهجای خواب تا نیمهشب تهران، `RateLimitExhaustedError` صادر میشود.
**نوتیفیکیشن**: در ۸۰/۹۰/۹۵/۱۰۰٪ مصرف روزانه، هشدار تلگرام ارسال میشود.

**دیاگرام جریان Rate Limiter:**

```mermaid
flowchart TB
    JOB["📊 Jobهای همگام‌سازی<br/>Candlestick · History · Symbol Detail · ..."]
    CALL["HTTP Request<br/>client.fetch() → acquire()"]
    CAT["لایه ۱ · سطل توکن per-category<br/>BRSAPI_RATE_LIMIT_* (tsetmc=60/min)"]
    WIN["لایه ۲ · پنجره غلتان ۵ دقیقه‌ای<br/>BRSAPI_GLOBAL_5MIN_LIMIT (1000)"]
    DAY["لایه ۳ · سقف سخت روزانه<br/>BRSAPI_GLOBAL_DAILY_LIMIT (4000)"]
    FF{"بودجه روزانه تمام شده؟<br/>BRSAPI_FAIL_FAST_ON_DAILY_EXHAUSTED"}
    REJ["⛔ رد فوری درخواست<br/>RateLimitExhaustedError — حفاظت از کلید"]
    SLEEP["😴 انتظار تا refill سطل/پنجره"]
    OK["✅ ارسال واقعی به api.brsapi.ir"]
    DB["💾 ذخیره در دیتابیس<br/>(یا حالت DB-only وقتی BRSAPI_ENABLED=false)"]

    JOB --> CALL --> CAT --> WIN --> DAY
    DAY -->|"جای خالی"| OK
    DAY -->|"تمام شده"| FF
    FF -->|true| REJ
    FF -->|false| SLEEP --> DAY
    OK --> DB

    style DAY fill:#fce4ec,stroke:#c62828
    style WIN fill:#fff3e0,stroke:#e65100
    style REJ fill:#ffebee,stroke:#b71c1c
    style OK fill:#e8f5e9,stroke:#2e7d32
```

### ۵.۳ Kill Switch و محافظت کلید

| مکانیزم | رفتار |
|---|---|
| `BRSAPI_ENABLED=false` | هیچ تماس زندهای؛ `fetch()` پیام DB-only برمیگرداند |
| چک ساعتی آمادگی (`BrsApiReadyCheckJob`) | ۱ ریکوئست/ساعت، تشخیص ریست شمارنده (HTTP 200 بهجای 302) |
| `scripts/run_backlog_sync.py` | رانر بودجه-آگاه عقبماندگی (زیر ۴,۰۰۰/روز) |

### ۵.۴ Endpointهای BrsApi

| دسته | Endpoint | نرخ مجاز |
|---|---|---|
| TSETMC | AllSymbols, Symbol, Index, History, Candlestick, Shareholder, Transaction, Nav, Option | ۲-۴ ریکوئست/۱۰ثانیه |
| CODAL | Announcement | ۲/۱۰s |
| IME | Futures, Option, Certificate, Fund, Physical | ۱-۳/۱۰s |
| Market | Commodity, Crypto, Gold_Currency, Coin, Currency, Gold_Currency_Pro | ۱-۶/دقیقه |

---

## ۶. دیتابیس و مهاجرتها

### ۶.۱ ساختار

- **موتور**: PostgreSQL 16 (TimescaleDB) با `asyncpg`
- **آدرس**: از `DATABASE_URL` در `.env` (قالب `postgresql+asyncpg://user:pass@host:5432/db`)
- **Pool**: `pool_size` + `max_overflow` + `pool_pre_ping` + `pool_recycle=3600`
- **مهاجرت**: Alembic — ۳۸ فایل در `migrations/versions/`

### ۶.۲ جدولهای اصلی

| جدول | محتوا | اندازه تقریبی |
|---|---|---|
| `brsapi_symbol_snapshots` | لحظهای همه نمادها | ۱.۲M ردیف / ۱,۹۲۰ نماد |
| `brsapi_historical_daily` | تاریخچه روزانه قیمت | ۱۲.۱M ردیف / ۱,۹۴۰ نماد |
| `brsapi_candlesticks` | کندلاستیک ۳ تایپ | ۲.۳M ردیف / ۱,۱۱۱ نماد |
| `brsapi_historical_real_legal` | حقیقی-حقوقی روزانه | ۹۱۰K ردیف / ۵۵۹ نماد |
| `brsapi_shareholder_records` | ترکیب سهامداران | ۷۷۷K ردیف |
| `brsapi_intraday_trades` | معاملات درونروز | ۱.۶M ردیف / ۶۸ نماد |
| `brsapi_option_snapshots` | اختیارها | ۵۰۵K ردیف |
| `brsapi_symbol_details` | جزئیات غنیشده نماد | ۴K ردیف / ۱,۴۴۲ نماد |
| `brsapi_index_values` | شاخصها | ۴K ردیف / ۸ نام |
| `brsapi_sync_log` | لاگ همه syncها | ۴۷K+ ردیف |
| `screener_daily_scores` | امتیاز ۱۱۰ ستونه روزانه | ۱,۵۳۳ ردیف / ۵۱۱ نماد |
| `ml_engineered_features` | ویژگیهای مهندسیشده ML | (بوتاسترپ) |
| `funds` | داده صندوقها | — |
| `queue_analysis_results` | تحلیل صف نمادها | — |
| `decision_architectures` | معماری موتور تصمیم | — |

**ستونهای تاریخ**: بیشتر جداول BrsApi دارای **هر دو** تاریخ `gregorian_date` (DATE) و `shamsi_date` (VARCHAR) هستند + `created_at`/`updated_at`.

**دیاگرام ER — روابط اصلی بین جداول:**

```mermaid
erDiagram
    %% ── لایه کاربر، پرتفوی و هشدارها ──
    USERS {
        string id PK
        string username UK
        string email UK
        string roles
    }
    SAVED_FILTERS {
        string id PK
        string user_id FK
        string name
    }
    PORTFOLIOS {
        string id PK
        string name
        float initial_capital
        float current_value
    }
    PORTFOLIO_POSITIONS {
        string id PK
        string portfolio_id FK
        string instrument_id FK
        int quantity
        float avg_cost
    }
    ALERTS {
        string id PK
        string instrument_id FK
        string alert_type
    }
    ALERT_HISTORY {
        string id PK
        string alert_id FK
        datetime triggered_at
    }

    %% ── لایه بازار و داده‌های معاملاتی ──
    INSTRUMENTS {
        string id PK
        string symbol UK
        string isin UK
        string market_type
        string status
    }
    SYMBOLS {
        int id PK
        string symbol UK
        string name
        string industry
    }
    QUOTES {
        string id PK
        string instrument_id FK
        string symbol
        float price_last
        float price_close
        bigint volume
    }
    TRADES {
        string id PK
        string instrument_id FK
        string symbol
        bigint volume
        float price
    }
    ORDERBOOKS {
        string id PK
        string instrument_id FK
        string symbol
    }
    DAILY_HISTORY {
        int symbol_id PK, FK
        date trade_date PK
        float price_close
        bigint trade_volume
    }
    INTRADAY_TRADES {
        int symbol_id PK, FK
        date trade_date PK
        int seq_no PK
        float price
        int volume
    }
    SHAREHOLDERS {
        int symbol_id PK, FK
        date record_date PK
        string holder_name PK
        bigint volume
    }
    DAILY_REAL_LEGAL {
        int symbol_id PK, FK
        date trade_date PK
        bigint real_buy_volume
        bigint legal_sell_volume
    }
    ETF_NAV {
        int symbol_id PK, FK
        datetime time PK
        float nav
    }
    OPTION_CONTRACTS {
        int id PK
        string symbol
        string underlying_symbol
        float strike_price
        date expiry_date
    }
    OPTION_SNAPSHOTS {
        int id PK
        int contract_id FK
        float price_last
    }

    %% ── لایه سیگنال، اسکرینر و تصمیم ──
    SIGNALS {
        string id PK
        string instrument_id FK
        string symbol
        string signal_type
        float strength
        string direction
    }
    SCREENER_PROFILES {
        string symbol PK
        string industry
        float eps_current
        float current_price
    }
    SCREENER_SNAPSHOTS {
        string symbol PK
        datetime timestamp PK
        float close
        bigint volume
    }
    SCREENER_SIGNALS {
        int id PK
        string symbol
        datetime generated_at
        float final_score
        string decision
    }
    DECISION_RESULTS {
        int id PK
        string symbol
        string run_id
        float final_score
        string decision
    }
    QUEUE_ANALYSIS_RESULTS {
        int id PK
        string symbol
        string queue_status
        float queue_volume_ratio
        string final_decision
    }
    FUNDS {
        string id PK
        string symbol UK
        string fund_type
        float nav
        float price_last
    }

    %% ── لایه ML، بک‌تست و Paper Trading ──
    ML_MODELS {
        string id PK
        string algorithm
        string status
    }
    ML_MODEL_VERSIONS {
        string id PK
        string model_id FK
        string version
        string artifact_path
    }
    ML_PREDICTIONS {
        string id PK
        string model_id FK
        string symbol
        float prediction
        float confidence
    }
    BACKTEST_RUNS {
        string id PK
        string strategy_type
        string symbols
        float total_return
    }
    BACKTEST_TRADES {
        string id PK
        string run_id FK
        string symbol
        float entry_price
        float exit_price
    }
    PAPER_SIGNAL_SNAPSHOTS {
        string id PK
        string batch_id
        string symbol
        string signal_type
    }
    PAPER_TRADES {
        string id PK
        string signal_snapshot_id FK
        string symbol
        float pnl_pct
    }

    %% ── CODAL Star Schema ──
    DIM_COMPANY {
        string company_id PK
        string name
    }
    DIM_DATE {
        string date_id PK
        date gregorian_date
    }
    DIM_ACCOUNT {
        string account_id PK
        string parent_account_id
        string name
    }
    DIM_DOCUMENT {
        string document_id PK
        string title
    }
    DIM_REPORT_TYPE {
        string report_type_id PK
        string name
    }
    FACT_FINANCIALS {
        string fact_id PK
        string company_id FK
        string date_id FK
        string account_id FK
        string document_id FK
        string report_type_id FK
        float value
    }

    %% ── لایه BrsApi (داده خام) ──
    BRSAPI_SYMBOL_SNAPSHOTS {
        string symbol PK
        date date PK
        float price_last
        float price_close
        bigint trade_volume
    }
    BRSAPI_SYMBOL_DETAILS {
        string symbol PK
        float eps
        float pe
        bigint market_cap
    }
    BRSAPI_HISTORICAL_DAILY {
        string symbol PK
        date trade_date PK
        float price_close
        bigint trade_volume
    }
    BRSAPI_CANDLESTICKS {
        string symbol PK
        date trade_date PK
        string timeframe PK
        float price_close
    }

    %% ── روابط ──
    USERS ||--o{ SAVED_FILTERS : "فیلترهای ذخیره‌شده"
    PORTFOLIOS ||--o{ PORTFOLIO_POSITIONS : "دارد"
    PORTFOLIO_POSITIONS }o--|| INSTRUMENTS : "نماد"
    ALERTS ||--o{ ALERT_HISTORY : "تاریخچه"
    ALERTS }o--|| INSTRUMENTS : "روی"

    INSTRUMENTS ||--o{ QUOTES : "آخرین قیمت"
    INSTRUMENTS ||--o{ TRADES : "معاملات"
    INSTRUMENTS ||--o{ ORDERBOOKS : "دفتر سفارش"
    INSTRUMENTS ||--o{ SIGNALS : "سیگنال‌ها"

    SYMBOLS ||--o{ DAILY_HISTORY : "تاریخچه روزانه"
    SYMBOLS ||--o{ INTRADAY_TRADES : "معاملات درون‌روز"
    SYMBOLS ||--o{ SHAREHOLDERS : "سهامداران"
    SYMBOLS ||--o{ DAILY_REAL_LEGAL : "حقیقی-حقوقی"
    SYMBOLS ||--o{ ETF_NAV : "NAV صندوق ETF"
    OPTION_CONTRACTS ||--o{ OPTION_SNAPSHOTS : "اسنپ‌شات"

    SCREENER_PROFILES ||--o{ SCREENER_SNAPSHOTS : "لحظه‌ای"
    SCREENER_PROFILES ||--o{ SCREENER_SIGNALS : "خروجی مدل"

    ML_MODELS ||--o{ ML_MODEL_VERSIONS : "نسخه‌ها"
    ML_MODELS ||--o{ ML_PREDICTIONS : "پیش‌بینی‌ها"
    BACKTEST_RUNS ||--o{ BACKTEST_TRADES : "معاملات بک‌تست"
    PAPER_SIGNAL_SNAPSHOTS ||--o{ PAPER_TRADES : "شبیه‌سازی"

    DIM_COMPANY ||--o{ FACT_FINANCIALS : ""
    DIM_DATE ||--o{ FACT_FINANCIALS : ""
    DIM_ACCOUNT ||--o{ FACT_FINANCIALS : ""
    DIM_DOCUMENT ||--o{ FACT_FINANCIALS : ""
    DIM_REPORT_TYPE ||--o{ FACT_FINANCIALS : ""

    BRSAPI_SYMBOL_SNAPSHOTS |o--o{ BRSAPI_SYMBOL_DETAILS : "تکمیل می‌کند"
    BRSAPI_SYMBOL_DETAILS ||--o{ BRSAPI_HISTORICAL_DAILY : ""
    BRSAPI_SYMBOL_DETAILS ||--o{ BRSAPI_CANDLESTICKS : ""
```

> **راهنما**: `||` = دقیقاً یک، `o{` = صفر یا چند. روابط با `FK` ستون‌های کلید خارجی واقعی در مدل‌ها هستند؛ جداول SCREENER/سایر جداول با ستون `symbol` به‌صورت منطقی (بدون FK دیتابیس) به نمادها متصل‌اند. نسخه کامل ستون‌ها در `migrations/versions/` و فایل‌های `models/` موجود است.



### ۶.۳ مهاجرتهای کلیدی (۳۸ مورد)

| نسخه | محتوا |
|---|---|
| `0001_initial_schema` | ۱۹ جدول پایه بر اساس endpointهای BrsApi |
| `0002-0003` | جداول صورتهای مالی CODAL |
| `0008_screener_tables` | جداول اسکرینر |
| `0013_decision_engine_tables` | موتور تصمیمگیری |
| `0014_queue_analysis_results` | تحلیل صف |
| `0015_funds_table` | جدول صندوقها |
| `0029_paper_trading_tables` | معاملات آزمایشی |
| `0035_feature_store_tables` | Feature Store (جدول ۵۰ ستونه) |
| `0036_clean_historical_view` | View داده پاکشده |
| `0037-0038` | ایندکسهای gregorian_date |

---

## ۷. زیرسیستم API

### ۷.۱ میدلورها (به ترتیب اجرا)

```
CORS → Security → CSRF → InputSanitization → Timing → Metrics → Logging → RateLimit
```

| میدلور | وظیفه |
|---|---|
| **SecurityMiddleware** | هدرهای امنیتی (CSP, HSTS, ...) |
| **CSRFMiddleware** | محافظت CSRF برای درخواستهای state-changing |
| **InputSanitizationMiddleware** | پاکسازی ورودی (XSS) |
| **TimingMiddleware** | ثبت `X-Response-Time-Ms` |
| **MetricsMiddleware** | متریکهای Prometheus |
| **LoggingMiddleware** | لاگ method/path/status |
| **RateLimitMiddleware** | محدودیت IP-based per-route |

### ۷.۲ گروههای endpoint (۶۳ ماژول)

| گروه | مسیرها | توضیح |
|---|---|---|
| **بازار** | `/market/overview`, `/market/gainers`, `/market/heatmap`, `/market/market-watch`, `/market/watch`, `/market/insights` | نمای کلی، صعودیها، هیتماپ |
| **نمادها** | `/instruments`, `/instruments/search`, `/symbols`, `/symbol/{symbol}`, `/symbol-details`, `/symbol-search` | اطلاعات نماد و جستجو |
| **قیمت** | `/quotes`, `/quotes/history`, `/trades`, `/orderbooks`, `/candles` | قیمت، تاریخچه، دفتر سفارش |
| **تحلیل** | `/analysis`, `/indicators`, `/anomalies`, `/comprehensive-analysis` | اندیکاتورها (sma/ema/rsi/macd/bollinger/stochastic/atr/obv/williams_r/ichimoku) |
| **سیگنال** | `/signals`, `/signals/insights`, `/multi-market-signals`, `/smart-money`, `/recommendations` | سیگنالهای چندبازاری |
| **اسکرینر** | `/screener`, `/screener110`, `/screener-v2`, `/smart-screener`, `/scanner`, `/mass-scanner` | فیلتر ۱۱۰ ستونه |
| **صف** | `/queue-analysis`, `/queue-analysis/batch` | تحلیل صف خرید/فروش |
| **بکتست** | `/backtests`, `/backtests/{id}`, `/compose` | اجرا و مدیریت بکتست |
| **ML** | `/ml/*`, `/ml/model-loader/cache-info` | مدلها، پیشبینی، کش |
| **CODAL** | `/codal`, `/codal/accounting`, `/codal/audit`, `/codal/professional` | اطلاعیهها و صورتهای مالی |
| **صندوق** | `/funds`, `/funds/{symbol}/update`, `/fund-analysis` | صندوقهای سرمایهگذاری |
| **اخبار** | `/news`, `/news/feed` | اخبار + احساسات |
| **هشدار** | `/alerts`, `/alerts/history` | هشدار قیمت/حجم/RSI |
| **پرتفوی** | `/portfolios`, `/watchlist` | سبد و واچلیست |
| **کاربر** | `/auth/*` | ثبتنام، لاگین، MFA، پروفایل |
| **دستیار** | `/assistant`, `/stock-assistant`, `/chat` | دستیار هوشمند فارسی |
| **سیستم** | `/health`, `/health/ready`, `/jobs`, `/rate-limits`, `/cache-stats`, `/orchestrator-cron-status` | سلامت و مدیریت |
| **بازارهای جهانی** | `/commodities`, `/crypto`, `/gold`, `/currency`, `/macro`, `/economic-calendar` | طلا، ارز، کالا، کریپتو |
| **سایر** | `/alpha`, `/options`, `/risk`, `/sentiment`, `/paper-trading`, `/tables`, `/data-import`, `/tabdeal` | — |

### ۷.۳ Endpointهای مدیریتی خاص

| مسیر | توضیح |
|---|---|
| `GET /api/v1/orchestrator-cron-status` | وضعیت cron ساعتی (سیگنالها، دقت، health) |
| `POST /api/v1/orchestrator-cron/toggle` | روشن/خاموش cron |
| `POST /api/v1/orchestrator-cron/run-now` | اجرای فوری orchestrator |
| `GET /api/v1/rate-limits` | مصرف بودجه BrsApi |
| `GET /api/v1/cache-stats` | آمار کش اسکرینر |
| `GET /metrics` | خروجی Prometheus |
| `GET/POST /jobs/queue/summary`, `/jobs/queue/replay` | مدیریت صف dead-letter |
| `GET /ml/model-loader/cache-info` | مانیتورینگ کش مدل |

---

## ۸. زمانبند و Jobها

### ۸.۱ معماری اجرا

```
APScheduler ──► (Queue mode) ──► Redis Stream (job:queue) ──► Worker(s)
    │                                                            │
    └── (Fallback) ──► JobDispatcher ──► اجرا درونفرایند          │
                                                                  ▼
                        JobLocking (Redis Lock) — فقط یک اجرا در لحظه
```

- **Queue mode** (`job_queue_enabled=true`): زمانبند فقط **تریگر** میکند؛ Worker از صف میخواند و با قفل توزیعشده اجرا میکند (مناسب چند-ریپلیکا).
- **Fallback**: بدون Redis، jobها درونفرایند و با قفل in-memory اجرا میشوند (تک-ریپلیکا).

### ۸.۲ JobDispatcher

هر job از طریق `JobDispatcher.dispatch(name)` اجرا میشود:
1. **Dedup**: جلوگیری از اجرای تکراری
2. **Lock**: `job:{name}` — اگر قفل گرفته نشد، skip
3. **Semaphore**: حداکثر ۱۰ job همزمان
4. **Retry policy**: مدیریت تلاش مجدد

### ۸.۳ Jobهای زمانبندیشده

| Job | زمان | توضیح |
|---|---|---|
| `SyncQuotesJob` | هر ۲ دقیقه | قیمتها |
| `SyncSnapshotsToQuotesJob` | هر ۲ دقیقه | اسنپشات → quotes |
| `SyncInstrumentsJob` | هر ۲۴ ساعت | نمادها |
| `SyncCodalJob` | هر ۶ ساعت | اطلاعیههای CODAL |
| `SyncNavAllJob` | ۹:۰۰ و ۱۸:۰۰ | NAV صندوقها |
| `NewsIngestionJob` | هر ۱۰ دقیقه | اخبار |
| `EvaluateAlertsJob` | هر ۲ دقیقه | هشدارهای کاربر |
| `BackfillHistoricalDataJob` | ۰۲:۰۰ | بکتفیل تاریخچه |
| `FundsSyncJob` | ۱۷:۳۰ | اسنپشات صندوقها |
| `PaperTradingJob` | ۲۱:۰۰ | معاملات آزمایشی |
| `FeatureStoreBuildJob` | ۲۳:۳۰ | ساخت feature store |
| `ScreenerDailyScoresJob` | ۲۳:۴۵ | امتیاز روزانه ۱۱۰ ستونه |
| `BrsApiReadyCheckJob` | هر ۱ ساعت | پراب آمادگی کلید |
| `brsapi_candlesticks_all` | ۱۳:۰۰ | بکتفیل کندل (چانکی) |
| `brsapi_shareholders_all` | ۱۳:۳۰ | سهامداران |
| `brsapi_history_price_all` | ۱۴:۰۰ | تاریخچه قیمت |
| `brsapi_history_real_legal_all` | ۱۴:۳۰ | حقیقی-حقوقی |
| `brsapi_symbol_details_all` | ۲۱:۰۰ | جزئیات نمادها |
| `brsapi_all_symbols` | هر ۲ دقیقه (ساعات بازار) | نمادها |

### ۸.۴ صف Dead-Letter

- Workerهای ناموفق → پیام به `job:dead`
- مدیریت: `GET /jobs/queue/summary` (گزارش)، `POST /jobs/queue/replay` (بازگردانی)
- ابزار CLI: `scripts/replay_dead_letter.py`

---

## ۹. موتور سیگنال و تصمیمگیری

### ۹.۱ مسیر تولید سیگنال

```
MultiMarketSignalEngine
   ├── تحلیل تکنیکال (Rule-based) + اندیکاتورها
   ├── تحلیل بنیادی (fundamental)
   ├── احساسات اخبار (persian_sentiment)
   ├── SignalDecisionEngine (۱۰ دروازه)
   ├── SignalVotingSystem (رأیگیری)
   ├── ConfidenceScorer + ProbabilityCalibrator
   └── ML Signal Connector (مدلهای ML بهعنوان مشاور)
```

### ۹.۲ SignalDecisionEngine — دروازههای تصمیم

| دروازه | بررسی |
|---|---|
| ۱. کیفیت داده | اعتبار قیمت/حجم |
| ۲. سلامت مدل | اعتبار پیشبینی ML |
| ۳. رژیم بازار | صعودی/نزولی/خنثی |
| ۴. نقدشوندگی | حجم و اسپرد |
| ۵. صفها | وضعیت صف خرید/فروش |
| ۶. نوسان | Volatility سنجی |
| ۷. فاصله تا سقف/کف | محدودیت دامنه |
| ۸. وقایع | اخبار، مجامع |
| ۹. ریسک | Risk Override |
| ۱۰. اعتماد | نهاییسازی |

**Rule-Based Overrideها** (از `services/decision_gate.py`):
- رکود بازار (نوسان ۳ روز < ۲٪) → نادیده گرفتن ML، اکتفا به Mean-Reversion
- حجم ۳ برابر میانگین ۲۰ روزه → افزایش ۵۰٪ وزن رأی ML
- صف فروش با streak ≥ ۳ روز → ریسک CRITICAL

### ۹.۳ Cron ساعتی (Orchestrator)

`_orchestrator_hourly_cron` در `apps/api/app.py` هر ساعت:
1. تولید سیگنال با `QuantSignalOrchestrator`
2. ثبت خروجیها
3. ارزیابی دقت (SignalAccuracyTracker)
4. بازآموزی خودکار اگر دقت < آستانه
5. هشدار تلگرام برای ۳ شکست متوالی / دقت < ۵۰٪

---

## ۱۰. زیرسیستم ML

### ۱۰.۱ معماری

| مؤلفه | توضیح |
|---|---|
| **ModelLoader** | Lazy-load از دیسک + `lru_cache(maxsize=20)` — فقط نمادهای فعال Watchlist/Screener |
| **ModelRegistry** | ثبت و ساخت مدلها بر اساس نوع |
| **Trainer** | آموزش با ارزیابی و متادیتای artifact |
| **ArtifactManager** | ذخیره/بارگذاری مدلهای آموزشدیده |
| **train_weight_optimizer** | Ridge Regression برای هر رژیم بازار → وزنهای bull/bear/neutral |
| **GlobalTrainingService** | آموزش سراسری (۱۵ الگوریتم) |
| **InferenceService** | پیشبینی |

### ۱۰.۲ ModelLoader (LRU Cache)

- فقط مدلهای نمادهای Watchlist + Smart Screener فعال بارگذاری میشوند
- `get_model(symbol)` → بارگذاری از دیسک و قرار در کش
- `invalidate(symbol)` → پس از بازآموزی خودکار
- `preload(symbols)` → warm-up در startup
- `GET /ml/model-loader/cache-info` → مانیتورینگ

### ۱۰.۳ وزندهی پویا

- `weights_bull.json / weights_bear.json / weights_neutral.json`
- ورودی: `screener_daily_scores` (۱۱۰ ستون) + بازده آینده
- خروجی: وزن نرمالشده (مجموع قدر مطلق = ۱)

---

## ۱۱. موتور بکتست

| مؤلفه | توضیح |
|---|---|
| **BacktestSimulator** | هسته شبیهسازی (Event-driven + Vectorized) |
| **Broker** | کارمزد، slippage، مالیات |
| **استراتژیها** | MA Cross, Momentum, Mean Reversion, Breakout, RSI Reversion, Volatility Breakout, Half Trend, Squeeze Momentum, Support/Resistance |
| **قوانین بازار ایران** | دامنه نوسان ±۵٪، تیک ۱ ریال، ساعت ۰۸:۴۵-۱۲:۳۰، حراج پایانی، اولویت صف |
| **متریکها** | Sharpe, Sortino, CAGR, Calmar, MDD, Win Rate, Profit Factor |
| **ریسک** | StopLoss, TakeProfit, DrawdownControl |
| **Microstructure** | صف سفارش، ایمپکت جذر، حراج بازگشایی/پایانی |
| **ABM** | MarketMaker, NoiseTrader, TrendFollower, MeanReversion |

**منابع داده بکتست**: `brsapi_historical_daily` ← `quotes` ← `brsapi_intraday_trades` (تجمیعشده).

---

## ۱۲. فرانتاند Next.js

### ۱۲.۱ معماری

- **App Router** با ۶۲ صفحه
- **Rewrite Proxy**: `/api/v1/*` → backend (هرگز فراخوانی مستقیم به Backend از مرورگر)
- **RTL کامل** + پشتیبانی فارسی
- **Dark Mode**

### ۱۲.۲ صفحات (frontend/src/app)

| بخش | صفحات |
|---|---|
| **اصلی** | `/` (داشبورد), `/markets`, `/market-watch`, `/market-insights`, `/heatmap` |
| **تحلیل** | `/analysis`, `/indicators`, `/fundamental`, `/anomalies`, `/codal` |
| **سیگنال** | `/signals`, `/multi-market-signals`, `/smart-money`, `/recommendations` |
| **اسکرینر** | `/screener`, `/screener110`, `/smart-screener` |
| **بکتست** | `/backtest`, `/experiments`, `/paper-trading` |
| **داده** | `/instruments`, `/symbols`, `/symbol/{sym}`, `/symbol-details`, `/quotes`, `/trades`, `/tables`, `/data-import` |
| **صندوق** | `/funds` (+ FundAnalysisModal, FundCompareModal) |
| **صف** | QueueStatusPanel, SmartScreener modal |
| **هشدار/پرتفوی** | `/alerts`, `/watchlist`, `/portfolio` |
| **اخبار** | `/news` |
| **مدیریت** | `/admin` (+ DeadLetterWidget), `/jobs`, `/scheduler`, `/sync`, `/sync-manager`, `/health` |
| **ML** | `/ml` |
| **سایر** | `/crypto`, `/crypto-exchange`, `/commodities`, `/macro`, `/options`, `/risk`, `/economic-calendar`, `/auth`, `/settings`, `/profile`, `/chat` |

### ۱۲.۳ کامپوننتهای نمودار

`AreaChartCard`, `BarChartCard`, `PieChartCard`, `CandleChartCard`, `EquityCurveChart`, `DrawdownChart`, `TradingViewChart`, `SentimentChart`, `MultiEquityChart`, `BacktestResultsDashboard`, `MLBacktestTab`, `IndicatorChart`.

---

## ۱۳. زیرساخت Docker

### سرویسهای `docker-compose.yml`

| سرویس | نقش |
|---|---|
| `timescaledb` | PostgreSQL 16 + TimescaleDB (پورت 5432) |
| `redis` | Redis 7 — کش + صف (پورت 6379) |
| `backend` | API + Admin + Scheduler (پورت 8000/8001) |
| `worker` | مصرفکننده صف jobها |
| `frontend` | Next.js (پورت 3000) |

**استقرار Production (Swarm)**: Traefik، TLS، Docker Secrets.

---

## ۱۴. امنیت

| لایه | پیادهسازی |
|---|---|
| **Auth** | ثبتنام/لاگین با OTP ایمیل/تلگرام + **MFA (TOTP)** + تغییر رمز |
| **توکنها** | JWT با refresh + logout همه-دستگاه |
| **رمز عبور** | hash امن (Argon2/bcrypt) |
| **CSRF** | توکن CSRF در درخواستهای state-changing |
| **Input Sanitization** | جلوگیری XSS |
| **Rate Limit** | per-IP + per-route |
| **قفل توزیعشده** | Redis Lock برای jobها و startup taskها |
| **محافظت کلید BrsApi** | Kill switch + بودجه روزانه + fail-fast |
| **Telegram** | هشدارهای آستانه مصرف، شکست کرون، ریست کلید |

---

## ۱۵. اسکریپتهای عملیاتی

| اسکریپت | کاربرد |
|---|---|
| `scripts/run_backlog_sync.py` | رانر بودجه-آگاه عقبماندگی sync (real-legal ← symbol-details ← candlesticks) |
| `scripts/check_brsapi_ready.py` | پراب دستی آمادگی کلید (`--once` بدون ذخیره state) |
| `scripts/sync_delta_report.py` | مقایسه قبل/بعد sync (ردیفهای جدید، تازگی) — `--before`, `--fast`, `--format markdown` |
| `scripts/replay_dead_letter.py` | بازگردانی پیامهای `job:dead` به صف اصلی (`--summary`, `--dry-run`) |
| `scripts/dead_letter_report.py` | گزارش توزیع خطاهای dead-letter |
| `scripts/build_feature_store.py` | ساخت Feature Store (batch=10، موازی=4) |
| `scripts/build_screener_scores.py` | محاسبه امتیاز روزانه ۱۱۰ ستونه |
| `scripts/clean_historical_data.py` | پاکسازی داده تاریخی + View پاکشده |
| `scripts/train.py` | آموزش مدلهای ML |
| `scripts/backfill_historical_data.py` | بکتفیل تاریخچه |
| `scripts/import_data.py` | ایمپورت داده |
| `scripts/seed_funds.py` | پر کردن جدول صندوقها از BrsApi |
| `scripts/start_scheduler.py` | شروع زمانبند مستقل |
| `scripts/ultimate_walk_forward.py` | اعتبارسنجی Walk-Forward |

---

## ۱۶. تست و CI

| دایرکتوری | محتوا |
|---|---|
| `tests/unit/` | تستهای واحد (services, ml, jobs, brsapi) |
| `tests/integration/` | تستهای یکپارچهسازی (DB, Redis, API) |
| `tests/e2e/` | تستهای end-to-end API |

**نکات تست کلیدی**:
- تستهای retry/kill-switch با autouse fixture `_force_live_mode` از `.env` ایزوله شدهاند
- تستهای BrsApi از `_FakeResp` / AsyncMock استفاده میکنند — هرگز شبکه واقعی
- تستهای queue از FakeRedis / Redis واقعی قابل اجرا هستند

**GitHub Actions**: CI شامل Lint (ruff), Typecheck (mypy), تستهای pytest با service containers (PostgreSQL, Redis).

---

## ۱۷. راهاندازی

### پیشنیازها
- Python 3.11+، Node 20+، PostgreSQL 16 (یا Docker)، Redis 7

### ۱. نصب
```bash
pip install -r requirements.txt        # backend
cd frontend && npm install --no-audit --no-fund
```

### ۲. تنظیم `.env`
```bash
cp .env.example .env
# حداقلها:
#   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
#   BRSAPI_API_KEY=YourApiKey
#   BRSAPI_ENABLED=true            # false = حالت DB-only (محافظت کلید)
#   BRSAPI_GLOBAL_DAILY_LIMIT=4000 # زیر سقف واقعی پلن
```

**دیاگرام معماری بارگذاری تنظیمات** (منابع مقدار → pydantic-settings → کلاسهای Settings → مصرفکنندهها):

```mermaid
flowchart TB
    subgraph SOURCES["📥 منابع مقدار"]
        OS["🖥️ متغیرهای محیطی OS"]
        ENVFILE["📄 .env"]
        PROD["📄 .env.production"]
        DEFAULTS["⚙️ پیش‌فرض‌های داخل کد"]
    end

    subgraph LOADER["🧬 لایه بارگذاری (pydantic-settings)"]
        P["BaseSettings + SettingsConfigDict<br/>env_file='.env' · extra='ignore' · case_sensitive=False"]
    end

    subgraph SETTINGS["🗂️ کلاس‌های تنظیمات (بر اساس پیشوند)"]
        C1["Settings اصلی<br/>(بدون پیشوند / alias)"]
        C2["BrsApiSettings<br/>BRSAPI_"]
        C3["DatabaseSettings<br/>DB_"]
        C4["ApiSettings · SecuritySettings<br/>API_ · SECURITY_"]
        C5["SchedulerSettings · MLSettings<br/>SCHEDULER_ · ML_"]
        C6["StorageSettings · ProviderSettings<br/>STORAGE_ · PROVIDER_"]
        C7["MonitoringSettings · AdminSettings<br/>MONITORING_ · ADMIN_"]
        C8["IndicatorSettings · FeatureFlagSettings<br/>INDICATOR_ · FF_"]
        C9["AppSettings · PathSettings<br/>APP_ · PATH_"]
        C10["IngestionConfig<br/>INGESTION_"]
    end

    subgraph CONSUMERS["⚙️ مصرف‌کننده‌ها"]
        API["FastAPI (apps/api)"]
        SCHED["APScheduler"]
        WORKER["Worker · Job Queue"]
        INGEST["سرویس Ingestion"]
        BR["BrsApi Client + RateLimiter"]
        FE["Frontend (Next.js)"]
    end

    OS -->|"اولویت ۱ · غلبه بر همه"| P
    ENVFILE -->|"اولویت ۲"| P
    PROD -->|"فقط در production"| P
    DEFAULTS -->|"اولویت ۳"| P

    P --> C1
    P --> C2
    P --> C3
    P --> C4
    P --> C5
    P --> C6
    P --> C7
    P --> C8
    P --> C9
    P --> C10

    C1 --> API
    C1 --> SCHED
    C1 --> WORKER
    C2 --> BR
    C3 --> API
    C5 --> SCHED
    C5 --> WORKER
    C7 --> API
    C10 --> INGEST
    FE -.->|"NEXT_PUBLIC_* (سمت مرورگر)"| API

    style OS fill:#fce4ec,stroke:#c62828
    style ENVFILE fill:#e3f2fd,stroke:#1565c0
    style PROD fill:#e8f5e9,stroke:#2e7d32
    style DEFAULTS fill:#f5f5f5,stroke:#616161
    style P fill:#fff3e0,stroke:#e65100
    style BR fill:#f3e5f5,stroke:#7b1fa2
```

> 📖 مرجع کامل همه متغیرها: [`docs/env-vars.md`](env-vars.md)

### ۳. مهاجرت دیتابیس
```bash
alembic upgrade head
```

### ۴. اجرا
```bash
python main.py                # API روی :8000 (docs: /docs)
cd frontend && npm run dev    # فرانتاند روی :3000
```

### ۵. Docker
```bash
docker compose up --build -d
```

### ۶. عملیات روزانه
```bash
# قبل از هر sync، baseline بگیر:
python scripts/sync_delta_report.py --before
# بعد از sync، دلتا را ببین:
python scripts/sync_delta_report.py
# بررسی سریع آمادگی کلید:
python scripts/check_brsapi_ready.py
```

---

## ۱۸. عیبیابی

| مشکل | راهحل |
|---|---|
| **کلید BrsApi 302 میدهد** | شمارنده سمت سرور پر است → `BRSAPI_ENABLED=false` تا ریست، چک ساعتی خودکار خبر میدهد |
| **بودجه روزانه تمام شد** | صبر تا نیمهشب تهران؛ `GET /api/v1/rate-limits` برای مصرف |
| **jobهای sync منجمد شدند** | `GET /jobs/queue/summary` → `POST /jobs/queue/replay` |
| **لاگین کند / مدل سنگین** | `GET /ml/model-loader/cache-info` → بررسی کش |
| **جدولها قدیمیاند** | `python scripts/sync_delta_report.py` → عقبماندگی را شناسایی کن → `run_backlog_sync.py` |
| **دقت سیگنال پایین** | `GET /api/v1/orchestrator-cron-status` → بازآموزی خودکار فعال است |
| **SQLite خطا میدهد** | باید PostgreSQL تنظیم شود؛ SQLite پشتیبانی نمیشود |
| **پیام تکراری در چند Worker** | قفل Redis + queue mode باید فعال باشند |

---

## پیوست: متغیرهای محیطی مهم

| متغیر | پیشفرض | توضیح |
|---|---|---|
| `DATABASE_URL` | — | اتصال asyncpg به PostgreSQL |
| `BRSAPI_API_KEY` | — | کلید BrsApi.ir |
| `BRSAPI_ENABLED` | true | Kill switch — false = DB-only |
| `BRSAPI_GLOBAL_DAILY_LIMIT` | 4000 | سقف روزانه (زیر ۵۰۰۰ واقعی پلن) |
| `BRSAPI_GLOBAL_5MIN_LIMIT` | 1000 | سقف ۵ دقیقهای |
| `BRSAPI_FAIL_FAST_ON_DAILY_EXHAUSTED` | true | رد فوری هنگام اتمام بودجه |
| `BRSAPI_RATE_LIMIT_TSETMC` | 60 | نرخ دسته tsetmc |
| `JOB_QUEUE_ENABLED` | — | true = حالت صف/Worker |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | — | هشدارهای تلگرام |
| `SCHEDULER_TIMEZONE` | Asia/Tehran | منطقه زمانی زمانبند |
