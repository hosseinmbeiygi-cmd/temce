# 📊 یکپارچه‌سازی BrsApi.ir

یکپارچه‌سازی کامل با **BrsApi.ir** — ارائه‌دهنده داده جامع بازار سرمایه ایران. این ماژول داده‌های لحظه‌ای و تاریخی TSETMC، IME، کالاهای جهانی، رمزارز و اطلاعیه‌های کدال را با رعایت دقیق محدودیت‌های نرخ دریافت می‌کند.

---

## 🗂️ معماری لایه‌ای

```
brsapi/
├── config.py          ← تنظیمات env، تعریف endpoint ها و نرخ‌های مجاز
├── client.py          ← کلاینت HTTP با retry، مدارشکن، rate-limit و کش
├── rate_limiter.py    ← محدودکننده نرخ ۳ لایه (روزانه / ۵دقیقه / سطل هر دسته)
├── constants.py       ← فهرست نمادهای صندوق ایرانی (فال‌بک)
├── parsers/           ← تبدیل JSON خام به dict ساختاریافته
│   ├── tsetmc.py      ├── ime.py      ├── commodity.py
│   ├── crypto.py      └── codal.py
├── models/            ← مدل‌های ORM (پیشوند brsapi_)
│   ├── base.py        ├── tsetmc.py   ├── ime.py  ├── commodity.py
│   ├── crypto.py      └── codal.py
├── repositories/      ← دسترسی داده: SyncLog, RawPayload, BulkUpsert
├── services/          ← ارکستراسیون sync
│   ├── sync_service.py            ├── query_service.py
│   └── history_fetch_service.py
├── jobs/              ← تعریف جاب‌های APScheduler
├── migrations/        ← مهاجرت‌های مستقل BrsApi
└── tests/             ← تست‌های یکپارچه‌سازی
```

---

## ⚙️ پیکربندی (`config.py`)

### تنظیمات محیطی (`BrsApiSettings` — پیشوند `BRSAPI_`)

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `BRSAPI_API_KEY` | `""` | کلید API |
| `BRSAPI_BASE_URL` | `https://api.brsapi.ir` | آدرس پایه |
| `BRSAPI_REQUEST_TIMEOUT` | `30.0` | تایم‌اوت هر درخواست |
| `BRSAPI_MAX_RETRIES` | `3` | تعداد retry |
| `BRSAPI_RETRY_BACKOFF_BASE` | `1.5` | پایه backoff |
| `BRSAPI_RETRY_MAX_DELAY` | `60.0` | حداکثر تأخیر |
| `BRSAPI_CONNECTION_POOL_SIZE` | `10` | اندازه pool اتصال |
| `BRSAPI_VERIFY_SSL` | `true` | اعتبارسنجی TLS (برای گواهی نامعتبر `false`) |
| `BRSAPI_PROXY_URL` | — | پروکسی (اختیاری) |
| `BRSAPI_RAW_PAYLOAD_SINK_ENABLED` | `false` | ذخیره پاسخ‌های خام برای ممیزی |
| `BRSAPI_MAX_RAW_PAYLOAD_AGE_DAYS` | `30` | نگهداری پاسخ‌های خام |
| `BRSAPI_GLOBAL_DAILY_LIMIT` | `10000` | سقف روزانه همه endpoint ها |
| `BRSAPI_GLOBAL_5MIN_LIMIT` | `500` | سقف پنج‌دقیقه‌ای (پکیج AIO) |
| `BRSAPI_RATE_LIMIT_TSETMC` | `30` | نرخ دسته tsetmc (در دقیقه) |
| `BRSAPI_RATE_LIMIT_CODAL` | `12` | نرخ دسته codal |
| `BRSAPI_RATE_LIMIT_IME` | `12` | نرخ دسته ime |
| `BRSAPI_RATE_LIMIT_COMMODITY` | `1` | نرخ دسته commodity |
| `BRSAPI_RATE_LIMIT_CRYPTO` | `1` | نرخ دسته crypto |
| `BRSAPI_ONLY_DURING_MARKET_HOURS` | `true` | فقط در ساعات بازار |
| `BRSAPI_MARKET_OPEN` / `MARKET_CLOSE` | `08:30` / `15:30` | ساعات بازار |

### تعریف endpoint ها (`BrsApiEndpoints`)

نرخ‌ها دقیقاً بر اساس مستندات رسمی BrsApi تنظیم شده‌اند:

| Endpoint | نرخ رسمی | معادل در دقیقه |
|----------|----------|----------------|
| `ALL_SYMBOLS` | 2/100s | 1 |
| `SYMBOL_DETAIL` | 3/10s | 18 |
| `INDEX` | 2/100s | 1 |
| `NAV` | 1/10s | 6 |
| `OPTION` | 3/10s | 18 |
| `TRANSACTION` | 2/10s | 12 |
| `HISTORY_PRICE` / `HISTORY_REALLEGAL` | 4/10s | 24 |
| `CANDLESTICK` | 2/10s | 12 |
| `SHAREHOLDER` | 2/10s | 12 |
| `CODAL_ANNOUNCEMENT` | 2/10s | 12 |
| `IME_FUTURES` / `IME_OPTION` | 2/10s | 12 |
| `IME_CERTIFICATE` / `IME_FUND` | 1/10s | 6 |
| `IME_PHYSICAL` | 3/10s | 18 |
| `COMMODITY` / `CRYPTOCURRENCY` | 3/1500s | 1 |
| `GOLD_COIN` / `CURRENCY` / `GOLD_CURRENCY` | — | 1 |
| `GOLD_CURRENCY_PRO` | — | 6 |
| `GOLD_COIN_HISTORY` / `CURRENCY_HISTORY` | — | 1 |

هر `EndpointConfig` شامل: `path`، `category`، `rate_limit_per_minute`، `sync_interval_seconds`، `required_params`، `optional_params`، `default_params`، `ttl_cache_seconds`.

> ⚠️ `GOLD_24H` و `CURRENCY_24H` حذف شده‌اند (از ~ژوئن ۲۰۲۶ خطای 404 می‌دهند) — داده‌های آن‌ها از `Gold_Currency.php` در دسترس است. همین‌طور `Coin.php`/`Currency.php` قدیمی deprecated شده‌اند.

---

## 🌐 کلاینت (`client.py`)

```python
from brsapi import BrsApiClient, BrsApiEndpoints
from brsapi.client import get_client, close_client

client = await get_client()                 # singleton lazy + start
result = await client.fetch(BrsApiEndpoints.ALL_SYMBOLS)
if result.success:
    print(result.value.data)                # JSON پارس‌شده
await close_client()
```

ویژگی‌ها:

- **Connection pooling** با `httpx.AsyncClient` و `Limits`
- **Retry با backoff** برای timeout و خطاهای شبکه + احترام به هدر `Retry-After` برای 429/503
- **مدارشکن** (`CircuitBreaker`) مستقل برای هر مسیر endpoint
- **Rate limiting** سه‌لایه از `rate_limiter`
- **حل مشکل پروکسی رجیستری ویندوز** — `core.fix_network.fix_network()` در import
- **پشتیبانی proxy** از طریق transport mount (سازگار با httpx ≥ 0.28)
- **پاسخ استاندارد** `BrsApiResponse` با `is_empty` برای تشخیص پاسخ‌های بدون داده

---

## ⏱️ محدودکننده نرخ (`rate_limiter.py`)

سه لایه برای **هر** درخواست اعمال می‌شود:

1. **سقف روزانه** — ۱۰,۰۰۰ درخواست/روز (زمان تهران، ریست نیمه‌شب)
2. **پنجره ۵ دقیقه‌ای** — حداکثر ۵۰۰ درخواست در هر پنجره لغزان
3. **سطل توکن (Token Bucket)** — مستقل برای هر دسته (`tsetmc`، `codal`, ...)

```python
from brsapi.rate_limiter import get_rate_limiter
limiter = get_rate_limiter()
await limiter.acquire("tsetmc", endpoint="/Tsetmc/AllSymbols.php")
limiter.status()   # گزارش لحظه‌ای برای داشبورد
```

- **اعلان آستانه**: هنگام رسیدن به ۸۰٪، ۹۰٪، ۹۵٪ و ۱۰۰٪ مصرف روزانه، callback ثبت‌شده صدا زده می‌شود (`on_threshold`)
- همه اندازه‌گیری‌ها با `time.monotonic()` انجام می‌شود (بدون وابستگی به event loop جاری)

> ✅ **رفع فاز ۲:** قبل از این `asyncio.get_event_loop().time()` استفاده می‌شد که هنگام ساخت کلاینت (خارج از حلقه رویداد) در Python جدید `RuntimeError` می‌داد.

---

## 🧩 پارسرها (`parsers/`)

| پارسر | endpoint ها | خروجی |
|-------|-------------|-------|
| `TsetmcParser` | AllSymbols، Symbol، Index، Nav، Option، Transaction، History (price + real/legal)، Candlestick، Shareholder | dict/list آماده ORM با `raw_json` |
| `ImeParser` | Futures، Option (call/put)، Certificate، Fund، Physical | قراردادهای آتی، اختیار دوطرفه، گواهی، صندوق کالایی |
| `CommodityParser` | Market/Commodity | قیمت کالاهای جهانی |
| `CryptoParser` | Market/Cryptocurrency | قیمت رمزارزها |
| `GoldCoinParser` / `CurrencyParser` | Coin/Currency/History | طلا، سکه، ارز |
| `GoldCurrencyProParser` | Gold_Currency_Pro | قیمت‌های Pro + تاریخچه ۲۴ساعته/روزانه |
| `CodalParser` | Announcement | اطلاعیه‌های کدال |

الگو: `parse_*` به‌صورت `classmethod`، مقاوم در برابر داده نامعتبر (برمی‌گرداند `[]`/`None` و log می‌کند)، و مقادیر را با `_int`/`_float` تمیز می‌کند.

---

## 🗄️ مدل‌ها (`models/`)

جدول‌های اصلی (`tsetmc.py`):

| مدل | جدول | کلید |
|-----|------|------|
| `SymbolSnapshotModel` | `brsapi_symbol_snapshots` | یکتا `(symbol, fetched_at)` — dedup خودکار upsert |
| `SymbolDetailModel` | `brsapi_symbol_details` | PK `ins_id` (آخرین نسخه نگهداری می‌شود) |
| `IndexValueModel` | `brsapi_index_values` | هر اسنپ‌شات شاخص |
| `NavRecordModel` | `brsapi_nav_records` | NAV صدور/ابطال |
| `OptionSnapshotModel` | `brsapi_option_snapshots` | قرارداد اختیار |
| `IntradayTradeModel` | `brsapi_intraday_trades` | تیک‌های معاملات |
| `HistoricalDailyModel` | `brsapi_historical_daily` | تاریخچه روزانه (پارتیشن `date`) |
| `HistoricalRealLegalModel` | `brsapi_historical_real_legal` | تفکیک حقیقی/حقوقی |
| `CandlestickModel` | `brsapi_candlesticks` | شمع‌های OHLCV |
| `ShareholderRecordModel` | `brsapi_shareholder_records` | ترکیب سهامداران |

مدل‌های پایه (`base.py`):

- `RawPayloadModel` — پاسخ‌های خام برای ممیزی (اختیاری)
- `SyncLogModel` — لاگ هر sync برای مشاهده‌پذیری و dedup
- `InstrumentRefMixin` — اتصال به جدول `instruments` اصلی

---

## 📚 مخازن (`repositories/`)

- `SyncLogRepository` — ثبت، `last_sync`، `needs_sync`، `count_since` (با `func.count()`)، `get_sync_stats`
- `RawPayloadRepository` — ذخیره/حذف پاسخ‌های خام (پاک‌سازی حجیم با `DELETE`)
- `BulkUpsertRepository` — درج گروهی با `ON CONFLICT DO NOTHING` یا `DO UPDATE`، `truncate`، `count`، `get_latest_by_symbol`

> ✅ **رفع فاز ۲:** `count_since` قبلاً همه ردیف‌ها را بارگذاری می‌کرد (`len(scalars().all())`) — حالا از `func.count()` در SQL استفاده می‌کند. `purge_older_than` قبلاً UTC aware را با ستون naive مقایسه می‌کرد — حالا همگام با `datetime.now()` مدل است و با یک `DELETE` حجیم انجام می‌شود.

---

## ⚙️ سرویس‌ها (`services/`)

- `sync_service.py` — ارکستراسیون اصلی: `sync(endpoint, parser, model_class, ...)` با لاگ SyncReport، پارس، upsert گروهی و مدیریت خطا
- `query_service.py` — کوئری‌های خواندنی (قیمت‌ها، شاخص‌ها، NAV)
- `history_fetch_service.py` — واکشی تاریخچه با throttling و backfill

---

## ⏰ جاب‌ها (`jobs/registry.py`)

`BrsApiSyncJob` + `BrsApiJobRegistry`:

- تعریف جاب‌های cron: `brsapi_all_symbols` (هر ۲ دقیقه)، `brsapi_index`، `brsapi_options`، `brsapi_ime_*`، `brsapi_gold_currency`، `brsapi_codal` و ...
- جاب‌های نیازمند نماد (`history_*`) به‌صورت on-demand با `_get_pro_symbols(session, max_symbols)` فعال می‌شوند
- `toggle_job()` — فعال/غیرفعال کردن جاب در حال اجرا
- `run_job_now()` — اجرای فوری
- `register_with_apscheduler()` — ثبت خودکار در APScheduler

> ✅ **رفع فاز ۲:** `_get_pro_symbols` حالا حالت دوگانه دارد — هم با AsyncSession (کوئری `SELECT DISTINCT`) و هم با لیست نمادهای از پیش‌بارگذاری‌شده کار می‌کند (برای تست/استفاده‌های خاص).

---

## 🧪 تست‌ها

```bash
python -m pytest tests/test_brsapi_manual.py tests/test_brsapi_job_registry.py -q
python -m pytest tests/unit/services/test_fund_service_update_brsapi.py -q
python brsapi/tests/test_tsetmc_symbols_integration.py   # تست زنده (نیاز به کلید API + DB)
```

---

## 🚀 شروع سریع

```bash
# 1. تنظیم env
echo "BRSAPI_API_KEY=your_key" >> .env

# 2. مهاجرت جداول BrsApi
alembic upgrade head   # یا migration مستقل brsapi/migrations

# 3. استفاده مستقیم
python - <<'EOF'
import asyncio
from brsapi.client import get_client, close_client

async def main():
    client = await get_client()
    res = await client.fetch(client.__class__.BrsApiEndpoints.ALL_SYMBOLS) if hasattr(client.__class__, "BrsApiEndpoints") else None
    print("client ready:", client.is_ready)
    await close_client()

asyncio.run(main())
EOF
```

> 📌 برای استفاده از `fetch(endpoint)`، `BrsApiEndpoints` را از `brsapi.config` ایمپورت کنید.
