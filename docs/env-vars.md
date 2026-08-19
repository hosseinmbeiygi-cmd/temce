# 📋 راهنمای کامل متغیرهای محیطی (.env)

این مستند مرجع کامل همه متغیرهای محیطی پروژه **Iran Market Data & Analytics Platform** است.
مقدارها از کد (کلاس‌های `BaseSettings`) استخراج شده‌اند، نه از حدس.

---

## 🧭 ۱. نحوه بارگذاری تنظیمات

| نکته | توضیح |
|---|---|
| فایل‌های محیطی | `.env` (پیش‌فرض)، `.env.production`، `.env.example` |
| کلاس پایه | `pydantic-settings` با `SettingsConfigDict(env_file=".env", extra="ignore")` |
| پیشوندها | هر ماژول پیشوند مخصوص دارد (مثل `BRSAPI_`، `DB_`، `ML_`) |
| بدون پیشوند | تنظیمات اصلی (`Settings`) بدون پیشوند خوانده می‌شوند یا با `alias` صریح (مثل `DATABASE_URL`) |
| **اولویت مقادیر** | متغیر محیطی سیستمعامل > `.env` > مقدار پیش‌فرض کد |
| `extra="ignore"` | متغیرهای ناشناخته بی‌صدا نادیده گرفته می‌شوند |

> ⚠️ **هشدار مهم:** متغیرهای محیطی سیستمعامل روی `.env` **غلبه می‌کنند**. اگر یک متغیر قدیمی در OS ست شده باشد (مثل `BRSAPI_GLOBAL_DAILY_LIMIT=10000`)، لیمیتر با مقدار اشتباه کار می‌کند. با `env | grep BRSAPI` بررسی کنید.

### 📐 دیاگرام ۱: معماری کلی بارگذاری تنظیمات

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

### 📐 دیاگرام ۲: جریان Rate Limiter سرویس BrsApi (مهم‌ترین بخش)

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

---

## 🔑 ۲. متغیرهای الزامی (REQUIRED)

| متغیر | توضیح | نکته |
|---|---|---|
| `BRSAPI_API_KEY` | کلید API سرویس BrsApi.ir | بدون آن هیچ داده‌ی زنده‌ای دریافت نمی‌شود |
| `SECRET_KEY` | کلید امضای JWT و سشن | در production **حتماً** از مقدار پیش‌فرض تغییر دهید |
| `ADMIN_SECRET_KEY` | کلید پنل ادمین | **الزامی** (حداقل ۱۶ کاراکتر — بدون آن اپ استارت نمی‌شود) |
| `DATABASE_URL` | آدرس کامل PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | آدرس Redis (کش، صف، قفل) | `redis://localhost:6379/0` |

---

## 🎛️ ۳. تنظیمات اصلی (بدون پیشوند — `core/config/__init__.py`)

### عمومی
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `ENV` | `development` | `development` \| `production` \| `staging` |
| `DEBUG` | `false` | حالت دیباگ |
| `SERVER_HOST` | `0.0.0.0` | آدرس بایند سرور |
| `SERVER_PORT` | `8000` | پورت API |
| `WORKERS` | `1` | تعداد workerها (پیشنهاد: ۱ در توسعه، ۲ در production) |
| `DATA_DIR` | `./data` | مسیر دیتا |

### دیتابیس و Redis
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://market:market@localhost:5432/market` | آدرس کامل دیتابیس |
| `DB_POOL_SIZE` | `20` | سایز connection pool |
| `DB_MAX_OVERFLOW` | `30` | حداکثر overflow |
| `DB_ECHO` | `false` | لاگ کوئری‌های SQL |
| `DATABASE_AUTO_CREATE_TABLES` | `false` | ساخت خودکار جدول‌ها (فقط dev؛ در production از Alembic استفاده کنید) |
| `REDIS_URL` | `redis://localhost:6379/0` | آدرس Redis |
| `REDIS_DEFAULT_TTL` | `300` | TTL پیش‌فرض کش (ثانیه) |

### لاگ
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `LOG_FORMAT` | `json` | `json` \| `console` |
| `LOG_FILE` | — | مسیر فایل لاگ (خالی = خروجی کنسول) |

### API و CORS
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `API_PREFIX` | `/api/v1` | پیشوند همه routeها |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | لیست originهای مجاز — در production دقیقاً مشخص کنید |
| `API_KEY_HEADER` | `X-API-Key` | نام هدر کلید API |
| `RATE_LIMIT_INCLUDE_HEADERS` | `true` | افزودن هدرهای `X-RateLimit-*` |

### امنیت و احراز هویت
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | کلید امضا — **در production الزاماً تغییر دهید** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | عمر access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | عمر refresh token |
| `JWT_ALGORITHM` | `HS256` | الگوریتم JWT |
| `BCRYPT_ROUNDS` | `12` | راندهای هش رمز |
| `MAX_LOGIN_ATTEMPTS` | `5` | حداکثر تلاش ورود |
| `LOCKOUT_MINUTES` | `15` | مدت قفل بعد از تلاش‌های ناموفق |
| `SESSION_TIMEOUT_MINUTES` | `30` | مهلت سشن |
| `ENABLE_CSRF` | `true` | فعال‌سازی CSRF |
| `AUTH_COOKIE_NAME` | `im_refresh` | نام کوکی httpOnly refresh |
| `AUTH_COOKIE_SECURE` | `false` | `true` در production (HTTPS) |
| `AUTH_COOKIE_DOMAIN` | — | دامنه کوکی |
| `AUTH_COOKIE_SAMESITE` | `lax` | `lax` \| `strict` \| `none` |
| `ENABLE_INPUT_SANITIZATION` | `true` | پاک‌سازی ورودی JSON (ضد XSS) |

### سرویس‌های داده خارجی
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `TSETMC_BASE_URL` | `http://tsetmc.com` | آدرس TSETMC |
| `TSETMC_WS_URL` | — | WebSocket TSETMC |
| `CODAL_BASE_URL` | `https://codal.ir` | آدرس کدال |
| `CODAL_API_KEY` | — | کلید API کدال |
| `CODAL_EXCEL_DIR` | — | مسیر ذخیره خروجی‌های Excel کدال |
| `FIPIRAN_API_KEY` | — | کلید فیپیران |

### ML
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `ML_MODEL_DIR` | `./data/models` | مسیر ذخیره مدل‌ها |
| `ML_DEFAULT_BATCH_SIZE` | `2048` | سایز batch |
| `ML_DEVICE` | `cpu` | `cpu` \| `cuda` |
| `ML_RANDOM_SEED` | `42` | seed تصادفی |
| `ML_EXPERIMENT_TRACKER_URI` | — | آدرس tracker (MLflow و...) |

### بک‌تست
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `BACKTEST_DEFAULT_CAPITAL` | `1000000000` | سرمایه اولیه (ریال) |
| `BACKTEST_DEFAULT_COMMISSION_PCT` | `0.0035` | کارمزد (۰.۳۵٪) |
| `BACKTEST_DEFAULT_SLIPPAGE_BPS` | `10.0` | لغزش (۱۰ واحد پایه) |

### مانیتورینگ
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `MONITORING_ENABLED` | `true` | فعال‌سازی متریک‌ها |
| `METRICS_PATH` | `/metrics` | مسیر متریک Prometheus |
| `OTLP_ENDPOINT` | — | OpenTelemetry collector |
| `SENTRY_DSN` | — | DSN سِنتری |
| `LOG_AGGREGATION_ENABLED` | `false` | تجمیع لاگ در Redis Streams |
| `LOG_AGGREGATION_SOURCE` | `api` | نام سرویس مبدأ لاگ |

### Scheduler و Job Queue
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `SCHEDULER_TIMEZONE` | `Asia/Tehran` | منطقه زمانی زمان‌بند |
| `JOBS_MAX_CONCURRENT` | `4` | حداکثر جاب همزمان |
| `JOBS_DEFAULT_TIMEOUT_MINUTES` | `30` | مهلت پیش‌فرض جاب‌ها |
| `JOB_QUEUE_ENABLED` | `false` | فعال‌سازی صف توزیع‌شده (در multi-replica **روشن** کنید؛ در dev خاموش بماند) |
| `JOB_QUEUE_NAME` | `job:queue` | نام صف اصلی Redis |
| `JOB_QUEUE_TOKEN` | — | توکن مشترک workerها — **در production ست کنید** |
| `JOB_QUEUE_LOCK_TTL` | `300` | TTL قفل توزیع‌شده (ثانیه) |
| `JOB_QUEUE_DEAD_LETTER` | `job:dead` | لیست dead-letter |
| `JOB_QUEUE_CONSUMER_TIMEOUT` | `1` | timeout مصرف‌کننده |

### تلگرام (اختیاری)
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | توکن ربات تلگرام (هشدارها) |
| `TELEGRAM_CHAT_ID` | — | شناسه چت مقصد |

---

## 🗄️ ۴. پیشوند `DB_` (`core/config/database.py`)

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://market:market@localhost:5432/market` | آدرس کامل (alias مشترک) |
| `DB_POOL_SIZE` | `20` | سایز pool |
| `DB_MAX_OVERFLOW` | `30` | حداکثر overflow |
| `DB_ECHO` | `false` | لاگ SQL |
| `DB_POOL_PRE_PING` | `true` | بررسی سلامت اتصال قبل از استفاده |
| `DB_POOL_RECYCLE` | `3600` | بازیافت اتصال (ثانیه) |
| `DB_CONNECT_TIMEOUT` | `10` | مهلت اتصال (ثانیه) |
| `DB_STATEMENT_TIMEOUT` | `30` | مهلت اجرای کوئری (ثانیه) |
| `DB_MIGRATION_DIR` | `./migrations` | مسیر migrationها |
| `REDIS_URL` | `redis://localhost:6379/0` | (مشترک) |
| `REDIS_MAX_CONNECTIONS` | `20` | حداکثر اتصال Redis |

---

## 🌐 ۵. پیشوند `API_` (`core/config/api.py`)

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `API_HOST` | `0.0.0.0` | آدرس بایند |
| `API_PORT` | `8000` | پورت |
| `API_WORKERS` | `1` | تعداد worker |
| `API_PREFIX` | `/api/v1` | پیشوند routeها |
| `API_TITLE` | `Iran Market Platform API` | عنوان سواگر |
| `CORS_ORIGINS` | `["*"]` | originهای مجاز |
| `CORS_ALLOW_CREDENTIALS` | `true` | اجازه cookie |
| `API_RATE_LIMIT_PER_MINUTE` | `60` | سقف rate limit پیش‌فرض |
| `API_MAX_REQUEST_SIZE_MB` | `10` | حداکثر حجم درخواست |
| `API_REQUEST_TIMEOUT_SECONDS` | `30` | مهلت درخواست |
| `API_DOCS_ENABLED` | `true` | نمایش `/docs` |
| `API_DEBUG` | `false` | حالت دیباگ |

---

## 🛡️ ۶. پیشوند `SECURITY_` (`core/config/security.py`)

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | (مشترک) |
| `SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | عمر access token |
| `SECURITY_REFRESH_TOKEN_EXPIRE_DAYS` | `30` | عمر refresh token |
| `SECURITY_ALLOWED_HOSTS` | `["*"]` | هاست‌های مجاز |
| `SECURITY_BCRYPT_ROUNDS` | `12` | راند هش |
| `SECURITY_RATE_LIMIT_PER_MINUTE` | `60` | سقف rate limit |
| `SECURITY_MAX_LOGIN_ATTEMPTS` | `5` | تلاش ورود |
| `SECURITY_LOCKOUT_MINUTES` | `15` | مهلت قفل |
| `SECURITY_ENABLE_CSRF` | `true` | CSRF |
| `SECURITY_ENABLE_HTTPS_REDIRECT` | `false` | ریدایرکت HTTPS |
| `SECURITY_CONTENT_SECURITY_POLICY` | — | هدر CSP |

---

## ⚙️ ۷. سایر پیشوندها

### `APP_` — تنظیمات برنامه
`APP_NAME`، `APP_DEBUG`، `APP_ENVIRONMENT` (alias `ENV`)، `APP_LOG_LEVEL`، `APP_LOG_FORMAT`، `APP_TIMEZONE`، `APP_DATA_DIR`، `APP_TEMP_DIR`، `APP_MAX_WORKERS`، `APP_SHUTDOWN_TIMEOUT_SECONDS`، `APP_VERSION`

### `SCHEDULER_` — زمان‌بند
| متغیر | پیش‌فرض |
|---|---|
| `SCHEDULER_ENABLED` | `true` |
| `SCHEDULER_TIMEZONE` | `Asia/Tehran` |
| `SCHEDULER_MAX_CONCURRENT_JOBS` | `4` |
| `SCHEDULER_DEFAULT_TIMEOUT_MINUTES` | `30` |
| `SCHEDULER_HEARTBEAT_INTERVAL_SECONDS` | `30` |
| `SCHEDULER_POLL_INTERVAL_SECONDS` | `10` |
| `SCHEDULER_MISSED_JOB_GRACE_MINUTES` | `5` |
| `SCHEDULER_RETRY_DELAY_SECONDS` | `60` |
| `SCHEDULER_MAX_RETRIES` | `3` |
| `SCHEDULER_STORE_RESULTS` | `true` |
| `SCHEDULER_RESULT_TTL_HOURS` | `168` |

### `ML_` — ML
`ML_MODEL_DIR`، `ML_DEFAULT_BATCH_SIZE` (2048)، `ML_DEVICE` (cpu)، `ML_RANDOM_SEED` (42)، `ML_EXPERIMENT_TRACKER_URI`، `ML_FEATURE_STORE_URI`، `ML_REGISTRY_URI`، `ML_TRAINING_TIMEOUT_MINUTES` (120)، `ML_INFERENCE_TIMEOUT_SECONDS` (30)، `ML_MAX_MODEL_SIZE_MB` (500)، `ML_ENABLE_AUTO_ML` (false)، `ML_ENABLE_EXPLAINABILITY` (true)، `ML_ENABLE_DRIFT_DETECTION` (true)، `ML_DRIFT_ALERT_THRESHOLD` (0.15)

### `STORAGE_` — ذخیره‌سازی
| متغیر | پیش‌فرض |
|---|---|
| `STORAGE_BACKEND` | `local` (`local` \| `s3` \| `gcs` \| `azure`) |
| `STORAGE_LOCAL_PATH` | `./data/storage` |
| `STORAGE_S3_BUCKET` / `STORAGE_S3_REGION` | — / `us-east-1` |
| `STORAGE_S3_ACCESS_KEY` / `STORAGE_S3_SECRET_KEY` / `STORAGE_S3_ENDPOINT_URL` | — |
| `STORAGE_GCS_BUCKET` / `STORAGE_AZURE_CONTAINER` | — |
| `STORAGE_MAX_FILE_SIZE_MB` | `100` |
| `STORAGE_COMPRESSION_ENABLED` | `true` |
| `STORAGE_ENCRYPTION_ENABLED` | `false` |
| `STORAGE_RETENTION_DAYS` | `90` |
| `STORAGE_ARCHIVE_AFTER_DAYS` | `30` |

### `PROVIDER_` — سرویس‌های خارجی
`PROVIDER_DEFAULT_TIMEOUT` (30)، `PROVIDER_MAX_RETRIES` (3)، `PROVIDER_RATE_LIMIT_PER_MINUTE` (60)، `PROVIDER_RATE_LIMIT_BURST` (10)، `PROVIDER_ENABLE_FAILOVER` (true)، `PROVIDER_ENABLE_CIRCUIT_BREAKER` (true)، `PROVIDER_CIRCUIT_BREAKER_FAILURE_THRESHOLD` (5)، `PROVIDER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` (30.0)، `PROVIDER_HEALTH_CHECK_INTERVAL_SECONDS` (60)، `PROVIDER_CONCURRENT_REQUESTS` (10)

### `MONITORING_` — رصد
`MONITORING_ENABLED` (true)، `MONITORING_OTLP_ENDPOINT`، `MONITORING_SENTRY_DSN`، `MONITORING_METRICS_PORT` (9090)، `MONITORING_METRICS_PATH` (/metrics)، `MONITORING_HEALTH_CHECK_PATH` (/health)، `MONITORING_LIVENESS_PATH` (/live)، `MONITORING_READINESS_PATH` (/ready)، `MONITORING_COLLECT_INTERVAL_SECONDS` (15)، `MONITORING_EXPORT_INTERVAL_SECONDS` (60)، `MONITORING_ENABLE_PROCESS_METRICS` (true)، `MONITORING_ENABLE_GC_METRICS` (true)

### `BACKTEST_` — بک‌تست
`BACKTEST_DEFAULT_CAPITAL` (1_000_000_000)، `BACKTEST_DEFAULT_COMMISSION_PCT` (0.0035)، `BACKTEST_DEFAULT_SLIPPAGE_BPS` (10.0)، `BACKTEST_MAX_POSITIONS` (50)، `BACKTEST_MAX_LEVERAGE` (1.0)، `BACKTEST_ALLOW_SHORT` (false)، `BACKTEST_DEFAULT_TIMEFRAME` (1d)، `BACKTEST_OUTPUT_DIR` (./data/backtest)، `BACKTEST_PARALLEL_RUNS` (4)، `BACKTEST_MAX_OPTIMIZATION_WORKERS` (4)، `BACKTEST_CACHE_RESULTS` (true)، `BACKTEST_MAX_OPTIMIZATION_TRIALS` (100)

### `INDICATOR_` — اندیکاتورها
`INDICATOR_DEFAULT_PERIOD` (14)، `INDICATOR_EMA_SPAN` (12)، `INDICATOR_SMA_SPAN` (20)، `INDICATOR_BOLLINGER_PERIOD` (20)، `INDICATOR_BOLLINGER_STD` (2.0)، `INDICATOR_RSI_PERIOD` (14)، `INDICATOR_MACD_FAST` (12)، `INDICATOR_MACD_SLOW` (26)، `INDICATOR_MACD_SIGNAL` (9)، `INDICATOR_ATR_PERIOD` (14)، `INDICATOR_VOLUME_MA_PERIOD` (20)، `INDICATOR_CACHE_RESULTS` (true)، `INDICATOR_CACHE_TTL_SECONDS` (3600)

### `FF_` — Feature Flags
`FF_USE_ML_MODELS` (true)، `FF_USE_WEBSOCKET` (true)، `FF_USE_CACHE` (true)، `FF_USE_ADVANCED_BACKTEST` (false)، `FF_ENABLE_AUDIT` (true)، `FF_ENABLE_SENTRY` (false)، `FF_ENABLE_METRICS` (true)، `FF_ENABLE_PROVIDER_FAILOVER` (true)، `FF_ENABLE_AUTO_RETRY` (true)، `FF_ENABLE_RATE_LIMITING` (true)، `FF_ENABLE_CIRCUIT_BREAKER` (true)

### `ADMIN_` — پنل ادمین
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `ADMIN_SECRET_KEY` | **الزامی** (min 16) | کلید ادمین — بدون آن استارت نمی‌شود |
| `ADMIN_ENABLED` | `true` | فعال‌سازی پنل |
| `ADMIN_SESSION_TIMEOUT_MINUTES` | `30` | مهلت سشن ادمین |
| `ADMIN_MAX_LOGIN_ATTEMPTS` | `5` | تلاش ورود |
| `ADMIN_ALLOWED_IPS` | `["127.0.0.1"]` | IPهای مجاز |
| `ADMIN_DASHBOARD_URL` | `/admin` | مسیر داشبورد |
| `ADMIN_AUDIT_LOG_ENABLED` | `true` | لاگ حسابرسی |
| `ADMIN_METRICS_REFRESH_SECONDS` | `10` | تازه‌سازی متریک‌ها |

### `PATH_` — مسیرها
`PATH_DATA_DIR` (./data)، `PATH_LOG_DIR` (./logs)، `PATH_CONFIG_DIR` (./config)، `PATH_TEMP_DIR` (./tmp)، `PATH_MODEL_DIR` (./data/models)، `PATH_EXPORT_DIR` (./data/exports)، `PATH_ARCHIVE_DIR` (./data/archive)، `PATH_BACKUP_DIR` (./data/backup)، `PATH_MIGRATION_DIR` (./migrations)

### `SECRET_` — مدیریت اسرار (`core/security/secrets.py`)
کلیدها با الگوی `SECRET_<KEY>` خوانده می‌شوند (مثلاً `SECRET_DB_PASSWORD`). تولید خودکار: `core.security.secrets.generate_secret()`.

---

## 📡 ۸. پیشوند `BRSAPI_` — سرویس BrsApi.ir (`brsapi/config.py`)

### کلید و حالت کلی
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `BRSAPI_API_KEY` | — | کلید API (الزامی) |
| `BRSAPI_BASE_URL` | `https://api.brsapi.ir` | آدرس پایه |
| `BRSAPI_ENABLED` | `true` | **کلید اصلی**: `false` = حالت DB-only بدون هیچ تماس زنده (موقع بلاک بودن کلید استفاده کنید) |
| `BRSAPI_REQUEST_TIMEOUT` | `30` | مهلت درخواست (ثانیه) |
| `BRSAPI_MAX_RETRIES` | `3` | حداکثر تلاش مجدد |
| `BRSAPI_RETRY_BACKOFF_BASE` | `1.5` | پایه backoff |
| `BRSAPI_RETRY_MAX_DELAY` | `60` | حداکثر تأخیر retry |
| `BRSAPI_CONNECTION_POOL_SIZE` | `10` | سایز pool اتصال |
| `BRSAPI_VERIFY_SSL` | `true` | بررسی گواهی TLS |

### کش
| متغیر | پیش‌فرض |
|---|---|
| `BRSAPI_CACHE_ENABLED` | `true` |
| `BRSAPI_CACHE_TTL_DEFAULT` | `55` |

### ساعات بازار
| متغیر | پیش‌فرض |
|---|---|
| `BRSAPI_MARKET_TIMEZONE` | `Asia/Tehran` |
| `BRSAPI_MARKET_OPEN` | `08:30` |
| `BRSAPI_MARKET_CLOSE` | `15:30` |
| `BRSAPI_ONLY_DURING_MARKET_HOURS` | `true` |

### سطل‌های نرخ (rate-limit per-category)
| متغیر | پیش‌فرض |
|---|---|
| `BRSAPI_RATE_LIMIT_TSETMC` | `60` (req/min — با پلن ارتقایافته هماهنگ شده) |
| `BRSAPI_RATE_LIMIT_CODAL` | `12` |
| `BRSAPI_RATE_LIMIT_IME` | `12` |
| `BRSAPI_RATE_LIMIT_COMMODITY` | `1` |
| `BRSAPI_RATE_LIMIT_CRYPTO` | `1` |

### 🚨 محدودیت‌های سراسری (مهم‌ترین بخش)
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `BRSAPI_GLOBAL_DAILY_LIMIT` | `4000` | سقف سخت روزانه. پلن رایگان کلید را بالای ~۵۰۰۰ req/day **بلاک** می‌کند؛ مقدار را دقیقاً روی سقف پلن خریداری‌شده تنظیم کنید |
| `BRSAPI_GLOBAL_5MIN_LIMIT` | `1000` | سقف پنج‌دقیقه‌ای (پلن ارتقایافته) |
| `BRSAPI_FAIL_FAST_ON_DAILY_EXHAUSTED` | `true` | وقتی بودجه روزانه تمام شد، درخواست فوراً رد شود (به‌جای خواب تا نیمه‌شب) — جلوی بلاک شدن کلید را می‌گیرد |

> ⚠️ این مقادیر باید با بسته خریداری‌شده شما هماهنگ باشند (مثلاً بسته AIO: 500 req/5min). به‌روزرسانی را از پنل کاربری BrsApi بررسی کنید.

### کنترل جاب‌های Backfill
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `BRSAPI_CANDLE_DAILY_MAX_SYMBOLS` | `1000` | حداکثر نماد در هر اجرای backfill کندلاستیک (0 = همه) |
| `BRSAPI_CANDLE_REQ_DELAY` | `0.2` | فاصله بین درخواست‌ها (ثانیه) |
| `BRSAPI_SHAREHOLDER_DAILY_MAX_SYMBOLS` | `1000` | حداکثر نماد سهامداران در روز |
| `BRSAPI_SHAREHOLDER_REQ_DELAY` | `5.0` | فاصله درخواست‌ها |
| `BRSAPI_HISTORY_PRICE_DAILY_MAX_SYMBOLS` | `500` | حداکثر نماد هیستوری قیمت در روز |
| `BRSAPI_HISTORY_PRICE_REQ_DELAY` | `5.0` | فاصله درخواست‌ها |
| `BRSAPI_HISTORY_REAL_LEGAL_DAILY_MAX_SYMBOLS` | `500` | حداکثر نماد حقیقی-حقوقی در روز |
| `BRSAPI_HISTORY_REAL_LEGAL_REQ_DELAY` | `5.0` | فاصله درخواست‌ها |
| `BRSAPI_SYMBOL_DETAIL_DAILY_MAX_SYMBOLS` | `1000` | حداکثر نماد جزئیات نماد در روز (شبانه ۲۱:۰۰) |
| `BRSAPI_SYMBOL_DETAIL_REQ_DELAY` | `4.0` | فاصله درخواست‌ها |
| `BRSAPI_RAW_PAYLOAD_SINK_ENABLED` | `false` | ذخیره JSON خام برای حسابرسی |
| `BRSAPI_MAX_RAW_PAYLOAD_AGE_DAYS` | `30` | حداکثر سن payload خام |
| `BRSAPI_PROXY_URL` | — | پراکسی اختیاری |
| `BRSAPI_HEALTH_CHECK_INTERVAL_SECONDS` | `60` | فاصله چک سلامت |

---

## 🗃️ ۹. پیشوند `INGESTION_` — جمع‌آوری داده (`ingestion/config.py`)

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `INGESTION_ENABLED_SOURCES` | همه منابع | لیست منابع فعال (JSON) |
| `INGESTION_WORKER_COUNT` | `4` | تعداد worker |
| `INGESTION_MAX_RETRIES` | `3` | تلاش مجدد |
| `INGESTION_RETRY_BACKOFF_BASE` | `2.0` | پایه backoff |
| `INGESTION_RETRY_MAX_DELAY` | `60.0` | حداکثر تأخیر |
| `INGESTION_REQUEST_TIMEOUT` | `30.0` | مهلت درخواست |
| `INGESTION_RATE_LIMIT_CALLS` | `10` | تعداد تماس مجاز |
| `INGESTION_RATE_LIMIT_PERIOD` | `1` | در هر چند ثانیه |
| `INGESTION_LAKE_BUCKET_RAW` | `raw-payloads` | باکت MinIO |
| `INGESTION_LAKE_BUCKET_PARSED` | `parsed-data` | باکت MinIO |
| `INGESTION_LAKE_ENDPOINT` | `http://minio:9000` | آدرس MinIO |
| `INGESTION_LAKE_ACCESS_KEY` / `INGESTION_LAKE_SECRET_KEY` | `minioadmin` | اعتبار MinIO |
| `INGESTION_DB_DSN` | `postgresql+asyncpg://postgres:postgres@localhost:5433/marketdb` | آدرس دیتابیس ingestion |
| `INGESTION_DB_POOL_SIZE` | `10` | سایز pool |
| `INGESTION_REDIS_URL` | `redis://localhost:6379/0` | Redis |
| `INGESTION_SCHEDULER_INTERVAL_SECONDS` | `15` | فاصله زمان‌بند |
| `INGESTION_MARKET_OPEN` / `INGESTION_MARKET_CLOSE` | `08:30` / `15:30` | ساعات بازار |
| `INGESTION_DEDUP_WINDOW_MINUTES` | `60` | پنجره حذف تکراری |
| `INGESTION_REPLAY_CHUNK_SIZE` | `1000` | سایز chunk replay |
| `INGESTION_REPLAY_CONCURRENCY` | `2` | همزمانی replay |

---

## 🖥️ ۱۰. فرانت‌اند (Next.js)

| متغیر | توضیح |
|---|---|
| `NEXT_PUBLIC_API_URL` | آدرس کامل API (مثال: `http://localhost:8000`) |
| `NEXT_PUBLIC_API_PREFIX` | پیشوند API (مثال: `/api/v1`) |

---

## 🧰 ۱۱. متغیرهای legacy و اسکریپتی

این متغیرها در `.env` موجودند اما توسط Settings اصلی خوانده نمی‌شوند — توسط اسکریپت‌های خاص یا Docker مصرف می‌شوند:

| متغیر | مصرف‌کننده | توضیح |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `scripts/batch_audit_all_symbols.py` | اتصال مستقیم psycopg2 در اسکریپت‌ها |
| `PG_HOST` / `PG_PORT` / `PG_USER` / `PG_PASSWORD` / `PG_DATABASE` | (در کد فعلی استفاده نمی‌شود) | ظاهراً legacy از نسخه‌های قبلی — قابل حذف |

---

## 🔒 ۱۲. چک‌لیست امنیتی Production

- [ ] `SECRET_KEY` از مقدار پیش‌فرض تغییر کرده
- [ ] `ADMIN_SECRET_KEY` ست شده (≥ ۱۶ کاراکتر)
- [ ] `CORS_ORIGINS` دقیقاً به دامنه‌های خودتان محدود شده
- [ ] `JOB_QUEUE_TOKEN` ست شده و `JOB_QUEUE_ENABLED=true`
- [ ] `AUTH_COOKIE_SECURE=true`
- [ ] `BRSAPI_GLOBAL_DAILY_LIMIT` دقیقاً روی سقف پلن شما
- [ ] متغیرهای اضافی از OS حذف شده‌اند (`env | grep BRSAPI` را بررسی کنید)
- [ ] `DATABASE_AUTO_CREATE_TABLES=false` (استفاده از Alembic)

---

## ⚡ ۱۳. دستورات کاربردی

```bash
# بررسی متغیرهای محیطی سیستم که روی .env غلبه می‌کنند
env | grep -E 'BRSAPI|SECRET|DATABASE|REDIS'

# حذف متغیر قدیمی سیستمعامل
unset BRSAPI_GLOBAL_DAILY_LIMIT

# تولید SECRET_KEY تصادفی (Python)
python -c "import secrets; print(secrets.token_hex(32))"

# اجرای اپ با محیط production
ENV=production python main.py
```

---

*این مستند به‌صورت خودکار از کلاس‌های `BaseSettings` کد تولید شده است. اگر متغیری را در کد اضافه/حذف کردید، این فایل را به‌روز کنید.*
