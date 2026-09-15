# 🧱 core/ — زیرساخت مرکزی پلتفرم

> لایه بنیادی سیستم که همه بخش‌ها (API، خدمات، jobs، providers) روی آن ساخته شده‌اند.
> **همراه: پیکربندی، امنیت، لاگینگ، Rate Limit، Retry، Event Bus، Health Check، اعتبارسنجی، DI و Database Session.**

---

## 📑 فهرست مطالب

- [نقش و جایگاه](#نقش-و-جایگاه)
- [معماری و اجزا](#معماری-و-اجزا)
- [پیکربندی (Settings)](#پیکربندی-settings)
- [مدیریت دیتابیس](#مدیریت-دیتابیس)
- [امنیت](#امنیت)
- [لاگینگ](#لاگینگ)
- [Rate Limiting](#rate-limiting)
- [Retry و Resilience](#retry-و-resilience)
- [Event Bus](#event-bus)
- [Health Check](#health-check)
- [اعتبارسنجی (Validation)](#اعتبارسنجی-validation)
- [تولید شناسه (IDs)](#تولید-شناسه-ids)
- [مسیرها و فایل‌ها (Paths)](#مسیرها-و-فایل‌ها-paths)
- [معماری‌های تکراری (تمیزکاری)](#معماریهای-تکراری-تمیزکاری)
- [تست‌ها](#تستها)
- [اشکالات رفع‌شده](#اشکالات-رفعشده)

---

## نقش و جایگاه

```
┌──────────────────────────────────────────────────────┐
│                     Apps / Services / Jobs           │
├──────────────────────────────────────────────────────┤
│   core/  (این پکیج)                                   │
│   config · security · logging · cache · database     │
│   rate_limit · retry · resilience · event_bus        │
│   health · validation · ids · paths · result · enums │
├──────────────────────────────────────────────────────┤
│            PostgreSQL · Redis · Filesystem           │
└──────────────────────────────────────────────────────┘
```

قانون طلایی: **هیچ لایه بالایی نباید مستقیماً با SQL خام یا Redis درگیر شود** — همه از طریق `core` به زیرساخت دسترسی پیدا می‌کنند.

---

## معماری و اجزا

| زیرپکیج | مسئولیت | فایل‌های کلیدی |
|----------|----------|----------------|
| `config/` | پیکربندی مرکزی (Pydantic Settings) | `__init__.py` |
| `security/` | هش رمز، JWT، API key، رمزنگاری | `hashing.py`, `tokens.py`, `secrets.py` |
| `logging/` | لاگ ساخت‌یافته JSON با پشتیبانی یونیکد | `__init__.py` |
| `database.py` | Engine و Session ناهمزمان + fallback | `database.py` |
| `cache.py` | کش Redis با fallback تهی | `cache.py` |
| `rate_limit/` | محدودیت نرخ Sliding Window | `limiter.py`, `tokens.py`, `adaptive.py` |
| `retry/` | سیاست و دکوراتور Retry | `__init__.py`, `backoff.py` |
| `resilience/` | Circuit Breaker، Failover، Degradation | `circuit_breaker.py`, `fallback.py` |
| `event_bus.py` | Event Bus هم‌زمان | `event_bus.py`, `events.py` |
| `health/` | سنجه‌های سلامت سیستم | `__init__.py`, `system_health.py` |
| `validation/` | اعتبارسنجی ورودی (نماد، تاریخ، عدد) | `__init__.py`, `symbols.py` |
| `ids/` | تولید شناسه‌های یکتا | `__init__.py` |
| `paths.py` | مدیریت امن مسیرهای فایل (ضد path traversal) | `paths.py` |
| `result.py` / `typing/` | Result Type (Ok/Err) و PaginatedResult | `result.py`, `typing/result.py` |
| `exceptions/` | سلسله‌مراتب خطاهای سفارشی | `__init__.py`, `api.py` |
| `concurrency/` | Worker Pool، Queue، Semaphore | `worker_pool.py`, `queues.py` |
| `dependency_injection/` | DI Container | `container.py` |
| `time/` | زمان، بازار، تقویم معاملاتی | `market_sessions.py`, `calendar_utils.py` |

---

## پیکربندی (Settings)

تنها منبع حقیقت: `core/config/__init__.py` → کلاس `Settings` (نمونه سراسری `settings`).

```python
from core.config import settings

print(settings.database_url_async)
print(settings.is_production)
```

### مهم‌ترین متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://market:market@localhost:5432/market` | اتصال دیتابیس |
| `REDIS_URL` | `redis://localhost:6379/0` | کش و صف |
| `SECRET_KEY` | `change-me-in-production` | کلید JWT / رمزنگاری |
| `ENV` | `development` | محیط اجرا (`production` باعث اعمال `validate_production()`) |
| `CORS_ORIGINS` | `["*"]` | منشأهای مجاز |
| `API_PREFIX` | `/api/v1` | پیشوند API |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | عمر توکن دسترسی |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | عمر توکن رفرش |
| `JWT_ALGORITHM` | `HS256` | الگوریتم JWT |
| `DATABASE_POOL_SIZE` | `20` | سایز pool |
| `DATABASE_MAX_OVERFLOW` | `30` | مازاد pool |
| `DATABASE_AUTO_CREATE_TABLES` | `false` | ساخت خودکار جداول (فقط dev/SQLite) |

> ⚠️ در production حتماً `validate_production()` صدا زده شود؛ با `SECRET_KEY` پیش‌فرض، `CORS_ORIGINS=["*"]` یا SQLite **برنامه متوقف می‌شود**.

---

## مدیریت دیتابیس

فایل `core/database.py`:

- `init_database()` — ساخت engine ناهمزمان (asyncpg) با pooling تنظیم‌پذیر.
- `get_session()` — Dependency سریع FastAPI با commit/rollback خودکار:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session
```

- `close_database()` — بستن امن engine در shutdown.
- `database_auto_create_tables` — ساخت جداول با `Base.metadata.create_all` فقط وقتی صریحاً فعال باشد؛ **production باید از Alembic استفاده کند**.

> 🔧 **اصلاح اعمال‌شده:** قبلاً `_create_all_tables()` روی PostgreSQL هم اجرا می‌شد (در تضاد با تاریخچه مهاجرت Alembic). حالا فقط با فلگ `database_auto_create_tables=true` اجرا می‌شود.

---

## امنیت

### هش رمز (`security/hashing.py`)
- الگوریتم **PBKDF2-HMAC-SHA256** با salt تصادفی.
- فرمت جدید hash: `{rounds}${salt}${hash}` — تعداد دورها داخل hash ذخیره می‌شود.
- **سازگاری عقب‌رو (Backward Compat)**: hashهای قدیمی با فرمت `{salt}${hash}` هم درست verify می‌شوند.

```python
from core.security import hash_password, verify_password

h = hash_password("my-secret")          # "100000$<salt>$<hash>"
assert verify_password("my-secret", h)
assert not verify_password("wrong", h)
```

> 🔧 **اصلاح اعمال‌شده:** قبلاً `verify_password` تعداد دورها را سخت‌کد کرده بود (۱۰۰ هزار) و روی hash خراب کرش می‌کرد؛ حالا دورها از hash خوانده می‌شود و با `try/except` امن است.

### توکن (JWT)
- `create_access_token` / `create_refresh_token` / `decode_*`.
- طول عمر و الگوریتم از `settings` خوانده می‌شوند.
- خطاهای انقضا/نامعتبر بودن به `AuthenticationError` تبدیل می‌شوند.

### رمزنگاری
- `encrypt_data` / `decrypt_data` با Fernet و کلید مشتق از `SECRET_KEY`.

> 🔧 **اصلاح اعمال‌شده:** `core/security/__init__.py` قبلاً همه توابع را **دوباره** پیاده‌سازی کرده بود (دو نسخه‌ی واگرا). حالا فقط facade است و از submodule های کانونی re-export می‌کند.

---

## لاگینگ

- `get_logger(name)` → لاگر با نام ماژول.
- فرمت پیش‌فرض **JSON** (سازگار با جمع‌آوری‌کننده‌های لاگ).
- `SafeStreamHandler` — روی ویندوز با متن فارسی/ایموجی کرش نمی‌کند.
- پشتیبانی از `log_file` برای خروجی فایل.

```python
from core.logging import get_logger
logger = get_logger(__name__)
logger.info("Quote saved: %s", symbol)
```

> 🔧 **اصلاح اعمال‌شده:** `core/logging/setup.py` یک پیاده‌سازی تکراری بدون `SafeStreamHandler` داشت؛ حالا به نسخه کانونی re-export می‌شود.

---

## Rate Limiting

- **Sliding Window** بر اساس `(rate, burst, window_seconds)`.
- `allow(key)` — بررسی غیرمسدودکننده.
- `acquire(key)` — مسدودکننده (برای throttle).
- `wrap(key, rate)` — دکوراتور محدودیت نرخ.

> 🔧 **اصلاح اعمال‌شده:** قبلاً `wrap()` با `burst=1` پیش‌فرض، هر کلید را به ۱ درخواست/۶۰ثانیه محدود می‌کرد! حالا `burst` از نرخ در دقیقه محاسبه می‌شود.

---

## Retry و Resilience

### Retry (`core/retry/`)
- کلاس `RetryPolicy(max_retries, base_delay, max_delay, backoff_factor, jitter)`.
- دکوراتور `@retry(...)` — برای توابع async و sync.

```python
from core.retry import retry

@retry(max_retries=3, base_delay=0.5, jitter=True)
async def fetch_quote(symbol: str): ...
```

- سیاست‌های آماده: `FastRetryPolicy`، `DefaultRetryPolicy`، `AggressiveRetryPolicy`، `NoRetryPolicy`.
- استراتژی‌های backoff: `ExponentialBackoff`، `LinearBackoff`، `FixedBackoff`، `FibonacciBackoff`.

> 🔧 **اصلاح اعمال‌شده:** سیستم Retry تکراری (`policies.py`/`wrappers.py`) با پیاده‌سازی `__init__.py` هم‌سو شد — حالا `policies.py` فقط re-export سیاست‌های کانونی است.

### Resilience (`core/resilience/`)
- `CircuitBreaker` — قطع خودکار بعد از N خطا با recovery timeout.
- `Fallback`، `Failover`، `Degradation`، `IncidentPolicy`.

---

## Event Bus

- اشتراک و انتشار رویدادهای دامنه (`DomainEvent`).

```python
from core.events import DomainEvent, MarketEvents
from core.event_bus import event_bus

async def on_quote(event: DomainEvent):
    ...

event_bus.subscribe(MarketEvents.QUOTE_UPDATED, on_quote)
await event_bus.publish(DomainEvent(event_type=MarketEvents.QUOTE_UPDATED, data={...}))
```

> 🔧 **اصلاح اعمال‌شده:** خطای یک handler دیگر بقیه را متوقف نمی‌کند (هر handler ایزوله است) و `unsubscribe` روی handler غایب کرش نمی‌کند.

---

## Health Check

```python
from core.health import get_health_registry

registry = get_health_registry()
registry.register("db", check_db_health)
statuses = await registry.run_all()
```

- `HealthStatus` با `status`، `message`، `details`، `duration_ms`.
- مناسب برای endpoints های `/health`, `/health/ready`, `/health/live`.

---

## اعتبارسنجی (Validation)

- `validate_required`, `validate_length`, `validate_range`, `validate_positive`…
- `validate_symbol` / `validate_isin` / `validate_ticker` — برای نمادهای بورس ایران و ISIN.
- `validate_email` / `validate_mobile` — الگوی شماره موبایل ایران (`09xxxxxxxxx`).
- کلاس زنجیره‌ای `Validator` برای جمع‌آوری چند خطا.

> 🔧 **اصلاح اعمال‌شده:** توابع تکراری `validate_symbol`/`validate_isin` در `validation/symbols.py` حذف و به نسخه کانونی re-export شدند.

---

## تولید شناسه (IDs)

```python
from core.ids import new_id, new_uuid, new_snowflake_id, id_from_timestamp

new_id("fund")        # "fund_<24hex>"
new_snowflake_id()    # شناسه سورتمه‌ای عددی برای ایندکس‌دهی
```

---

## مسیرها و فایل‌ها (Paths)

- `safe_resolve(base, user_path)` — جلوگیری از **Path Traversal** (چک `relative_to`).
- `sanitize_path_component`, `validate_safe_path`.
- `data_path()`, `models_path()`, `logs_path()`, `reports_path()`, `temp_path()`.

---

## معماری‌های تکراری (تمیزکاری)

| مشکل | وضعیت |
|------|-------|
| `core/security/__init__.py` دو نسخه‌ی تکراری از هش/توکن | ✅ رفع — حالا facade |
| `core/retry/policies.py` + `wrappers.py` سیستم Retry جدا | ✅ رفع — re-export کانونی |
| `core/logging/setup.py` پیاده‌سازی تکراری | ✅ رفع — re-export کانونی |
| `core/validation/symbols.py` توابع تکراری | ✅ رفع — re-export کانونی |
| فایل‌های config پراکنده (`core/config/*.py`) | 🟡 باقی‌مانده — کلاس `Settings` مرجع است؛ فایل‌های فرعی می‌توانند به‌مرور حذف شوند |

---

## تست‌ها

```bash
pytest tests/unit/core -v
```

| فایل تست | پوشش |
|----------|------|
| `tests/unit/core/test_rate_limiter.py` | Sliding window، burst، استقلال کلیدها |
| `tests/unit/core/test_retry_policy.py` | RetryPolicy، backoff، jitter، دکوراتور |
| `tests/unit/core/test_circuit_breaker.py` | Circuit Breaker |
| `tests/unit/core/test_market_sessions.py` | سشن‌های بازار |
| `tests/unit/core/test_db_utils.py` | تبدیل امن ردیف‌های DB |

---

## اشکالات رفع‌شده

1. **Security تکراری** — `verify_password` بدون مدیریت خطا (کرش روی hash خراب) و دو نسخه‌ی واگرا.
2. **Refresh token سخت‌کد** — `timedelta(days=30)` به‌جای `settings.refresh_token_expire_days`.
3. **`create_all` روی PostgreSQL** — اجرای `Base.metadata.create_all` در تضاد با مهاجرت‌ها → گیت‌شده با فلگ.
4. **لاگینگ تکراری** — نسخه‌ی بدون `SafeStreamHandler` که روی متن فارسی ویندوز کرش می‌کرد.
5. **باگ `wrap()`** — محدودیت ۱/۶۰ثانیه به‌دلیل `burst=1` پیش‌فرض.
6. **Event Bus** — خطای یک handler بقیه را متوقف می‌کرد.
7. **Retry تکراری** — دو سیستم موازی که می‌توانستند واگرا شوند.
8. **Hash rounds** — تعداد دورهای PBKDF2 حالا داخل hash ذخیره و خوانده می‌شود (با سازگاری عقب‌رو).
