# 🔗 لایه یکپارچه‌سازی‌ها (Integrations)

لایه `integrations/` شامل اتصالات و سرویس‌های زیرساختی است که بقیه سیستم از آن‌ها استفاده می‌کند: کش، صف پیام، اعلان‌ها، فایل‌سیستم‌ها/آبجکت‌استور، جستجو، مشاهده‌پذیری (Prometheus/OTel)، و ابزارهای سرویس‌های خارجی.

---

## 🗂️ ساختار

```
integrations/
├── cache/            ← کش: MemoryCache, RedisClient, CacheManager, TTLManager, KeyBuilder
├── queue/            ← صف پیام: Broker, Consumer, Publisher, RetryQueue, DeadLetterQueue, Manager
├── notifications/    ← اعلان: Telegram, Email, SMS, Webhook + قالب‌ها
├── filesystems/      ← فایل: LocalStorage, S3CompatibleStorage, PathManager, RetentionManager
├── search/           ← جستجو (Elasticsearch-compatible): IndexClient, QueryClient, DocumentMapper, AliasManager
├── observability/    ← مشاهده‌پذیری: PrometheusExporter, OTelExporter, StructuredLogger, ErrorReporter
├── http_client.py    ← کلاینت HTTP عمومی با retry و connection reuse
├── webhooks.py       ← ارسال وبهوک
├── object_store.py   ← آبجکت‌استور محلی
├── fileshare.py      ← اشتراک فایل
├── secrets.py        ← مدیریت رازها (env)
├── auth.py           ← مدیریت توکن سرویس‌ها
├── broker_api.py     ← API شبیه‌سازی‌شده کارگزار
├── admin_bridge.py   ← پل مدیریت
├── contracts.py      ← رابط‌های انتزاعی (ABC)
└── types.py          ← انواع داده مشترک
```

---

## 🗃️ کش (cache/)

### `MemoryCache` — کش درون‌حافظه‌ای با TTL

```python
from integrations.cache import MemoryCache
cache = MemoryCache(default_ttl=300, max_size=10000)
cache.set("quote:فملی", {...})
cache.get("quote:فملی")          # None بعد از انقضا
cache.get_or_set("key", factory)
cache.purge_expired()            # حذف دستی منقضی‌ها
```

- پیاده‌سازی با `OrderedDict` + `Lock` (thread-safe)
- **Eviction LRU** هنگام رسیدن به `max_size`
- `__contains__`، `__getitem__`، `__setitem__` پشتیبانی می‌شود

### `RedisClient` — کلاینت async Redis

```python
client = RedisClient()
await client.connect()
await client.set("k", {"a": 1}, ttl=60)     # JSON خودکار
val = await client.get("k")
await client.disconnect()
```

- سریال‌سازی JSON خودکار (با `default=str` برای datetime و ...)
- عملیات: get/set/delete/exists/expire/ttl/keys/incr، مجموعه‌ها (sadd/srem/smembers)، publish/clear

### `CacheManager` — مدیر ترکیبی (Redis + fallback محلی)

```python
from integrations.cache.manager import cache_manager
await cache_manager.set("key", value, ttl=300)
await cache_manager.get("key")
```

- اگر Redis در دسترس نباشد به‌صورت خودکار به کش محلی سوییچ می‌کند
- ✅ **رفع فاز ۲:** حالا TTL در fallback محلی هم اعمال می‌شود (قبلاً مقدار تا ابد برمی‌گشت)؛ `set` همیشه fallback را به‌روز می‌کند؛ سریال‌سازی با `default=str`

### `TTLManager` — مدیریت TTL بر اساس دسته

```python
ttl = TTLManager()
ttl.get_ttl("quotes:فملی:1d")      # بر اساس پری‌ست quote → 60
ttl.get_all_presets()
```

### `KeyBuilder` — ساخت کلید کش یکدست

```python
kb = KeyBuilder(prefix="imp")
kb.quote_key("IR1234567890", "1d")   # imp:quotes:IR1234567890:1d
kb.lock_key("job:sync")               # imp:locks:job:sync
```

---

## 📨 صف پیام (queue/)

### `Broker` — صف درون‌حافظه‌ای async

```python
broker = Broker()
await broker.declare_queue("jobs")
await broker.publish("jobs", Message(body={...}))
await broker.consume("jobs", handler)     # handler async
await broker.start()
```

- `Message.serialize()/deserialize()` — JSON با id، routing_key و headers
- هر handler جدا ایزوله است — خطای یکی بقیه را متوقف نمی‌کند

### `Consumer` / `Publisher`

```python
publisher = Publisher(broker)
msg_id = await publisher.publish_json("jobs", {...})
consumer = Consumer(broker, "jobs")
await consumer.register(handler)
```

### `RetryQueue` — retry با backoff نمایی

```python
rq = RetryQueue(broker, max_retries=3, base_delay=5.0)
await rq.schedule(msg)                  # تأخیر نمایی: 5s, 10s, 20s
await rq.process_retries(handler)
```

✅ **رفع فاز ۲:** دو باگ مهم رفع شد:
1. تأخیر backoff واقعاً اعمال می‌شود (قبلاً فقط log می‌شد و پیام فوراً اجرا می‌شد)
2. شمارش retry بر اساس `original_message_id` ثابت می‌ماند (قبلاً هر بار id جدید ساخته می‌شد و سقف `max_retries` هرگز اعمال نمی‌شد)

### `DeadLetterQueue` — صف پیام‌های ناموفق

```python
dlq = DeadLetterQueue(broker)
await dlq.send(msg, reason="handler_error")
await dlq.replay(message_id, target_queue)   # بازپخش
await dlq.list_messages()
```

✅ **رفع فاز ۲:** حالا بدنه کامل پیام اصلی ذخیره می‌شود و `replay` پیام را با محتوای واقعی (و routing_key اصلی) بازپخش می‌کند — قبلاً بدنه همیشه خالی بود.

### `QueueManager` — مدیر ساده handler محلی

---

## 🔔 اعلان‌ها (notifications/)

همه sender ها نتیجه را با الگوی `core.result.Result` برمی‌گردانند:

| کلاس | کانال | نکات |
|------|-------|------|
| `TelegramSender` | تلگرام | `send` (HTML)، `send_photo`، `send_document` (با `validate_safe_path`) |
| `EmailSender` | SMTP | HTML/plain، cc/bcc، `send_alert`، `send_report` |
| `SmsSender` | SMS | `send`، `send_alert` |
| `WebhookSender` | وبهوک | امضای HMAC-SHA256 با `X-Signature`، POST/PUT، `send_event` |
| `NotificationTemplates` | — | قالب‌های متنی و HTML: سیگنال، توصیه، خلاصه بازار، خطا، جدول |

✅ **رفع فاز ۲:** `EmailSender` حالا SMTP (بلوک‌کننده) را با `asyncio.to_thread` در نخ جدا اجرا می‌کند تا event loop بلاک نشود — قبلاً در `async def send` به‌صورت همگام اجرا می‌شد.

```python
from integrations.notifications import TelegramSender, EmailSender
tg = TelegramSender()
result = await tg.send("<b>Alert</b>")
if result.success: ...
```

---

## 💾 فایل‌سیستم و آبجکت‌استور (filesystems/)

### `LocalStorage` — ذخیره‌سازی محلی

```python
from integrations.filesystems import LocalStorage
storage = LocalStorage("./data")
await storage.write("quotes/فملی.json", data)
await storage.read("quotes/فملی.json")
await storage.delete(...) / exists / list / move / copy / size
async for f in storage.iter_files(pattern="quotes/*"): ...
```

- ✅ متد `stat()` اضافه شد (برمی‌گرداند `{"size", "modified"}`) — مورد نیاز `RetentionManager`
- همه مسیرها با `safe_resolve` از خروج از base جلوگیری می‌کنند (traversal-safe)

### `S3CompatibleStorage` — ذخیره‌سازی سازگار با S3

```python
storage = S3CompatibleStorage(endpoint_url="https://minio.local", ...)
await storage.write("key", data)
await storage.read("key") / delete / exists / list / stat / iter_files
```

- پیکربندی از `STORAGE_*` (StorageSettings): `STORAGE_S3_ENDPOINT_URL`، `STORAGE_S3_ACCESS_KEY`، `STORAGE_S3_SECRET_KEY`، `STORAGE_S3_BUCKET`، `STORAGE_S3_REGION`
- ✅ **رفع فاز ۲:** `stat()` و `iter_files()` اضافه شدند تا با `RetentionManager` سازگار باشد (قبلاً فقط با LocalStorage کار می‌کرد)

### `PathManager` — مدیریت مسیرهای منظم

```python
pm = PathManager("./data", use_date_prefix=True)
pm.quote_path("IR1234", "1d")        # data/2026/07/31/quotes/IR1234/1d
pm.report_path("daily", "summary", "csv")
pm.temp_path(".tmp") / model_path / log_path / backup_path
```

### `RetentionManager` — سیاست نگهداری

```python
rm = RetentionManager(storage)
rm.add_rule("quotes/*", retention_days=30)
deleted = await rm.apply_rules()     # {pattern: count}
```

✅ **رفع فاز ۲:** حالا با `Result` حاصل از `stat()` کار می‌کند و با هر دو storage (محلی و S3) سازگار است.

---

## 🔎 جستجو (search/)

کلاینت‌های سازگار با **Elasticsearch API**:

| کلاس | عملیات |
|------|--------|
| `IndexClient` | `create_index`، `delete_index`، `index_exists`، `index_document`، `bulk_index` (NDJSON)، `update_document`، `delete_document`، `get_mapping` |
| `QueryClient` | `search`، `search_by_field`، `search_by_text` (multi_match)، `suggest` (completion)، `count`، `scroll` |
| `DocumentMapper` | تبدیل موجودیت‌های دامنه (Instrument، Quote، Signal، Recommendation، Indicator) به سند جستجو و بالعکس |
| `AliasManager` | `add_alias`، `remove_alias`، `swap_alias` (blue/green)، `alias_exists` |

```python
from integrations.search import IndexClient, QueryClient
idx = IndexClient(base_url="http://localhost:9200")
q = QueryClient()
await idx.index_document("instruments", "IR1234", doc)
res = await q.search_by_text("instruments", "فملی")
```

---

## 📈 مشاهده‌پذیری (observability/)

### `PrometheusExporter` — متریک‌های Prometheus

```python
exporter = PrometheusExporter()
exporter.inc("requests_total", {"endpoint": "/quotes"})
exporter.set_gauge("pool_size", 10)
with exporter.observe_duration("fetch_ms") as t:
    await fetch()
text = exporter.export_text()    # فرمت متن Prometheus
```

- counter / gauge / histogram
- ✅ **رفع فاز ۲:** خروجی histogram حالا فرمت استاندارد دارد: باکت‌های ثابت (`le`)، `_bucket{le="+Inf"}`، `_count`، `_sum` — و label ها به درستی بعد از `_bucket` قرار می‌گیرند (قبلاً خروجی نامعتبر بود)

### `OTelExporter` — OpenTelemetry

```python
otel = OTelExporter(service_name="market")
otel.setup()                       # خواندن settings.otlp_endpoint
span = otel.start_span("fetch")
span.set_attribute("symbol", "فملی")
await otel.shutdown()
```

✅ **رفع فاز ۲:** tracer حالا **بعد از** نصب provider ساخته می‌شود — قبلاً در `__init__` ساخته می‌شد و به provider پیش‌فرض no-op می‌چسبید، بنابراین همه span ها بی‌صدا حذف می‌شدند.

### `StructuredLogger` — لاگ JSON ساختاریافته

```python
log = StructuredLogger("market")
log.info("job_finished", job="sync", items=120, duration_ms=500)
```

### `ErrorReporter` — گزارش خطا

```python
reporter = ErrorReporter(environment="production")
reporter.report(exc, context={"job": "sync"})
reporter.report_message("rate limit hit", level="warning")
reporter.add_handler(my_handler)
```

---

## 🧰 ابزارهای عمومی

| کلاس | توضیح |
|------|-------|
| `HttpClient` | کلاینت HTTP با retry، **connection reuse** و context manager |
| `WebhookClient` | ارسال وبهوک با `close()` |
| `ObjectStore` | آبجکت‌استور محلی با `safe_resolve` |
| `FileShare` | اشتراک فایل محلی |
| `SecretsManager` | خواندن رازها از env (`get`، `get_required`) |
| `AuthManager` | نگهداری توکن سرویس‌ها و هدر `Authorization` |
| `BrokerAPI` | شبیه‌سازی سفارش کارگزار (برای توسعه بدون اتصال واقعی) |
| `AdminBridge` | اکشن‌های مدیریتی |

---

## 🧪 تست‌ها

بخش‌های مربوطه:

```bash
python -m pytest tests/unit/test_cache_manager.py -q
python -m pytest tests/unit/test_rate_limit_middleware.py -q
python -m pytest tests/unit/core/test_circuit_breaker.py -q
```

---

## 🔒 نکات امنیتی

- همه مسیرها با `core.paths.safe_resolve` / `validate_safe_path` بررسی می‌شوند (جلوگیری از path traversal)
- `WebhookSender` امضای HMAC با `X-Signature` دارد
- `SecretsManager.get_required` در صورت نبود راز خطا می‌دهد
- `RetentionManager` فقط فایل‌های قدیمی‌تر از بازه را حذف می‌کند
