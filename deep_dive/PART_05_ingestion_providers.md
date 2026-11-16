# قسمت ۰۵ — دریافت داده، فراهمکنندگان و بودجه/سهمیه BrsApi

| | |
|---|---|
| **مبنای اندازهگیری** | کامیت `73a6c52d` (`fix(monitoring): use settings.job_queue_dead_letter…`) — جهش **بزرگ** از مبنای قسمت ۰۴ (`bfd1e78d`): شمارش این قسمت روی HEAD جدید انجام شده است. |
| **وضعیت worktree** | **۱۰۴ فایل تغییریافته** (Dirty)؛ دو فایل محوری این قسمت مستقیماً در worktree اصلاح شدهاند: `ingestion/config.py` و `brsapi/config.py`. هر دو تنها حامل اصلاح **CFG-06** (مسیر `.env` مخزن‑محور) هستند — جزئیات در بند ۶. |
| **تعهد** | فقط این فایل Markdown ساخته شد. **هیچ فایل کد، پیکربندی یا تستی تغییر نکرد.** |
| **زبان** | فارسی |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقط‌خواندنی)

| درخت | فایل `.py` | مجموع خط | زیرشاخه |
|---|---:|---:|---:|
| `ingestion/` | ۵۹ | ~۷٬۰۶۵ | ۱۳ |
| `providers/` | ۲۵۱ | ~۱۲٬۰۰۰ | ۴۰ |
| `brsapi/` | ۷۸ | ~۱۶٬۷۲۵ | ۲۰ |

> عدد «۲۵۱» در نقشه راه قسمت ۰۵ همان **تعداد فایلهای `.py`** در `providers/` است (مطابقت دقیق). توجه: `providers/` شامل یک کپی داخل `.agents/skills/ai-research-explore/...` نیز هست که در شمارش بالا نیامده (مربوط به یک مهارت جستجوی مستقل است، نه پشته داده سیستم).

ماژولهای کانونی بررسیشده:
- `ingestion/`: `config.py`, `main.py`, `scheduler.py`, `worker.py`, `http_client.py`, `retry.py`, `cache.py`, `lake/__init__.py`, `market_data.py`, `sources/base.py`, `storage/dedup.py`, `db/session.py`, `quotas.py`, `brs_api_client.py`.
- `brsapi/`: `config.py`, `budget.py`.
- `providers/`: `README.md`, `macro_sources/base.py` (بهعلاوه نمونهگیری از الگوی Adapter در `macro/`, `historical/`, `manual/`).

---

## ۲ — ردیابی جریان اجرا (از ورودی تا خروجی)

### ۲‑الف — مسیر دریافت درونی (`ingestion/`)
```
run_ingestion()                         ingestion/main.py:149
  └─ IngestionConfig()  → (INGESTION_ prefix, .env مخزنمحور)   config.py:33
  └─ DatabaseSession(config.db_dsn)     db/session.py:9   (CFG-18 اینجا حل شد)
  └─ aioredis.from_url(config.redis_url)
  └─ IngestionEngine.start()            main.py:58
       ├─ HttpClient.start()            http_client.py:32  (aiohttp + TCPConnector)
       ├─ RawDataLake.start()           lake/__init__.py:21 (گارد fail-closed CFG-17)
       ├─ ParserRegistry.register(×۷)
       ├─ DeduplicationEngine(redis, dedup_window_minutes)   storage/dedup.py:12
       ├─ StorageLayer(db) / IdentityResolver(db)
       ├─ IngestionWorker(...)          worker.py:22
       ├─ _register_sources()          main.py:111  (فقط آنهایی که در enabled_sourcesاند)
       └─ MarketScheduler.start()       scheduler.py:24  → on_tick(worker.ingest_all)
            └─ _run_loop()             scheduler.py:37  (فقط داخل ساعت بازار)
                 └─ ingest_all()       worker.py:51
                      └─ برای هر منبع → _ingest_source()   worker.py:107
                           fetch → dedup.is_duplicate → lake.store_raw → parser.parse
                           → identity.resolve → storage.write_* → dedup.mark_seen
```

### ۲‑ب — مسیر سهمیه/بودجه BrsApi
```
BrsApiIngestionClient.fetch_all_symbols()        brs_api_client.py:109
  └─ super().fetch(ALL_SYMBOLS)                  (BrsApiClient در brsapi/client.py)
       └─ budget_governor.acquire(category, …)  budget.py:449  (پیش‌بررسی fail-fast)
            ├─ _is_blocked_now()  → BudgetBlockedError (کول‌داون ۳۰۲)
            ├─ _daily_used()  (شمارنده پایدار Redis/فایل/حافظه)
            ├─ _gate_daily_usage()  (warn ۸۵٪ / soft-reject ۹۵٪ برای غیر‑critical)
            ├─ _reserve_daily()  (Lua اتمیک در Redis)
            ├─ _enforce_5min()  (پنجره لغزان ۵ دقیقه‌ای Redis)
            └─ _limiter.acquire()  (token bucket درون‌فرآیندی)
       └─ TsetmcParser.parse_all_symbols(payload)
```

### ۲‑ج — پشته `providers/` (موازی)
الگوی Adapter/Provider یکسان: `BaseProvider` (ABC) + `safe_fetch()` (retry + circuit breaker) + `ProviderResult` (Result pattern) + `ProviderCapabilities` + `RatePolicy` + `HttpClient` + `HealthCheckRegistry`. هر زیرسیستم (`macro/`, `historical/`, `reference/`, `news/`, `web_scraping/`, `manual/`) الگوی ثابت `client/parser/mapping/health/throttling/provider` را دارد. این پشته **موازی با `ingestion/`** است و کد مشترکی ندارند (بند ING-12).

---

## ۳ — سیاست شکست (برای هر گام)

| گام | سیاست شکست | محل |
|---|---|---|
| دریافت HTTP | retry روی ۴۰۸/۴۲۵/۴۲۹/۵۰۰/۵۰۲/۵۰۳/۵۰۴ + خطاهای اتصال؛ سایر ۴xx **فوری** | `retry.py:31-70` |
| مدارشکن | پس از ۵ شکست متوالی باز میشود، ۳۰s بازیابی | `retry.py:75-118` |
| کش Redis | **fail-open**: خطای Redis → cache miss، روند ادامه مییابد | `cache.py:24-35` |
| کش داده‑دریاچه (lake) | گارد fail-closed روی اعتبار MinIO در تولید | `lake/__init__.py:24-31` |
| خواندن دوباره از lake | **fail-silent**: همه استثناء → `None` | `lake/__init__.py:100-102` |
| نوشتن رخداد | استثناء → علامت «نوشته‌نشده»، تلاش در tick بعد | `worker.py:196-202` |
| بودجه BrsApi | **fail-fast**: پایان بودجه روزانه / کول‌داون ۳۰۲ → رد درخواست | `budget.py:395-403,468-491` |
| بدون Redis (بودجه) | تخریب به «فایل» سپس «حافظه»؛ شمارنده در راه‌اندازی مجدد **ریست میشود** | `budget.py:205-218` |
| زمانبند | خطای callback → لاگ + ادامه (fail-open) | `scheduler.py:40-44` |

---

## ۴ — یافتهها (شناسه `ING-01` … `ING-14`)

| شناسه | شدت | خط دقیق | عنوان | اثر عملی | جهت اصلاح |
|---|---|---|---|---|---|
| **ING-01** | 🔴 بالا | `config.py:42,47,48,74,75` | **پنج فیلد پیکربندی مرده** | `worker_count`، `rate_limit_calls`، `rate_limit_period`، `replay_chunk_size`، `replay_concurrency` هیچکجا خوانده نمیشوند (تأییدشده با grep: فقط در `config.py` تعریف شدهاند). دریافت عملاً تک‌رشتهای و ترتیبی اجرا میشود، مستقل از `worker_count`. پیچه‌های گمراه‌کننده. | یا این فیلدها را واقعاً به جریان متصل کن (asyncio.gather روی منابع/نمادها) یا حذفشان کن تا قرارداد پیکربندی صادق بماند. |
| **ING-02** | 🟡 متوسط | `http_client.py:106-128` + `sources/*.py` | **سه لایه نرخ‑محدودسازی با مقادیر پراکنده، بدون منبع واحد** | `HttpClient.fetch` **هیچ‌گاه** `.acquire()` فراخوانی نمیکند؛ لایه عمومی نرخ‌محدود نمیشود. در عوض هر `sources/*.py` یک `RateLimiter` **با مقادیر سخت‑کد شده** میسازد (`max_calls=10/period=1.0` یا `5/1.0`). این لایه درون‌فرآیندی و **بین رپلیکا به اشتراک نیست** → با `replicas: 2` (EX-05) نرخ مؤثر به upstream دوبرابر میشود و وضعیت مدارشکن هم مشترک نیست. | یک `RateLimiter` پیکربندی‌محور و مشترک ( Redis‑backed) بساز؛ مقادیر سخت‌کد را از منابع حذف کن. |
| **ING-03** | 🔴 بالا | `scheduler.py:37-47` | **نبود نگهبان بازورود (re-entrancy)** | `_run_loop` هیچ قفلی ندارد. با `scheduler_interval_seconds=15`، اگر یک چرخه `ingest_all` (مثلاً `tsetmc_trades` که روی **همه** شناسه‌های نماد ترتیبی حلقه میزند) بیش از ۱۵s طول بکشد، tick بعدی **قبل از پایان قبلی** شروع میشود → چرخههای همپوشان، دریافت تکراری، و نوشتهای همزمان روی lake/DB. | قفل `asyncio.Lock` دور بدنه tick، یا پرچم «skip if still running». |
| **ING-04** | 🟡 متوسط | `worker.py:206-210` | **نشت Invariant تکرارزدایی → از دست رفتن ساکت داده** | `mark_seen` وقتی `payload_written_all` درست باشد اجرا میشود؛ این پرچم پیش‌فرض `True` است و فقط روی استثناء نوشتن `False` میشود. وقتی `storage` یا `identity` برابر `None` باشد، بلوک نوشتن (خط ۱۷۷/۱۹۵) کلاً رد میشود → `written` صفر میماند، پرچم `True` میماند → پیلود **علی‌رغم نوشته‌نشدن** علامت «دیده‌شده» میخورد؛ در tick بعد نادیده گرفته میشود → **از دست رفتن دائمی ساکت**. | `payload_written_all` را به «تلاش واقعی نوشتن» گره بزن؛ اگر storage/identity نبود، اصلاً `mark_seen` را فراخوانی نکن. |
| **ING-05** | 🟡 متوسط | `worker.py:148-170` | **یک پیلود نامعتبر کل منبع را در آن tick متوقف میکند** | `ParseError` در خط ۱۶۲ **re-raise** میشود → در `ingest_all` (خط ۸۷) به `results[name] = -1` میرسد. اما در `_ingest_source`، این raise حلقه پیلودهای باقیمانده آن منبع را برای **همین tick** قطع میکند؛ منبع با -1 علامت میخورد حتی اگر ۹/۱۰ پیلود موفق بوده باشند. | روی خطای parse از `continue` استفاده کن تا بقیه پیلودها پردازش شوند؛ فقط در سطح منبع شکست را گزارش کن. |
| **ING-06** | 🔴 بالا | `quotas.py:177-201` | **تشخیص drift سهمیه نادرست → توصیه اصلاح خطرناک** | `assess_active_profile` سهمیه زیر‑محدوده دریافت (`five_min_limit=300`) را با **سقف کل پلتفرم** (`BRSAPI_GLOBAL_5MIN_LIMIT=1000`) مقایسه میکند و همیشه «drift» گزارش میدهد؛ سپس در `recommended_env` پیشنهاد میکند `BRSAPI_GLOBAL_5MIN_LIMIT=300` ست شود — که کل پلتفرم را به ۳۰۰/۵min محدود میکند (نه فقط دریافت). رفع اشتباهی که میتواند حادثه بسازد. | تشخیص را فقط علیه سقف محلی governor دریافت مقایسه کن؛ سهمیه ۳۰۰ یک «رزرو» از ۱۰٬۰۰۰ کل است، نه جایگزین سقف جهانی. |
| **ING-07** | 🔴 بالا | `budget.py:205-218,280-324,548-560` | **پایداری بودجه کاملاً به Redis وابسته است** | بدون Redis (یا وقتی مسیر فایل fallback در کانتینر غیرقابل‌نوشتن باشد) backend بی‌سروصدا به «حافظه» تخریب میشود و شمارنده‌ها در راه‌اندازی مجدد **ریست میشوند** — دقیقاً همان شرطی که در گذشته کلید را مسدود کرد. در backend غیر‑Redis، درخواستهای **رد‑شده** هم شمارش میشوند (over-count) → پلتفرم زودتر از موعد درخواستهای موجه را متوقف میکند. | وابستگی به Redis را صریح کن (یا هشدار صادر کن)؛ فایل fallback را روی_VOLUME قابل‌نوشتن قرار بده؛ over-count را با release اتمیک اصلاح کن. |
| **ING-08** | 🟡 متوسط | `config.py:435,442-443` + `quotas.py:65-69` | **سقف طرح BrsApi در مستندات متناقض** | docstring خط ۴۳۵ میگوید «AIO: ۵۰۰ درخواست/۵ دقیقه»، اما `global_5min_limit` پیش‌فرض **۱۰۰۰** است؛ روزانه «۱۰٬۰۰۰» ادعا شده. اگر سقف واقعی provider ۵۰۰ باشد، اجازه ۱۰۰۰ توسط governor **۲×** حد واقعی است → ریسک مسدودیت دوباره (همان کلاس باگ اصلی). | عدد دقیق ۵‑دقیقه و روزانه را از قرارداد تثبیت کن و در یک تست assert کن. |
| **ING-09** | 🟡 متوسط | `lake/__init__.py:88-102` | **fail-silent در خواندن دوباره** | `get_raw` همه استثناءها را میبلعد و `None` برمیگرداند؛ تفاوت بین «شیء موجود نیست» (۴۰۴) و «خطای دسترسی/شبکه» از بین میرود → مکانیزم replay نمیتواند تشخیص دهد. | ۴۰۴/NoSuchKey را از سایر خطاها تفکیک کن؛ فقط ۴۰۴ را به‌عنوان «یافت نشد» بازگردان. |
| **ING-10** | 🟢 کم | `cache.py:19,16` | **حافظه درون‌فرآیندی نامحدود + نام عجیب** | `_memory` دیکت بدون سقف رشد میکند (اگرچه با TTL منقضی میشود، اما پیش‌گیری نمیشود)؛ namespace سخت‌کد `"antigravity:market"` نامی قدیمی/گمراه‌کننده است. | LRU با سقف؛ نام namespace را به مقدار پیکربندی منتقل کن. |
| **ING-11** | 🟢 کم | `scheduler.py:52` + `config.py:412` | **محاسبه دستی ساعت تهران به‌جای zoneinfo** | `_in_market_hours` و brsapi از `timedelta(hours=3, minutes=30)` سخت‌کد استفاده میکنند به‌جای `ZoneInfo(config.market_timezone)`. ایران DST را ۱۴۰۱ لغو کرد (اکنون درست)، اما اگر کانتینر TZ اشتباه داشته باشد یا کشور DST را برگرداند، دروازه ساعت بازار لغزش پیدا میکند. | از `zoneinfo.ZoneInfo(self._config.market_timezone)` استفاده کن. |
| **ING-12** | 🟡 متوسط | `providers/` (۲۵۱) در مقابل `ingestion/` (۵۹) | **دو پشته دریافت موازی، بدون کد مشترک** | `ingestion/` و `providers/` هر دو TSETMC/طلا/FX/کلان/کدال را پیاده میکنند اما **هیچ کدی به اشتراک نمیگذارند**: دو HTTP client، دو rate limiter، دو چارچوب health. نگهداری دوبرابر و ریسک ناسازگاری معنایی نرخ/retry بین دو پشته. | یک پشته را به عنوان منبع واحد تثبیت کن؛ دیگری را به آن refactor کن یا حذف کن. |
| **ING-13** | 🟢 کم | `main.py:136-146` | **نمونه‌سازی مجدد ReplayEngine در هر دسترسی** | ویژگی `replay` در هر بار خواندن یک `ReplayEngine`/`StorageLayer`/`IdentityResolver` **تازه** میسازد → اگر بارها فراخوانی شود، نشت منابع. | نمونه را یک‌بار بساز و کش کن (lazy singleton روی self). |
| **ING-14** | 🟢 کم | `budget.py:622-655` | **وضعیت block (۳۰۲) در backend حافظه بین راه‌اندازی مجدد از دست میرود** | `report_302` وضعیت کول‌داون را فقط در Redis/فایل پایدار میکند؛ در backend حافظه، کرش بلافاصله بعد از یک ۳۰۲ اجازه retry فوری میدهد → احتمالاً ۳۰۲ دوباره و مسدودیت. (دفاع در عمق؛ زیرمجموعه ING-07) | در حالت memory هم یک کول‌داون محلی حداقل نگه دار. |

---

## ۵ — نقاط قوت تأییدشده (برای توازن حسابرسی)

1. **تجرید تمیز مدل داده:** `MarketTick` (`market_data.py`) از `Decimal` برای قیمتها و نرمال‌سازی UTC استفاده میکند؛ `DataSource` ABC (`sources/base.py`) با `SourcePayload`/`FetchResult` (cursor/has_more) قرارداد یکسانی دارد.
2. **طراحی idempotent دریافت:** `mark_seen` فقط پس از نوشتن **موفق کل** پیلود (خط ۲۰۶)؛ شکست نوشت جزئی → تلاش در tick بعد. درست (تا زمان نقص ING-04).
3. **بودجه reuse-first:** `quotas.py` صریحاً اعلام میکند شمارنده دوم نمیسازد و به `BrsApiBudgetGovernor` اشتراکی متصل میشود؛ `IngestionQuotaTracker` فقط‌خواندنی است و fail-fast میکند.
4. **گارد fail-closed MinIO (CFG-17) زنده است:** `lake/__init__.py:24-31` وقتی `is_production` و کلید پیش‌فرض باشد، `RuntimeError` میدهد — پس از اصلاح CFG-01 (`ENV: production`) اکنون فعال است.
5. **CFG-18 واقعاً حل شد:** `db/session.py:14` پسوند `postgresql+asyncpg://` را قبل از `asyncpg.create_pool()` میتراشد (تأییدشده در کد فعلی).
6. **طراحی رزرو اتمیک بودجه:** Lua `check-and-reserve` در Redis (budget.py:65-75) اجازه نمیدهد درخواست رد‑شده شمارش شود (در مسیر Redis).
7. **بازیابی تدریج بودجه:** `report_ok` کول‌داون را پس از پاسخ ۲۰۰ و گذشت زمان پاک میکند؛ سلسله‌مراتب warn ۸۵٪ / soft-reject ۹۵٪ برای حفظ رکورد روزِ بازار طراحی شده.

---

## ۶ — تصحیح گزارش اصلی و بازخوانی یافتههای پیشین

### ۶‑الف — بازخوانی وضعیت یافتههای قسمت ۰۳ در برابر HEAD `73a6c52d` / worktree
| یافته | وضعیت در این قسمت | مدرک |
|---|---|---|
| **CFG-06** | ✅ **اصلاح شد** (در worktree، هنوز کامیت‌نشده) | هر دو `ingestion/config.py` و `brsapi/config.py` اکنون `_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"` دارند؛ diff worktree دقیقاً همین ۳ خط است. |
| **CFG-17** | ✅ **زنده و فعال** | `lake/__init__.py:24` به `settings.is_production` وابسته است؛ پس از `d6962d0a` (`ENV: production`) اکنون اجرا میشود. |
| **CFG-18** | ✅ **حل شد (کد)** | `db/session.py:14` تراش پسوند driver قبل از `asyncpg`. |
| **CFG-01** (ENV=production) | ✅ بسته‌شده توسط `d6962d0a` (از قسمت ۰۳) | خارج از محدوده این قسمت، اما پیش‌نیاز فعال‌شدن CFG-17 است. |

### ۶‑ب — هشدار روش (live-sync)
 HEAD از `bfd1e78d` (مبنای قسمت ۰۴) به **`73a6c52d`** جهش کرده — یعنی **تیم بین قسمت ۰۴ و ۰۵ دهها کامیت دیگر زده است** (از جمله اصلاح monitoring در خودِ `73a6c52d`). worktree نیز با ۱۰۴ فایل dirty ناپایدار است؛ دو فایل محوری این قسمت (`ingestion/config.py`, `brsapi/config.py`) مستقیماً در worktree تغییر یافتهاند — هر دو تنها حامل CFG-06. یافتههای ING-* روی **نسخه دیسکی** (worktree) اندازهگیری شدهاند؛ اگر این تغییرات کامیت نشوند، بخشی از ING-* ممکن است در HEAD کامیت‌شده کمی متفاوت باشد. قسمتهای ۰۱–۰۴ بر مبنای قدیمی معتبرند؛ از این قسمت به بعد مبنا `73a6c52d` است.

---

## ۷ — مرز روش

- **بدون اجرا:** هیچ تستی اجرا نشد، سرور بوت نشد، به DB/Redis زنده وصل نشد، و هیچ درخواست شبکه‌ای صادر نشد.
- **بدون ادعای زمان‌اجرا:** رفتار نرخ‌محدودسازی و بودجه فقط از خواندن کد و AST استنتاج شد؛ عدد واقعی درخواستهای روزانه و وضعیت Redis در محیط اجرا راستی‌آزمایی نشد.
- **پوشش انتخابی `providers/`:** با ۲۵۱ فایل، کل پشته خوانده نشد؛ الگوی Adapter از `README.md` + `macro_sources/base.py` + نمونهگیری از چند زیرسیستم استخراج شد. ادعای «موازی بودن با `ingestion/`» بر اساس همپوشانی دامنه (TSETMC/طلا/FX/کلان/کدال) و نبود import متقابل است.

---

## پیوست — به‌روزرسانی ماتریس ریسک تجمیعی (افزوده‌شده به README)

خوشههای تازه از این قسمت:
- **L — پیکربندی دریافت مرده / نرخ‌محدودسازی پراکنده** (`ING-01`, `ING-02`, `ING-08`): پیچههای گمراه + سه لایه نرخ بدون منبع واحد + سقف طرح متناقض.
- **M — همزمانی زمانبند/دریافت** (`ING-03`, `ING-04`, `ING-05`): بازورود نگهبان‌ندارد + نشت dedup + توقف منبع با یک پیلود.
- **N — پایداری بودجه BrsApi** (`ING-06`, `ING-07`, `ING-09`, `ING-14`): وابستگی کامل به Redis + تشخیص drift غلط + fail-silent در lake.
- **O — تکرار ساختاری پشته داده** (`ING-12`, `ING-10`, `ING-11`, `ING-13`): دو پشته موازی + کش نامحدود + ساعت سخت‌کد + نشت replay.

ترتیب بستن پیشنهادی (بدون تغییر کد، صرفاً اولویت): **H → B → N → M → L → O → …**

---

*فقط‌خواندنی نسبت به کد · ایستا · بدون اجرای تست کامل، بدون اتصال به DB/Redis زنده، بدون بوت سرور.*
