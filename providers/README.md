# 🔌 لایه تأمین‌کنندگان داده (Providers)

لایه `providers/` تمام منابع داده خارجی سیستم را یکپارچه می‌کند: بورس تهران (TSETMC)، کدال، اخبار، شاخص‌های کلان، داده‌های تاریخی، ارز/طلا/فلزات/انرژی، وب‌اسکروپینگ و سلامت تأمین‌کنندگان.

معماری بر پایه **الگوی Adapter/Provider** است: هر منبع داده یک `Provider` با رابط یکسان است و بقیه سیستم فقط از طریق این رابط با آن حرف می‌زند.

---

## 🗂️ ساختار

```
providers/
├── base/            ← هسته: BaseProvider, Result, Capabilities, Registry, ParserBase, HttpClient
├── capabilities/    ← ماتریس قابلیت‌ها و انتخاب‌گر تأمین‌کننده
├── realtime/        ← داده لحظه‌ای: TSETMC, TSE, MarketWatch, کارگزاران (آگاه/مفید/فردانما), WebSocket
├── historical/      ← داده تاریخی: TSETMC historical, TSE archive, file_archive, sql_database
├── reference/       ← داده مرجع: instrument_master, codal, alias_manager, manual, tse_reference
├── news/            ← اخبار: داخلی (اقتصادی/بازار/RSS)، خارجی (کالا/ارز/بازار جهانی)، RSS، احساسات
├── macro/           ← شاخص‌های کلان: کالا، انرژی، ارز، طلا، فلزات، بازارهای جهانی
├── codal/           ← پارسر اطلاعیه‌های کدال
├── funds/           ← صندوق‌ها: کلاینت، پارسر، نگاشت
├── health/          ← سلامت تأمین‌کننده: checker, SLA, incidents, score
├── web_scraping/    ← ابزار وب‌اسکروپینگ: browser_pool, captcha_guard, proxy_rotation, robots_policy
├── manual/          ← ورود دستی: quote, codal, news, macro
└── tsetmc/          ← پارسر مشترک TSETMC
```

---

## 🏛️ هسته (base/)

### `BaseProvider` — `providers/base/base_provider.py`

کلاس انتزاعی پایه همه تأمین‌کنندگان:

```python
class BaseProvider(ABC):
    def __init__(self, name: str, config: dict | None = None):
        self.name = name
        self.retry_policy = RetryPolicy(...)          # از core.retry
        self.circuit_breaker = CircuitBreaker(...)    # از core.resilience

    @abstractmethod
    async def fetch(self, **kwargs) -> Result[Any]: ...
    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

    async def safe_fetch(self, **kwargs) -> Result[Any]:  # retry + circuit breaker
```

`safe_fetch()` به‌صورت خودکار **retry با backoff** و **مدارشکن** را اعمال می‌کند.

### `ProviderResult` — `providers/base/result.py`

نتیجه استاندارد همه تأمین‌کنندگان (الگوی Result):

- `success: bool`، `data`، `error: str | None`، `metadata`، `timestamp`
- سازنده‌های `ok(data, **metadata)` و `fail(error, **metadata)`

### `ProviderCapabilities` — `providers/base/capabilities.py`

اعلام قابلیت‌های هر تأمین‌کننده:

```python
caps = ProviderCapabilities("tsetmc", features=["realtime", "history", "orderbook"])
caps.supports("realtime")   # True
caps.enable("news"); caps.disable("history")
```

### `RatePolicy` — `providers/base/rate_policy.py`

سیاست محدودیت نرخ: `requests_per_minute`، `requests_per_hour`، `concurrent_limit`، `retry_on_limit`، `max_retry_wait`، `delay_between_requests`.

### `HttpClient` — `providers/base/http_client.py`

کلاینت HTTP ناهمگام با **اتصال پایدار (connection pooling)**، **semaphore همزمانی**، هدر User-Agent شبیه مرورگر و `follow_redirects`:

```python
async with HttpClient(base_url="https://www.tsetmc.com") as client:
    result = await client.get("/api/Instrument")
    if result.success:
        data = result.value.json()
```

### `HealthStatus` + `HealthCheckRegistry` — `providers/base/health.py`

- `HealthStatus` — وضعیت (healthy/degraded/down/unknown)، پیام، زمان آخرین بررسی، تأخیر ms
- `HealthCheckRegistry` — ثبت/اجرای چک‌ها به‌صورت ناهمگام

### رابط‌های تخصصی (Abstract base classes)

| کلاس | متدها |
|------|-------|
| `RealtimeDataProvider` | `get_quote`, `get_orderbook`, `get_trades`, `subscribe`, `unsubscribe` |
| `HistoricalDataProvider` | `get_historical_data`, `get_daily_summary` |
| `ReferenceDataProvider` | `get_instrument`, `search_instruments`, `get_all_instruments` |
| `NewsProvider` | `fetch_news`, `search_news` (متد `fetch` به `fetch_news` delegate می‌کند) |
| `MacroDataProvider` | `fetch_latest`, `fetch_history` |
| `ManualDataProvider` | `submit`, `validate`, `get_pending` |
| `ParserBase` | `parse`, `validate` |
| `AuthHandler` | `get_headers` (X-API-Key / Bearer)، `get_auth` (basic) |

### `ProviderRegistry` — `providers/base/provider.py`

رجیستری ساده با `register`، `unregister`، `get`، `list` و `health_all()`.

### `ProviderMetadata` + `ProviderRegistryMeta` — `providers/base/registry.py`

متادیتای تأمین‌کنندگان (نسخه، توضیح، برچسب‌ها، وابستگی‌ها) با الگوی **Singleton از طریق metaclass**.

---

## 📡 زیرسیستم‌ها

### realtime/
| زیرسیستم | توضیح |
|----------|-------|
| `tsetmc/` | کلاینت + پارسر + نگاشت + throttling + health برای API عمومی TSETMC |
| `tse/` | نسخه جایگزین TSE |
| `marketwatch/` | نمای زنده بازار |
| `brokerage/` | کارگزاران: `agah_*`، `mofid_*`، `fardanama_*` با auth اختصاصی |
| `websocket/` | اتصال زنده WS: `base_ws_client`، `connection_manager`، `reconnect`، `subscriptions` |

### historical/
| زیرسیستم | توضیح |
|----------|-------|
| `tsetmc_historical/` | تاریخچه رسمی TSETMC |
| `tse_archive/` | آرشیو TSE |
| `file_archive/` | CSV / Excel / JSON با health و throttling |
| `sql_database/` | اتصال به دیتابیس SQL به‌عنوان منبع داده (با `query_builder`) |

### reference/
| زیرسیستم | توضیح |
|----------|-------|
| `instrument_master/` | استاد ابزارها: normalizer، market_classifier، instrument_mapper |
| `codal/` | کلاینت کدال + پارسر صورت مالی (`statement_parser`) + `attachment_extractor` |
| `alias_manager/` | دیکشنری نام مستعار نمادها با `resolver` |
| `manual/` | ایمپورت فایل (`file_importer`) و فرم (`form_parser`) |
| `tse_reference/` | داده مرجع TSE |

### news/
- `domestic/` — اقتصادی، بازار، RSS داخلی
- `foreign/` — کالا، ارز، بازار جهانی
- `rss/` — کلاینت و پارسر RSS عمومی
- `sentiment/` — طبقه‌بندی احساسات: `preprocessor`، `lexicon`، `scoring`، `classifier`

### macro/
| زیرسیستم | توضیح |
|----------|-------|
| `commodities/` | کشاورزی، پتروشیمی، عمده |
| `energy/` | نفت، گاز، برق |
| `fx/` | ارز داخلی و جهانی |
| `gold/` | طلا داخلی و جهانی |
| `metals/` | فلزات گرانبها و صنعتی |
| `global_markets/` | شاخص‌ها و نرخ‌های جهانی |

هر زیرسیستم الگوی ثابت دارد: `client.py`، `parser.py`، `mapping.py`، `health.py`، `throttling.py`، `provider.py`.

### health/
- `health_checker.py` — اجرای چک‌های سلامت
- `provider_health_score.py` — امتیاز سلامت
- `provider_health_manager.py` — مدیریت سلامت
- `provider_sla.py` — SLA
- `provider_incidents.py` — رویدادهای خرابی
- `provider_status_history.py` — تاریخچه وضعیت

### web_scraping/
ابزارهای مقاوم برای اسکرپینگ: `browser_pool` (مدیریت مرورگر)، `captcha_guard`، `proxy_rotation`، `robots_policy`، `html_fetcher`، `scrape_scheduler`.

---

## 🧪 تست‌ها

`tests/unit/providers/`:

```
test_codal_parser.py    test_macro_parser.py
test_manual_provider.py test_news_parser.py
test_tsetmc_parser.py
```

اجرا:

```bash
python -m pytest tests/unit/providers/ -q
```

---

## 🔧 نکات استفاده

1. **همیشه `Result` برگردانید** — هرگز استثنا پرتاب نکنید؛ خطاها در `error` قرار می‌گیرند
2. **از `safe_fetch` استفاده کنید** — retry + مدارشکن به‌صورت خودکار اعمال می‌شود
3. **قابلیت‌ها را اعلام کنید** — تا `capabilities/selectors` بتواند تأمین‌کننده مناسب را انتخاب کند
4. **health چک بنویسید** — هر تأمین‌کننده باید `health()` را پیاده کند
5. **throttling** — هر زیرسیستم `throttling.py` دارد؛ از نرخ مجاز منبع تجاوز نکنید

---

## ✅ رفع‌های فاز ۲

- **`providers/base/http_client.py`** — اتصال پایدار با reuse، semaphore و redirect
- **سازگاری کامل** `NewsProvider.fetch` با `BaseProvider.safe_fetch` (delegate به `fetch_news`)
- تمام رابط‌های انتزاعی پیاده‌سازی‌شده و تست‌های ۵ پارسر اصلی پاس‌اند
