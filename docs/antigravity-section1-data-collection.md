# Antigravity — بخش ۱: لایه جمع‌آوری داده

این سند طراحی و پیاده‌سازی لایه جمع‌آوری داده برای بازار طلای ایران است. دامنه
این بخش فقط دریافت، اعتبارسنجی، نرمال‌سازی، ذخیره‌سازی و پایش داده است؛ تحلیل
ETF، اندیکاتورها و مدل‌های پیش‌بینی در بخش‌های بعدی اضافه می‌شوند.

## ۱. معماری

```text
TSETMC / IME / BrsApi / Nobitex / Wallex / Ramzinex / Global APIs
                         │
                 HttpClient + RateLimiter
                         │
                Retry + Circuit Breaker
                         │
                 RawDataLake (immutable)
                         │
                 ParserRegistry (JSON/CSV)
                         │
              CanonicalMarketTick + Validator
                    ┌────┴────┐
              Redis hot cache  TimescaleDB
                    │             │
              API/WebSocket   history/analytics
```

اصل مهم: payload خام هرگز overwrite نمی‌شود. ابتدا با hash یکتا در lake ذخیره
می‌شود، سپس رکورد نرمال در `market_ticks` نوشته می‌شود. بنابراین هر مقدار
قابل بازبینی و بازپردازش (replay) است.

## ۲. قرارداد داده نرمال

مدل `ingestion/market_data.py:MarketTick` قرارداد داخلی تمام منابع است:

- `source` و `instrument`: فضای نام منبع و نماد (`USDTIRT`, `XAUUSD` یا کد صندوق)
- `observed_at`: زمان اعلام‌شده توسط منبع؛ `received_at`: زمان دریافت سامانه
- `price`، `bid`، `ask`، OHLC، `volume` و `value` از نوع `Decimal`
- `asset_class`: یکی از `gold_etf`, `gold`, `fx`, `crypto`, `global`, `commodity`
- `quality`: `clean`, `suspicious` یا `stale`
- `raw_object_key` و `raw_sha256`: ارجاع به payload خام، نه ذخیره blob در دیتابیس

قیمت‌ها عمداً `Decimal` هستند تا خطای محاسبات اعشاری ریال/تومان وارد نشود.

## ۳. منابع و polling

| منبع | adapter | داده | دوره پیشنهادی |
|---|---|---|---:|
| TSETMC CDN | `ingestion/sources/tsetmc.py` | market watch، معاملات، order book | ۱۵ ثانیه |
| IME | `ingestion/sources/energy.py` | آب‌شده، شمش، سکه و معاملات کالا | ۳۰ ثانیه |
| BrsApi | سرویس‌های موجود `brsapi/` | snapshot، NAV و تاریخچه | طبق سهمیه |
| نوبیتکس | `NobitexSource` | بهترین bid/ask و قیمت USDT/IRT | ۱۵ ثانیه |
| والکس | `WallexSource` | order book USDT/IRT | ۱۵ ثانیه |
| رمزینکس | `RamzinexSource` | order book USDT/IRT | ۱۵ ثانیه |
| جهانی | `ConfiguredMarketSource` | XAU/USD، DXY و FX | ۱–۵ دقیقه |

URL و مسیر صرافی‌ها در adapter قابل پیکربندی هستند؛ پیش از production باید
قرارداد رسمی API هر تأمین‌کننده و محدودیت نرخ آن در محیط staging تأیید شود.

### معیار تصمیم: دلاری یا ریالی

لایه جمع‌آوری هر دو مقدار را نگه می‌دارد و تصمیم‌گیری در موتور سیگنال با
`DecisionBasis` انجام می‌شود:

- **ریالی (`rial`)**: معیار اجرای سفارش در بورس/بازار ایران؛ بازده
  \[
  r_{IRR} = \frac{P_t}{P_0}-1
  \]
  و حد ضرر/هدف مستقیماً بر حسب ریال یا تومان محاسبه می‌شود.
- **دلاری (`dollar`)**: معیار حفظ قدرت خرید؛ ابتدا قیمت به دلار تبدیل می‌شود:
  \[
  P_{USD,t}=\frac{P_{IRR,t}}{FX_{IRR/USD,t}},\qquad
  r_{USD}=\frac{P_{USD,t}}{P_{USD,0}}-1
  \]
- **دوگانه (`dual`)**: حالت پیشنهادی سامانه؛ سفارش با مبنای ریالی صادر می‌شود
  اما اگر جهت `r_IRR` و `r_USD` متضاد باشد، سیگنال به‌جای BUY/SELL با برچسب
  `nominal_only` و confidence کمتر نمایش داده می‌شود.

قاعده عملیاتی پیشنهادی برای معامله‌گر طلا: معاملات کوتاه‌مدت با مبنای ریالی،
ارزیابی سرمایه‌گذاری و مقایسه با طلای جهانی با مبنای دلاری، و حالت `dual` برای
گزارش اصلی داشبورد. نرخ تبدیل ترجیحاً USDT/IRR تجمیع‌شده از چند صرافی است؛
در صورت نبود آن، USD آزاد استفاده می‌شود و منبع/زمان نرخ باید همراه tick ذخیره
شود.

## ۴. محدودسازی نرخ و resilience

`ingestion/http_client.py` برای هر درخواست timeout، connection pool و retry
دارد. پاسخ‌های 408، 425، 429، 5xx با backoff نمایی و jitter تکرار می‌شوند؛
خطاهای دائمی 4xx تکرار نمی‌شوند. هر منبع rate limiter مستقل دارد تا خرابی یا
سهمیه یک منبع روی منبع دیگر اثر نگذارد.

قواعد عملیاتی:

1. timeout اتصال ۳ ثانیه و timeout کل ۳۰ ثانیه.
2. حداکثر سه retry برای polling؛ backfill باید job جدا با بودجه مستقل باشد.
3. پس از پنج خطای متوالی، circuit breaker منبع را باز و health metric را قرمز
   می‌کند؛ پس از ۳۰ ثانیه یک probe انجام می‌شود.
4. payload نامعتبر در dead-letter/lake نگه داشته می‌شود و باعث توقف کل worker
   نمی‌شود.

## ۵. اعتبارسنجی و پاک‌سازی

`ingestion/validation.py:MarketDataValidator` داده را حذف بی‌صدا نمی‌کند:

- `price > 0` شرط رد قطعی است.
- پرش قیمت:
  \[
  jumpPct = \frac{|P_t-P_{t-1}|}{P_{t-1}}
  \]
  اگر `jumpPct > 20%` باشد رکورد `suspicious` می‌شود.
- کهنگی:
  \[
  age = now - observedAt
  \]
  اگر بیشتر از ۲۰ دقیقه باشد `stale` می‌شود.
- spread:
  \[
  spreadPct = \frac{ask-bid}{bid}
  \]
  ask کمتر از bid یا spread بالاتر از ۱۰٪، مشکوک است.

رکورد مشکوک برای تحلیل پسین حفظ می‌شود؛ موتور سیگنال در بخش ۵ فقط رکوردهای
`clean` را مصرف خواهد کرد مگر آن‌که کاربر صراحتاً fallback را فعال کند.

## ۶. کش Redis

`ingestion/cache.py:MarketDataCache` از کلیدهای namespaced استفاده می‌کند:

```text
antigravity:market:quote:{source}:{instrument}
antigravity:market:health:{source}
```

TTL قیمت لحظه‌ای ۱۰–۱۵ ثانیه، TTL نمادها یک ساعت و TTL داده‌های مرجع روزانه
۲۴ ساعت است. در صورت قطع Redis، fallback حافظه‌ای با همان TTL فعال می‌ماند؛
کش منبع حقیقت نیست و هرگز جایگزین TimescaleDB نمی‌شود.

## ۷. اسکیمای TimescaleDB

مهاجرت `migrations/versions/0043_data_collection_layer.py` این جداول را
می‌سازد:

- `market_data_sources`: registry، وضعیت health، دوره polling و آخرین خطا
- `market_ticks`: hypertable با کلید `(source, instrument, observed_at)`
- `market_data_quality_events`: رخدادهای کیفیت برای audit و داشبورد

`market_ticks` به‌صورت chunk روزانه، با indexهای `(instrument, observed_at)` و
`(quality_flag, observed_at)` ساخته می‌شود. در محیط‌هایی که TimescaleDB نصب
نیست، migration باید پس از فعال‌سازی extension اجرا شود؛ داده خام همچنان در
lake قابل نگهداری است.

## ۸. اتصال به Worker موجود

سه adapter صرافی در `ingestion/sources/crypto.py` و parser عمومی در
`ingestion/parser/market_data.py` ثبت شده‌اند. `IngestionEngine` آن‌ها را
در کنار منابع فعلی فعال می‌کند و `StorageLayer.write_market_tick` با upsert
روی کلید زمانی از duplicate جلوگیری می‌کند. برای نمادهای غیر TSE، identity
resolver دور زده می‌شود و فضای نام canonical مستقیماً ذخیره می‌گردد.

## ۹. نمونه .NET 8

نمونه مستقل و قابل build در `examples/Antigravity.DataCollection/` قرار دارد:

```powershell
dotnet run --project examples/Antigravity.DataCollection
```

نمونه شامل `IQuoteConnector`، `NobitexConnector`، مدل `CanonicalMarketTick`,
`PeriodicTimer` و retryهای Polly است. برای production، connectorهای Wallex و
Ramzinex با همان interface اضافه و persistence به repository داخلی متصل شوند.

## ۱۰. استقرار و مشاهده‌پذیری

- worker جدا از API اجرا شود؛ برای هر source یک job idempotent داشته باشید.
- secretها فقط از environment/secret manager خوانده شوند، نه از کد یا lake.
- metricهای ضروری: latency، success/error rate، retry count، circuit state،
  freshness، تعداد `suspicious` و lag بین `observed_at` و `received_at`.
- log ساختاری شامل `source`, `instrument`, `trace_id`, `object_key` و
  `quality_flag` باشد؛ payload کامل در log چاپ نشود.
- alert عملیاتی: نبود داده بیش از ۲ دوره polling، خطای 429، رشد dead-letter و
  نسبت suspicious بالاتر از ۵٪.

## ۱۱. ترتیب اجرای عملیاتی

1. اجرای migrationها (`alembic upgrade head`) روی staging.
2. ثبت sourceها و intervalها در `market_data_sources`.
3. اجرای health check بدون فعال‌کردن write و مقایسه با پاسخ رسمی API.
4. فعال‌سازی یک منبع در هر مرحله و بررسی freshness/quality.
5. فعال‌سازی Redis و replay چند payload خام برای اطمینان از idempotency.
6. پس از تأیید این بخش، طراحی بخش ۲ (ETF Analysis Engine) روی همین قرارداد
   `MarketTick` و جداول تاریخی انجام می‌شود.

## معیار پذیرش بخش ۱

- حداقل ۹۹٪ pollingهای سالم در ساعات بازار بدون توقف worker.
- عدم ثبت قیمت غیرمثبت در `market_ticks`.
- امکان replay payload خام و تولید hash یکسان.
- upsert تکراری بدون duplicate.
- تشخیص stale/jump/spread و ثبت رخداد کیفیت.
- ادامه سرویس با cache-memory در زمان قطعی Redis.
