# فهرست ۱۰۰۰ ایراد پروژه temce — با محل دقیق

این گزارش بر پایه کد موجود در مخزن ساخته شده و هر ردیف به **فایل:خط واقعی** اشاره می‌کند؛
متن کد نقل‌شده از همان خط خوانده شده است، نه از حافظه یا گزارش قبلی.

- تعداد ردیف: **1000**
- توزیع شدت: P0=39 · P1=324 · P2=292 · P3=345
- منبع هر ردیف: pattern=451 · ruff=291 · دستی/تأییدشده=181 · eslint=77

## راهنمای شدت و وضعیت

| شدت | معنا |
|---|---|
| P0 | مسیر داده/سرویس را می‌شکند یا علت مستقیم کهنه‌بودن داده است |
| P1 | ریسک بالا: خطای بی‌صدا، داده ناقص، مصرف سهمیه، رفتار نادرست |
| P2 | نقص کیفیت/پایداری که در شرایط خاص اثر می‌گذارد |
| P3 | بدهی فنی و خوانایی |

| وضعیت | معنا |
|---|---|
| تأییدشده | با خواندن کد در همین نسخه تأیید شده |
| ابزار (ruff/eslint) | خروجی ابزار با فایل:خط دقیق |
| الگو (regex) | الگوی مشخص در خط مشخص؛ نیازمند قضاوت انسانی |
| نیازمند آزمون | رفتار وابسته به محیط/داده است |

## زنجیره علت کهنه‌شدن داده (به ترتیب اثر)

```
منبع (BRSAPI_ENABLED/سهمیه 302)
   └─ همگام‌سازی اجرا نمی‌شود یا شکست می‌خورد (خطای بلعیده‌شده)
        └─ جدول snapshot تازه نمی‌شود؛ خواندن با MAX(id) رکورد قدیمی را «آخرین» می‌بیند
             └─ API پاسخ success=True با داده کهنه می‌دهد (بدون as_of)
                  └─ فرانت isLive را از «تعداد ردیف > 0» می‌سازد → داده قدیمی «زنده» دیده می‌شود
```

## ۱۲ یافته‌ای که باید اول بررسی شوند (به ترتیب همین زنجیره)

**DEP-001** — `Dockerfile:41` — ایمیج اصلی به‌جای FastAPI موتور ingestion را اجرا می‌کند

> CMD ["python", "-m", "ingestion.main"]

اثر: سرویس backend روی پورت 8000 هیچ API‌ای سرو نمی‌کند؛ فرانت‌اند پاسخ نمی‌گیرد. — راه‌حل: برای سرویس backend از Dockerfile.api یا command صریح uvicorn استفاده شود.

**DEP-004** — `docker-compose.yml:120` — کانتکست build فرانت به پوشه‌ای اشاره می‌کند که Dockerfile ندارد

> context: ./frontend

اثر: docker compose build frontend با خطا متوقف می‌شود. — راه‌حل: از dockerfile: ../Dockerfile.frontend با context ریشه، یا افزودن frontend/Dockerfile استفاده شود.

**DEP-005** — `docker-compose.override.yml:6` — override سرویس api را بدون image/build تعریف می‌کند

> api:

اثر: docker compose config با «service api has neither image nor build» شکست می‌خورد. — راه‌حل: سرویس api با build/Dockerfile.api در فایل پایه تعریف شود.

**DEP-003** — `docker-compose.yml:129` — آدرس داخلی Docker به‌عنوان آدرس عمومی API به فرانت تزریق می‌شود

> - NEXT_PUBLIC_API_URL=http://backend:8000

اثر: مرورگر کاربر نمی‌تواند نام backend را resolve کند؛ درخواست‌ها شکست می‌خورند. — راه‌حل: NEXT_PUBLIC_API_URL حذف و مسیر نسبی /api/v1 با rewrite سمت سرور Next استفاده شود.

**FE-006** — `frontend/src/hooks/useMarketData.ts:281` — وجود یک رکورد برای زنده بودن کافی است

> return { data: cells, isLive: cells.length > 0, isError, isLoading };

اثر: داده چند روزه «زنده» نمایش داده می‌شود؛ همان شکایت اصلی کاربر. — راه‌حل: isLive بر اساس سن fetched_at و موفقیت آخرین sync.

**DATA-015** — `brsapi/services/query_service.py:111` — انتخاب «آخرین snapshot» بر اساس MAX(id) است نه fetched_at

> func.max(SymbolSnapshotModel.id).label("max_id"),

اثر: با backfill یا درج نامرتب، رکورد قدیمی‌تر با id بزرگ‌تر به‌عنوان جاری نمایش داده می‌شود. — راه‌حل: استفاده از fetched_at با tie-break روی id (مثل get_latest_snapshots).

**CACHE-004** — `apps/api/endpoints/market.py:283` — پاسخ heatmap فاقد fetched_at هر نماد است

> "board": s.get("board", ""),

اثر: تشخیص «زنده» از «قدیمی» در کل مسیر UI ممکن نیست. — راه‌حل: افزودن fetched_at و age_seconds به هر سلول.

**DATA-012** — `ingestion/config.py:56` — DSN پیش‌فرض ingestion به localhost:5433 اشاره می‌کند

> default="postgresql+asyncpg://postgres:postgres@localhost:5433/marketdb",

اثر: داخل کانتینر localhost وجود ندارد؛ اتصال دیتابیس شکست می‌خورد. — راه‌حل: خواندن DATABASE_URL مشترک یا اجبار INGESTION_DB_DSN در compose.

**DATA-011** — `ingestion/lake/__init__.py:26` — راه‌اندازی ingestion به MinIO با اعتبار پیش‌فرض وابسته است

> or self._config.lake_secret_key == "minioadmin"

اثر: در محیطی که MinIO وجود ندارد (Compose پایه) موتور قبل از دریافت داده متوقف می‌شود. — راه‌حل: MinIO به compose اضافه یا lake اختیاری/محلی شود.

**DATA-008** — `ingestion/worker.py:160` — شمارنده رویدادها حتی وقتی نوشتن در دیتابیس شکست خورده افزایش می‌یابد

> count += len(events)

اثر: گزارش «تعداد رکورد ذخیره‌شده» کاذب است و مشکل داده قدیمی را پنهان می‌کند. — راه‌حل: شمارش فقط پس از write موفق.

**SCH-001** — `apps/api/app.py:852` — هر replica از API یک SchedulerApp می‌سازد

> scheduler_app = SchedulerApp()

اثر: با دو replica، وظایف چند بار ثبت و اجرا می‌شوند. — راه‌حل: زمان‌بند فقط در سرویس scheduler و پشت feature flag.

**SCH-005** — `apps/scheduler/app.py:42` — اگر صف Redis در دسترس نباشد، بی‌صدا به اجرای درون‌فرایندی برمی‌گردد

> "Scheduler could not enqueue %s — falling back to in-process dispatch",

اثر: در محیط چندنمونه‌ای هر replica کار را خودش اجرا می‌کند → اجرای تکراری و مصرف چندبرابر. — راه‌حل: سیاست صریح fail-closed یا قفل اجباری در fallback.

---

## DEP — استقرار، Docker و اتصال سرویس‌ها (22 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 1 | DEP-001 | P0 | `Dockerfile:41` | ایمیج اصلی به‌جای FastAPI موتور ingestion را اجرا می‌کند | سرویس backend روی پورت 8000 هیچ API‌ای سرو نمی‌کند؛ فرانت‌اند پاسخ نمی‌گیرد. → برای سرویس backend از Dockerfile.api یا command صریح uvicorn استفاده شود. | `CMD ["python", "-m", "ingestion.main"]` |
| 2 | DEP-002 | P0 | `docker-compose.yml:39` | سرویس backend روی Dockerfile اصلی (بدون uvicorn) ساخته می‌شود | ترکیب Compose پایه، API را بالا نمی‌آورد. → dockerfile: Dockerfile.api و command uvicorn تنظیم شود. | `dockerfile: Dockerfile` |
| 3 | DEP-003 | P0 | `docker-compose.yml:129` | آدرس داخلی Docker به‌عنوان آدرس عمومی API به فرانت تزریق می‌شود | مرورگر کاربر نمی‌تواند نام backend را resolve کند؛ درخواست‌ها شکست می‌خورند. → NEXT_PUBLIC_API_URL حذف و مسیر نسبی /api/v1 با rewrite سمت سرور Next استفاده شود. | `- NEXT_PUBLIC_API_URL=http://backend:8000` |
| 4 | DEP-004 | P0 | `docker-compose.yml:120` | کانتکست build فرانت به پوشه‌ای اشاره می‌کند که Dockerfile ندارد | docker compose build frontend با خطا متوقف می‌شود. → از dockerfile: ../Dockerfile.frontend با context ریشه، یا افزودن frontend/Dockerfile استفاده شود. | `context: ./frontend` |
| 5 | DEP-005 | P0 | `docker-compose.override.yml:6` | override سرویس api را بدون image/build تعریف می‌کند | docker compose config با «service api has neither image nor build» شکست می‌خورد. → سرویس api با build/Dockerfile.api در فایل پایه تعریف شود. | `api:` |
| 6 | DEP-006 | P0 | `docker-compose.override.yml:31` | سرویس admin فقط در override تعریف شده و در فایل پایه وجود ندارد | ترکیب Compose نامعتبر است؛ admin هرگز بالا نمی‌آید. → سرویس admin با image و build در فایل پایه اضافه شود. | `admin:` |
| 7 | DEP-007 | P0 | `docker-compose.override.yml:42` | سرویس scheduler بدون image/build در override تعریف شده | زمان‌بند مستقل در استقرار Compose اجرا نمی‌شود. → سرویس scheduler با Dockerfile.scheduler در فایل پایه تعریف شود. | `scheduler:` |
| 8 | DEP-008 | P1 | `docker-compose.override.yml:47` | override سرویس postgres را تعریف می‌کند ولی فایل پایه نام سرویس را timescaledb گذاشته | پورت دیتابیس دو بار bind می‌شود یا سرویس اضافی/بی‌استفاده ساخته می‌شود. → نام سرویس‌ها یکسان‌سازی شود (postgres یا timescaledb). | `postgres:` |
| 9 | DEP-009 | P1 | `docker-compose.production.yml:165` | در تولید آدرس API به نام داخلی nginx تنظیم شده است | اگر این متغیر در باندل مرورگر درج شود، مرورگر nginx را resolve نمی‌کند. → مسیر نسبی /api/v1 استفاده شود و پروکسی در همان دامنه بماند. | `NEXT_PUBLIC_API_URL: http://nginx/api/v1` |
| 10 | DEP-010 | P2 | `docker-compose.production.yml:186` | volume درایور مخصوص Swarm/cloudstor دارد | docker compose معمولی نمی‌تواند این volume را بسازد. → برای Compose از درایور local و برای Swarm فایل جدا استفاده شود. | `driver: cloudstor:aws` |
| 11 | DEP-011 | P2 | `docker-compose.production.yml:181` | شبکه observability به‌صورت external تعریف شده و باید از قبل وجود داشته باشد | استقرار روی میزبان تازه با خطای network not found متوقف می‌شود. → شبکه در همان فایل ساخته یا precondition در اسکریپت استقرار بررسی شود. | `observability:` |
| 12 | DEP-012 | P0 | `docker-compose.production.yml:38` | API در تولید دو replica دارد و هر replica زمان‌بند درون‌فرایندی می‌سازد | دو زمان‌بند موازی به‌علاوه سرویس scheduler = سه نقطه اجرای وظایف و مصرف سه‌برابر سهمیه. → زمان‌بندی فقط در سرویس scheduler انجام شود و در API غیرفعال گردد. | `replicas: 2` |
| 13 | DEP-013 | P3 | `docker-compose.yml:1` | کلید version در Compose v2 منسوخ است | هشدار منسوخ‌شدن در هر اجرا. → حذف کلید version. | `version: '3.8'` |
| 14 | DEP-014 | P2 | `docker-compose.yml:5` | ایمیج دیتابیس با تگ latest-pg15 پین نشده | ارتقای ناخواسته ایمیج می‌تواند داده/رفتار را بشکند. → تگ دقیق نسخه + digest پین شود. | `image: timescale/timescaledb:latest-pg15` |
| 15 | DEP-015 | P2 | `docker-compose.yml:40` | container_name ثابت امکان scale کردن سرویس را می‌گیرد | docker compose up --scale backend=N با تعارض نام شکست می‌خورد. → حذف container_name و اتکا به نام سرویس. | `container_name: tse_backend` |
| 16 | DEP-016 | P2 | `docker-compose.yml:45` | backend فقط به شروع Redis (نه سالم بودن آن) وابسته است | در اولین ثانیه‌ها اتصال Redis شکست می‌خورد و قفل/صف بی‌صدا غیرفعال می‌شود. → healthcheck برای redis و condition: service_healthy اضافه شود. | `condition: service_started` |
| 17 | DEP-017 | P2 | `Dockerfile:36` | همه اسکریپت‌های ریشه وارد ایمیج تولید می‌شوند | فایل‌های موقت (z.py، fix_*.py، probe‌ها) در ایمیج اجرایی حاضرند و سطح حمله را بالا می‌برند. → فقط entrypoint‌های لازم کپی شوند. | `COPY *.py ./` |
| 18 | DEP-018 | P2 | `Dockerfile:39` | ایمیج اصلی healthcheck ندارد | Docker/ orchestrator وضعیت سرویس را تشخیص نمی‌دهد. → HEALTHCHECK مشابه Dockerfile.api اضافه شود. | `USER app` |
| 19 | DEP-019 | P2 | `Dockerfile:34` | ایمیج اصلی پوشه‌های reports/storage/tabdeal/app را کپی نمی‌کند | اگر ingestion به این پکیج‌ها import داشته باشد، در کانتینر ImportError رخ می‌دهد. → فهرست COPY با Dockerfile.api یکسان شود. | `COPY services/ ./services/` |
| 20 | DEP-020 | P0 | `Dockerfile.worker:56` | worker image ماژولی را اجرا می‌کند که بلوک `__main__` ندارد؛ کانتینر بلافاصله خارج می‌شود | `apps/worker/app.py` فقط کلاس تعریف می‌کند و هیچ نقطهٔ ورودی ندارد (برخلاف `apps/worker/__main__.py`). با `restart: always` این یعنی حلقهٔ restart و صفر مصرف؛ در حالت queue هیچ job دریافت داده‌ای اجرا نمی‌شود. → CMD را به `python -m apps.worker` (که `__main__.py` را اجرا می‌کند) تغییر دهید یا بلوک `__main__` را به `apps/worker/app.py` اضافه کنید. | `CMD ["python", "-m", "apps.worker.app"]` |
| 21 | DEP-021 | P1 | `ingestion/config.py:31` | تنظیمات ingestion پیشوند `INGESTION_` دارد ولی compose فقط `DATABASE_URL`/`REDIS_URL` می‌دهد | `db_dsn` و `redis_url` به مقدار پیش‌فرض برمی‌گردند (`localhost:5433/marketdb` و `localhost:6379`)؛ یعنی حتی اگر سرویس ingestion درست بالا بیاید، به سرویس‌های Compose وصل نمی‌شود. → تنظیم `INGESTION_DB_DSN`/`INGESTION_REDIS_URL` در سرویس مربوطه یا هم‌نام کردن پیشوند با متغیرهای موجود. | `model_config = {"env_prefix": "INGESTION_", "env_file": ".env", "extra": "ignore"}` |
| 22 | DEP-022 | P1 | `ingestion/db/session.py:15` | DSN با scheme `postgresql+asyncpg` بدون تبدیل به asyncpg داده می‌شود و رد می‌شود | `IngestionConfig.db_dsn` پیش‌فرض `postgresql+asyncpg://…` دارد و validator فقط `str(v)` است. اجرای واقعی: `ClientConfigurationError: invalid DSN: scheme is expected to be either "postgresql" or "postgres", got 'postgresql+asyncpg'`. پس تعیین درست میزبان هم کافی نیست. → حذف `+asyncpg` از DSN پیش‌فرض/مستندات یا تبدیل scheme پیش از `create_pool`. | `self._pool = await asyncpg.create_pool(` |

## DATA — منبع داده، دریافت و همگام‌سازی (174 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 23 | DATA-001 | P0 | `brsapi/config.py:391` | کلید اصلی BrsApi به‌صورت پیش‌فرض فعال است اما در .env.example مستند نشده | اپراتور نمی‌داند کلید توقف وجود دارد؛ در حالت مسدودی سهمیه، خطاهای تکراری تولید می‌شود. → BRSAPI_ENABLED در .env.example با توضیح و پیش‌فرض امن مستند شود. | `enabled: bool = Field(` |
| 24 | DATA-002 | P0 | `brsapi/client.py:216` | در حالت disabled هیچ درخواست زنده‌ای زده نمی‌شود و فقط خطا برمی‌گردد | با BRSAPI_ENABLED=false داده هرگز تازه نمی‌شود؛ API همچنان داده قدیمی می‌دهد. → پایش صریح روی این حالت + نمایش هشدار در UI و health. | `if not brsapi_settings.enabled:` |
| 25 | DATA-003 | P1 | `brsapi/client.py:547` | health check در حالت disabled خطا برمی‌گرداند نه وضعیت degraded | مانیتورینگ بین «سرویس خراب» و «عمداً غیرفعال» تفاوت نمی‌گذارد. → وضعیت DB_ONLY به‌عنوان حالت مشخص در health گزارش شود. | `"error": "BrsApi disabled via BRSAPI_ENABLED=false — DB-only mode",` |
| 26 | DATA-004 | P1 | `brsapi/config.py:432` | سقف روزانه ۴۰۰۰ درخواست با نظرات کد درباره سقف واقعی ۵۰۰۰ هم‌راستا نیست | یا زودتر از موعد متوقف می‌شود یا سهمیه واقعی را رد می‌کند. → سقف بر اساس پلن واقعی در یک منبع واحد تعریف شود. | `global_daily_limit: int = Field(default=4000, ge=1, description="Max requests per day across all endpoints (hard cap — t` |
| 27 | DATA-005 | P1 | `ingestion/main.py:67` | فقط ۷ پارسر ثبت می‌شود در حالی که ۱۲ منبع در همان فایل ثبت می‌شوند | برای ifb/ime_energy/options/futures/codal پارسر وجود ندارد و داده خام بی‌استفاده می‌ماند. → برای هر منبع فعال، پارسر متناظر ثبت یا منبع غیرفعال شود. | `self._parsers.register(TsetmcMarketWatchParser())` |
| 28 | DATA-006 | P1 | `ingestion/main.py:119` | منبع ifb در فهرست منابع هست ولی پارسر آن در رجیستری نیست | پاسخ دریافت و در lake ذخیره می‌شود اما رکوردی در دیتابیس ساخته نمی‌شود. → افزودن پارسر IFB یا حذف منبع از enabled_sources. | `"ifb": IFBSource(self._http),` |
| 29 | DATA-007 | P1 | `ingestion/worker.py:123` | نبودن پارسر فقط warning است و جریان با موفقیت ادامه می‌یابد | دریافت داده بدون ذخیره ساختاریافته، بی‌صدا «موفق» شمرده می‌شود. → شمارش خطا و گزارش شکست در متریک ingestion. | `logger.warning("No parser for source=%s endpoint=%s", payload.source, payload.endpoint)` |
| 30 | DATA-008 | P0 | `ingestion/worker.py:160` | شمارنده رویدادها حتی وقتی نوشتن در دیتابیس شکست خورده افزایش می‌یابد | گزارش «تعداد رکورد ذخیره‌شده» کاذب است و مشکل داده قدیمی را پنهان می‌کند. → شمارش فقط پس از write موفق. | `count += len(events)` |
| 31 | DATA-009 | P0 | `ingestion/worker.py:157` | در except از متغیر تعریف‌نشده instrument_id استفاده می‌شود | NameError داخل except خطای اصلی را می‌پوشاند و مسیر خطا کاملاً مبهم می‌شود. → استفاده از ins_id و ثبت exc_info. | `logger.exception("Failed to write event for %s", instrument_id)` |
| 32 | DATA-010 | P1 | `ingestion/worker.py:141` | نوشتن رویداد به وجود هم‌زمان identity resolver و storage مشروط شده | اگر یکی از این دو مقدار None باشد، هیچ داده‌ای نوشته نمی‌شود ولی ingestion ادامه می‌دهد. → در startup صریحاً fail شود یا حالت بدون DB اعلام گردد. | `if self._identity and self._storage:` |
| 33 | DATA-011 | P0 | `ingestion/lake/__init__.py:26` | راه‌اندازی ingestion به MinIO با اعتبار پیش‌فرض وابسته است | در محیطی که MinIO وجود ندارد (Compose پایه) موتور قبل از دریافت داده متوقف می‌شود. → MinIO به compose اضافه یا lake اختیاری/محلی شود. | `or self._config.lake_secret_key == "minioadmin"` |
| 34 | DATA-012 | P0 | `ingestion/config.py:56` | DSN پیش‌فرض ingestion به localhost:5433 اشاره می‌کند | داخل کانتینر localhost وجود ندارد؛ اتصال دیتابیس شکست می‌خورد. → خواندن DATABASE_URL مشترک یا اجبار INGESTION_DB_DSN در compose. | `default="postgresql+asyncpg://postgres:postgres@localhost:5433/marketdb",` |
| 35 | DATA-013 | P0 | `ingestion/config.py:50` | آدرس lake پیش‌فرض به سرویس minio اشاره می‌کند که در Compose نیست | startup ingestion با خطای اتصال متوقف می‌شود. → سرویس minio اضافه یا مقدار از env اجباری شود. | `lake_endpoint: str = Field(default="http://minio:9000")` |
| 36 | DATA-014 | P1 | `ingestion/config.py:33` | پیش‌فرض enabled_sources همه منابع است، از جمله منابع بدون پارسر | بار اضافی روی منابع و ذخیره داده خام بدون استفاده. → پیش‌فرض فقط منابع دارای پارسر. | `enabled_sources: list[SourceType] = Field(` |
| 37 | DATA-015 | P0 | `brsapi/services/query_service.py:111` | انتخاب «آخرین snapshot» بر اساس MAX(id) است نه fetched_at | با backfill یا درج نامرتب، رکورد قدیمی‌تر با id بزرگ‌تر به‌عنوان جاری نمایش داده می‌شود. → استفاده از fetched_at با tie-break روی id (مثل get_latest_snapshots). | `func.max(SymbolSnapshotModel.id).label("max_id"),` |
| 38 | DATA-016 | P1 | `brsapi/services/query_service.py:50` | پنجره اسکن ثابت ۵۰٬۰۰۰ رکوردی، نمادهای قدیمی‌تر را حذف می‌کند | نمادی که در این پنجره رکورد ندارد بی‌صدا از heatmap حذف می‌شود (نه خطا، نه نشانه). → پنجره بر اساس تعداد چرخه/زمان محاسبه شود و حذف گزارش گردد. | `_SNAPSHOT_SCAN_WINDOW = 50_000` |
| 39 | DATA-017 | P1 | `brsapi/services/query_service.py:82` | شکست JOIN باعث بازگشت بی‌صدا به داده غنی‌نشده می‌شود | کاهش کیفیت داده (eps/pe/sector) بدون هیچ خطای قابل مشاهده. → متریک fallback و هشدار در پاسخ API. | `"get_enriched_snapshots JOIN failed — falling back to simple snapshots",` |
| 40 | DATA-018 | P1 | `brsapi/services/sync_service.py:461` | upsert روی (symbol, fetched_at) با timestamp ثانیه‌ای انجام می‌شود | دو چرخه در یک ثانیه، رکورد دوم را روی اولی می‌نویسد و داده از دست می‌رود. → کلید یکتا با دقت میکروثانیه یا شناسه چرخه. | `conflict_target = ["symbol", "fetched_at"] if on_conflict_update else None` |
| 41 | DATA-019 | P1 | `jobs/definitions/sync_jobs.py:77` | همگام‌سازی quotes هر ۲ دقیقه دو درخواست به سهمیه محدود می‌زند | ۲۱۰ اجرا در روز × ۲ درخواست × ۳ زمان‌بند، بخش بزرگی از سهمیه ۴۰۰۰ را می‌بلعد. → کاهش فرکانس، اجرای تک‌نمونه و شمارش مصرف در متریک. | `class SyncQuotesJob(BaseJob):` |
| 42 | DATA-020 | P2 | `jobs/definitions/sync_jobs.py:33` | خارج از ساعت بازار، job «موفق» گزارش می‌شود بدون انجام کاری | داشبورد تصور می‌کند همگام‌سازی انجام شده؛ در واقع داده ثابت مانده است. → وضعیت skipped صریح در پاسخ و متریک. | `if not is_tehran_market_open():` |
| 43 | DATA-021 | P0 | `ingestion/main.py:121` | منابع options و futures برای هر نماد درخواست می‌زنند اما هیچ پارسری برای آن‌ها ثبت نشده | با ~۱۰۰۰ نماد، دو هزار درخواست در هر tick فقط برای دور ریختن پاسخ مصرف می‌شود و هیچ رکوردی ذخیره نمی‌گردد. → یا پارسر این دو منبع اضافه شود یا از enabled_sources حذف شوند. | `"tsetmc_options": TsetmcOptionSource(self._http),` |
| 44 | DATA-022 | P0 | `ingestion/worker.py:58` | برای منابع trade/orderbook/options/futures هر tick روی همه نمادها حلقه می‌زند | با interval پیش‌فرض ۱۵ ثانیه و ~۱۰۰۰ نماد، هر tick هزاران درخواست HTTP تولید می‌کند؛ صف هرگز تمام نمی‌شود و داده عقب می‌افتد. → round-robin/صف کار با سهمیه per-tick و متریک backlog. | `for ins_id in self._instrument_ids:` |
| 45 | DATA-023 | P1 | `ingestion/sources/tsetmc.py:47` | کش فهرست نمادها هرگز منقضی یا refresh نمی‌شود | نماد جدید/حذف‌شده بعد از اولین دریافت وارد فهرست نمی‌شود؛ تازه‌سازی ساعتی worker بی‌اثر است. → TTL یا force refresh برای فهرست نمادها. | `if self._instruments is not None:` |
| 46 | DATA-024 | P1 | `ingestion/sources/tsetmc.py:57` | شکست دریافت فهرست نمادها فهرست خالی برمی‌گرداند و یک ساعت retry نمی‌شود | worker با فهرست خالی، برای منابع per-instrument هیچ درخواستی نمی‌فرستد و بی‌صدا بی‌کار می‌ماند. → تفکیک خطا از فهرست خالی + retry کوتاه‌تر. | `logger.exception("Failed to fetch instrument list")` |
| 47 | DATA-025 | P1 | `ingestion/worker.py:88` | شکست یک منبع فقط -1 در دیکشنری نتیجه می‌شود و مصرف‌کننده آن را نمی‌بیند | scheduler نتیجه ingest_all را دور می‌ریزد؛ شکست همگام‌سازی هیچ متریک/هشداری ندارد. → ثبت متریک موفقیت/شکست per-source. | `results[name] = -1` |
| 48 | DATA-026 | P1 | `ingestion/worker.py:147` | اگر identity resolver شناسه را پیدا نکند، شناسه خارجی (insCode) به‌عنوان instrument_id نوشته می‌شود | نوشتن در جدول با FK به instruments.id شکست می‌خورد و فقط لاگ می‌شود → رکورد ذخیره نمی‌شود. → در صورت resolve نشدن، رکورد را quarantine/رد و شمارش کن. | `if ins_id:` |
| 49 | DATA-027 | P1 | `ingestion/retry.py:23` | مجموعه خطاهای قابل retry شامل خطاهای اتصال aiohttp نیست | ClientConnectorError/DNS از ConnectionError پایتون ارث نمی‌برد؛ اختلال کوتاه بدون retry یک tick را از بین می‌برد. → افزودن aiohttp.ClientError و حفظ CancelledError. | `retryable_exceptions: tuple[type[Exception], ...] = (` |
| 50 | DATA-028 | P1 | `ingestion/parser/tsetmc_parsers.py:25` | زمان رویداد از لحظه parse گرفته می‌شود، نه لحظه fetch | سن داده و تأخیر منبع قابل محاسبه نیست و replay زمان واقعی را از دست می‌دهد. → پاس دادن fetch_time از payload به parser. | `now = datetime.now(UTC).isoformat()` |
| 51 | DATA-029 | P1 | `ingestion/parser/tsetmc_parsers.py:52` | تبدیل int روی مقدار خام می‌تواند برای یک رکورد خراب exception بدهد | کل parse همان payload دور ریخته می‌شود و همه رکوردهای سالم هم ذخیره نمی‌شوند. → اعتبارسنجی per-record و quarantine. | `"volume": int(rec.get("qTotTran5J", 0)),` |
| 52 | DATA-030 | P2 | `ingestion/parser/tsetmc_parsers.py:163` | خطای تبدیل عدد در _to_decimal بی‌صدا None می‌شود | مقدار نامعتبر از مقدار ناموجود قابل تفکیک نیست؛ کیفیت داده قابل سنجش نیست. → خطای validation با نام فیلد و شمارنده. | `except Exception:` |
| 53 | DATA-031 | P1 | `ingestion/storage/__init__.py:74` | upsert روزانه fetched_at را به‌روزرسانی نمی‌کند | پس از اصلاح داده، زمان آخرین دریافت قدیمی می‌ماند و پایش تازگی گمراه می‌شود. → fetched_at = NOW() در SET. | `ON CONFLICT (instrument_id, trade_date) DO UPDATE SET` |
| 54 | DATA-032 | P1 | `ingestion/storage/__init__.py:19` | ON CONFLICT DO NOTHING بدون کلید یکتای طبیعی هیچ تکراری را حذف نمی‌کند | چون id خودافزا تکراری نمی‌شود، هر polling رکورد جدید می‌سازد و ON CONFLICT هرگز فعال نمی‌شود. → کلید یکتا بر هویت واقعی رکورد. | `ON CONFLICT DO NOTHING` |
| 55 | DATA-033 | P1 | `ingestion/storage/__init__.py:32` | جدول snapshot فقط append می‌شود و upsert ندارد | با هر poll یک ردیف جدید برای هر نماد؛ جدول هم تاریخچه و هم «وضعیت جاری» را قاطی می‌کند. → upsert وضعیت جاری یا partition/retention صریح. | `INSERT INTO market_snapshots (` |
| 56 | DATA-034 | P2 | `ingestion/storage/__init__.py:85` | ستون open از first_price پر می‌شود که قیمت اولین معامله است نه open روزانه | شاخص‌های OHLC روی داده نادرست محاسبه می‌شوند. → نگاشت صریح open از منبع یا NULL. | `data.get("first_price") or data.get("open"),` |
| 57 | DATA-035 | P2 | `ingestion/db/models.py:38` | جدول trade_ticks کلید یکتای طبیعی ندارد | تکرار polling به رکوردهای تکراری و آمار دوباره‌شماری منجر می‌شود. → UniqueConstraint روی (instrument_id, trade_date, ...). | `trade_ticks = sa.Table(` |
| 58 | DATA-036 | P2 | `ingestion/db/models.py:69` | market_snapshots فقط index غیریکتا دارد | هیچ قیدی از درج چند snapshot برای یک نماد در یک چرخه جلوگیری نمی‌کند. → کلید (instrument_id, snapshot_at) یا upsert. | `sa.Index("ix_market_snapshots_instrument", "instrument_id"),` |
| 59 | DATA-037 | P2 | `ingestion/db/models.py:83` | orderbook_events شناسه snapshot/زمان گروهی ندارد | سطوح عمق بازار چند چرخه با هم مخلوط می‌شوند و «عمق فعلی» قابل استخراج مطمئن نیست. → snapshot_id مشترک برای هر fetch. | `sa.Index("ix_orderbook_events_instrument_side", "instrument_id", "side"),` |
| 60 | DATA-038 | P2 | `ingestion/sources/tsetmc.py:106` | منبعی با نام tsetmc_trades در واقع تاریخچه قیمت پایانی روزانه می‌گیرد | نام/معنا ناهماهنگ است؛ مصرف‌کننده ممکن است داده روزانه را با tick اشتباه بگیرد. → تغییر نام منبع یا مستندسازی صریح. | `url = f"{TSETMC_BASE}/ClosingPrice/GetClosingPriceHistory/{ins_id}"` |
| 61 | DATA-039 | P1 | `docs/brsapi-sync-status-report.md:46` | گزارش داخلی تأیید می‌کند دریافت زنده در حالت DB-only متوقف بوده | شاهد تاریخی برای قدیمی شدن داده؛ نیازمند تأیید وضعیت امروز. → بررسی مقدار فعلی و وضعیت سهمیه پیش از هر تغییر. | `\| حالت فعلی پلتفرم \| `BRSAPI_ENABLED=false` (DB-only) — هیچ تماس زندهای زده نمیشود \|` |
| 62 | DATA-040 | P1 | `docs/brsapi-sync-status-report.md:26` | پاسخ 302 به فایل حجیم نشانه اشباع سهمیه بوده است | فعال‌سازی بدون بررسی سهمیه، خطاهای بیشتر تولید می‌کند. → پروب سهمیه قبل از فعال‌سازی. | `KEY -->\|"HTTP 302 → فایل حجیم"\| KS` |
| 63 | DATA-041 | P1 | `brsapi/services/sync_service.py:388` | پاسخ خالی منبع با status=success ثبت می‌شود و این شاخه commit نمی‌کند | لاگ «موفق با صفر داده» ممکن است ذخیره نشود و پاسخ خالی از پاسخ پرمحتوا تفکیک نمی‌گردد. → وضعیت empty جدا، commit یکنواخت در همه خروجی‌ها. | `if brs_resp.is_empty:` |
| 64 | DATA-042 | P1 | `brsapi/services/sync_service.py:429` | خروجی پارسر با نوع غیرمنتظره به لیست خالی تبدیل و «موفق» گزارش می‌شود | تغییر قرارداد منبع یا باگ پارسر به‌جای خطا، موفقیت صفررکورد می‌شود و در پایش دیده نمی‌شود. → نوع غیرمجاز را ParseError بدانید؛ فقط آرایه خالی معتبر status=empty بگیرد. | `# Normalise to list` |
| 65 | DATA-043 | P0 | `brsapi/services/sync_service.py:1280` | سه بخش طلا/ارز/رمزارز در یک session و یک تراکنش ذخیره می‌شوند | خطای بخش سوم باعث rollback بخش‌های اول و دوم (و لاگ‌هایشان) می‌شود؛ گزارش موفق قبلی هم از بین می‌رود. → تراکنش مستقل per-section یا اتمیک کردن کل عملیات با گزارش صریح. | `sections: list[tuple[str, Callable[[Any], Any], type, str, str]] = [` |
| 66 | DATA-044 | P0 | `brsapi/services/sync_service.py:1468` | مسیر Gold_Currency_Pro جدول را قبل از هر اعتبارسنجی کیفیت خالی می‌کند | پاسخ ناقص ولی غیرخالی، جدول را با مجموعه کوچک‌تر جایگزین می‌کند و نمادها از خروجی ناپدید می‌شوند. → staging + اعتبارسنجی حداقل رکورد و سپس تعویض اتمیک. | `await repo.truncate()` |
| 67 | DATA-045 | P1 | `services/quote_service.py:128` | ذخیره دسته‌ای قیمت‌ها، شکست‌های جزئی را موفق گزارش می‌کند | اگر بخشی از نمادها ذخیره نشوند، فراخواننده Result.ok می‌گیرد و داده ناقص را کامل می‌پندارد. → برگرداندن requested/succeeded/failed و وضعیت partial. | `return Result.ok(count)` |
| 68 | DATA-046 | P2 | `services/quote_service.py:87` | دریافت تاریخچه در QuoteService پیاده‌سازی نشده و همیشه fail برمی‌گرداند | در این نسخه هیچ call-site ندارد؛ قابلیت مرده است و اگر روزی وصل شود، تاریخچه خالی می‌ماند. → حذف/غیرفعال‌سازی صریح یا پیاده‌سازی با تست انتها‌به‌انتها. | `async def ingest_historical(` |
| 69 | DATA-047 | P1 | `services/quote_service.py:59` | فیلدهای غایب پاسخ TSETMC به صفر تبدیل می‌شوند | پاسخ ناقص یا تغییرساختار، صفر معتبر تولید می‌کند و قیمت صحیح قبلی را مخدوش می‌کند. → اعتبارسنجی فیلد ضروری و تفکیک None از صفر واقعی. | `price_close=float(data.get("pClosing", 0)),` |
| 70 | DATA-048 | P1 | `ingestion/market_scan_service.py:58` | MarketScanService بدون session_factory فقط لایه hot دارد | اگر session_factory تزریق نشود، warm sink برابر None است و اسکن در دیتابیس پایدار نمی‌شود. → اجبار warm sink در production و نمایش degraded در health. | `self._warm_sink = warm_sink or (` |
| 71 | DATA-049 | P2 | `ingestion/market_scan_service.py:128` | شکست اسکن در scan_once بی‌صدا None برمی‌گرداند | علت شکست (منبع یا persistence) به فراخواننده و مانیتورینگ نمی‌رسد. → تفکیک منبع/خالی/ذخیره‌سازی و ثبت کد خطا. | `if not result.success or result.value is None:` |
| 72 | DATA-050 | P0 | `apps/currency_service/infra/collectors.py:112` | نرخ ارز در شکست منبع، از fixture با jitter تصادفی ساخته می‌شود | قیمت نمایش‌داده‌شده واقعی نیست، اما timestamp تازه می‌گیرد و jitter تغییر ظاهری می‌سازد؛ کاربر آن را زنده می‌پندارد. → فیلد is_fallback/source_status در پاسخ و برچسب صریح «غیرزنده» در UI. | `free = await fetch_tgju_dollar(client) or fixture.free` |
| 73 | DATA-051 | P1 | `apps/currency_service/infra/collectors.py:72` | خطای منبع ارز فقط warning است و به caller ساخت‌یافته منتقل نمی‌شود | لایه بالاتر نمی‌تواند «زنده موفق» را از «fallback» تشخیص دهد. → نتیجه collector = داده + وضعیت + خطای اختیاری. | `logger.warning("tgju fetch failed; falling back to fixture", exc_info=True)` |
| 74 | DATA-052 | P1 | `brsapi/services/sync_service.py:1506` | همگام‌سازی ۲۴ساعتهٔ Pro جدول را برای هر نماد از صفر می‌سازد | `sync()` وقتی `truncate_first` true است `TRUNCATE TABLE` می‌زند و بلافاصله commit می‌کند (`:465`، `:478`). registry این تابع را در حلقه روی تا ۲۰ نماد صدا می‌زند؛ پس بعد از هر اجرا فقط ردیف‌های آخرین نماد در جدول می‌ماند. جاب disabled است ولی از manage API قابل اجراست. → حذف/upsert محدود به همان نماد با کلید یکتا (symbol, time) به‌جای TRUNCATE، یا staging. | `truncate_first=True,` |
| 75 | DATA-053 | P1 | `brsapi/budget.py:506` | گرفتن BaseException [PY_EXCEPT_BASE] | لغو/خروج سیستم هم بلعیده می‌شود → Exception | `except BaseException:` |
| 76 | DATA-054 | P1 | `brsapi/client.py:261` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 77 | DATA-055 | P1 | `brsapi/jobs/gold_desk_jobs.py:92` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as sig_exc:` |
| 78 | DATA-056 | P1 | `brsapi/jobs/gold_desk_jobs.py:122` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as rt_exc:` |
| 79 | DATA-057 | P1 | `brsapi/jobs/gold_desk_jobs.py:131` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 80 | DATA-058 | P1 | `brsapi/jobs/gold_desk_jobs.py:164` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 81 | DATA-059 | P1 | `brsapi/jobs/gold_desk_jobs.py:199` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 82 | DATA-060 | P1 | `brsapi/jobs/gold_desk_jobs.py:261` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 83 | DATA-061 | P1 | `brsapi/jobs/gold_desk_jobs.py:286` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 84 | DATA-062 | P1 | `brsapi/jobs/registry.py:440` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 85 | DATA-063 | P1 | `brsapi/jobs/registry.py:489` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 86 | DATA-064 | P1 | `brsapi/json_sink.py:45` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 87 | DATA-065 | P1 | `brsapi/parsers/tsetmc.py:551` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 88 | DATA-066 | P1 | `brsapi/pipelines/enrichment/base_enricher.py:32` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 89 | DATA-067 | P1 | `brsapi/pipelines/ingestion/quote_pipeline.py:38` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 90 | DATA-068 | P1 | `brsapi/rate_limiter.py:129` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 91 | DATA-069 | P1 | `brsapi/rate_limiter.py:421` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 92 | DATA-070 | P1 | `brsapi/repositories/base.py:330` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders}) {conflict_sql}'),` |
| 93 | DATA-071 | P1 | `brsapi/repositories/base.py:346` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `await self.session.execute(text(f'TRUNCATE TABLE "{table_name}"'))` |
| 94 | DATA-072 | P1 | `brsapi/services/history_fetch_service.py:14` | کتابخانه requests در کد async/سرویس [PY_SYNC_REQUESTS] | I/O مسدودکننده در مسیر درخواست → httpx.AsyncClient | `import requests` |
| 95 | DATA-073 | P1 | `brsapi/services/history_fetch_service.py:66` | کتابخانه requests در کد async/سرویس [PY_SYNC_REQUESTS] | I/O مسدودکننده در مسیر درخواست → httpx.AsyncClient | `resp = requests.get(BASE_URL, params=params, headers=HEADERS, verify=_VERIFY_SSL, timeout=60)` |
| 96 | DATA-074 | P1 | `brsapi/services/history_fetch_service.py:87` | کتابخانه requests در کد async/سرویس [PY_SYNC_REQUESTS] | I/O مسدودکننده در مسیر درخواست → httpx.AsyncClient | `resp = requests.get(BASE_URL, params=params, headers=HEADERS, verify=_VERIFY_SSL, timeout=60)` |
| 97 | DATA-075 | P1 | `brsapi/services/history_fetch_service.py:123` | کتابخانه requests در کد async/سرویس [PY_SYNC_REQUESTS] | I/O مسدودکننده در مسیر درخواست → httpx.AsyncClient | `resp = requests.get(BASE_URL, params=params, headers=HEADERS, verify=_VERIFY_SSL, timeout=180)` |
| 98 | DATA-076 | P1 | `brsapi/services/history_fetch_service.py:239` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 99 | DATA-077 | P1 | `brsapi/services/history_fetch_service.py:308` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 100 | DATA-078 | P1 | `brsapi/services/sync_service.py:108` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 101 | DATA-079 | P1 | `brsapi/services/sync_service.py:410` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 102 | DATA-080 | P1 | `brsapi/services/sync_service.py:480` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 103 | DATA-081 | P1 | `brsapi/services/sync_service.py:511` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 104 | DATA-082 | P1 | `brsapi/services/sync_service.py:612` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 105 | DATA-083 | P1 | `brsapi/services/sync_service.py:743` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 106 | DATA-084 | P1 | `brsapi/services/sync_service.py:810` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 107 | DATA-085 | P1 | `brsapi/services/sync_service.py:887` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 108 | DATA-086 | P1 | `brsapi/services/sync_service.py:896` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 109 | DATA-087 | P1 | `brsapi/services/sync_service.py:1290` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 110 | DATA-088 | P1 | `brsapi/services/sync_service.py:1355` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 111 | DATA-089 | P1 | `brsapi/services/sync_service.py:1385` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 112 | DATA-090 | P1 | `brsapi/services/sync_service.py:1451` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 113 | DATA-091 | P1 | `brsapi/services/sync_service.py:1476` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 114 | DATA-092 | P1 | `brsapi/services/sync_service.py:1490` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 115 | DATA-093 | P1 | `brsapi/services/sync_service.py:1700` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 116 | DATA-094 | P1 | `brsapi/services/sync_service.py:1728` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 117 | DATA-095 | P1 | `ingestion/market_scan_service.py:188` | حلقه انتظار فعال (busy wait) در async [ASYNC110] | مصرف CPU و تأخیر سایر وظایف → asyncio.Event | `while True:` |
| 118 | DATA-096 | P2 | `brsapi/client.py:275` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._client is not None` |
| 119 | DATA-097 | P2 | `ingestion/config.py:61` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `redis_url: str = Field(default="redis://localhost:6379/0")` |
| 120 | DATA-098 | P2 | `ingestion/http_client.py:85` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._session is not None` |
| 121 | DATA-099 | P2 | `ingestion/lake/__init__.py:98` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert resp is not None` |
| 122 | DATA-100 | P2 | `ingestion/main.py:112` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._http is not None` |
| 123 | DATA-101 | P2 | `ingestion/main.py:113` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._worker is not None` |
| 124 | DATA-102 | P2 | `ingestion/main.py:138` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._lake is not None` |
| 125 | DATA-103 | P2 | `ingestion/market_scan_service.py:117` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._pipeline is not None` |
| 126 | DATA-104 | P2 | `ingestion/market_scan_service.py:126` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._scanner is not None` |
| 127 | DATA-105 | P2 | `ingestion/market_scan_service.py:137` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert self._scanner is not None` |
| 128 | DATA-106 | P3 | `brsapi/__init__.py:29` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 129 | DATA-107 | P3 | `brsapi/budget.py:215` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 130 | DATA-108 | P3 | `brsapi/budget.py:246` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 131 | DATA-109 | P3 | `brsapi/budget.py:298` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 132 | DATA-110 | P3 | `brsapi/budget.py:319` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 133 | DATA-111 | P3 | `brsapi/budget.py:353` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 134 | DATA-112 | P3 | `brsapi/budget.py:370` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 135 | DATA-113 | P3 | `brsapi/budget.py:543` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 136 | DATA-114 | P3 | `brsapi/budget.py:557` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 137 | DATA-115 | P3 | `brsapi/budget.py:586` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 138 | DATA-116 | P3 | `brsapi/budget.py:600` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 139 | DATA-117 | P3 | `brsapi/budget.py:610` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 140 | DATA-118 | P3 | `brsapi/budget.py:618` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001` |
| 141 | DATA-119 | P3 | `brsapi/budget.py:638` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 142 | DATA-120 | P3 | `brsapi/budget.py:675` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001` |
| 143 | DATA-121 | P3 | `brsapi/budget.py:728` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 144 | DATA-122 | P3 | `brsapi/client.py:198` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `async def fetch(` |
| 145 | DATA-123 | P3 | `brsapi/client.py:268` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `async def _do_fetch(` |
| 146 | DATA-124 | P3 | `brsapi/client.py:308` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001` |
| 147 | DATA-125 | P3 | `brsapi/client.py:336` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001` |
| 148 | DATA-126 | P3 | `brsapi/client.py:474` | وضعیت global [PY_GLOBAL] | غیرقابل تست و نشت بین درخواست‌ها → DI/کلاس | `global rate limiter (fail-fast, never sleeps) so it can never burn` |
| 149 | DATA-127 | P3 | `brsapi/client.py:504` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 150 | DATA-128 | P3 | `brsapi/config.py:348` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_ALL: dict[str, EndpointConfig] = {}` |
| 151 | DATA-129 | P3 | `brsapi/jobs/gold_desk_jobs.py:182` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001` |
| 152 | DATA-130 | P3 | `brsapi/jobs/gold_desk_jobs.py:304` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `endpoint_config=None,  # type: ignore — direct function call` |
| 153 | DATA-131 | P3 | `brsapi/jobs/gold_desk_jobs.py:310` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `endpoint_config=None,  # type: ignore` |
| 154 | DATA-132 | P3 | `brsapi/jobs/gold_desk_jobs.py:316` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `endpoint_config=None,  # type: ignore` |
| 155 | DATA-133 | P3 | `brsapi/jobs/gold_desk_jobs.py:322` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `endpoint_config=None,  # type: ignore` |
| 156 | DATA-134 | P3 | `brsapi/jobs/gold_desk_jobs.py:328` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `endpoint_config=None,  # type: ignore` |
| 157 | DATA-135 | P3 | `brsapi/jobs/gold_desk_jobs.py:334` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `endpoint_config=None,  # type: ignore` |
| 158 | DATA-136 | P3 | `brsapi/jobs/registry.py:610` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `async def run_job(self, job_name: str, *, force: bool = False) -> SyncReport \| None:` |
| 159 | DATA-137 | P3 | `brsapi/parsers/__init__.py:22` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 160 | DATA-138 | P3 | `brsapi/parsers/commodity.py:27` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `PRECIOUS_METALS = {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"}` |
| 161 | DATA-139 | P3 | `brsapi/parsers/commodity.py:28` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `BASE_METALS = {"COPPER", "ALUMINUM", "ZINC", "LEAD", "NICKEL"}` |
| 162 | DATA-140 | P3 | `brsapi/parsers/commodity.py:29` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `ENERGY = {"BRENT", "WTI", "NGAS", "GASOLINE", "GASOIL"}` |
| 163 | DATA-141 | P3 | `brsapi/pipelines/funds/enrichment.py:76` | if قابل تبدیل به min/max [PLR1730] | خوانایی → min/max | `if nav_val > peak:` |
| 164 | DATA-142 | P3 | `brsapi/pipelines/funds/enrichment.py:80` | if قابل تبدیل به min/max [PLR1730] | خوانایی → min/max | `if drawdown > max_drawdown:` |
| 165 | DATA-143 | P3 | `brsapi/pipelines/indicators.py:67` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `macd_line.append(ema12[i] - ema26[i])  # type: ignore` |
| 166 | DATA-144 | P3 | `brsapi/pipelines/indicators.py:80` | enumerate با اندیس اضافه [PLR1736] | خوانایی → مستقیم | `if macd_line[i] is not None:` |
| 167 | DATA-145 | P3 | `brsapi/pipelines/indicators.py:81` | enumerate با اندیس اضافه [PLR1736] | خوانایی → مستقیم | `histogram[i] = macd_line[i] - sig  # type: ignore` |
| 168 | DATA-146 | P3 | `brsapi/pipelines/indicators.py:99` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `upper.append(middle[i] + num_std * std)  # type: ignore` |
| 169 | DATA-147 | P3 | `brsapi/pipelines/indicators.py:100` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `lower.append(middle[i] - num_std * std)  # type: ignore` |
| 170 | DATA-148 | P3 | `brsapi/pipelines/macro/__init__.py:8` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 171 | DATA-149 | P3 | `brsapi/pipelines/market/__init__.py:8` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 172 | DATA-150 | P3 | `brsapi/pipelines/normalization/quote_normalizer.py:9` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `FIELD_MAP = {` |
| 173 | DATA-151 | P3 | `brsapi/pipelines/quotes/validator.py:10` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `REQUIRED_FIELDS = {"symbol", "price_close", "volume", "date"}` |
| 174 | DATA-152 | P3 | `brsapi/pipelines/quotes/validator.py:21` | else پس از return [RET505] | خوانایی → حذف else | `elif field_name == "date":` |
| 175 | DATA-153 | P3 | `brsapi/pipelines/validation/quote_validator.py:11` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `REQUIRED_FIELDS = ["instrument_id", "price_close"]` |
| 176 | DATA-154 | P3 | `brsapi/pipelines/validation/quote_validator.py:12` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `POSITIVE_FIELDS = ["price_close", "volume"]` |
| 177 | DATA-155 | P3 | `brsapi/repositories/__init__.py:14` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 178 | DATA-156 | P3 | `brsapi/repositories/base.py:336` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `rc = result.rowcount  # type: ignore[attr-defined]` |
| 179 | DATA-157 | P3 | `brsapi/services/__init__.py:16` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 180 | DATA-158 | P3 | `brsapi/services/sync_service.py:129` | تخصیص بی‌استفاده پیش از return [RET504] | خوانایی → return مستقیم | `return v` |
| 181 | DATA-159 | P3 | `brsapi/services/sync_service.py:322` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `async def sync(` |
| 182 | DATA-160 | P3 | `ingestion/fx/fx_adapter.py:23` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `clean_rows: list[dict[str, Any]] = None  # type: ignore[assignment]` |
| 183 | DATA-161 | P3 | `ingestion/fx/fx_adapter.py:26` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `errors: list[str] = None  # type: ignore[assignment]` |
| 184 | DATA-162 | P3 | `ingestion/fx/fx_adapter.py:59` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `PRIMARY_SYMBOLS: list[str] = [` |
| 185 | DATA-163 | P3 | `ingestion/fx/fx_adapter.py:70` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `REFERENCE_SYMBOLS: list[str] = [` |
| 186 | DATA-164 | P3 | `ingestion/gold/gold_adapter.py:34` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `clean_rows: list[dict[str, Any]] = None  # type: ignore[assignment]` |
| 187 | DATA-165 | P3 | `ingestion/gold/gold_adapter.py:37` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `errors: list[str] = None  # type: ignore[assignment]` |
| 188 | DATA-166 | P3 | `ingestion/gold/gold_adapter.py:60` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `PRIMARY_SYMBOLS: list[str] = [` |
| 189 | DATA-167 | P3 | `ingestion/gold/gold_adapter.py:72` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `GLOBAL_FEATURES: list[str] = [` |
| 190 | DATA-168 | P3 | `ingestion/parser/library_parsers.py:305` | چند مقایسه قابل ادغام [PLR1714] | خوانایی → in | `elif data_type == "price_history" or data_type == "closing_price":` |
| 191 | DATA-169 | P3 | `ingestion/scanners/all_symbols.py:30` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `def get_armor_client():  # type: ignore` |
| 192 | DATA-170 | P3 | `ingestion/scanners/all_symbols.py:118` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `if not raw_resp.success:  # type: ignore` |
| 193 | DATA-171 | P3 | `ingestion/scanners/all_symbols.py:131` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `resp = raw_resp  # type: ignore` |
| 194 | DATA-172 | P3 | `ingestion/scanners/all_symbols.py:156` | شرط if/else بی‌اثر [RUF034] | منطق تکراری → ساده‌سازی | `len(rows) if isinstance(raw, list) else len(rows),` |
| 195 | DATA-173 | P3 | `ingestion/sources/library_sources.py:130` | else-if قابل ادغام [PLR5501] | خوانایی → elif | `else:` |
| 196 | DATA-174 | P3 | `ingestion/storage/layered_pipeline.py:91` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `async with async_session_factory() as session:  # type: ignore` |

## SCH — زمان‌بند و اجرای وظایف (48 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 197 | SCH-001 | P0 | `apps/api/app.py:852` | هر replica از API یک SchedulerApp می‌سازد | با دو replica، وظایف چند بار ثبت و اجرا می‌شوند. → زمان‌بند فقط در سرویس scheduler و پشت feature flag. | `scheduler_app = SchedulerApp()` |
| 198 | SCH-002 | P0 | `apps/scheduler/__main__.py:20` | سرویس scheduler جداگانه هم همان وظایف را ثبت می‌کند | منبع سوم اجرای وظایف و مصرف سهمیه. → حذف زمان‌بند درون API یا غیرفعال‌کردن سرویس مستقل. | `app = SchedulerApp()` |
| 199 | SCH-003 | P1 | `apps/scheduler/app.py:74` | فاصله ۲ دقیقه‌ای برای SyncQuotesJob بدون توجه به سهمیه واقعی | احتمال اشباع سهمیه و دریافت 302/خطا در ساعات ابتدایی روز. → بودجه‌محور کردن فرکانس (adaptive interval). | `self.add_job("SyncQuotesJob", trigger="interval", minutes=2)` |
| 200 | SCH-004 | P2 | `apps/scheduler/app.py:150` | ارزیابی هشدارها هر ۲ دقیقه در هر سه نمونه اجرا می‌شود | بار تکراری روی دیتابیس و Redis. → قفل توزیع‌شده اجباری و interval تطبیقی. | `self.add_job("EvaluateAlertsJob", trigger="interval", minutes=2, max_instances=1, replace_existing=True)` |
| 201 | SCH-005 | P0 | `apps/scheduler/app.py:42` | اگر صف Redis در دسترس نباشد، بی‌صدا به اجرای درون‌فرایندی برمی‌گردد | در محیط چندنمونه‌ای هر replica کار را خودش اجرا می‌کند → اجرای تکراری و مصرف چندبرابر. → سیاست صریح fail-closed یا قفل اجباری در fallback. | `"Scheduler could not enqueue %s — falling back to in-process dispatch",` |
| 202 | SCH-006 | P1 | `apps/api/app.py:678` | همگام‌سازی کامل BrsApi در startup API اجرا می‌شود | هر بار ری‌استارت/دیپلوی، همگام‌سازی سنگین و مصرف سهمیه. → انتقال به job دوره‌ای یا اجرای فقط با فلگ. | `if not await _with_startup_lock("brsapi_sync", "brsapi-sync"):` |
| 203 | SCH-007 | P1 | `apps/api/app.py:703` | در startup همه endpointها پشت سر هم فراخوانی می‌شوند | زمان بالا آمدن سرویس طولانی و در صورت خطا سه بار تکرار می‌شود. → اجرای غیرهمزمان پس از ready شدن سرویس. | `reports = await service.sync_all(session)` |
| 204 | SCH-008 | P1 | `ingestion/scheduler.py:52` | منطقه زمانی به‌صورت ثابت +۳:۳۰ کدنویسی شده و market_timezone نادیده گرفته می‌شود | تغییر تنظیمات زمانی اثر ندارد؛ مرزهای بازه بازار ممکن است اشتباه باشد. → استفاده از ZoneInfo(config.market_timezone). | `tz = timezone(timedelta(hours=3, minutes=30))` |
| 205 | SCH-009 | P1 | `ingestion/scheduler.py:39` | تمام callbackها خارج از ساعت بازار کنار گذاشته می‌شوند | منابع شبانه‌روزی (اخبار/کریپتو) هم متوقف می‌شوند. → ساعت بازار per-source به‌جای global gate. | `if self._in_market_hours():` |
| 206 | SCH-010 | P2 | `apps/scheduler/app.py:73` | SyncInstrumentsJob هر ۲۴ ساعت اجرا می‌شود | نماد جدید تا یک روز در سیستم دیده نمی‌شود. → اجرای روزانه در ساعت مشخص + قابلیت دستی. | `self.add_job("SyncInstrumentsJob", trigger="interval", hours=24)` |
| 207 | SCH-011 | P1 | `jobs/definitions/market_data_jobs.py:22` | QuoteIngestionJob حتی با شکست همه نمادها موفق گزارش می‌شود | داشبورد jobها سبز می‌ماند در حالی که هیچ داده‌ای وارد نشده؛ retry و هشدار فعال نمی‌شوند. → ثبت requested/succeeded/failed و شکست صریح در شکست کامل. | `return JobResult.success_result(job_name=self.name, data={"ingested": count, "source": source})` |
| 208 | SCH-012 | P1 | `jobs/definitions/market_data_jobs.py:36` | HistoricalDataJob همیشه موفق است، حتی وقتی ingest_historical همیشه fail می‌دهد | این job با تابع پیاده‌سازی‌نشده ترکیب شده و برای همیشه سبز است؛ هیچ تاریخچه‌ای وارد نمی‌شود ولی کسی خبردار نمی‌شود. → حذف job یا disabled صریح تا پیاده‌سازی؛ گزارش شکست. | `return JobResult.success_result(job_name=self.name, data={"processed": count, "symbols": len(symbols)})` |
| 209 | SCH-013 | P2 | `jobs/definitions/market_data_jobs.py:48` | RealtimeQuoteJob نبود داده را موفقیت تلقی می‌کند | شکست منبع یا پاسخ خالی در وضعیت job دیده نمی‌شود. → تفکیک موفق/خالی/ناموفق. | `return JobResult.success_result(job_name=self.name, data={"quotes": len(results)})` |
| 210 | SCH-014 | P0 | `jobs/definitions/sync_jobs.py:126` | SyncQuotesJob وضعیت success گزارش‌های sync را بررسی نمی‌کند | شکست دریافت نمادها یا شاخص‌ها به‌عنوان اجرای موفق ثبت می‌شود؛ همان مسیری که snapshot را تازه می‌کند. → بررسی success/error هر دو گزارش و شکست جزئی صریح. | `indices_count = idx_report.items_count` |
| 211 | SCH-015 | P0 | `jobs/queue_consumer.py:166` | ack پیام در finally انجام می‌شود، حتی وقتی مدیریت خطا/retry نیمه‌کاره مانده | پیام از processing حذف می‌شود بدون نتیجه نهایی؛ job دریافت داده دیگر خودکار تکرار نمی‌شود. → ack فقط پس از نتیجه قطعی (موفق/requeued/dead-lettered). | `await self._ack_message(client, raw)` |
| 212 | SCH-016 | P1 | `jobs/queue_consumer.py:192` | مسیر جایگزین BRPOP پیام را به لیست processing منتقل نمی‌کند | اگر worker بعد از BRPOP بمیرد، پیام از صف خارج شده و recovery (که فقط processing را می‌گردد) آن را پیدا نمی‌کند. → الزام BRPOPLPUSH/BLMOVE یا fallback durable. | `result = await client.brpop(self._queue_name, self._poll_timeout)` |
| 213 | SCH-017 | P0 | `jobs/queue_consumer.py:302` | شکست requeue مانع ack نمی‌شود | اگر lpush در زمان retry شکست بخورد، پیام اصلی هم از processing حذف می‌شود و job برای همیشه از دست می‌رود. → تأیید موفقیت enqueue پیش از ack و نگه‌داشتن پیام در خطا. | `await client.lpush(self._queue_name, json.dumps(payload, ensure_ascii=False, default=str))` |
| 214 | SCH-018 | P2 | `jobs/queue_publisher.py:82` | is_available فقط وجود client را می‌سنجد، نه سلامت صف | Redis قطع یا بدون مجوز، «queue mode قابل استفاده» تلقی می‌شود و تصمیم fallback را خراب می‌کند. → health واقعی (ping + مجوز LPUSH/BRPOP). | `return self._redis() is not None` |
| 215 | SCH-019 | P2 | `jobs/definitions/sync_jobs.py:195` | توابع legacy دریافت داده، completed با count=0 برمی‌گردانند | هر call-site قدیمی موفقیت کاذب می‌بیند بدون اینکه داده‌ای وارد شود. → حذف یا پاسخ deprecated/unsupported. | `return {"status": "completed", "source": source, "count": 0}` |
| 216 | SCH-020 | P1 | `brsapi/jobs/registry.py:506` | در حالت queue، شکست publish برای jobهای BrsApi هیچ fallback درون‌فرآیندی ندارد | پوشش صف در `apps/scheduler/app.py:69` فقط `publish()` را صدا می‌زند؛ خروجی None بررسی نمی‌شود، پس هنگام اختلال Redis این jobها نه در صف می‌روند نه درون‌فرآیند اجرا می‌شوند. → بررسی نتیجه publish و اجرای امن درون‌فرآیندی یا ثبت خطای قابل‌پایش و retry زمان‌بندی. | `await self._run_handler(job_name)` |
| 217 | SCH-021 | P0 | `apps/worker/consumer.py:30` | worker در نبود Redis هنگام startup برای همیشه idle می‌ماند | اگر `initialize()` در `core/cache.py` شکست بخورد، `_redis` برای همیشه None می‌ماند و `WorkerApp.start()` هیچ تلاش دوره‌ای برای اتصال مجدد یا start دوباره consumer ندارد؛ Redis که چند ثانیه دیرتر بالا بیاید، تا restart مصرف نمی‌شود. → retry با backoff برای اتصال و راه‌اندازی consumer؛ readiness صادق و restart مصرف‌کننده پس از قطعی. | `if self.consumer.is_available:` |
| 218 | SCH-022 | P1 | `jobs/queue_consumer.py:234` | پیام با token نامعتبر دور ریخته می‌شود و به dead-letter نمی‌رود | با ناسازگاری `JOB_QUEUE_TOKEN` بین scheduler و worker، job دریافت داده رد و سپس در `finally` از processing پاک می‌شود؛ فقط شمارنده بالا می‌رود و بدنه پیام برای بررسی نمی‌ماند. → ثبت متادیتای امن و علت رد در dead-letter و قابل‌مقایسه کردن پیکربندی دو طرف در health. | `if self._token and payload.get("token") != self._token:` |
| 219 | SCH-023 | P2 | `jobs/queue_consumer.py:229` | پیام غیرقابل‌پارس بدون dead-letter حذف می‌شود | `json.loads` که شکست بخورد فقط log و شمارنده failed دارد و حلقه پیام را ack می‌کند؛ نام job، پارامترها و زمان انتشار برای عیب‌یابی از دست می‌رود. → انتقال پیام خراب به dead-letter جداگانه با علت، زمان و شناسه (بدون نگه‌داشتن token). | `logger.error("JobQueueConsumer: malformed message dropped")` |
| 220 | SCH-024 | P1 | `jobs/queue_consumer.py:105` | شرط `is_available` که شروع worker را کنترل می‌کند فقط وجود شیء client را می‌سنجد | همین شرط در `apps/worker/consumer.py:30` تصمیم شروع worker را می‌گیرد؛ client ساخته‌شده با Redis از دست‌رفته «آماده» دیده می‌شود و LPUSH/BRPOP بعدی شکست می‌خورد. → health فعال (PING) و جدا کردن «client ساخته شده» از «صف قابل استفاده». | `return self._redis() is not None` |
| 221 | SCH-025 | P0 | `apps/worker/app.py:32` | worker هرگز کلاس‌های job را register نمی‌کند؛ dispatcher همه را «not found» می‌بیند | `job_registry.register_module(job_definitions)` فقط در `apps/scheduler/app.py:61` صدا زده می‌شود. registry در فرآیند worker خالی است، پس `dispatch()` هر job صف‌شده را ناموجود می‌بیند، به retry می‌فرستد و در نهایت dead-letter می‌کند. → register کردن definitionها در startup worker (مشترک با scheduler) و تست دود «هر نامی که scheduler منتشر می‌کند در worker قابل dispatch است». | `await self.consumer.start()` |
| 222 | SCH-026 | P1 | `jobs/definitions/brsapi_jobs.py:103` | نام jobهای BrsApi در صف با کلید registry یکی نیست | scheduler نام `brsapi_all_symbols` را منتشر می‌کند، اما `JobRegistry.register` کلید را از `job_class.__name__` می‌سازد (`BrsApiAllSymbolsJob`). حتی با رفع نبودِ registration، این نام‌ها هرگز تطبیق نمی‌شوند. → نگاشت صریح نام صف به کلاس job (یا ثبت با نام صف) و تست تطبیق برای همهٔ jobهای BrsApi. | `class BrsApiAllSymbolsJob(_BrsApiSyncBaseJob):` |
| 223 | SCH-027 | P1 | `jobs/definitions/brsapi_jobs.py:41` | کلاس‌های BrsApi گیت ساعات بازار و سهمیه را دور می‌زنند | `market_hours_only`/`codal_window` فقط در `BrsApiJobRegistry.run_job` اعمال می‌شود؛ مسیر صف به این کلاس‌ها می‌رسد و گیت را ندارد. امروز با نام‌های نامطابق پوشیده شده، اما با اصلاح نام‌ها سهمیهٔ رایگان خارج از ساعت بازار مصرف می‌شود و به HTTP 402 می‌رسد. → اعمال همان گیت در لایهٔ job یا در consumer پیش از dispatch. | `class _BrsApiSyncBaseJob(BaseJob):` |
| 224 | SCH-028 | P1 | `jobs/job_dispatcher.py:83` | در مسیر صف هیچ پلی به `BrsApiJobRegistry.run_job` وجود ندارد؛ فقط gold_desk پوشش داده شده | `_dispatch_brsapi_direct_job` فقط `GOLD_DESK_JOB_FUNCTIONS` را می‌شناسد و برای بقیه None برمی‌گرداند؛ `run_job` که گیت ساعات بازار را دارد فقط از مسیر in-process/مدیریتی صدا زده می‌شود. پس حتی با ثبت registry در worker، jobهای endpoint اجرا نمی‌شوند. → افزودن پل صریح: اگر نام در BrsApiJobRegistry هست، همان `run_job` (با گیت) اجرا شود. | `if job_name not in GOLD_DESK_JOB_FUNCTIONS:` |
| 225 | SCH-029 | P1 | `apps/scheduler/app.py:324` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(get_cache().initialize())` |
| 226 | SCH-030 | P1 | `apps/scheduler/app.py:328` | حلقه انتظار فعال (busy wait) در async [ASYNC110] | مصرف CPU و تأخیر سایر وظایف → asyncio.Event | `while True:` |
| 227 | SCH-031 | P1 | `jobs/signal_eval_daily.py:58` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception: pass` |
| 228 | SCH-032 | P2 | `jobs/signal_eval_daily.py:53` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `{"now": _dt.datetime.utcnow(), "aid": aid})` |
| 229 | SCH-033 | P3 | `jobs/definitions/brsapi_jobs.py:107` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_params = {"type": "1"}` |
| 230 | SCH-034 | P3 | `jobs/definitions/brsapi_jobs.py:153` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_params = {"type": "1"}` |
| 231 | SCH-035 | P3 | `jobs/definitions/brsapi_jobs.py:187` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_params = {"type": "2"}` |
| 232 | SCH-036 | P3 | `jobs/definitions/brsapi_jobs.py:191` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_params = {"type": "3"}` |
| 233 | SCH-037 | P3 | `jobs/definitions/housekeeping_jobs.py:23` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_TABLES = {` |
| 234 | SCH-038 | P3 | `jobs/job_dispatcher.py:33` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `async def dispatch(` |
| 235 | SCH-039 | P3 | `jobs/scheduler.py:97` | تخصیص بی‌استفاده پیش از return [RET504] | خوانایی → return مستقیم | `return result` |
| 236 | SCH-040 | P3 | `jobs/signal_eval_daily.py:15` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `if i in halted_days: continue  # 5.7: locked -> cannot exit, keep pending` |
| 237 | SCH-041 | P3 | `jobs/signal_eval_daily.py:17` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `if b["high"]>=signal["take_profit"]: hit_tp=True; px=signal["take_profit"]; break` |
| 238 | SCH-042 | P3 | `jobs/signal_eval_daily.py:18` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `if b["low"]<=signal["stop_loss"]: hit_sl=True; px=signal["stop_loss"]; break` |
| 239 | SCH-043 | P3 | `jobs/signal_eval_daily.py:20` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `if b["low"]<=signal["take_profit"]: hit_tp=True; px=signal["take_profit"]; break` |
| 240 | SCH-044 | P3 | `jobs/signal_eval_daily.py:21` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `if b["high"]>=signal["stop_loss"]: hit_sl=True; px=signal["stop_loss"]; break` |
| 241 | SCH-045 | P3 | `jobs/signal_eval_daily.py:27` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `if hit_tp: status="hit_target"; correct = direction in ("buy","sell")` |
| 242 | SCH-046 | P3 | `jobs/signal_eval_daily.py:28` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `elif hit_sl: status="hit_stop"; correct=False` |
| 243 | SCH-047 | P3 | `jobs/signal_eval_daily.py:29` | چند دستور در یک خط [E701] | خوانایی و پوشش تست → شکستن خط | `else: status="expired_neutral"; correct = net>0` |
| 244 | SCH-048 | P3 | `jobs/signal_eval_daily.py:57` | try/except/pass قابل تبدیل به contextlib.suppress [SIM105] | خوانایی → contextlib.suppress | `try: session.rollback()` |

## DB — پایگاه داده، مدل و کوئری (28 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 245 | DB-001 | P1 | `brsapi/models/tsetmc.py:127` | ستون fetched_at بدون timezone ذخیره می‌شود | مقایسه زمان‌ها بین سرویس‌ها/سرورها می‌تواند جابه‌جا شود و تازگی را خراب نشان دهد. → DateTime(timezone=True) و ذخیره UTC. | `fetched_at: Mapped[datetime \| None] = mapped_column(DateTime, index=True)` |
| 246 | DB-002 | P1 | `brsapi/models/tsetmc.py:140` | کلید یکتا بر (symbol, fetched_at) با دقت ثانیه | چرخه‌های هم‌ثانیه روی هم نوشته می‌شوند. → دقت میکروثانیه یا شناسه چرخه در کلید. | `UniqueConstraint("symbol", "fetched_at", name="uq_snap_symbol_fetched"),` |
| 247 | DB-003 | P2 | `brsapi/models/tsetmc.py:129` | created_at از ساعت دیتابیس و fetched_at از ساعت اپلیکیشن پر می‌شود | اختلاف ساعت دو منبع، تحلیل تازگی را نامعتبر می‌کند. → یک منبع زمان واحد. | `created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)` |
| 248 | DB-004 | P2 | `brsapi/services/query_service.py:122` | ترتیب/محدودسازی روی max(trade_value) داخل زیرکوئری گروه‌بندی‌شده اعمال می‌شود | ممکن است نمادهای با ارزش معاملات بالا همیشه انتخاب شوند و بقیه از خروجی حذف گردند. → مرتب‌سازی نهایی روی snapshot انتخاب‌شده انجام شود. | `.order_by(func.max(SymbolSnapshotModel.trade_value).desc().nullslast())` |
| 249 | DB-005 | P2 | `brsapi/services/query_service.py:123` | محدودیت limit روی زیرکوئری گروه‌بندی انجام می‌شود نه روی نتیجه نهایی | تعداد ردیف نهایی با limit هم‌خوان نیست. → limit پس از join اعمال شود. | `.limit(limit)` |
| 250 | DB-006 | P2 | `brsapi/services/query_service.py:385` | آخرین مقدار شاخص با created_at انتخاب می‌شود نه fetched_at | درج مجدد داده قدیمی (backfill) رکورد قدیمی را به‌عنوان مقدار جاری معرفی می‌کند. → مرتب‌سازی بر اساس fetched_at با tie-break. | `sa_func.max(IndexValueModel.created_at).label("max_created"),` |
| 251 | DB-007 | P2 | `brsapi/services/query_service.py:430` | آخرین NAV با created_at انتخاب می‌شود نه تاریخ خود NAV | اگر منبع NAV با تاریخ قدیمی‌تر را دیرتر درج کند، همان به‌عنوان NAV فعلی نمایش داده می‌شود. → مرتب‌سازی بر اساس date نرمال‌شده و سپس created_at. | `stmt = stmt.order_by(NavRecordModel.created_at.desc()).limit(1)` |
| 252 | DB-008 | P1 | `brsapi/services/query_service.py:437` | قراردادهای اختیار معامله همهٔ snapshotها را برمی‌گرداند | با هر پنج دقیقه sync، قرارداد تکراری با قیمت‌های قدیمی در خروجی ظاهر می‌شود. → آخرین snapshot هر قرارداد بر اساس fetched_at. | `async def get_options_by_underlying(self, underlying: str) -> list[dict[str, Any]]:` |
| 253 | DB-009 | P2 | `brsapi/services/query_service.py:766` | فهرست سهام‌داران بر اساس درصد مرتب می‌شود، نه آخرین snapshot | ترکیب سهام‌داران چند تاریخ با هم مخلوط می‌شود. → ابتدا آخرین تاریخ snapshot را انتخاب کنید. | `stmt = stmt.order_by(ShareholderRecordModel.percent.desc().nullslast()).limit(50)` |
| 254 | DB-010 | P2 | `brsapi/services/query_service.py:788` | معاملات درون‌روزی بدون فیلتر تاریخ بازار و بدون کلید یکتای معامله خوانده می‌شوند | معامله تکراری در فهرست «اخیر» دیده می‌شود و رکوردهای روزهای قبل باقی می‌مانند. → کلید یکتای منبع + فیلتر روز معاملاتی. | `stmt = stmt.order_by(IntradayTradeModel.created_at.desc()).limit(limit)` |
| 255 | DB-011 | P1 | `brsapi/services/query_service.py:644` | قیمت کالاها به‌صورت پیش‌فرض کل تاریخچه را برمی‌گرداند | بسیاری از فراخوان‌ها (market_dashboard، gold live، macro) پارامتر latest_only را نمی‌دهند و چند نسخه زمانی از یک کالا می‌گیرند. → پیش‌فرض latest_only=True برای نمای جاری. | `latest_only: bool = False,` |
| 256 | DB-012 | P1 | `brsapi/services/query_service.py:713` | قیمت رمزارزها بر اساس rank مرتب و محدود می‌شود، بدون انتخاب آخرین رکورد هر نماد | یک رمزارز چند بار در ۵۰ نتیجه ظاهر می‌شود و ردیف‌های قدیمی جای بقیه را می‌گیرند. → آخرین ردیف هر symbol بر اساس fetched_at. | `async def get_crypto_prices(` |
| 257 | DB-013 | P2 | `brsapi/services/query_service.py:601` | قراردادهای IME تمام ردیف‌های ذخیره‌شده را برمی‌گردانند | نسخه‌های قدیمی قرارداد در خروجی جاری می‌مانند (وابسته به dedup sync). → کلید طبیعی قرارداد + upsert و انتخاب آخرین نسخه. | `async def get_ime_futures(self) -> list[dict[str, Any]]:` |
| 258 | DB-014 | P2 | `brsapi/services/query_service.py:304` | شاخهٔ fallback اتصال بر اساس symbol عملاً غیرقابل وقوع است | چون ins_id در مدل nullable=False است، شرط IS NULL هرگز برقرار نمی‌شود؛ در صورت ناسازگاری شناسه، فیلدهای غنی (sector/EPS) بی‌صدا خالی می‌مانند. → سیاست تطبیق symbol با کنترل ابهام و متریک no-match. | `SymbolSnapshotModel.ins_id.is_(None) & (SymbolSnapshotModel.symbol == SymbolDetailModel.symbol),` |
| 259 | DB-015 | P0 | `repositories/news_repository.py:37` | نام تعریف‌نشده در کد (NameError در زمان اجرا) [F821] | مسیر اجرا با خطای NameError متوقف می‌شود → تعریف/ایمپورت متغیر | `async def _route(self, discriminator: str) -> tuple[ReadPathDecision, Any, Any]:` |
| 260 | DB-016 | P1 | `brsapi/services/query_service.py:80` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 261 | DB-017 | P1 | `brsapi/services/query_service.py:223` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 262 | DB-018 | P1 | `repositories/news_repository.py:111` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception:  # noqa: BLE001 — probe failure must not break serving` |
| 263 | DB-019 | P1 | `repositories/news_repository.py:150` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception:  # noqa: BLE001` |
| 264 | DB-020 | P1 | `repositories/news_repository.py:207` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception:  # noqa: BLE001` |
| 265 | DB-021 | P3 | `brsapi/models/__init__.py:75` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 266 | DB-022 | P3 | `repositories/base_repository.py:38` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_shared_store: dict[str, dict[str, Any]] = {}` |
| 267 | DB-023 | P3 | `repositories/news_repository.py:93` | متغیر unpack‌شده بی‌استفاده [RUF059] | نویز → حذف | `decision, legacy, items = await self._route(f"list:{page}:{page_size}")` |
| 268 | DB-024 | P3 | `repositories/news_repository.py:109` | try/except/pass قابل تبدیل به contextlib.suppress [SIM105] | خوانایی → contextlib.suppress | `try:` |
| 269 | DB-025 | P3 | `repositories/news_repository.py:126` | متغیر unpack‌شده بی‌استفاده [RUF059] | نویز → حذف | `decision, legacy, items = await self._route(f"search:{query}:{page}:{page_size}")` |
| 270 | DB-026 | P3 | `repositories/news_repository.py:148` | try/except/pass قابل تبدیل به contextlib.suppress [SIM105] | خوانایی → contextlib.suppress | `try:` |
| 271 | DB-027 | P3 | `repositories/news_repository.py:180` | متغیر unpack‌شده بی‌استفاده [RUF059] | نویز → حذف | `decision, legacy, items = await self._route(f"symbol:{symbol}:{page}:{page_size}")` |
| 272 | DB-028 | P3 | `repositories/news_repository.py:203` | try/except/pass قابل تبدیل به contextlib.suppress [SIM105] | خوانایی → contextlib.suppress | `try:` |

## CACHE — کش و تازگی داده (5 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 273 | CACHE-001 | P1 | `apps/api/endpoints/market.py:517` | کش aggregate در حافظه هر replica است | دو کاربر روی دو replica می‌توانند داده با سن متفاوت ببینند. → کش مشترک (Redis) یا حذف کش محلی. | `_AGG_CACHE: dict[str, tuple[float, Any]] = {}` |
| 274 | CACHE-002 | P2 | `apps/api/endpoints/market.py:518` | TTL پنج‌دقیقه‌ای با polling ۳۰ ثانیه‌ای فرانت هم‌خوان نیست | تا ۵ دقیقه پاسخ تکراری/قدیمی با success=True سرو می‌شود. → TTL کوتاه‌تر یا برچسب as_of در پاسخ. | `_AGG_TTL = 300.0  # seconds` |
| 275 | CACHE-003 | P1 | `apps/api/endpoints/market.py:258` | هیت‌مپ کش‌شده هیچ زمان تولیدی همراه ندارد | فرانت نمی‌تواند سن داده را تشخیص دهد. → افزودن generated_at و as_of به پاسخ. | `cached = _agg_cache_get("enriched-heatmap:500")` |
| 276 | CACHE-004 | P0 | `apps/api/endpoints/market.py:283` | پاسخ heatmap فاقد fetched_at هر نماد است | تشخیص «زنده» از «قدیمی» در کل مسیر UI ممکن نیست. → افزودن fetched_at و age_seconds به هر سلول. | `"board": s.get("board", ""),` |
| 277 | CACHE-005 | P1 | `apps/api/endpoints/market.py:139` | پاسخ خالی/قدیمی با success=True برگردانده می‌شود | خطای داده از «بازار خالی» قابل تفکیک نیست. → success=false برای نبود داده تازه یا افزودن فیلد freshness. | `return ApiResponse[list[dict[str, Any]]](success=True, data=cells)` |

## API — بک‌اند و API (307 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 278 | API-001 | P1 | `apps/api/endpoints/market.py:253` | endpoint هیت‌مپ فقط از دیتابیس می‌خواند و هیچ fallback زنده‌ای ندارد | اگر sync متوقف باشد، پاسخ موفق اما کهنه است. → پاسخ شامل وضعیت همگام‌سازی و زمان آخرین موفقیت. | `@router.get("/enriched-heatmap", summary="Enriched market heatmap", description="Symbol heatmap data enriched with price` |
| 279 | API-002 | P2 | `apps/api/endpoints/market.py:215` | بازه تاریخ با date.today محلی محاسبه می‌شود | در سرور با TZ متفاوت، بازه یک روز جابه‌جا می‌شود. → محاسبه در Asia/Tehran یا UTC صریح. | `end = date.today().isoformat()` |
| 280 | API-003 | P2 | `apps/api/endpoints/market.py:296` | treemap تا ۵۰۰۰ نماد را از دیتابیس می‌خواند و در حافظه گروه‌بندی می‌کند | پاسخ سنگین و فشار روی DB در هر کش‌میش. → پیش‌تجمیع در job یا کش مشترک. | `limit: int = Query(2000, ge=50, le=5000),` |
| 281 | API-004 | P2 | `core/config/__init__.py:451` | پیکربندی observability فقط هشدار است نه خطا | در تولید بدون trace، عیب‌یابی داده قدیمی تقریباً غیرممکن می‌شود. → الزام یا هشدار قابل مشاهده در health. | `errors.append("OTLP_ENDPOINT should be configured for observability in production")` |
| 282 | API-005 | P1 | `apps/api/endpoints/market.py:120` | heatmap ساده فقط ۱۰۰ نماد می‌گیرد و پارامتر limit ندارد | در بازار با بیش از ۱۰۰ نماد، بقیه در پاسخ نیستند و پاسخ همچنان success=True است. → صفحه‌بندی واقعی یا limit قابل تنظیم + اعلام total/returned در قرارداد. | `snapshots = await brsapi.get_latest_snapshots(limit=100)` |
| 283 | API-006 | P1 | `apps/api/endpoints/market.py:261` | heatmap غنی سقف ثابت ۵۰۰ نماد دارد | نمادهای فراتر از ۵۰۰ حذف می‌شوند؛ با مرتب‌سازی بر ارزش معامله، نمادهای کم‌معامله بیشتر قربانی می‌شوند. → cursor/صفحه‌بندی و نمایش total. | `enriched = await brsapi.get_enriched_snapshots(limit=500)` |
| 284 | API-007 | P1 | `services/market_service.py:35` | آمار «کل بازار» از حداکثر ۵۰۰ snapshot محاسبه می‌شود | total_instruments/total_quotes و مجموع ارزش و میانگین تغییر، آمار کل بازار نیستند. → تجمیع در SQL روی کل آخرین چرخه یا نام‌گذاری صریح «نمونه». | `snapshots = await self._brsapi.get_latest_snapshots(limit=500)` |
| 285 | API-008 | P2 | `services/market_service.py:109` | خلاصه صنایع حداکثر ۲۰۰ نماد را می‌بیند | شمارش و ارزش هر صنعت ناقص است. → تجمیع دیتابیسی روی کل snapshotهای چرخه آخر. | `snapshots = await self._brsapi.get_latest_snapshots(limit=200)` |
| 286 | API-009 | P2 | `services/market_service.py:135` | میانگین تغییر صنعت همیشه صفر برگردانده می‌شود | فیلد avg_change هرگز از price_last_change_pct محاسبه نمی‌شود و گمراه‌کننده است. → محاسبه میانگین با سیاست روشن برای null. | `sec["avg_change"] = 0` |
| 287 | API-010 | P1 | `services/market_service.py:128` | نام فیلد صنعت با مدل snapshot هم‌خوان نیست | مدل و `_row_dict` فیلد `sector` می‌دهند؛ بنابراین همه نمادها در دسته «سایر» می‌افتند. → افزودن `sector` به زنجیره خواندن و یکسان‌سازی نام فیلد. | `sector = s.get("sector_name") or s.get("industry", "سایر")` |
| 288 | API-011 | P2 | `services/market_service.py:776` | sparkline برخلاف docstring از جدید به قدیم برگردانده می‌شود | نمودارهایی که آرایه را چپ‌به‌راست زمانی رسم می‌کنند روند را وارونه نشان می‌دهند. → reverse پس از انتخاب N ردیف یا ORDER BY صعودی در خروجی. | `ORDER BY symbol, date DESC` |
| 289 | API-012 | P1 | `services/market_service.py:216` | فیلتر بازه تاریخی بعد از محدودسازی به ۵۰۰ ردیف اعمال می‌شود | درخواست بازه قدیمی‌تر ممکن است خالی برگردد در حالی که داده در دیتابیس موجود است. → انتقال شرط تاریخ به کوئری دیتابیس. | `data = await self._brsapi.get_historical_daily(symbol, limit=500)` |
| 290 | API-013 | P2 | `services/market_service.py:326` | بازه fallback با تاریخ محلی سرور و روز تقویمی ساخته می‌شود | اختلاف timezone مرز روز را جابه‌جا می‌کند و تعطیلات در limit*3 حساب نمی‌شوند. → تاریخ بازار با timezone صریح + شمارش کندل به‌جای روز تقویمی. | `start = (date.today() - timedelta(days=limit * 3)).isoformat()` |
| 291 | API-014 | P2 | `services/market_service.py:501` | MACD با fast بزرگ‌تر از slow اعتبارسنجی نمی‌شود | با fast>slow آفست منفی می‌شود و EMAها نادرست هم‌تراز می‌شوند؛ خروجی بی‌معنی. → اعتبارسنجی رابطه‌ای fast<slow در endpoint و تابع. | `offset = slow - fast` |
| 292 | API-015 | P2 | `services/market_service.py:672` | سری‌های Ichimoku هم‌تراز نیستند و شیفت Senkou/Chikou اعمال نمی‌شود | tenkan/kijun/senkou/chikou طول‌های متفاوت دارند؛ تاریخ‌ها فقط با سری اول هم‌تراز می‌شوند. → خروجی با آرایه تاریخ مستقل یا null برای نقاط شیفت‌خورده. | `chikou = closes[kijun_period:] if n > kijun_period else []` |
| 293 | API-016 | P2 | `services/market_service.py:562` | طول سری %D کمتر از %K است اما تاریخ‌ها با طول %K هم‌تراز می‌شوند | نقاط D با تاریخ اشتباه یا تعداد نامتوازن رسم می‌شوند. → تاریخ مستقل per-series یا offset صریح. | `d_line = MarketService._sma(k_line, d_smooth)` |
| 294 | API-017 | P2 | `services/market_service.py:287` | کندل روزانه close را از price_last می‌گیرد و price_close را نادیده می‌برد | نمودار روزانه به‌جای قیمت پایانی رسمی، آخرین معامله را نشان می‌دهد. → استفاده از price_close برای کندل روزانه و price_last فقط برای realtime. | `"close": d.get("price_last"),` |
| 295 | API-018 | P2 | `services/market_service.py:907` | نبود دادهٔ macro به‌صورت موفقیت بدون کلید data برگردانده می‌شود | مصرف‌کننده پاسخ را موفق می‌بیند و بعداً به‌خاطر نبود data خطا می‌دهد. → data: [] صریح یا Result.fail با دلیل. | `return Result.ok({"indicator": indicator, "country": country})` |
| 296 | API-019 | P1 | `apps/api/endpoints/market.py:364` | خلاصه جریان بازار روی حداکثر ۵۰۰ snapshot محاسبه می‌شود | real_net_b/legal_net_b/queue_buy/queue_sell نماینده کل بازار نیستند و به انتخاب ۵۰۰ نماد سوگیری دارند. → تجمیع در SQL روی کل چرخه آخر یا افزودن sample_size/is_partial. | `limit: int = Query(500, ge=50, le=2000),` |
| 297 | API-020 | P2 | `apps/api/endpoints/market.py:473` | ترتیب تاریخچه شاخص به معکوس‌سازی در دو لایه وابسته است | سرویس created_at DESC می‌دهد و endpoint reverse می‌کند؛ مصرف‌کننده دیگر ترتیب متفاوتی می‌بیند و tie-breaker ندارد. → قرارداد ترتیب در یک لایه با (created_at, id). | `rows.reverse()  # oldest-first for charting` |
| 298 | API-021 | P2 | `brsapi/services/query_service.py:314` | جست‌وجوی نماد با یک پارامتر روی دو ستون symbol و ins_id انجام می‌شود | اگر رشته ورودی با ins_id رکورد دیگری برابر باشد، رکورد نامرتبط انتخاب می‌شود؛ اولویت ins_id/symbol صریح نیست. → ابتدا تطبیق دقیق ins_id و سپس fallback symbol با کنترل ابهام. | `SymbolSnapshotModel.ins_id == symbol,` |
| 299 | API-022 | P2 | `apps/api/endpoints/health.py:107` | در /health/full فقط وضعیت دیتابیس روی overall اثر می‌گذارد | Redis یا BrsApi می‌توانند error باشند ولی overall=ok بماند؛ /ready با همان شرایط 503 می‌دهد. → تعریف واحد از overall و مستندسازی معنای هر endpoint. | `if db_status != "ok":` |
| 300 | API-023 | P2 | `apps/api/endpoints/monitoring.py:45` | چک null_check در داشبورد کیفیت داده، nullها را بررسی نمی‌کند | نام چک با محاسبه هم‌خوان نیست و سلامت فیلدهای قیمت/حجم را القا می‌کند بدون بررسی. → متریک null_price_rows/null_volume_rows واقعی یا حذف/تغییر نام چک. | `"null_check": staleness < 300,  # no staleness > 5min` |
| 301 | API-024 | P1 | `apps/api/endpoints/ingestion.py:60` | خطای خواندن صف dead-letter به «صف خالی» تبدیل می‌شود | اگر Redis قطع باشد، داشبورد عمق صفر گزارش می‌کند و هشدار هرگز فعال نمی‌شود. → queue_status=unknown و success=false در خطا. | `dl_len = 0` |
| 302 | API-025 | P2 | `apps/api/endpoints/quotes.py:200` | اندپوینت تست قیمت مستقیماً SQLite جدا می‌سازد و engine را dispose نمی‌کند | نتیجه با PostgreSQL برنامه متفاوت است و اتصال‌ها نشت می‌کنند؛ در محیط عمومی ریسک اطلاعاتی دارد. → استفاده از session واحد یا محدودسازی به محیط توسعه + dispose. | `engine = create_async_engine("sqlite+aiosqlite:///data/market.db")` |
| 303 | API-026 | P2 | `apps/api/endpoints/symbols.py:166` | متن خام استثنا به کلاینت برگردانده می‌شود | ممکن است مسیر فایل یا جزئیات اتصال افشا شود. → پیام عمومی + شناسه درخواست و جزئیات فقط در لاگ. | `return ApiResponse[dict[str, Any]](success=False, error={"message": f"Server error: {exc}"})` |
| 304 | API-027 | P0 | `apps/api/endpoints/market.py:117` | نام تعریف‌نشده در کد (NameError در زمان اجرا) [F821] | مسیر اجرا با خطای NameError متوقف می‌شود → تعریف/ایمپورت متغیر | `select(brsapi.models.SymbolSnapshotModel.fetched_at).order_by(brsapi.models.SymbolSnapshotModel.fetched_at.desc()).limit` |
| 305 | API-028 | P0 | `apps/api/endpoints/options_frontend.py:103` | نام تعریف‌نشده در کد (NameError در زمان اجرا) [F821] | مسیر اجرا با خطای NameError متوقف می‌شود → تعریف/ایمپورت متغیر | `) -> dict[str, LiquidityQuote]:` |
| 306 | API-029 | P0 | `apps/api/endpoints/symbol_alerts.py:81` | نام تعریف‌نشده در کد (NameError در زمان اجرا) [F821] | مسیر اجرا با خطای NameError متوقف می‌شود → تعریف/ایمپورت متغیر | `def _make_task(symbol: str, market: str, user_id: str) -> Any:` |
| 307 | API-030 | P1 | `api/routers/precompute_router.py:116` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 308 | API-031 | P1 | `api/routers/precompute_router.py:133` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 309 | API-032 | P1 | `apps/api/app.py:148` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 310 | API-033 | P1 | `apps/api/app.py:166` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 311 | API-034 | P1 | `apps/api/app.py:354` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 312 | API-035 | P1 | `apps/api/app.py:399` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 313 | API-036 | P1 | `apps/api/app.py:474` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 314 | API-037 | P1 | `apps/api/app.py:526` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 315 | API-038 | P1 | `apps/api/app.py:573` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 316 | API-039 | P1 | `apps/api/app.py:586` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 317 | API-040 | P1 | `apps/api/app.py:610` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 318 | API-041 | P1 | `apps/api/app.py:652` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 319 | API-042 | P1 | `apps/api/app.py:750` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 320 | API-043 | P1 | `apps/api/app.py:779` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 321 | API-044 | P1 | `apps/api/app.py:797` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 322 | API-045 | P1 | `apps/api/app.py:803` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 323 | API-046 | P1 | `apps/api/app.py:810` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 324 | API-047 | P1 | `apps/api/app.py:822` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 325 | API-048 | P1 | `apps/api/app.py:831` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 326 | API-049 | P1 | `apps/api/app.py:845` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 327 | API-050 | P1 | `apps/api/app.py:856` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 328 | API-051 | P1 | `apps/api/app.py:874` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 329 | API-052 | P1 | `apps/api/app.py:886` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 330 | API-053 | P1 | `apps/api/app.py:900` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 331 | API-054 | P1 | `apps/api/dependencies.py:285` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 332 | API-055 | P1 | `apps/api/endpoints/analysis.py:45` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 333 | API-056 | P1 | `apps/api/endpoints/analysis.py:73` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 334 | API-057 | P1 | `apps/api/endpoints/analysis.py:201` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 335 | API-058 | P1 | `apps/api/endpoints/analysis.py:276` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 336 | API-059 | P1 | `apps/api/endpoints/analysis.py:356` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 337 | API-060 | P1 | `apps/api/endpoints/analysis.py:434` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 338 | API-061 | P1 | `apps/api/endpoints/anomalies.py:157` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 339 | API-062 | P1 | `apps/api/endpoints/anomalies.py:191` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 340 | API-063 | P1 | `apps/api/endpoints/assistant.py:118` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 341 | API-064 | P1 | `apps/api/endpoints/auth.py:376` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 342 | API-065 | P1 | `apps/api/endpoints/auth.py:414` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 343 | API-066 | P1 | `apps/api/endpoints/auth.py:425` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 344 | API-067 | P1 | `apps/api/endpoints/auth.py:438` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 345 | API-068 | P1 | `apps/api/endpoints/backtests.py:177` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"""` |
| 346 | API-069 | P1 | `apps/api/endpoints/backtests.py:187` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 347 | API-070 | P1 | `apps/api/endpoints/backtests.py:203` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 348 | API-071 | P1 | `apps/api/endpoints/backtests.py:219` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 349 | API-072 | P1 | `apps/api/endpoints/backtests.py:503` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 350 | API-073 | P1 | `apps/api/endpoints/backtests.py:537` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as dsr_err:` |
| 351 | API-074 | P1 | `apps/api/endpoints/backtests.py:806` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(` |
| 352 | API-075 | P1 | `apps/api/endpoints/backtests.py:1166` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(` |
| 353 | API-076 | P1 | `apps/api/endpoints/brsapi.py:51` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 354 | API-077 | P1 | `apps/api/endpoints/brsapi.py:83` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 355 | API-078 | P1 | `apps/api/endpoints/brsapi.py:100` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 356 | API-079 | P1 | `apps/api/endpoints/brsapi.py:125` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 357 | API-080 | P1 | `apps/api/endpoints/brsapi.py:142` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 358 | API-081 | P1 | `apps/api/endpoints/brsapi.py:162` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 359 | API-082 | P1 | `apps/api/endpoints/brsapi.py:186` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 360 | API-083 | P1 | `apps/api/endpoints/brsapi.py:287` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 361 | API-084 | P1 | `apps/api/endpoints/brsapi.py:342` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 362 | API-085 | P1 | `apps/api/endpoints/brsapi.py:413` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 363 | API-086 | P1 | `apps/api/endpoints/brsapi.py:494` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 364 | API-087 | P1 | `apps/api/endpoints/brsapi.py:536` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 365 | API-088 | P1 | `apps/api/endpoints/brsapi.py:635` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 366 | API-089 | P1 | `apps/api/endpoints/brsapi.py:644` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 367 | API-090 | P1 | `apps/api/endpoints/brsapi.py:660` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 368 | API-091 | P1 | `apps/api/endpoints/brsapi.py:1058` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 369 | API-092 | P1 | `apps/api/endpoints/brsapi.py:1075` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 370 | API-093 | P1 | `apps/api/endpoints/brsapi.py:1081` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 371 | API-094 | P1 | `apps/api/endpoints/brsapi.py:1109` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 372 | API-095 | P1 | `apps/api/endpoints/brsapi.py:1180` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 373 | API-096 | P1 | `apps/api/endpoints/brsapi.py:1205` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 374 | API-097 | P1 | `apps/api/endpoints/brsapi.py:1257` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 375 | API-098 | P1 | `apps/api/endpoints/brsapi.py:1440` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 376 | API-099 | P1 | `apps/api/endpoints/brsapi.py:1477` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 377 | API-100 | P1 | `apps/api/endpoints/brsapi.py:1505` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 378 | API-101 | P1 | `apps/api/endpoints/brsapi.py:1600` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 379 | API-102 | P1 | `apps/api/endpoints/brsapi.py:1637` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 380 | API-103 | P1 | `apps/api/endpoints/brsapi.py:1697` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 381 | API-104 | P1 | `apps/api/endpoints/brsapi.py:1731` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 382 | API-105 | P1 | `apps/api/endpoints/brsapi.py:1783` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 383 | API-106 | P1 | `apps/api/endpoints/brsapi.py:1819` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 384 | API-107 | P1 | `apps/api/endpoints/brsapi.py:1920` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 385 | API-108 | P1 | `apps/api/endpoints/brsapi.py:2077` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 386 | API-109 | P1 | `apps/api/endpoints/brsapi.py:2238` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 387 | API-110 | P1 | `apps/api/endpoints/brsapi.py:2275` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 388 | API-111 | P1 | `apps/api/endpoints/brsapi.py:2523` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 389 | API-112 | P1 | `apps/api/endpoints/brsapi.py:2721` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 390 | API-113 | P1 | `apps/api/endpoints/brsapi.py:2732` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 391 | API-114 | P1 | `apps/api/endpoints/brsapi.py:2838` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 392 | API-115 | P1 | `apps/api/endpoints/brsapi.py:2890` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 393 | API-116 | P1 | `apps/api/endpoints/brsapi.py:2907` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 394 | API-117 | P1 | `apps/api/endpoints/brsapi.py:2977` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))` |
| 395 | API-118 | P1 | `apps/api/endpoints/brsapi.py:2979` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r2 = await session.execute(text(f"SELECT MIN(date), MAX(date), COUNT(DISTINCT symbol) FROM {table}"))` |
| 396 | API-119 | P1 | `apps/api/endpoints/brsapi.py:2988` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as e:` |
| 397 | API-120 | P1 | `apps/api/endpoints/brsapi.py:3165` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"""` |
| 398 | API-121 | P1 | `apps/api/endpoints/brsapi.py:3176` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"""` |
| 399 | API-122 | P1 | `apps/api/endpoints/brsapi.py:3191` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if CRYPTO_DIR.exists():` |
| 400 | API-123 | P1 | `apps/api/endpoints/brsapi.py:3192` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `for fp in sorted(CRYPTO_DIR.glob("*.json")):` |
| 401 | API-124 | P1 | `apps/api/endpoints/brsapi.py:3198` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if HISTORY_DIR.exists():` |
| 402 | API-125 | P1 | `apps/api/endpoints/brsapi.py:3199` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `for fp in sorted(HISTORY_DIR.glob("*.json")):` |
| 403 | API-126 | P1 | `apps/api/endpoints/codal.py:157` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"""` |
| 404 | API-127 | P1 | `apps/api/endpoints/codal.py:166` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"""` |
| 405 | API-128 | P1 | `apps/api/endpoints/codal_audit.py:55` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"SELECT COUNT(*) as cnt FROM {_TABLE}{wsql}"), params` |
| 406 | API-129 | P1 | `apps/api/endpoints/codal_audit.py:61` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"SELECT * FROM {_TABLE}{wsql} ORDER BY {sort_col} {sdir} NULLS LAST LIMIT :limit OFFSET :offset"),` |
| 407 | API-130 | P1 | `apps/api/endpoints/compose.py:37` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(svc.start(` |
| 408 | API-131 | P1 | `apps/api/endpoints/decision_engine.py:802` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `count_result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))` |
| 409 | API-132 | P1 | `apps/api/endpoints/decision_engine.py:816` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `ts_result = await session.execute(text(f"SELECT MAX({ts_col}) FROM {table_name}"))` |
| 410 | API-133 | P1 | `apps/api/endpoints/funds.py:87` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(_rebuild_cache())` |
| 411 | API-134 | P1 | `apps/api/endpoints/funds.py:1040` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(_rebuild_overview_cache())` |
| 412 | API-135 | P1 | `apps/api/endpoints/news.py:479` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(_run_refresh(), name="news-manual-refresh")` |
| 413 | API-136 | P1 | `apps/api/endpoints/scanner.py:61` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(_run())` |
| 414 | API-137 | P1 | `apps/api/endpoints/signal_insights.py:170` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 415 | API-138 | P1 | `apps/api/endpoints/signal_insights.py:183` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r2 = await session.execute(text(f"""` |
| 416 | API-139 | P1 | `apps/api/endpoints/tables.py:96` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `count_result = await session.execute(text(f'SELECT COUNT(*) FROM "{t}"'))` |
| 417 | API-140 | P1 | `apps/api/endpoints/tables.py:105` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `count_result = await session.execute(text(f'SELECT COUNT(*) FROM "{t}"'))` |
| 418 | API-141 | P1 | `apps/api/endpoints/tables.py:160` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f'SELECT COUNT(*) FROM "{table_name}"')` |
| 419 | API-142 | P1 | `apps/api/endpoints/tables.py:179` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f'SELECT {select_list} FROM "{table_name}" {where_clause} ORDER BY 1 LIMIT :limit OFFSET :offset'),` |
| 420 | API-143 | P1 | `apps/api/endpoints/tests_runner.py:36` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `test_dir = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "comprehensive"` |
| 421 | API-144 | P1 | `apps/api/middleware.py:165` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 422 | API-145 | P1 | `apps/api/middleware.py:247` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 423 | API-146 | P1 | `apps/api/middleware.py:252` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 424 | API-147 | P1 | `apps/api/middleware.py:293` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 425 | API-148 | P1 | `apps/api/middleware.py:323` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 426 | API-149 | P2 | `apps/api/endpoints/market.py:116` | متغیر محلی تخصیص‌یافته اما بی‌استفاده [F841] | نشانه منطق نیمه‌کاره یا محاسبه دورریخته → حذف یا استفاده صحیح | `latest_fetched = (await brsapi.session.execute(` |
| 427 | API-150 | P2 | `apps/api/endpoints/tests_runner.py:71` | subprocess بدون check [PLW1510] | خطای اجرا نادیده گرفته می‌شود → check=True | `proc = subprocess.run(` |
| 428 | API-151 | P2 | `apps/api/endpoints/websocket.py:4` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `Connection: ws://localhost:8000/api/v1/ws/market` |
| 429 | API-152 | P3 | `api/job_state.py:99` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _mem_status` |
| 430 | API-153 | P3 | `api/job_state.py:112` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api.ws_manager import get_armor_ws_manager` |
| 431 | API-154 | P3 | `api/job_state.py:121` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _started_at` |
| 432 | API-155 | P3 | `api/job_state.py:187` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _started_at` |
| 433 | API-156 | P3 | `api/job_state.py:235` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _finalizing, _started_at` |
| 434 | API-157 | P3 | `api/routers/precompute_router.py:39` | سرکوب هشدار با noqa [PY_NOQA] | خطای واقعی پنهان می‌شود → رفع علت | `save_status as _save_status,  # noqa: F401 (re-exported by apps.api.endpoints.precompute)` |
| 435 | API-158 | P3 | `api/routers/precompute_router.py:51` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api import job_state as _js` |
| 436 | API-159 | P3 | `api/routers/precompute_router.py:82` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api.job_state import default_status` |
| 437 | API-160 | P3 | `api/routers/precompute_router.py:209` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _mem_lock_until` |
| 438 | API-161 | P3 | `api/routers/precompute_router.py:251` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from precompute.workers.celery_tasks import (  # type: ignore` |
| 439 | API-162 | P3 | `api/ws_manager.py:53` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _STATE_EVENT_TYPES` |
| 440 | API-163 | P3 | `api/ws_manager.py:56` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api.job_state import STATE_EVENT_TYPES` |
| 441 | API-164 | P3 | `api/ws_manager.py:197` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api.job_state import handle_event` |
| 442 | API-165 | P3 | `api/ws_manager.py:277` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.cache import get_cache` |
| 443 | API-166 | P3 | `api/ws_manager.py:290` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.cache import get_cache` |
| 444 | API-167 | P3 | `api/ws_manager.py:301` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.cache import get_cache` |
| 445 | API-168 | P3 | `api/ws_manager.py:329` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api.job_state import load_status` |
| 446 | API-169 | P3 | `api/ws_manager.py:336` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.cache import get_cache` |
| 447 | API-170 | P3 | `api/ws_manager.py:368` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _manager` |
| 448 | API-171 | P3 | `apps/api/app.py:36` | سرکوب هشدار با noqa [PY_NOQA] | خطای واقعی پنهان می‌شود → رفع علت | `from src.gold_desk.api_token import SALT as _GOLD_TOKEN_SALT  # noqa: F401` |
| 449 | API-172 | P3 | `apps/api/app.py:89` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from integrations.notifications.telegram_sender import TelegramSender` |
| 450 | API-173 | P3 | `apps/api/app.py:174` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from integrations.notifications.telegram_sender import TelegramSender` |
| 451 | API-174 | P3 | `apps/api/app.py:191` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `import time` |
| 452 | API-175 | P3 | `apps/api/app.py:277` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from datetime import UTC, datetime` |
| 453 | API-176 | P3 | `apps/api/app.py:279` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.quant_signal_orchestrator import QuantSignalOrchestrator` |
| 454 | API-177 | P3 | `apps/api/app.py:393` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _startup_locker` |
| 455 | API-178 | P3 | `apps/api/app.py:396` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from jobs.locking import JobLocking` |
| 456 | API-179 | P3 | `apps/api/app.py:416` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `import os` |
| 457 | API-180 | P3 | `apps/api/app.py:417` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `import socket` |
| 458 | API-181 | P3 | `apps/api/app.py:418` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `import uuid` |
| 459 | API-182 | P3 | `apps/api/app.py:463` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from apps.api.endpoints.decision_engine import _auto_seed` |
| 460 | API-183 | P3 | `apps/api/app.py:492` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.fund_sync_service import FundSyncService, _is_market_open, _next_market_open_delay` |
| 461 | API-184 | P3 | `apps/api/app.py:497` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.services.query_service import BrsApiQueryService` |
| 462 | API-185 | P3 | `apps/api/app.py:498` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.database import async_session_factory` |
| 463 | API-186 | P3 | `apps/api/app.py:499` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.fund_service import FundService` |
| 464 | API-187 | P3 | `apps/api/app.py:555` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from sqlalchemy import text` |
| 465 | API-188 | P3 | `apps/api/app.py:557` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from ml.model_loader import get_model_loader` |
| 466 | API-189 | P3 | `apps/api/app.py:628` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.news_ingestion import NewsIngestionService` |
| 467 | API-190 | P3 | `apps/api/app.py:686` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.client import get_client` |
| 468 | API-191 | P3 | `apps/api/app.py:687` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.services.sync_service import BrsApiSyncService` |
| 469 | API-192 | P3 | `apps/api/app.py:729` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.rate_limiter import get_rate_limiter` |
| 470 | API-193 | P3 | `apps/api/app.py:776` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.observability_sentry import init_sentry` |
| 471 | API-194 | P3 | `apps/api/app.py:818` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.usage_recorder import get_usage_recorder` |
| 472 | API-195 | P3 | `apps/api/app.py:827` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.accuracy_outcome_queue import get_accuracy_outcome_queue` |
| 473 | API-196 | P3 | `apps/api/app.py:836` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.rate_limiter import get_rate_limiter` |
| 474 | API-197 | P3 | `apps/api/app.py:850` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from apps.scheduler.app import SchedulerApp` |
| 475 | API-198 | P3 | `apps/api/app.py:870` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.realtime_service import get_realtime_service` |
| 476 | API-199 | P3 | `apps/api/app.py:882` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api.ws_manager import get_armor_ws_manager` |
| 477 | API-200 | P3 | `apps/api/app.py:896` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from apps.api.endpoints.multi_market_signals import warm_signal_cache` |
| 478 | API-201 | P3 | `apps/api/app.py:918` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from api.ws_manager import get_armor_ws_manager` |
| 479 | API-202 | P3 | `apps/api/app.py:925` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.realtime_service import get_realtime_service` |
| 480 | API-203 | P3 | `apps/api/app.py:932` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.client import close_client` |
| 481 | API-204 | P3 | `apps/api/app.py:936` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.usage_recorder import get_usage_recorder` |
| 482 | API-205 | P3 | `apps/api/app.py:940` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.accuracy_outcome_queue import get_accuracy_outcome_queue` |
| 483 | API-206 | P3 | `apps/api/app.py:994` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from schemas.common.responses import ApiResponse` |
| 484 | API-207 | P3 | `apps/api/app.py:1017` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from schemas.common.responses import ApiResponse` |
| 485 | API-208 | P3 | `apps/api/app.py:1033` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from schemas.common.responses import ApiResponse` |
| 486 | API-209 | P3 | `apps/api/app.py:1048` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from datetime import UTC, datetime` |
| 487 | API-210 | P3 | `apps/api/app.py:1050` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from schemas.common.responses import ApiResponse` |
| 488 | API-211 | P3 | `apps/api/app.py:1051` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.quant_signal_orchestrator import QuantSignalOrchestrator` |
| 489 | API-212 | P3 | `apps/api/app.py:1092` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.rate_limiter import get_rate_limiter` |
| 490 | API-213 | P3 | `apps/api/app.py:1093` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from schemas.common.responses import ApiResponse` |
| 491 | API-214 | P3 | `apps/api/app.py:1106` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from schemas.common.responses import ApiResponse` |
| 492 | API-215 | P3 | `apps/api/app.py:1107` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.screener_service import ScreenerPipeline, ScreenerService` |
| 493 | API-216 | P3 | `apps/api/auth.py:48` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.security.tokens import decode_access_token, is_token_revoked` |
| 494 | API-217 | P3 | `apps/api/dependencies.py:30` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.database import get_session` |
| 495 | API-218 | P3 | `apps/api/dependencies.py:38` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from core.database import get_replica_session as _get_replica` |
| 496 | API-219 | P3 | `apps/api/dependencies.py:52` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.services.query_service import BrsApiQueryService` |
| 497 | API-220 | P3 | `apps/api/dependencies.py:58` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.analytics_service import AnalyticsService` |
| 498 | API-221 | P3 | `apps/api/dependencies.py:64` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.screener_service import ScreenerService` |
| 499 | API-222 | P3 | `apps/api/dependencies.py:96` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `import importlib` |
| 500 | API-223 | P3 | `apps/api/dependencies.py:106` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.symbol_service import SymbolService` |
| 501 | API-224 | P3 | `apps/api/dependencies.py:112` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from repositories.instrument_repository import InstrumentRepository` |
| 502 | API-225 | P3 | `apps/api/dependencies.py:113` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.instrument_import_service import InstrumentImportService` |
| 503 | API-226 | P3 | `apps/api/dependencies.py:119` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.quote_service import QuoteService` |
| 504 | API-227 | P3 | `apps/api/dependencies.py:125` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.services.query_service import BrsApiQueryService` |
| 505 | API-228 | P3 | `apps/api/dependencies.py:132` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from brsapi.client import get_client` |
| 506 | API-229 | P3 | `apps/api/dependencies.py:142` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.market_service import MarketService` |
| 507 | API-230 | P3 | `apps/api/dependencies.py:148` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.analytics_service import AnalyticsService` |
| 508 | API-231 | P3 | `apps/api/dependencies.py:154` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.signal_service import SignalService` |
| 509 | API-232 | P3 | `apps/api/dependencies.py:160` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.recommendation_service import RecommendationService` |
| 510 | API-233 | P3 | `apps/api/dependencies.py:166` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.codal_service import CodalService` |
| 511 | API-234 | P3 | `apps/api/dependencies.py:172` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.codal_financial_service import CodalFinancialService` |
| 512 | API-235 | P3 | `apps/api/dependencies.py:178` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.codal_financial_import_service import CodalFinancialImportService` |
| 513 | API-236 | P3 | `apps/api/dependencies.py:184` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.news_service import NewsService` |
| 514 | API-237 | P3 | `apps/api/dependencies.py:190` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from repositories.backtest_repository import BacktestRepository` |
| 515 | API-238 | P3 | `apps/api/dependencies.py:191` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.backtest_service import BacktestService` |
| 516 | API-239 | P3 | `apps/api/dependencies.py:197` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from repositories.ml_repository import MlRepository` |
| 517 | API-240 | P3 | `apps/api/dependencies.py:198` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from repositories.quote_repository import QuoteRepository` |
| 518 | API-241 | P3 | `apps/api/dependencies.py:199` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.inference_service import InferenceService` |
| 519 | API-242 | P3 | `apps/api/dependencies.py:208` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.smart_money_service import SmartMoneyService` |
| 520 | API-243 | P3 | `apps/api/dependencies.py:217` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.trade_service import TradeService` |
| 521 | API-244 | P3 | `apps/api/dependencies.py:227` | import داخل تابع [PLC0415] | چرخه import و تأخیر اولین فراخوانی پنهان می‌شود → import در سطح ماژول | `from services.orderbook_service import OrderBookService` |
| 522 | API-245 | P3 | `apps/api/dependencies.py:251` | خط خالی دارای فضای سفید [W293] | نویز → حذف فاصله | `` |
| 523 | API-246 | P3 | `apps/api/dependencies.py:257` | خط خالی دارای فضای سفید [W293] | نویز → حذف فاصله | `` |
| 524 | API-247 | P3 | `apps/api/endpoints/__init__.py:11` | ترتیب __all__ [RUF022] | نویز → مرتب‌سازی | `__all__ = [` |
| 525 | API-248 | P3 | `apps/api/endpoints/alpha.py:42` | if قابل تبدیل به min/max [PLR1730] | خوانایی → min/max | `if p > peak:` |
| 526 | API-249 | P3 | `apps/api/endpoints/alpha.py:45` | if قابل تبدیل به min/max [PLR1730] | خوانایی → min/max | `if dd > max_dd:` |
| 527 | API-250 | P3 | `apps/api/endpoints/analysis.py:55` | پیمایش dict بدون items() [PLC0206] | کارایی → items() | `for sector in by_sector:` |
| 528 | API-251 | P3 | `apps/api/endpoints/auth.py:270` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `)  # type: ignore[return-value]` |
| 529 | API-252 | P3 | `apps/api/endpoints/backtests.py:224` | بررسی کلید و دسترسی تکراری در dict [RUF019] | کارایی → dict.get | `if "symbols" in body and body["symbols"]:` |
| 530 | API-253 | P3 | `apps/api/endpoints/backtests.py:284` | else پس از return [RET505] | خوانایی → حذف else | `else:` |
| 531 | API-254 | P3 | `apps/api/endpoints/backtests.py:497` | else پس از return [RET505] | خوانایی → حذف else | `else:` |
| 532 | API-255 | P3 | `apps/api/endpoints/brsapi.py:1132` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `async def sync_section(` |
| 533 | API-256 | P3 | `apps/api/endpoints/brsapi.py:1950` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _candle_backfill_task` |
| 534 | API-257 | P3 | `apps/api/endpoints/brsapi.py:2107` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _shareholder_backfill_task` |
| 535 | API-258 | P3 | `apps/api/endpoints/brsapi.py:2302` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _history_price_backfill_task` |
| 536 | API-259 | P3 | `apps/api/endpoints/brsapi.py:2389` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _history_real_legal_backfill_task` |
| 537 | API-260 | P3 | `apps/api/endpoints/chat.py:55` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _engine` |
| 538 | API-261 | P3 | `apps/api/endpoints/decision_engine.py:192` | سرکوب هشدار با noqa [PY_NOQA] | خطای واقعی پنهان می‌شود → رفع علت | `DecisionArchitecture.is_active == True  # noqa: E712` |
| 539 | API-262 | P3 | `apps/api/endpoints/decision_engine.py:845` | سرکوب هشدار با noqa [PY_NOQA] | خطای واقعی پنهان می‌شود → رفع علت | `DecisionArchitecture.is_active == True  # noqa: E712` |
| 540 | API-263 | P3 | `apps/api/endpoints/funds.py:69` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _cache, _cache_at` |
| 541 | API-264 | P3 | `apps/api/endpoints/funds.py:120` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _cache, _cache_at` |
| 542 | API-265 | P3 | `apps/api/endpoints/funds.py:133` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `def _infer_fund_type(name: str \| None, symbol: str \| None = None) -> str:` |
| 543 | API-266 | P3 | `apps/api/endpoints/funds.py:1010` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _overview_cache, _overview_cache_at` |
| 544 | API-267 | P3 | `apps/api/endpoints/funds.py:1028` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _overview_cache, _overview_cache_at` |
| 545 | API-268 | P3 | `apps/api/endpoints/funds.py:1582` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _overview_cache, _overview_cache_at` |
| 546 | API-269 | P3 | `apps/api/endpoints/funds.py:1605` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _overview_cache, _overview_cache_at` |
| 547 | API-270 | P3 | `apps/api/endpoints/gold.py:140` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `for symbol, info in ETF_UNIVERSE.items():  # type: ignore[var-annotated]` |
| 548 | API-271 | P3 | `apps/api/endpoints/gold.py:218` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `position_type=body.position_type,  # type: ignore[arg-type]` |
| 549 | API-272 | P3 | `apps/api/endpoints/gold.py:352` | TODO/FIXME باز [PY_TODO] | کار ناتمام در مسیر تولید → پیگیری در issue | `total_equity=0.0,  # TODO: زمانی که account snapshot اضافه شد` |
| 550 | API-273 | P3 | `apps/api/endpoints/gold.py:371` | TODO/FIXME باز [PY_TODO] | کار ناتمام در مسیر تولید → پیگیری در issue | `# TODO: oz_history / usd_history از TimescaleDB (در phase بعدی)` |
| 551 | API-274 | P3 | `apps/api/endpoints/ingestion.py:56` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _last_dl_alert` |
| 552 | API-275 | P3 | `apps/api/endpoints/market.py:434` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `return ApiResponse[dict[str, Any] \| list[dict[str, Any]]](success=True, data=[])  # type: ignore[arg-type]` |
| 553 | API-276 | P3 | `apps/api/endpoints/market.py:480` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `def _classify_asset(name: str) -> str \| None:` |
| 554 | API-277 | P3 | `apps/api/endpoints/multi_market_signals.py:70` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _cache, _cache_at` |
| 555 | API-278 | P3 | `apps/api/endpoints/multi_market_signals.py:109` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _cold_start_build_task` |
| 556 | API-279 | P3 | `apps/api/endpoints/multi_market_signals.py:138` | global بدون تخصیص [PLW0602] | کد مرده/گیج‌کننده → حذف | `global _cache, _cache_at` |
| 557 | API-280 | P3 | `apps/api/endpoints/multi_market_signals.py:154` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _cold_start_build_task` |
| 558 | API-281 | P3 | `apps/api/endpoints/news.py:288` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001 — transparency only, never break the read` |
| 559 | API-282 | P3 | `apps/api/endpoints/options.py:93` | چند مقایسه قابل ادغام [PLR1714] | خوانایی → in | `elif body.strategy == "long_straddle" or body.strategy == "short_straddle":` |
| 560 | API-283 | P3 | `apps/api/endpoints/options.py:95` | چند مقایسه قابل ادغام [PLR1714] | خوانایی → in | `elif body.strategy == "long_strangle" or body.strategy == "short_strangle":` |
| 561 | API-284 | P3 | `apps/api/endpoints/options.py:97` | چند مقایسه قابل ادغام [PLR1714] | خوانایی → in | `elif body.strategy == "bull_call_spread" or body.strategy == "bear_call_spread":` |
| 562 | API-285 | P3 | `apps/api/endpoints/options.py:100` | چند مقایسه قابل ادغام [PLR1714] | خوانایی → in | `elif body.strategy == "bull_put_spread" or body.strategy == "bear_put_spread":` |
| 563 | API-286 | P3 | `apps/api/endpoints/options.py:103` | چند مقایسه قابل ادغام [PLR1714] | خوانایی → in | `elif body.strategy == "strip" or body.strategy == "strap":` |
| 564 | API-287 | P3 | `apps/api/endpoints/options.py:684` | نام متغیر مبهم (l/O/I) [E741] | خوانایی → نام واضح | `for l in body.legs` |
| 565 | API-288 | P3 | `apps/api/endpoints/screener110.py:45` | global بدون تخصیص [PLW0602] | کد مرده/گیج‌کننده → حذف | `global _last_run` |
| 566 | API-289 | P3 | `apps/api/endpoints/screener110.py:115` | global بدون تخصیص [PLW0602] | کد مرده/گیج‌کننده → حذف | `global _last_run` |
| 567 | API-290 | P3 | `apps/api/endpoints/screener_v2.py:435` | else-if قابل ادغام [PLR5501] | خوانایی → elif | `else:` |
| 568 | API-291 | P3 | `apps/api/endpoints/sentiment.py:19` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _service` |
| 569 | API-292 | P3 | `apps/api/endpoints/signal_insights.py:145` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `async def get_walk_forward(` |
| 570 | API-293 | P3 | `apps/api/endpoints/signal_insights.py:271` | else پس از return [RET505] | خوانایی → حذف else | `else:` |
| 571 | API-294 | P3 | `apps/api/endpoints/signal_insights.py:346` | else پس از return [RET505] | خوانایی → حذف else | `else:` |
| 572 | API-295 | P3 | `apps/api/endpoints/symbols.py:164` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception as exc:  # noqa: BLE001 - we want a clean JSON error envelope, not a 500 stack` |
| 573 | API-296 | P3 | `apps/api/endpoints/tests_runner.py:40` | متغیر unpack‌شده بی‌استفاده [RUF059] | نویز → حذف | `stdout, stderr = _execute_pytest(test_file, test_dir)` |
| 574 | API-297 | P3 | `apps/api/endpoints/tests_runner.py:102` | بازنویسی متغیر حلقه [PLW2901] | گیج‌کننده → متغیر جدید | `line = line.strip()` |
| 575 | API-298 | P3 | `apps/api/endpoints/websocket.py:60` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001 — any decoding failure means "not authenticated"` |
| 576 | API-299 | P3 | `apps/api/metrics.py:27` | استفاده از global [PLW0603] | وضعیت مشترک و غیرقابل تست → کپسوله‌سازی در کلاس/DI | `global _exporter` |
| 577 | API-300 | P3 | `apps/api/metrics.py:86` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001 — monitoring must never break serving` |
| 578 | API-301 | P3 | `apps/api/middleware.py:205` | ویژگی کلاس تغییرپذیر بدون ClassVar [RUF012] | اشتراک ناخواسته بین نمونه‌ها → ClassVar / field | `_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}` |
| 579 | API-302 | P3 | `apps/api/middleware.py:322` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `request._headers = None  # type: ignore[attr-defined]` |
| 580 | API-303 | P3 | `apps/api/middleware.py:340` | تعداد زیاد return [PLR0911] | پیچیدگی → بازآرایی | `def _sanitize_value(value, depth: int = 0):` |
| 581 | API-304 | P3 | `apps/api/pagination.py:40` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `@computed_field  # type: ignore[misc]` |
| 582 | API-305 | P3 | `apps/api/pagination.py:47` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `@computed_field  # type: ignore[misc]` |
| 583 | API-306 | P3 | `apps/api/pagination.py:52` | سرکوب type checker [PY_TYPE_IGNORE] | ناسازگاری نوع پنهان → رفع نوع | `@computed_field  # type: ignore[misc]` |
| 584 | API-307 | P3 | `apps/api/router.py:299` | noqa بی‌مورد [RUF100] | پنهان‌سازی بی‌دلیل → حذف noqa | `except Exception:  # noqa: BLE001 — optional surface; never block startup` |

## FE — فرانت‌اند و نمایش (282 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 585 | FE-001 | P0 | `frontend/src/lib/api.ts:1` | آدرس API از متغیر NEXT_PUBLIC خوانده می‌شود که در زمان build درج می‌شود | تغییر مقدار در runtime روی باندل مرورگر اثر ندارد؛ آدرس اشتباه تا ابد می‌ماند. → استفاده از مسیر نسبی و پروکسی سمت سرور. | `const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL \|\| '/api/v1';` |
| 586 | FE-002 | P1 | `frontend/src/lib/api.ts:307` | اگر ساختار پاسخ ناشناخته باشد آرایه خالی برمی‌گردد | خطای ساختاری به «فهرست خالی» تبدیل می‌شود و علت واقعی دیده نمی‌شود. → پرتاب خطا یا نتیجه discriminated union. | `export function extractArray<T = unknown>(response: unknown): T[] {` |
| 587 | FE-003 | P1 | `frontend/src/lib/api.ts:353` | خطای backend فقط console.warn می‌شود و خروجی خالی برمی‌گردد | کاربر داده خالی می‌بیند بدون پیام خطا. → صعود خطا تا سطح UI و نمایش وضعیت. | `export function safeExtractArray<T = unknown>(response: unknown, endpoint?: string): T[] {` |
| 588 | FE-004 | P1 | `frontend/src/hooks/useMarketData.ts:263` | هیت‌مپ فقط success:false را warn می‌کند | شکست دریافت از «بازار بدون داده» تفکیک نمی‌شود. → isError واقعی و پیام قابل مشاهده. | `function useEnrichedHeatmap(): LiveDataResult<HeatmapCell[]> {` |
| 589 | FE-005 | P1 | `frontend/src/hooks/useMarketData.ts:272` | هشدار کنسول تنها واکنش به پاسخ ناموفق است | خطا در محیط کاربر دیده نمی‌شود. → state خطا + retry/بنر. | `console.warn("[useEnrichedHeatmap] backend returned success:false", res);` |
| 590 | FE-006 | P0 | `frontend/src/hooks/useMarketData.ts:281` | وجود یک رکورد برای زنده بودن کافی است | داده چند روزه «زنده» نمایش داده می‌شود؛ همان شکایت اصلی کاربر. → isLive بر اساس سن fetched_at و موفقیت آخرین sync. | `return { data: cells, isLive: cells.length > 0, isError, isLoading };` |
| 591 | FE-007 | P2 | `frontend/src/hooks/useMarketData.ts:276` | بازخوانی ۳۰ ثانیه‌ای بدون توجه به تازگی منبع | بار اضافی روی API بدون تازه‌تر شدن داده. → interval تطبیقی با age داده. | `refetchInterval: 30_000,` |
| 592 | FE-008 | P3 | `frontend/src/hooks/useMarketData.ts:709` | برخی بخش‌ها ۱۰ دقیقه یک‌بار بازخوانی می‌شوند | ناهم‌گونی سن داده بین ویجت‌ها. → سیاست refresh یکسان و مستند. | `refetchInterval: 600_000,` |
| 593 | FE-009 | P1 | `frontend/next.config.ts:19` | پروکسی Next به http://api:8000 پیش‌فرض می‌شود | در محیطی که سرویس API نام دیگری دارد، همه درخواست‌ها 502 می‌شوند. → اجبار API_URL در production یا fail در startup. | `const apiUrl = process.env.API_URL \|\| (process.env.NODE_ENV === "production" ? "http://api:8000" : "http://127.0.0.1:8` |
| 594 | FE-010 | P2 | `frontend/next.config.ts:23` | پروکسی ارز به سرویس currency وابسته است که ممکن است بالا نباشد | بخش ارز بی‌صدا خالی می‌شود. → fallback و پیام خطای صریح. | `const currencyUrl = process.env.CURRENCY_API_URL \|\| (process.env.NODE_ENV === "production" ? "http://currency:8002" : ` |
| 595 | FE-011 | P3 | `frontend/src/lib/api.ts:2` | timeout پیش‌فرض ۶۰ ثانیه برای همه درخواست‌ها | در شبکه کند، کاربر تا یک دقیقه منتظر می‌ماند. → timeout کوتاه‌تر برای خواندن و بلندتر فقط برای sync. | `const REQUEST_TIMEOUT_MS = 60_000;` |
| 596 | FE-012 | P3 | `frontend/src/lib/api.ts:3` | timeout ۱۰ دقیقه‌ای برای مسیرهای sync | درخواست‌های طولانی منابع سرور را قفل می‌کنند. → انتقال به job + polling وضعیت. | `const LONG_TIMEOUT_MS = 600_000; // 10 minutes for heavy sync operations` |
| 597 | FE-013 | P2 | `frontend/src/hooks/useMarketData.ts:430` | شکست هر منبع در کارت‌های قیمت بی‌صدا به آرایه خالی تبدیل می‌شود | allSettled از reject جلوگیری می‌کند، اما useQuery خطا نمی‌بیند؛ اگر رمزارز خراب باشد، isError=false می‌ماند و فقط کارت‌ها کم می‌شوند. → وضعیت partial/منبع ناموفق را در خروجی برگردانید و در UI نشان دهید. | `const [goldRes, curRes, cryptoRes] = await Promise.allSettled([` |
| 598 | FE-014 | P2 | `frontend/src/hooks/useMarketData.ts:498` | بازارهای جهانی هم شکست منبع را بی‌صدا حذف می‌کنند | نبود طلا/برنت/BTC از خطای endpoint قابل تفکیک نیست. → نتیجه per-source با وضعیت و زمان آخرین موفقیت. | `const [comRes, btcRes] = await Promise.allSettled([` |
| 599 | FE-015 | P2 | `frontend/src/hooks/useMarketData.ts:572` | پاسخ success:false نقشه صنایع فقط warn می‌شود و به فهرست خالی تبدیل می‌گردد | خطا و «صنعت بدون داده» یکسان دیده می‌شوند؛ heuristic طول صفر هم بازار خالی را خطا علامت می‌زند. → حالت error جدا از empty با پیام قابل مشاهده. | `console.warn("[useSectorMap] backend returned success:false", res);` |
| 600 | FE-016 | P2 | `frontend/src/hooks/useMarketData.ts:609` | خطای جریان حقیقی/حقوقی فقط warn و آرایه خالی برمی‌گرداند | خرابی endpoint با «جریان مالی وجود ندارد» اشتباه می‌شود. → isError واقعی و پیام در UI. | `console.warn("[useOwnershipFlows] backend returned success:false", res);` |
| 601 | FE-017 | P2 | `frontend/src/hooks/useMarketData.ts:634` | خلاصه جریان در خطا null برمی‌گرداند و catch خالی است | null می‌تواند یعنی خطا یا نبود داده؛ مصرف‌کننده تفکیک نمی‌کند. → نوع نتیجه با وضعیت خطا و updatedAt. | `console.warn("[useFlowSummary] backend returned success:false", res);` |
| 602 | FE-018 | P2 | `frontend/src/hooks/useMarketData.ts:693` | خطای تقویم اقتصادی با «بدون رویداد» یکسان می‌شود | اختلال API به «هیچ رویداد اقتصادی وجود ندارد» تبدیل می‌شود. → تفکیک empty از error و ثبت payload نامعتبر. | `console.warn("[useMarketEvents] backend returned success:false", res);` |
| 603 | FE-019 | P1 | `frontend/src/hooks/useApiMonitor.ts:10` | مانیتور API به‌طور پیش‌فرض localhost کاربر را بررسی می‌کند | در production، مرورگر خودِ دستگاه کاربر را روی پورت ۸۰۰۰ می‌زند و API سالم را offline نشان می‌دهد. → آدرس از پیکربندی واحد/مسیر same-origin و بدون پیش‌فرض localhost در تولید. | `export function useApiMonitor(baseUrl: string = "http://localhost:8000") {` |
| 604 | FE-020 | P2 | `frontend/src/hooks/useApiMonitor.ts:32` | وضعیت «آنلاین» فقط از کد ۲۰۰ ساخته می‌شود و بدنه بررسی نمی‌شود | /health فقط liveness است؛ دیتابیس، Redis و منبع داده ممکن است خراب باشند ولی پنل «آنلاین» بدهد. → تفکیک liveness/readiness و نمایش آخرین sync. | `if (response.ok) {` |
| 605 | FE-021 | P1 | `frontend/src/hooks/useWebSocket.ts:130` | اشتراک WebSocket فقط در onopen ارسال می‌شود و با تغییر نمادها به‌روز نمی‌شود | نماد تازه‌اضافه‌شده قیمت زنده نمی‌گیرد و نماد حذف‌شده در اشتراک می‌ماند. → ارسال subscribe/unsubscribe در effect وابسته به symbols یا بازسازی اتصال. | `action: 'subscribe',` |
| 606 | FE-022 | P1 | `frontend/src/hooks/useWebSocket.ts:147` | زمان دریافت مرورگر جای timestamp منبع را می‌گیرد | پیام دیررس «تازه» به نظر می‌رسد و تأخیر شبکه/منبع قابل اندازه‌گیری نیست. → حفظ timestamp سرور و افزودن received_at جداگانه. | `timestamp: Date.now(),` |
| 607 | FE-023 | P2 | `frontend/src/hooks/useWebSocket.ts:154` | پیام نامعتبر WebSocket بی‌صدا دور ریخته می‌شود | اتصال connected می‌ماند ولی قیمت‌ها به‌روز نمی‌شوند؛ هیچ نشانه‌ای ثبت نمی‌شود. → شمارنده decode_error + لاگ محدود + اعتبارسنجی schema. | `// Ignore malformed messages` |
| 608 | FE-024 | P2 | `frontend/src/hooks/useBackgroundBackfill.ts:66` | خطای polling وضعیت backfill به undefined تبدیل می‌شود | خطای شبکه/۵۰۰ از «وضعیت در دسترس نیست» قابل تفکیک نیست و UI وضعیت قدیمی را نشان می‌دهد. → فیلد pollError و last_poll_ok_at. | `const res = await apiGet<{ success: boolean; data: BackfillState }>(statusUrl);` |
| 609 | FE-025 | P2 | `frontend/src/hooks/useBackgroundBackfill.ts:97` | شروع backfill بدون بررسی started به running تغییر می‌کند | اگر سرور درخواست را رد کند، UI همچنان «در حال اجرا» می‌ماند. → اعتبارسنجی success/started و شروع polling فقط برای job واقعی. | `setBackfill({ ...IDLE_BACKFILL, status: "running", message: "در حال راه‌اندازی..." });` |
| 610 | FE-026 | P2 | `frontend/src/hooks/useBackgroundBackfill.ts:96` | خطای شروع backfill به undefined تبدیل می‌شود | دلیل شکست شروع job به کاربر نمی‌رسد. → نتیجه {ok:false,error} و نمایش پیام سرور. | `const res = await apiPost<{ success: boolean; data: StartResponse }>(startUrl);` |
| 611 | FE-027 | P2 | `frontend/src/hooks/useBackgroundBackfill.ts:108` | لغو backfill بدون تأیید سرور و بدون بازخوانی وضعیت انجام می‌شود | ممکن است UI لغو را انجام‌شده بداند در حالی که job در سرور ادامه دارد. → پس از لغو، status را دوباره بخوانید و تا تأیید سرور «لغوشده» نشان ندهید. | `const res = await apiPost<{ success: boolean; data: CancelResponse }>(cancelUrl);` |
| 612 | FE-028 | P1 | `frontend/src/app/layout.tsx:109` | dangerouslySetInnerHTML [TS_DANGEROUS_HTML] | ریسک XSS → sanitize | `<script nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />` |
| 613 | FE-029 | P2 | `frontend/src/app/admin/page.tsx:95` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `const API_BASE = process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000/api/v1";` |
| 614 | FE-030 | P2 | `frontend/src/app/admin/page.tsx:172` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const schedJobs = schedulerData?.jobs ?? [];` |
| 615 | FE-031 | P2 | `frontend/src/app/admin/page.tsx:365` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const { data: hist, isLoading } = useQuery({ queryKey: ["admin-sync-hist", tr], queryFn: async (): Promise<SyncLogEntry[` |
| 616 | FE-032 | P2 | `frontend/src/app/admin/page.tsx:376` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const { data: hist, isLoading } = useQuery({ queryKey: ["admin-sync-events"], queryFn: async (): Promise<SyncLogEntry[]>` |
| 617 | FE-033 | P2 | `frontend/src/app/admin/page.tsx:449` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `try { const r = await fetch(`${API_BASE}${ep}`, { method: "POST", body: form }); const d = await r.json(); setResult({ t` |
| 618 | FE-034 | P2 | `frontend/src/app/admin/page.tsx:488` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const tables: TableInfo[] = (tblResp && typeof tblResp === "object" && "data" in tblResp) ? ((tblResp as { data?: { tabl` |
| 619 | FE-035 | P2 | `frontend/src/app/admin/page.tsx:532` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const ps = SEARCHABLE_TABLES.map(async tn => { try { const r = await apiGet<{ data?: { rows?: Record<string, unknown>[];` |
| 620 | FE-036 | P2 | `frontend/src/app/admin/users/page.tsx:46` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 621 | FE-037 | P2 | `frontend/src/app/alerts/page.tsx:120` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `setHistoryData(data?.data?.items ?? []);` |
| 622 | FE-038 | P2 | `frontend/src/app/anomalies/page.tsx:116` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const items = data?.items ?? [];` |
| 623 | FE-039 | P2 | `frontend/src/app/backtest/adaptive/page.tsx:261` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `}).catch(() => {});` |
| 624 | FE-040 | P2 | `frontend/src/app/backtest/compose/page.tsx:47` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `.catch(() => {});` |
| 625 | FE-041 | P2 | `frontend/src/app/backtest/compose/page.tsx:63` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `.catch(() => {});` |
| 626 | FE-042 | P2 | `frontend/src/app/backtest/decision/page.tsx:235` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `apiGet<{ success: boolean; data: RegimeData }>("/backtests/adaptive/regime").then(r => { if (r?.data?.initialized) setRe` |
| 627 | FE-043 | P2 | `frontend/src/app/backtest/full-scan/page.tsx:135` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `.catch(() => {});` |
| 628 | FE-044 | P2 | `frontend/src/app/backtest/full-scan/page.tsx:202` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 629 | FE-045 | P2 | `frontend/src/app/backtest/generate/page.tsx:249` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 630 | FE-046 | P2 | `frontend/src/app/backtest/generate/page.tsx:436` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 631 | FE-047 | P2 | `frontend/src/app/backtest/page.tsx:266` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const selected = (strategies ?? []).find((s: Record<string, unknown>) => s.name === strategyName);` |
| 632 | FE-048 | P2 | `frontend/src/app/backtest/page.tsx:321` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [strategies, prevStrategies]);` |
| 633 | FE-049 | P2 | `frontend/src/app/backtest/page.tsx:384` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `setAllResults(r?.data?.results ?? []);` |
| 634 | FE-050 | P2 | `frontend/src/app/backtest/page.tsx:407` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const saved = localStorage.getItem("bt-radar-metrics");` |
| 635 | FE-051 | P2 | `frontend/src/app/backtest/page.tsx:430` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem("bt-radar-metrics", JSON.stringify(enabledRadarMetrics));` |
| 636 | FE-052 | P2 | `frontend/src/app/backtest/page.tsx:526` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `setCompareResults(r?.data?.results ?? []);` |
| 637 | FE-053 | P2 | `frontend/src/app/backtest/page.tsx:597` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 638 | FE-054 | P2 | `frontend/src/app/backtest/page.tsx:881` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const selected = (strategies ?? []).find((s: Record<string, unknown>) => s.name === formData.strategyType);` |
| 639 | FE-055 | P2 | `frontend/src/app/backtest/page.tsx:893` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const selected = (strategies ?? []).find((s: Record<string, unknown>) => s.name === formData.strategyType);` |
| 640 | FE-056 | P2 | `frontend/src/app/backtest/page.tsx:894` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const params = (selected?.params ?? []) as Array<{ name: string; type: string; default: unknown }>;` |
| 641 | FE-057 | P2 | `frontend/src/app/backtest/page.tsx:1454` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const desc = (strategies ?? []).find((s: Record<string, unknown>) => s.name === r.strategy)?.description as string \| un` |
| 642 | FE-058 | P2 | `frontend/src/app/brsapi/codal/page.tsx:221` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 643 | FE-059 | P2 | `frontend/src/app/brsapi/codal/page.tsx:250` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const announcements = data?.items ?? [];` |
| 644 | FE-060 | P2 | `frontend/src/app/brsapi/history/[symbol]/page.tsx:154` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `setData(res.data.items ?? []);` |
| 645 | FE-061 | P2 | `frontend/src/app/brsapi/page.tsx:100` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 646 | FE-062 | P2 | `frontend/src/app/brsapi/page.tsx:277` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `return res?.data ?? [];` |
| 647 | FE-063 | P2 | `frontend/src/app/brsapi/page.tsx:691` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `href={`${process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000/api/v1"}/brsapi/manage/download/${section.id}?forma` |
| 648 | FE-064 | P2 | `frontend/src/app/brsapi/page.tsx:700` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `href={`${process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000/api/v1"}/brsapi/manage/download/${section.id}?forma` |
| 649 | FE-065 | P2 | `frontend/src/app/codal/[id]/page.tsx:141` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `return res?.data ?? [];` |
| 650 | FE-066 | P2 | `frontend/src/app/codal/accounting/[symbol]/page.tsx:143` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `return res?.data ?? [];` |
| 651 | FE-067 | P2 | `frontend/src/app/codal/import/page.tsx:9` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `const API_BASE = process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000/api/v1";` |
| 652 | FE-068 | P2 | `frontend/src/app/codal/import/page.tsx:117` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 653 | FE-069 | P2 | `frontend/src/app/codal/page.tsx:198` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const items = res.data.announcements ?? [];` |
| 654 | FE-070 | P2 | `frontend/src/app/codal/page.tsx:219` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const announcements = data?.items ?? [];` |
| 655 | FE-071 | P2 | `frontend/src/app/crypto-market/page.tsx:155` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `const sparkData = useMemo(() => generateSparkline(change), [coin.symbol, change]);` |
| 656 | FE-072 | P2 | `frontend/src/app/crypto-market/page.tsx:239` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `const sparkData = useMemo(() => generateSparkline(change), [coin.symbol, change]);` |
| 657 | FE-073 | P2 | `frontend/src/app/crypto-market/page.tsx:317` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [cryptos, tab, tf, search]);` |
| 658 | FE-074 | P2 | `frontend/src/app/data-import/page.tsx:92` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 659 | FE-075 | P2 | `frontend/src/app/data-import/page.tsx:103` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `const API_BASE = process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000/api/v1";` |
| 660 | FE-076 | P2 | `frontend/src/app/data-import/page.tsx:157` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `errors: data?.data?.errors ?? data?.data?.parse_errors ?? [],` |
| 661 | FE-077 | P2 | `frontend/src/app/data/page.tsx:65` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 662 | FE-078 | P2 | `frontend/src/app/decision-engine/page.tsx:224` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 663 | FE-079 | P2 | `frontend/src/app/decision-engine/page.tsx:233` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 664 | FE-080 | P2 | `frontend/src/app/decision-engine/page.tsx:252` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 665 | FE-081 | P2 | `frontend/src/app/economic-calendar/page.tsx:74` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 666 | FE-082 | P2 | `frontend/src/app/economic-calendar/page.tsx:82` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 667 | FE-083 | P2 | `frontend/src/app/economic-calendar/page.tsx:124` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `const grouped = data?.grouped \|\| {};` |
| 668 | FE-084 | P2 | `frontend/src/app/funds/intraday/page.tsx:43` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `() => topQuery.data?.items.map((i) => i.symbol) ?? [],` |
| 669 | FE-085 | P2 | `frontend/src/app/funds/intraday/page.tsx:57` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `? candlesQuery.data?.symbols?.[activeSymbol]?.candles ?? []` |
| 670 | FE-086 | P2 | `frontend/src/app/funds/page.tsx:119` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const funds = useMemo(() => fundsData?.items ?? [], [fundsData]);` |
| 671 | FE-087 | P2 | `frontend/src/app/funds/page.tsx:131` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 672 | FE-088 | P2 | `frontend/src/app/funds/page.tsx:141` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const clean = (pts ?? [])` |
| 673 | FE-089 | P2 | `frontend/src/app/funds/page.tsx:159` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const donut = (ov.trade_breakdown ?? []).map((c, i) => ({` |
| 674 | FE-090 | P2 | `frontend/src/app/funds/page.tsx:195` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `data={(ov.categories ?? []).map((c) => ({ date: c.name, value: c.real_inflow }))}` |
| 675 | FE-091 | P2 | `frontend/src/app/funds/page.tsx:225` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `{(ov.returns ?? []).length ? (` |
| 676 | FE-092 | P2 | `frontend/src/app/funds/page.tsx:602` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const rows = data?.rankings ?? [];` |
| 677 | FE-093 | P2 | `frontend/src/app/funds/page.tsx:640` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const rows = diffs?.diffs ?? [];` |
| 678 | FE-094 | P2 | `frontend/src/app/funds/page.tsx:645` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `{(ov?.cashflow_periods ?? []).length ? (` |
| 679 | FE-095 | P2 | `frontend/src/app/funds/page.tsx:651` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `{Array.from(new Set((ov?.categories ?? []).map((c) => c.name))).slice(0, 8).map((c) => (` |
| 680 | FE-096 | P2 | `frontend/src/app/funds/page.tsx:657` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `{(ov?.cashflow_periods ?? []).map((p) => (` |
| 681 | FE-097 | P2 | `frontend/src/app/funds/page.tsx:756` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `setIds(JSON.parse(localStorage.getItem(WATCH_KEY) ?? "[]") as string[]);` |
| 682 | FE-098 | P2 | `frontend/src/app/funds/page.tsx:757` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 683 | FE-099 | P2 | `frontend/src/app/funds/page.tsx:857` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `setWatch(JSON.parse(localStorage.getItem(WATCH_KEY) ?? "[]") as string[]);` |
| 684 | FE-100 | P2 | `frontend/src/app/funds/page.tsx:858` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 685 | FE-101 | P2 | `frontend/src/app/funds/page.tsx:867` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(WATCH_KEY, JSON.stringify(next));` |
| 686 | FE-102 | P2 | `frontend/src/app/funds/page.tsx:868` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 687 | FE-103 | P2 | `frontend/src/app/gold/alerts/page.tsx:72` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `{(rules ?? []).map((r) => (` |
| 688 | FE-104 | P2 | `frontend/src/app/gold/alerts/page.tsx:108` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `events={events ?? []}` |
| 689 | FE-105 | P2 | `frontend/src/app/gold/analytics/page.tsx:55` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `<ScoreChart points={scoreHist ?? []} />` |
| 690 | FE-106 | P2 | `frontend/src/app/gold/analytics/page.tsx:178` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const points = (hist ?? [])` |
| 691 | FE-107 | P2 | `frontend/src/app/gold/chat/page.tsx:66` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 692 | FE-108 | P2 | `frontend/src/app/gold/coins/page.tsx:215` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 693 | FE-109 | P2 | `frontend/src/app/gold/coins/page.tsx:250` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const updated: string[] = [...(wl?.symbols ?? []), newSymbol];` |
| 694 | FE-110 | P2 | `frontend/src/app/gold/coverage/page.tsx:37` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 695 | FE-111 | P2 | `frontend/src/app/gold/coverage/page.tsx:44` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 696 | FE-112 | P2 | `frontend/src/app/gold/coverage/page.tsx:52` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 697 | FE-113 | P2 | `frontend/src/app/gold/coverage/page.tsx:60` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 698 | FE-114 | P2 | `frontend/src/app/gold/etf/page.tsx:53` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `) ?? [],` |
| 699 | FE-115 | P2 | `frontend/src/app/gold/funds/page.tsx:20` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 700 | FE-116 | P2 | `frontend/src/app/gold/funds/page.tsx:23` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const funds = data?.funds ?? [];` |
| 701 | FE-117 | P2 | `frontend/src/app/gold/health/page.tsx:156` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `{(freshness?.sources ?? []).map((s) => (` |
| 702 | FE-118 | P2 | `frontend/src/app/gold/options/page.tsx:206` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const scenarios = scenariosQuery.data ?? [];` |
| 703 | FE-119 | P2 | `frontend/src/app/gold/page.tsx:27` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 704 | FE-120 | P2 | `frontend/src/app/gold/portfolio/page.tsx:81` | fallback به آرایه خالی [TS_EMPTY_FALLBACK] | نبود داده و خطا یکسان نمایش داده می‌شوند → تفکیک حالت خالی از خطا | `const ids = (holding.holding_ids ?? []).filter((id) => Number.isFinite(id));` |
| 705 | FE-121 | P2 | `frontend/src/app/gold/terminal/GoldFundsTable.tsx:47` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 706 | FE-122 | P2 | `frontend/src/app/gold/terminal/page.tsx:28` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 707 | FE-123 | P2 | `frontend/src/app/gold/tokens/page.tsx:160` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `curl -H &quot;Authorization: Bearer YOUR_TOKEN&quot; http://localhost:8000/api/v1/gold/snapshot` |
| 708 | FE-124 | P2 | `frontend/src/app/health/page.tsx:61` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 709 | FE-125 | P2 | `frontend/src/app/heatmap/page.tsx:178` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 710 | FE-126 | P2 | `frontend/src/app/heatmap/page.tsx:193` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 711 | FE-127 | P2 | `frontend/src/app/indicators/page.tsx:117` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 712 | FE-128 | P2 | `frontend/src/app/instruments/page.tsx:69` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 713 | FE-129 | P2 | `frontend/src/app/jobs/page.tsx:85` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 714 | FE-130 | P2 | `frontend/src/app/jobs/page.tsx:102` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 715 | FE-131 | P2 | `frontend/src/app/layout.tsx:60` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `var t = localStorage.getItem('theme');` |
| 716 | FE-132 | P2 | `frontend/src/app/macro/page.tsx:216` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 717 | FE-133 | P2 | `frontend/src/app/macro/page.tsx:239` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 718 | FE-134 | P2 | `frontend/src/app/macro/page.tsx:253` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 719 | FE-135 | P2 | `frontend/src/app/markets/commodity/page.tsx:214` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 720 | FE-136 | P2 | `frontend/src/app/markets/gold/page.tsx:301` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const raw = window.localStorage.getItem(TRADES_KEY);` |
| 721 | FE-137 | P2 | `frontend/src/app/markets/gold/page.tsx:303` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 722 | FE-138 | P2 | `frontend/src/app/markets/gold/page.tsx:311` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `window.localStorage.setItem(TRADES_KEY, JSON.stringify(next));` |
| 723 | FE-139 | P2 | `frontend/src/app/markets/gold/page.tsx:312` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 724 | FE-140 | P2 | `frontend/src/app/markets/gold/page.tsx:322` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `window.localStorage.setItem(TRADES_KEY, JSON.stringify(next));` |
| 725 | FE-141 | P2 | `frontend/src/app/markets/gold/page.tsx:323` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 726 | FE-142 | P2 | `frontend/src/app/markets/gold/page.tsx:467` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [live.bySymbol]);` |
| 727 | FE-143 | P2 | `frontend/src/app/markets/gold/page.tsx:1191` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [trades, live.bySymbol, fundCache]);` |
| 728 | FE-144 | P2 | `frontend/src/app/markets/gold/page.tsx:1325` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [trades, live.bySymbol]);` |
| 729 | FE-145 | P2 | `frontend/src/app/markets/page.tsx:49` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `const snapshots: Snapshot[] = (heatmapData && typeof heatmapData === "object" && "data" in heatmapData)` |
| 730 | FE-146 | P2 | `frontend/src/app/markets/silver/components/BacktestTab.tsx:171` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 731 | FE-147 | P2 | `frontend/src/app/markets/silver/components/TradingViewWidget.tsx:49` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 732 | FE-148 | P2 | `frontend/src/app/multi-market-signals/page.tsx:618` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [cronData?.alerts]);` |
| 733 | FE-149 | P2 | `frontend/src/app/options/components/tabs/BacktestTab.tsx:56` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `.catch(() => setStrategies([]));` |
| 734 | FE-150 | P2 | `frontend/src/app/options/components/tabs/BacktestTab.tsx:75` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 735 | FE-151 | P2 | `frontend/src/app/options/components/tabs/ChainTab.tsx:141` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `.catch(() => setSymbols([]));` |
| 736 | FE-152 | P2 | `frontend/src/app/options/components/tabs/ChainTab.tsx:158` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `.catch(() => {` |
| 737 | FE-153 | P2 | `frontend/src/app/options/components/tabs/ForecastTab.tsx:67` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 738 | FE-154 | P2 | `frontend/src/app/options/components/tabs/RiskTab.tsx:48` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 739 | FE-155 | P2 | `frontend/src/app/options/components/tabs/SignalsTab.tsx:71` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 740 | FE-156 | P2 | `frontend/src/app/personal/page.tsx:133` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 741 | FE-157 | P2 | `frontend/src/app/personal/page.tsx:149` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 742 | FE-158 | P2 | `frontend/src/app/personal/page.tsx:163` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 743 | FE-159 | P2 | `frontend/src/app/personal/page.tsx:177` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 744 | FE-160 | P2 | `frontend/src/app/personal/page.tsx:191` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 745 | FE-161 | P2 | `frontend/src/app/profile/page.tsx:47` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 746 | FE-162 | P2 | `frontend/src/app/providers.tsx:42` | بازخوانی هنگام بازگشت به تب خاموش است [TS_REFETCH_OFF] | کاربر داده کهنه می‌بیند تا interval بعدی → فعال‌سازی refetchOnWindowFocus | `refetchOnWindowFocus: false,` |
| 747 | FE-163 | P2 | `frontend/src/app/quotes/import/page.tsx:9` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `const API_BASE = process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000/api/v1";` |
| 748 | FE-164 | P2 | `frontend/src/app/quotes/import/page.tsx:119` | بلعیدن خطا در catch [TS_CATCH_SILENT] | شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود → نمایش خطا و retry | `} catch {` |
| 749 | FE-165 | P2 | `frontend/src/app/settings/page.tsx:15` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `const [apiEndpoint, setApiEndpoint] = useState("http://localhost:8000/api/v1");` |
| 750 | FE-166 | P2 | `frontend/src/app/symbol/[symbol]/page.tsx:335` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [sparkHistory, displayQuote?.price_close]);` |
| 751 | FE-167 | P2 | `frontend/src/app/sync-settings/page.tsx:127` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, []);` |
| 752 | FE-168 | P2 | `frontend/src/app/sync-settings/page.tsx:141` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, []);` |
| 753 | FE-169 | P2 | `frontend/src/components/charts/TradingViewChart.tsx:405` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, [buildChart]);` |
| 754 | FE-170 | P2 | `frontend/src/components/gold/ThemeProvider.tsx:22` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const saved = (typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null) as Theme \| null;` |
| 755 | FE-171 | P2 | `frontend/src/components/gold/ThemeProvider.tsx:33` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY, theme);` |
| 756 | FE-172 | P2 | `frontend/src/hooks/useClientData.ts:30` | وابستگی useEffect ناقص [react-hooks/exhaustive-deps] | داده کهنه در UI یا حلقه بی‌پایان → تکمیل deps | `}, []);` |
| 757 | FE-173 | P2 | `frontend/src/hooks/useDebugLogs.ts:32` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const saved = localStorage.getItem(STORAGE_KEY);` |
| 758 | FE-174 | P2 | `frontend/src/hooks/useDebugLogs.ts:50` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY, JSON.stringify(logs.slice(0, maxLogs)));` |
| 759 | FE-175 | P2 | `frontend/src/hooks/useFileUpload.ts:104` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `const apiBase = process.env.NEXT_PUBLIC_API_URL \|\| 'http://localhost:8000/api/v1';` |
| 760 | FE-176 | P2 | `frontend/src/hooks/useNotificationSound.ts:33` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `setMuted(localStorage.getItem(storageKey) === "true");` |
| 761 | FE-177 | P2 | `frontend/src/hooks/useNotificationSound.ts:40` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(storageKey, String(next));` |
| 762 | FE-178 | P2 | `frontend/src/hooks/useTheme.ts:21` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const t = localStorage.getItem(STORAGE_KEY);` |
| 763 | FE-179 | P2 | `frontend/src/hooks/useTheme.ts:119` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY, next);` |
| 764 | FE-180 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:71` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const muted = localStorage.getItem(STORAGE_KEY_MUTED);` |
| 765 | FE-181 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:72` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const variant = localStorage.getItem(STORAGE_KEY_VARIANT) as SoundVariant \| null;` |
| 766 | FE-182 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:73` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const enabled = localStorage.getItem(STORAGE_KEY_ENABLED);` |
| 767 | FE-183 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:74` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const vol = localStorage.getItem(STORAGE_KEY_VOLUME);` |
| 768 | FE-184 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:90` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY_MUTED, String(this.state.muted));` |
| 769 | FE-185 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:91` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY_VARIANT, this.state.variant);` |
| 770 | FE-186 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:92` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY_ENABLED, String(this.state.enabled));` |
| 771 | FE-187 | P2 | `frontend/src/lib/sound/SoundEffectManager.ts:93` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY_VOLUME, String(this.state.volume));` |
| 772 | FE-188 | P2 | `frontend/src/lib/sync-settings.ts:49` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `const raw = localStorage.getItem(STORAGE_KEY);` |
| 773 | FE-189 | P2 | `frontend/src/lib/sync-settings.ts:72` | ذخیره داده در localStorage [TS_LOCALSTORAGE] | ریسک XSS و داده کهنه بین نسخه‌ها → حافظه/کوکی httpOnly | `localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));` |
| 774 | FE-190 | P2 | `frontend/src/middleware.ts:51` | آدرس localhost هاردکد در فرانت [TS_LOCALHOST] | در دسترسی از موبایل/شبکه کار نمی‌کند → مسیر نسبی | `"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.goo` |
| 775 | FE-191 | P3 | `frontend/src/__tests__/GoldBacktestPage.test.tsx:12` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import type { ReactNode } from "react";` |
| 776 | FE-192 | P3 | `frontend/src/__tests__/GoldPortfolioSafety.test.tsx:13` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import type { ReactNode } from "react";` |
| 777 | FE-193 | P3 | `frontend/src/__tests__/LiveChainPanel.test.tsx:18` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const apiGetMock = vi.fn((_url: string, _token?: unknown, _signal?: AbortSignal) =>` |
| 778 | FE-194 | P3 | `frontend/src/__tests__/LiveChainPanel.test.tsx:65` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `apiGetMock.mockImplementation((_url: string, _token?: unknown, _signal?: AbortSignal) =>` |
| 779 | FE-195 | P3 | `frontend/src/__tests__/fixtures/swHarness.ts:106` | خطای پارس/قاعده ESLint [parse] | فایل ممکن است هرگز بررسی نشود → رفع خطای پارس | `// eslint-disable-next-line no-new-func -- تست SW یعنی اجرای همین اسکریپت در sandbox` |
| 780 | FE-196 | P3 | `frontend/src/__tests__/useSymbolPrices.test.ts:14` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `constructor(_url: string) {` |
| 781 | FE-197 | P3 | `frontend/src/app/admin/page.tsx:8` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { Card, CardAction } from "@/components/ui/Card";` |
| 782 | FE-198 | P3 | `frontend/src/app/admin/page.tsx:166` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const outdatedCount = overviewEntries.filter(([, i]) => i.status === "outdated").length;` |
| 783 | FE-199 | P3 | `frontend/src/app/admin/page.tsx:179` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const handleToggleJob = useCallback(async (name: string) => {` |
| 784 | FE-200 | P3 | `frontend/src/app/admin/page.tsx:353` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const [toast, setToast] = useState<{ message: string; type: "success" \| "error" \| "warning" } \| null>(null);` |
| 785 | FE-201 | P3 | `frontend/src/app/admin/page.tsx:356` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `for (let i = 0; i < keys.length; i++) { const id = SECTION_ID_MAP[keys[i]]; try { const r = await apiPost<{ success: boo` |
| 786 | FE-202 | P3 | `frontend/src/app/admin/page.tsx:486` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const [page, setPage] = useState(1);` |
| 787 | FE-203 | P3 | `frontend/src/app/admin/page.tsx:487` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const { data: tblResp, isLoading } = useQuery({ queryKey: ["tables-list"], queryFn: async () => apiGet<unknown>("/tables` |
| 788 | FE-204 | P3 | `frontend/src/app/backtest/cascade/page.tsx:306` | setInterval دستی [TS_INTERVAL] | نشت تایمر/به‌روزرسانی تکراری در StrictMode → بررسی cleanup | `const iv = setInterval(async () => {` |
| 789 | FE-205 | P3 | `frontend/src/app/backtest/compose/page.tsx:52` | setInterval دستی [TS_INTERVAL] | نشت تایمر/به‌روزرسانی تکراری در StrictMode → بررسی cleanup | `const interval = setInterval(() => {` |
| 790 | FE-206 | P3 | `frontend/src/app/backtest/engine/page.tsx:375` | setInterval دستی [TS_INTERVAL] | نشت تایمر/به‌روزرسانی تکراری در StrictMode → بررسی cleanup | `const interval = setInterval(async () => {` |
| 791 | FE-207 | P3 | `frontend/src/app/backtest/full-scan/page.tsx:187` | setInterval دستی [TS_INTERVAL] | نشت تایمر/به‌روزرسانی تکراری در StrictMode → بررسی cleanup | `pollRef.current = setInterval(async () => {` |
| 792 | FE-208 | P3 | `frontend/src/app/backtest/generate/page.tsx:374` | setInterval دستی [TS_INTERVAL] | نشت تایمر/به‌روزرسانی تکراری در StrictMode → بررسی cleanup | `const interval = setInterval(async () => {` |
| 793 | FE-209 | P3 | `frontend/src/app/backtest/page.tsx:11` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `FlaskConical, Dices, FlaskRound, Cpu, Rocket, TrendingUp,` |
| 794 | FE-210 | P3 | `frontend/src/app/backtest/page.tsx:315` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/set-state-in-effect -- sync: adopt server strategies into form once` |
| 795 | FE-211 | P3 | `frontend/src/app/backtest/page.tsx:330` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 5000,` |
| 796 | FE-212 | P3 | `frontend/src/app/backtest/page.tsx:409` | JSON.parse بدون اعتبارسنجی [TS_JSON_PARSE] | استثنا در زمان اجرا → schema/zod | `const parsed = JSON.parse(saved) as string[];` |
| 797 | FE-213 | P3 | `frontend/src/app/backtest/page.tsx:425` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/exhaustive-deps` |
| 798 | FE-214 | P3 | `frontend/src/app/brsapi/history/[symbol]/page.tsx:170` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/set-state-in-effect -- intentional synchronous state reset on mount/filter chang` |
| 799 | FE-215 | P3 | `frontend/src/app/brsapi/history/[symbol]/page.tsx:172` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/exhaustive-deps` |
| 800 | FE-216 | P3 | `frontend/src/app/brsapi/history/[symbol]/page.tsx:176` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/set-state-in-effect -- intentional synchronous state reset on mount/filter chang` |
| 801 | FE-217 | P3 | `frontend/src/app/brsapi/history/[symbol]/page.tsx:178` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/exhaustive-deps` |
| 802 | FE-218 | P3 | `frontend/src/app/brsapi/page.tsx:6` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { Card, CardAction } from "@/components/ui/Card";` |
| 803 | FE-219 | P3 | `frontend/src/app/brsapi/page.tsx:256` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const queryClient = useQueryClient();` |
| 804 | FE-220 | P3 | `frontend/src/app/codal/accounting/[symbol]/page.tsx:11` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { formatDateShamsi } from "@/lib/dates";` |
| 805 | FE-221 | P3 | `frontend/src/app/codal/accounting/[symbol]/page.tsx:183` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const { data: ratiosData, isLoading: ratiosLoading } = useQuery({` |
| 806 | FE-222 | P3 | `frontend/src/app/codal/analysis/[symbol]/page.tsx:148` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const [tab, setTab] = useState<"market" \| "accounting">("market");` |
| 807 | FE-223 | P3 | `frontend/src/app/codal/audit/page.tsx:62` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const { data: stats, isLoading: stLoad } = useQuery({` |
| 808 | FE-224 | P3 | `frontend/src/app/codal/import/page.tsx:116` | JSON.parse بدون اعتبارسنجی [TS_JSON_PARSE] | استثنا در زمان اجرا → schema/zod | `resolve(JSON.parse(xhr.responseText));` |
| 809 | FE-225 | P3 | `frontend/src/app/codal/page.tsx:36` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `interface PaginatedResult<T> {` |
| 810 | FE-226 | P3 | `frontend/src/app/crypto-exchange/page.tsx:3` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { useState, useEffect } from "react";` |
| 811 | FE-227 | P3 | `frontend/src/app/crypto-exchange/page.tsx:25` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `interface TimeframeData {` |
| 812 | FE-228 | P3 | `frontend/src/app/crypto-exchange/page.tsx:45` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const isPositive = crypto.change_percent >= 0;` |
| 813 | FE-229 | P3 | `frontend/src/app/crypto-exchange/page.tsx:62` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img` |
| 814 | FE-230 | P3 | `frontend/src/app/crypto-exchange/page.tsx:288` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img` |
| 815 | FE-231 | P3 | `frontend/src/app/crypto-market/page.tsx:170` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img src={coin.icon_url} alt={coin.symbol} className="w-9 h-9 rounded-full shadow-lg" loading="lazy"` |
| 816 | FE-232 | P3 | `frontend/src/app/crypto-market/page.tsx:249` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img src={coin.icon_url} alt={coin.symbol} className="w-7 h-7 rounded-full" loading="lazy"` |
| 817 | FE-233 | P3 | `frontend/src/app/crypto/page.tsx:134` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img src={c.icon_url} alt={c.symbol} className="w-8 h-8 rounded-full" loading="lazy"` |
| 818 | FE-234 | P3 | `frontend/src/app/crypto/page.tsx:186` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img src={c.icon_url} alt="" className="w-6 h-6 rounded-full" loading="lazy"` |
| 819 | FE-235 | P3 | `frontend/src/app/crypto/page.tsx:229` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img src={c.icon_url} alt="" className="w-6 h-6 rounded-full" loading="lazy"` |
| 820 | FE-236 | P3 | `frontend/src/app/crypto/page.tsx:323` | img خام به‌جای next/image [@next/next/no-img-element] | کارایی تصویر → next/image | `<img src={c.icon_url} alt="" className="w-7 h-7 rounded-full" loading="lazy"` |
| 821 | FE-237 | P3 | `frontend/src/app/data-health/page.tsx:10` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `BarChart3,` |
| 822 | FE-238 | P3 | `frontend/src/app/data-health/page.tsx:15` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `RefreshCw,` |
| 823 | FE-239 | P3 | `frontend/src/app/decision-engine/page.tsx:361` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `{layers.map((layer, i) => (` |
| 824 | FE-240 | P3 | `frontend/src/app/economic-calendar/page.tsx:5` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import Link from "next/link";` |
| 825 | FE-241 | P3 | `frontend/src/app/economic-calendar/page.tsx:106` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const queryClient = useQueryClient();` |
| 826 | FE-242 | P3 | `frontend/src/app/fundamental/page.tsx:39` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line @typescript-eslint/no-explicit-any` |
| 827 | FE-243 | P3 | `frontend/src/app/funds/page.tsx:852` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/exhaustive-deps -- fire on URL change only` |
| 828 | FE-244 | P3 | `frontend/src/app/gold/coins/page.tsx:238` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const [watchlistEditing, setWatchlistEditing] = useState(false);` |
| 829 | FE-245 | P3 | `frontend/src/app/gold/coins/page.tsx:240` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const onAddSymbol = async () => {` |
| 830 | FE-246 | P3 | `frontend/src/app/gold/components/MacroPostureSection.tsx:185` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 5 * 60_000,` |
| 831 | FE-247 | P3 | `frontend/src/app/gold/futures/page.tsx:65` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 5000,` |
| 832 | FE-248 | P3 | `frontend/src/app/gold/physical/page.tsx:49` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 5000,` |
| 833 | FE-249 | P3 | `frontend/src/app/heatmap/page.tsx:3` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { useState, useCallback } from "react";` |
| 834 | FE-250 | P3 | `frontend/src/app/indicators/page.tsx:89` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/set-state-in-effect` |
| 835 | FE-251 | P3 | `frontend/src/app/indicators/page.tsx:91` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/exhaustive-deps` |
| 836 | FE-252 | P3 | `frontend/src/app/macro/page.tsx:73` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `Object.entries(INDICATOR_META).find(([_, v]) => v.label === indicator.name)?.[1];` |
| 837 | FE-253 | P3 | `frontend/src/app/market-depth/page.tsx:6` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { Card, CardAction } from "@/components/ui/Card";` |
| 838 | FE-254 | P3 | `frontend/src/app/market-depth/page.tsx:7` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import Skeleton from "@/components/Skeleton";` |
| 839 | FE-255 | P3 | `frontend/src/app/market-depth/page.tsx:24` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const [depthView, setDepthView] = useState<"count" \| "volume" \| "value">("count");` |
| 840 | FE-256 | P3 | `frontend/src/app/market-watch/page.tsx:103` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const bg = color === "emerald" ? "bg-accent-emerald/10" : "bg-accent-rose/10";` |
| 841 | FE-257 | P3 | `frontend/src/app/markets/commodity/page.tsx:14` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `DollarSign,` |
| 842 | FE-258 | P3 | `frontend/src/app/markets/gold/page.tsx:31` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `sma,` |
| 843 | FE-259 | P3 | `frontend/src/app/markets/gold/page.tsx:118` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 10 * 60_000,` |
| 844 | FE-260 | P3 | `frontend/src/app/markets/gold/page.tsx:229` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 2 * 60_000,` |
| 845 | FE-261 | P3 | `frontend/src/app/markets/gold/page.tsx:248` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 5 * 60_000,` |
| 846 | FE-262 | P3 | `frontend/src/app/markets/gold/page.tsx:302` | JSON.parse بدون اعتبارسنجی [TS_JSON_PARSE] | استثنا در زمان اجرا → schema/zod | `if (raw) setTrades(JSON.parse(raw) as Trade[]);` |
| 847 | FE-263 | P3 | `frontend/src/app/markets/indices/page.tsx:6` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { fmtInt, fmtPct } from "@/lib/market-format";` |
| 848 | FE-264 | P3 | `frontend/src/app/markets/options-market/page.tsx:195` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const putContracts = totalContracts - callContracts;` |
| 849 | FE-265 | P3 | `frontend/src/app/markets/silver/components/BacktestTab.tsx:169` | JSON.parse بدون اعتبارسنجی [TS_JSON_PARSE] | استثنا در زمان اجرا → schema/zod | `parsed = JSON.parse(paramsText \|\| "{}") as Record<string, unknown>;` |
| 850 | FE-266 | P3 | `frontend/src/app/markets/silver/components/GoldSilverRatioCard.tsx:7` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `interface PreciousItem {` |
| 851 | FE-267 | P3 | `frontend/src/app/markets/silver/components/TechnicalPanel.tsx:16` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const prev = candles[candles.length - 2];` |
| 852 | FE-268 | P3 | `frontend/src/app/ml/page.tsx:395` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `}, []); // eslint-disable-line react-hooks/exhaustive-deps` |
| 853 | FE-269 | P3 | `frontend/src/app/multi-market-signals/page.tsx:191` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const GRADE_COLORS: Record<string, string> = {` |
| 854 | FE-270 | P3 | `frontend/src/app/multi-market-signals/page.tsx:199` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const GRADE_LABELS: Record<string, string> = {` |
| 855 | FE-271 | P3 | `frontend/src/app/multi-market-signals/page.tsx:364` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `.map((e, i) => `${x(history.indexOf(e))},${yAcc(e.accuracy)}`)` |
| 856 | FE-272 | P3 | `frontend/src/app/multi-market-signals/page.tsx:369` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `.map((e, i) => `${x(history.indexOf(e))},${ySig(e.signals)}`)` |
| 857 | FE-273 | P3 | `frontend/src/app/multi-market-signals/page.tsx:604` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/set-state-in-effect -- intentional synchronous state reset on mount/filter chang` |
| 858 | FE-274 | P3 | `frontend/src/app/multi-market-signals/page.tsx:1130` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `{Object.entries(MARKET_LABELS).map(([market, label]) => {` |
| 859 | FE-275 | P3 | `frontend/src/app/news/page.tsx:3` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `import { useState, useEffect, useCallback } from "react";` |
| 860 | FE-276 | P3 | `frontend/src/app/news/page.tsx:41` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const [sourceFilter, setSourceFilter] = useState("");` |
| 861 | FE-277 | P3 | `frontend/src/app/news/page.tsx:107` | interval بازخوانی کوتاه [TS_POLL_FAST] | بار اضافی بدون تازه‌تر شدن منبع → interval تطبیقی | `refetchInterval: 2000,` |
| 862 | FE-278 | P3 | `frontend/src/app/news/page.tsx:118` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const allSources = news ? [...new Set(news.map((n: NewsItem) => n.source).filter(Boolean))].sort() : [];` |
| 863 | FE-279 | P3 | `frontend/src/app/news/page.tsx:133` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const paginated = filtered?.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE) \|\| [];` |
| 864 | FE-280 | P3 | `frontend/src/app/news/page.tsx:138` | disabled کردن eslint [TS_ESLINT_DISABLE] | قاعده کیفیت غیرفعال → رفع علت | `// eslint-disable-next-line react-hooks/set-state-in-effect` |
| 865 | FE-281 | P3 | `frontend/src/app/news/page.tsx:142` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const getSentimentColor = (sentiment_score: number) => {` |
| 866 | FE-282 | P3 | `frontend/src/app/news/page.tsx:148` | متغیر/پارامتر بی‌استفاده [@typescript-eslint/no-unused-vars] | نویز و نشانه کد ناتمام → حذف | `const getSentimentDot = (sentiment_score: number) => {` |

## PROC — پردازش، پارسر و یکپارچگی داده (117 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 867 | PROC-001 | P0 | `core/enums/provider.py:29` | مقدار محرمانه هاردکد [PY_HARDCODED_SECRET] | افشای اعتبارنامه در مخزن → secret manager | `API_KEY = "api_key"` |
| 868 | PROC-002 | P1 | `apps/admin/dashboard.py:101` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 869 | PROC-003 | P1 | `apps/admin/dashboard.py:142` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 870 | PROC-004 | P1 | `apps/admin/dashboard.py:161` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 871 | PROC-005 | P1 | `apps/admin/dashboard.py:177` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 872 | PROC-006 | P1 | `apps/admin/dashboard.py:194` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 873 | PROC-007 | P1 | `apps/admin/dashboard.py:210` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 874 | PROC-008 | P1 | `apps/admin/dashboard.py:221` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 875 | PROC-009 | P1 | `apps/admin/dashboard.py:235` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 876 | PROC-010 | P1 | `apps/admin/dashboard.py:266` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 877 | PROC-011 | P1 | `apps/admin/dashboard.py:305` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 878 | PROC-012 | P1 | `apps/admin/health.py:47` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 879 | PROC-013 | P1 | `apps/admin/health.py:69` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 880 | PROC-014 | P1 | `apps/admin/health.py:93` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 881 | PROC-015 | P1 | `apps/admin/health.py:125` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception as exc:` |
| 882 | PROC-016 | P1 | `apps/admin/health.py:135` | except Exception بدون re-raise [PY_BROAD_EXCEPT_SWALLOW] | خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند → لاگ ساختارمند + شکست صریح/متریک | `except Exception:` |
| 883 | PROC-017 | P1 | `apps/analytics_worker/app.py:17` | حلقه انتظار فعال (busy wait) در async [ASYNC110] | مصرف CPU و تأخیر سایر وظایف → asyncio.Event | `while self._running:` |
| 884 | PROC-018 | P1 | `apps/backtest_worker/app.py:17` | حلقه انتظار فعال (busy wait) در async [ASYNC110] | مصرف CPU و تأخیر سایر وظایف → asyncio.Event | `while self._running:` |
| 885 | PROC-019 | P1 | `apps/ml_worker/app.py:17` | حلقه انتظار فعال (busy wait) در async [ASYNC110] | مصرف CPU و تأخیر سایر وظایف → asyncio.Event | `while self._running:` |
| 886 | PROC-020 | P1 | `apps/worker/app.py:33` | حلقه انتظار فعال (busy wait) در async [ASYNC110] | مصرف CPU و تأخیر سایر وظایف → asyncio.Event | `while self._running:` |
| 887 | PROC-021 | P1 | `config/timeframes.py:36` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception:` |
| 888 | PROC-022 | P1 | `core/concurrency/batching.py:28` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(self._flush())` |
| 889 | PROC-023 | P1 | `core/concurrency/batching.py:39` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(self._flush())` |
| 890 | PROC-024 | P1 | `core/database.py:151` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `Path(settings.data_dir).mkdir(parents=True, exist_ok=True)` |
| 891 | PROC-025 | P1 | `core/seed.py:15` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception:` |
| 892 | PROC-026 | P1 | `core/seed.py:27` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception:` |
| 893 | PROC-027 | P1 | `core/seed.py:29` | try/except/pass — خطا کاملاً بلعیده می‌شود [S110] | شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند → لاگ + بازگرداندن خطا یا شمارش | `except Exception:` |
| 894 | PROC-028 | P1 | `domain/options/signals.py:291` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 895 | PROC-029 | P1 | `providers/historical/file_archive/csv_provider.py:34` | open مسدودکننده در تابع async [ASYNC230] | event loop بلاک می‌شود → to_thread / aiofiles | `with open(path, encoding="utf-8") as f:` |
| 896 | PROC-030 | P1 | `providers/historical/file_archive/csv_provider.py:48` | open مسدودکننده در تابع async [ASYNC230] | event loop بلاک می‌شود → to_thread / aiofiles | `with open(path, "w", newline="", encoding="utf-8") as f:` |
| 897 | PROC-031 | P1 | `providers/historical/file_archive/json_provider.py:34` | open مسدودکننده در تابع async [ASYNC230] | event loop بلاک می‌شود → to_thread / aiofiles | `with open(path, encoding="utf-8") as f:` |
| 898 | PROC-032 | P1 | `providers/historical/file_archive/json_provider.py:45` | open مسدودکننده در تابع async [ASYNC230] | event loop بلاک می‌شود → to_thread / aiofiles | `with open(path, "w", encoding="utf-8") as f:` |
| 899 | PROC-033 | P1 | `providers/reference/manual/file_importer.py:19` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if not path.exists():` |
| 900 | PROC-034 | P1 | `providers/reference/manual/file_importer.py:32` | open مسدودکننده در تابع async [ASYNC230] | event loop بلاک می‌شود → to_thread / aiofiles | `with open(path, encoding="utf-8") as f:` |
| 901 | PROC-035 | P1 | `providers/reference/manual/file_importer.py:41` | open مسدودکننده در تابع async [ASYNC230] | event loop بلاک می‌شود → to_thread / aiofiles | `with open(path, encoding="utf-8") as f:` |
| 902 | PROC-036 | P1 | `services/adjusted_price_reader.py:135` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `await session.execute(text(f"SELECT to_regclass('public.{ADJUSTED_VIEW}')"))` |
| 903 | PROC-037 | P1 | `services/auto_retrain_pipeline.py:152` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 904 | PROC-038 | P1 | `services/auto_retrain_pipeline.py:170` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r2 = await session.execute(text(f"""` |
| 905 | PROC-039 | P1 | `services/auto_retrain_pipeline.py:386` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 906 | PROC-040 | P1 | `services/auto_retrain_pipeline.py:405` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r2 = await session.execute(text(f"""` |
| 907 | PROC-041 | P1 | `services/backtest_framework.py:149` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 908 | PROC-042 | P1 | `services/cascade_engine.py:361` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 909 | PROC-043 | P1 | `services/cascade_engine.py:371` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 910 | PROC-044 | P1 | `services/chat/chart_generator.py:66` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 911 | PROC-045 | P1 | `services/chat/chart_generator.py:95` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 912 | PROC-046 | P1 | `services/chat/news_fetcher.py:187` | کتابخانه requests در کد async/سرویس [PY_SYNC_REQUESTS] | I/O مسدودکننده در مسیر درخواست → httpx.AsyncClient | `resp = requests.get(url, params={"key": self._brsapi_key, "l18": symbol, "days": days_back},` |
| 913 | PROC-047 | P1 | `services/codal_download_service.py:201` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if os.path.exists(filepath) and os.path.getsize(filepath) > 100:` |
| 914 | PROC-048 | P1 | `services/codal_financial_import_service.py:42` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if not os.path.isdir(CODAL_EXCEL_DIR):` |
| 915 | PROC-049 | P1 | `services/codal_financial_import_service.py:49` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if os.path.isdir(dir_path):` |
| 916 | PROC-050 | P1 | `services/codal_import_service.py:223` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if not dir_path.is_dir():` |
| 917 | PROC-051 | P1 | `services/codal_import_service.py:227` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `files = sorted(list(dir_path.glob("*.xlsx")) + list(dir_path.glob("*.csv")))` |
| 918 | PROC-052 | P1 | `services/codal_import_service.py:241` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `content = fp.read_bytes()` |
| 919 | PROC-053 | P1 | `services/confidence_scorer.py:353` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 920 | PROC-054 | P1 | `services/diagnostics_runner.py:401` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 921 | PROC-055 | P1 | `services/fund_circuit_breaker.py:197` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:  # noqa: BLE001` |
| 922 | PROC-056 | P1 | `services/fund_read_through.py:219` | نتیجه asyncio.create_task ذخیره نمی‌شود [RUF006] | تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود → نگه‌داشتن رفرنس تا اتمام | `asyncio.create_task(self._rebuild_universe_background())` |
| 923 | PROC-057 | P1 | `services/history_backfill_service.py:156` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"""` |
| 924 | PROC-058 | P1 | `services/inference_service.py:214` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 925 | PROC-059 | P1 | `services/inference_service.py:226` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 926 | PROC-060 | P1 | `services/materialized_view_service.py:25` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `await session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))` |
| 927 | PROC-061 | P1 | `services/multi_timeframe_confirmer.py:239` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 928 | PROC-062 | P1 | `services/news_tag_symbol_mapper.py:212` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"SELECT symbol FROM {table} WHERE id = :i"), {"i": param}` |
| 929 | PROC-063 | P1 | `services/probability_calibrator.py:234` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 930 | PROC-064 | P1 | `services/probability_calibrator.py:415` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 931 | PROC-065 | P1 | `services/probability_calibrator.py:599` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 932 | PROC-066 | P1 | `services/quant_signal_orchestrator.py:307` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 933 | PROC-067 | P1 | `services/quant_signal_orchestrator.py:354` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 934 | PROC-068 | P1 | `services/quant_signal_orchestrator.py:364` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 935 | PROC-069 | P1 | `services/quant_signal_orchestrator.py:953` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 936 | PROC-070 | P1 | `services/quant_signal_orchestrator.py:1886` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r2 = await session.execute(text(f"""` |
| 937 | PROC-071 | P1 | `services/queue_analysis_service.py:275` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 938 | PROC-072 | P1 | `services/quote_import_service.py:294` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `if not dir_path.is_dir():` |
| 939 | PROC-073 | P1 | `services/quote_import_service.py:298` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `csv_files = sorted(dir_path.glob("*.csv"))` |
| 940 | PROC-074 | P1 | `services/quote_import_service.py:312` | فراخوانی مسدودکننده فایل در تابع async [ASYNC240] | event loop بلاک و زمان‌بندی وظایف مختل می‌شود → asyncio.to_thread | `content = file.read_bytes()` |
| 941 | PROC-075 | P1 | `services/risk_adjusted_filter.py:217` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 942 | PROC-076 | P1 | `services/screener_service.py:782` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `text(f"""` |
| 943 | PROC-077 | P1 | `services/signal_accuracy_tracker.py:199` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 944 | PROC-078 | P1 | `services/signal_backtest_engine.py:304` | SQL ساخته‌شده با f-string [PY_SQL_FSTRING] | نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است → شناسه‌های مجاز را allowlist و مقادیر را bind کنید | `r = await session.execute(text(f"""` |
| 945 | PROC-079 | P1 | `services/stock_assistant_service.py:1972` | try/except/continue — خطا نادیده گرفته می‌شود [S112] | ردیف معیوب بی‌صدا حذف می‌شود → ثبت خطا و متریک | `except Exception:` |
| 946 | PROC-080 | P2 | `apps/funds/db.py:37` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert _engine is not None` |
| 947 | PROC-081 | P2 | `apps/funds/db.py:44` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert _session_factory is not None, "call init_db() first"` |
| 948 | PROC-082 | P2 | `apps/funds/db.py:50` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert _session_factory is not None, "call init_db() first"` |
| 949 | PROC-083 | P2 | `apps/funds/resilience.py:158` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert last_exc is not None` |
| 950 | PROC-084 | P2 | `core/database.py:162` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `"Set the DATABASE_URL in your .env file (e.g. postgresql+asyncpg://user:pass@localhost:5432/dbname) "` |
| 951 | PROC-085 | P2 | `core/database.py:166` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `"SQLite cannot be used. Set the DATABASE_URL in your .env file (e.g. postgresql+asyncpg://user:pass@localhost:5432/dbnam` |
| 952 | PROC-086 | P2 | `core/database.py:167` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `"in your .env file. Note: PostgreSQL must be running on localhost:5432."` |
| 953 | PROC-087 | P2 | `core/database.py:176` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `"Please ensure PostgreSQL is running on localhost:5432. "` |
| 954 | PROC-088 | P2 | `core/fix_network.py:5` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `Windows has ``ProxyEnable=1`` in the registry with ``ProxyServer=127.0.0.1:57630``` |
| 955 | PROC-089 | P2 | `domain/pricing_version/calc_version.py:14` | فراخوانی subprocess [PY_SUBPROCESS] | ریسک تزریق/وابستگی سیستمی → بازبینی ورودی | `return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()` |
| 956 | PROC-090 | P2 | `providers/funds/client.py:218` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `base_url = getattr(settings, "fund_api_base_url", "http://localhost:8500/api/funds")` |
| 957 | PROC-091 | P2 | `providers/gold_spot/brsapi.py:93` | httpx.Client همگام [PY_SYNC_HTTPX_CLIENT] | بلاک شدن worker در async → AsyncClient | `return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True` |
| 958 | PROC-092 | P2 | `providers/gold_spot/yahoo.py:91` | httpx.Client همگام [PY_SYNC_HTTPX_CLIENT] | بلاک شدن worker در async → AsyncClient | `return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True` |
| 959 | PROC-093 | P2 | `providers/macro_sources/cftc.py:179` | httpx.Client همگام [PY_SYNC_HTTPX_CLIENT] | بلاک شدن worker در async → AsyncClient | `return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True` |
| 960 | PROC-094 | P2 | `providers/macro_sources/fred.py:208` | httpx.Client همگام [PY_SYNC_HTTPX_CLIENT] | بلاک شدن worker در async → AsyncClient | `return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True` |
| 961 | PROC-095 | P2 | `providers/news/parser.py:33` | پارس XML با پیکربندی ناامن [S314] | ریسک XXE → defusedxml | `root = ET.fromstring(feed_xml)` |
| 962 | PROC-096 | P2 | `providers/news/rss/rss_parser.py:47` | پارس XML با پیکربندی ناامن [S314] | ریسک XXE → defusedxml | `root = ET.fromstring(raw_xml)` |
| 963 | PROC-097 | P2 | `providers/reference/codal/attachment_extractor.py:71` | پارس XML با پیکربندی ناامن [S314] | ریسک XXE → defusedxml | `root = ET.fromstring(content)` |
| 964 | PROC-098 | P2 | `services/chat/news_fetcher.py:180` | httpx.Client همگام [PY_SYNC_HTTPX_CLIENT] | بلاک شدن worker در async → AsyncClient | `with httpx.Client() as client:` |
| 965 | PROC-099 | P2 | `services/codal_financial_statement_import.py:97` | datetime.now بدون timezone [PY_NAIVE_NOW] | ذخیره زمان بی‌ناحیه و مقایسه نادرست تازگی → datetime.now(UTC یا Tehran) | `report_date = (published_at or datetime.now()).strftime("%Y-%m-%d")` |
| 966 | PROC-100 | P2 | `services/fund_circuit_breaker.py:84` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")` |
| 967 | PROC-101 | P2 | `services/fund_compliance.py:53` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `base = created_at or datetime.utcnow()` |
| 968 | PROC-102 | P2 | `services/fund_compliance.py:296` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `{"str_id": int(row[0]), "submitted_at": str(datetime.utcnow())},` |
| 969 | PROC-103 | P2 | `services/fund_ledger.py:159` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `effective_at = effective_at or datetime.utcnow()` |
| 970 | PROC-104 | P2 | `services/fund_nav_reconciliation.py:577` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `"sla": datetime.utcnow() + timedelta(days=sla_days),` |
| 971 | PROC-105 | P2 | `services/fund_nav_reconciliation.py:686` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `resolved = datetime.utcnow() if lifecycle in ("RESOLVED", "ACCEPTED") else None` |
| 972 | PROC-106 | P2 | `services/gold/feed_health.py:162` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert result is not None` |
| 973 | PROC-107 | P2 | `services/news_source_health.py:52` | datetime.now بدون timezone [PY_NAIVE_NOW] | ذخیره زمان بی‌ناحیه و مقایسه نادرست تازگی → datetime.now(UTC یا Tehran) | `# so comparing stored values against Python's datetime.now() can be` |
| 974 | PROC-108 | P2 | `services/pre_buy_service.py:299` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `updated_at=datetime.utcnow(),` |
| 975 | PROC-109 | P2 | `services/pre_buy_service.py:332` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `sheet.updated_at = now or datetime.utcnow()` |
| 976 | PROC-110 | P2 | `services/pre_buy_service.py:357` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `now = now or datetime.utcnow()` |
| 977 | PROC-111 | P2 | `services/pre_buy_service.py:399` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `now = datetime.utcnow()` |
| 978 | PROC-112 | P2 | `services/pre_buy_service.py:422` | datetime.utcnow منسوخ و naive [PY_UTCNOW] | تاریخ‌های بی‌ناحیه → datetime.now(UTC) | `sheet.updated_at = datetime.utcnow()` |
| 979 | PROC-113 | P2 | `services/resample_timeframes.py:22` | assert در کد اجرایی [PY_ASSERT] | با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود → raise صریح | `assert timeframe in RULES, timeframe` |
| 980 | PROC-114 | P2 | `services/smart_money/layer8_microstructure.py:15` | متغیر محلی تخصیص‌یافته اما بی‌استفاده [F841] | نشانه منطق نیمه‌کاره یا محاسبه دورریخته → حذف یا استفاده صحیح | `ab = quote.get("avg_buy", 0.0) or 1.0` |
| 981 | PROC-115 | P2 | `services/smart_money/layer8_microstructure.py:16` | متغیر محلی تخصیص‌یافته اما بی‌استفاده [F841] | نشانه منطق نیمه‌کاره یا محاسبه دورریخته → حذف یا استفاده صحیح | `as_ = quote.get("avg_sell", 0.0) or 1.0` |
| 982 | PROC-116 | P2 | `services/smart_money/layer8_microstructure.py:20` | متغیر محلی تخصیص‌یافته اما بی‌استفاده [F841] | نشانه منطق نیمه‌کاره یا محاسبه دورریخته → حذف یا استفاده صحیح | `h = quote.get("price_high", 0.0)` |
| 983 | PROC-117 | P2 | `services/smart_money/layer8_microstructure.py:21` | متغیر محلی تخصیص‌یافته اما بی‌استفاده [F841] | نشانه منطق نیمه‌کاره یا محاسبه دورریخته → حذف یا استفاده صحیح | `low = quote.get("price_low", 0.0)` |

## SEC — امنیت و پیکربندی (5 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 984 | SEC-001 | P1 | `apps/api/app.py:959` | CORS از تنظیمات می‌آید و allow_credentials=True است | اگر CORS_ORIGINS=* تنظیم شود، مرورگر کوکی را رد می‌کند و نشست می‌شکند. → اعتبارسنجی صریح: ستاره با credentials ممنوع. | `allow_origins=settings.cors_origins,` |
| 985 | SEC-002 | P1 | `core/config/api.py:16` | یک کلاس تنظیمات دوم با پیش‌فرض * برای CORS وجود دارد | بسته به اینکه کدام settings ایمپورت شود، پیش‌فرض امن یا باز است. → حذف کلاس تکراری و تک‌منبع‌سازی تنظیمات. | `cors_origins: list[str] = Field(default=["*"], alias="CORS_ORIGINS")` |
| 986 | SEC-003 | P0 | `core/config/__init__.py:120` | SECRET_KEY پیش‌فرض committed دارد | اگر env ست نشود، توکن‌ها با کلید عمومی قابل جعل‌اند. → حذف پیش‌فرض و fail-fast در همه محیط‌ها. | `secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")` |
| 987 | SEC-004 | P2 | `apps/api/app.py:952` | مستندات OpenAPI در تولید هم فعال است | سطح حمله و افشای ساختار داخلی. → غیرفعال‌سازی docs در production. | `docs_url="/docs",` |
| 988 | SEC-005 | P2 | `frontend/src/lib/goldApi.ts:407` | توکن دسترسی برای WebSocket به‌صورت query parameter ارسال می‌شود | توکن در لاگ سرور/پروکسی ثبت می‌شود. → استفاده از subprotocol یا کوکی. | `return `${root.replace(/\/$/, "")}/gold/ws${token ? `?token=${encodeURIComponent(token)}` : ""}`;` |

## OBS — پایش، آزمون و پیکربندی محیط (12 مورد)

| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |
|---|---|---|---|---|---|---|
| 989 | OBS-001 | P1 | `apps/api/router.py:24` | health سرویس تازگی داده را نمی‌سنجد | سرویس سالم گزارش می‌شود در حالی که داده روزها قدیمی است. → health شامل last_sync_at, data_age, source_status. | `{"path": "/health", "tag": "Health", "description": "Health check"},` |
| 990 | OBS-002 | P2 | `core/config/__init__.py:445` | اعتبارسنجی تولید فقط بخشی از ریسک‌ها را می‌گیرد و به تازگی داده کاری ندارد | استقرار می‌تواند «سالم» باشد ولی هیچ داده تازه‌ای نداشته باشد. → افزودن precondition تازگی داده به چک‌لیست استقرار. | `errors.append("CORS_ORIGINS must be restricted in production")` |
| 991 | OBS-003 | P2 | `core/config/__init__.py:84` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `database_url: str = Field(default="postgresql+asyncpg://market:market@localhost:5432/market", alias="DATABASE_URL")` |
| 992 | OBS-004 | P2 | `core/config/__init__.py:92` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")` |
| 993 | OBS-005 | P2 | `core/config/__init__.py:117` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `default=["http://localhost:3000"], alias="CORS_ORIGINS"` |
| 994 | OBS-006 | P2 | `core/config/database.py:10` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `url: str = Field(default="postgresql+asyncpg://market:market@localhost:5432/market", alias="DATABASE_URL")` |
| 995 | OBS-007 | P2 | `core/config/database.py:19` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")` |
| 996 | OBS-008 | P2 | `integrations/filesystems/s3_compatible_storage.py:116` | پارس XML با پیکربندی ناامن [S314] | ریسک XXE → defusedxml | `root = ET.fromstring(resp.text)` |
| 997 | OBS-009 | P2 | `integrations/observability/error_reporter.py:59` | httpx.Client همگام [PY_SYNC_HTTPX_CLIENT] | بلاک شدن worker در async → AsyncClient | `with httpx.Client(timeout=10.0) as client:` |
| 998 | OBS-010 | P2 | `integrations/search/aliases.py:15` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `self._base_url = (base_url or "http://localhost:9200").rstrip("/")` |
| 999 | OBS-011 | P2 | `integrations/search/index_client.py:17` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `self._base_url = (base_url or "http://localhost:9200").rstrip("/")` |
| 1000 | OBS-012 | P2 | `integrations/search/query_client.py:16` | آدرس localhost هاردکد [PY_HARDCODED_LOCAL] | در کانتینر/تولید به مقصد اشتباه می‌رود → env | `self._base_url = (base_url or "http://localhost:9200").rstrip("/")` |

---

## پیوست — بازبینی ادعاهای مسیر ingestion (DATA-013 تا DATA-026)

ادعاهای یک تحلیل قبلی روی همین مخزن دوباره با کد فعلی مقایسه شد. سه مورد در این نسخه برقرار نیستند؛
آن‌ها را دور نزنید، اما به‌عنوان باگ موجود هم ثبت نکنید.

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-013 (محدودیت ۵ نماد) | رد شد | `ingestion/worker.py:58` | هیچ برش `[:5]` وجود ندارد؛ حلقه روی همه نمادهاست. مشکل واقعی برعکس است: هر tick همه نمادها فراخوانی می‌شوند. |
| DATA-014 (کش نمادها تازه نمی‌شود) | تأیید شد | `ingestion/sources/tsetmc.py:47` | تا وقتی `_instruments` پر باشد همان فهرست برگردانده می‌شود؛ refresh ساعتی worker بی‌اثر است. |
| DATA-015 (dedup قبل از ذخیره) | رد شد | `ingestion/worker.py:154` | `mark_seen` اکنون بعد از `_write_event` موفق صدا زده می‌شود. |
| DATA-016 (retry خطاهای aiohttp) | تأیید شد | `ingestion/retry.py:23-27` | فقط TimeoutError/ConnectionError/ConnectionResetError؛ ClientConnectorError پوشش ندارد. |
| DATA-017 (نادیده گرفتن market_timezone) | تأیید شد | `ingestion/scheduler.py:56` | افست +۳:۳۰ هاردکد شده و تنظیمات خوانده نمی‌شود. |
| DATA-018 (زمان fetch در parser) | تأیید شد | `ingestion/parser/tsetmc_parsers.py:25,71,113` و `worker.py:127` | زمان parse جای زمان fetch می‌نشیند. |
| DATA-019 (یک رکورد خراب، کل payload) | تأیید شد | `ingestion/worker.py:127` + `tsetmc_parsers.py:52` | `int()` روی مقدار خام است و try دور کل parse است. |
| DATA-020 (None شدن مقدار خراب) | تأیید شد | `ingestion/parser/tsetmc_parsers.py:163` | `_to_decimal` هر استثنا را می‌بلعد. |
| DATA-021 (تاریخچه به‌عنوان trade_tick) | منقضی شد | `ingestion/parser/tsetmc_parsers.py:78` | اکنون `event_type="daily_ohlcv"` است؛ ادعای قبلی با کد امروز نمی‌خواند. |
| DATA-022 (نبود کلید یکتا در trade_ticks) | تأیید ساختاری | `ingestion/db/models.py:38-50` | درست است، اما مسیر فعلی parser چیزی در این جدول نمی‌نویسد؛ اثر عملی محدود است. |
| DATA-023 (append شدن snapshotها) | تأیید شد | `ingestion/storage/__init__.py:32` | `INSERT` بدون upsert برای هر poll. |
| DATA-024 (به‌روز نشدن fetched_at در upsert) | تأیید شد | `ingestion/storage/__init__.py:74-82` | فهرست SET شامل fetched_at نیست. |
| DATA-025 (تکرار orderbook) | تأیید شد | `ingestion/storage/__init__.py:55` | هر سطح با INSERT ساده و بدون snapshot_id ثبت می‌شود. |
| DATA-026 (جدا بودن مسیر ingestion از heatmap) | تأیید شد | `ingestion/storage/__init__.py` در برابر `apps/api/endpoints/market.py:261` | storage در جدول‌های ingestion می‌نویسد؛ heatmap از جدول‌های BrsApi می‌خواند. |

### دستهٔ دوم: DATA-027 تا DATA-040 (سرویس sync و کوئری‌های خواندن)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-027 (پاسخ خالی = موفقیت بدون commit) | تأیید شد | `brsapi/services/sync_service.py:388-403` | شاخهٔ `is_empty` هم `status=success` می‌نویسد و هم بدون commit برمی‌گردد. |
| DATA-028 (خروجی نامعتبر پارسر) | تأیید شد | `brsapi/services/sync_service.py:429-445` | نوع غیر list/dict به `records=[]` تبدیل و «موفق با صفر رکورد» ثبت می‌شود. |
| DATA-029 (rollback گستردهٔ سه بخش) | تأیید شد | `brsapi/services/sync_service.py:1352` + `:1382` | rollback در خطا + commit نهایی روی همان session؛ تغییرات بخش‌های قبلی هم از دست می‌رود. |
| DATA-030 (truncate قبل از اعتبارسنجی) | تأیید با جابه‌جایی محل | `brsapi/services/sync_service.py:1468` | مسیر Gold_Currency عادی اکنون upsert است، اما مسیر Gold_Currency_Pro هنوز `truncate()` سپس insert می‌کند. |
| DATA-031 (sparkline با success=true) | منقضی شد | `apps/api/endpoints/market.py:239` | اکنون `success=result.success` است؛ ادعای قبلی با کد امروز نمی‌خواند. |
| DATA-032 (شاخص بر اساس created_at) | تأیید شد | `brsapi/services/query_service.py:385` | MAX(created_at) معیار انتخاب است، نه fetched_at. |
| DATA-033 (NAV بر اساس created_at) | تأیید شد | `brsapi/services/query_service.py:430` | مرتب‌سازی با created_at و limit 1؛ تاریخ NAV نقشی ندارد. |
| DATA-034 (همهٔ snapshotهای اختیار) | تأیید شد | `brsapi/services/query_service.py:437-444` | فقط فیلتر underlying_symbol و مرتب‌سازی date_end. |
| DATA-035 (سهام‌داران بر اساس درصد) | تأیید شد | `brsapi/services/query_service.py:765` | `percent DESC LIMIT 50` بدون انتخاب آخرین snapshot. |
| DATA-036 (معاملات درون‌روزی بدون فیلتر روز) | تأیید شد | `brsapi/services/query_service.py:786` | مرتب‌سازی با created_at و بدون شرط trade_date. |
| DATA-037 (کالاها: کل تاریخچه) | تأیید شد | `brsapi/services/query_service.py:542` و `apps/api/endpoints/brsapi.py:70` | `latest_only` وجود دارد اما پیش‌فرض False است و چند فراخوان آن را ست نمی‌کنند. |
| DATA-038 (رمزارز بدون آخرین رکورد) | تأیید شد | `brsapi/services/query_service.py:713-720` | مرتب‌سازی با rank و limit؛ هر symbol می‌تواند چند بار بیاید. |
| DATA-039 (IME: کل تاریخچه) | تأیید نسبی | `brsapi/services/query_service.py:601-624` | کوئری‌ها همهٔ ردیف‌ها را می‌خوانند؛ تکرار واقعی به dedup سمت sync بستگی دارد. |
| DATA-040 (fallback غیرقابل وقوع) | تأیید شد | `brsapi/services/query_service.py:100-109` و `:304` + `brsapi/models/tsetmc.py:49` | شرط `ins_id IS NULL` با nullable=False هرگز برقرار نمی‌شود؛ هم fallback پایتونی و هم JOIN SQL بی‌اثرند. |

### دستهٔ سوم: DATA-041 تا DATA-054 (اندپوینت بازار و اندیکاتورها)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-041 (heatmap: سقف ۱۰۰) | تأیید شد | `apps/api/endpoints/market.py:120` | `get_latest_snapshots(limit=100)` ثابت است و پارامتری ندارد. |
| DATA-042 (heatmap غنی: سقف ۵۰۰) | تأیید شد | `apps/api/endpoints/market.py:261` | بدون صفحه‌بندی و بدون total. |
| DATA-043 (آمار کل بازار از ۵۰۰) | تأیید شد | `services/market_service.py:35-53` | `total = len(snapshots)` روی همان ۵۰۰ ردیف. |
| DATA-044 (خلاصه صنایع: ۲۰۰ و avg=0) | تأیید شد | `services/market_service.py:109` و `:133` | سقف ۲۰۰ و `sec["avg_change"] = 0`. |
| DATA-045 (ترتیب sparkline) | تأیید شد | `services/market_service.py:778-787` | `ORDER BY symbol, date DESC` و بدون reverse. |
| DATA-046 (sparkline با success=true) | رد شد | `apps/api/endpoints/market.py:239` | کد فعلی `success=result.success` است؛ این ادعا با DATA-031 تکراری و منقضی است. |
| DATA-047 (فیلتر تاریخ بعد از limit) | تأیید شد | `services/market_service.py:217` | ابتدا limit=500 سپس فیلتر Python. |
| DATA-048 (تاریخ محلی و limit*3) | تأیید شد | `services/market_service.py:325-326` | `date.today()` بدون timezone و بازه تقویمی. |
| DATA-049 (MACD fast>slow) | تأیید شد | `services/market_service.py:503` | `offset = slow - fast` بدون اعتبارسنجی رابطه. |
| DATA-050 (Ichimoku ناهم‌تراز) | تأیید شد | `services/market_service.py:668-671` | senkou_b بدون شیفت و chikou با برش ساده. |
| DATA-051 (Stochastic K/D) | تأیید شد | `services/market_service.py:561-562` | D از SMA روی K ساخته می‌شود (کوتاه‌تر)؛ تاریخ با طول K هم‌تراز می‌شود. |
| DATA-052 (close=price_last) | تأیید شد | `services/market_service.py:285` | `price_close` در `_to_ohlcv` استفاده نمی‌شود. |
| DATA-053 (نام فیلد صنعت) | تأیید شد | `services/market_service.py:125` | مدل `sector` می‌دهد، کد `sector_name`/`industry` می‌خواند → همه در «سایر». |
| DATA-054 (macro موفق بدون data) | تأیید شد | `services/market_service.py:907` | `Result.ok({indicator, country})` بدون کلید data. |

### دستهٔ چهارم: DATA-055 تا DATA-068 (هوک‌های فرانت و تجمیع جریان)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-055 (Promise.all در کارت‌ها) | رد شد | `frontend/src/hooks/useMarketData.ts:430` | کد فعلی `Promise.allSettled` است؛ اما خطای هر منبع بی‌صدا حذف می‌شود و isError نمی‌شود — مشکل باقی است، با مکانیزم متفاوت. |
| DATA-056 (بازار جهانی → []) | تأیید نسبی | `frontend/src/hooks/useMarketData.ts:501-521` | دیگر catch خالی نیست؛ allSettled خطا را می‌بلعد و isError=false می‌ماند. |
| DATA-057 (rangeIdx بی‌استفاده) | رد شد | `frontend/src/hooks/useMarketData.ts:536-545` | rangeIdx به limitMap نگاشت و در URL استفاده می‌شود. |
| DATA-058 (treemap: خطا = خالی) | تأیید نسبی | `frontend/src/hooks/useMarketData.ts:571-583` | isError برگردانده می‌شود، اما از heuristic «طول صفر» ساخته می‌شود؛ empty و error قاطی می‌شوند. |
| DATA-059 (جریان حقیقی/حقوقی) | تأیید شد | `frontend/src/hooks/useMarketData.ts:613-617` | success:false → warn → [] (بدون حالت خطا در hook). |
| DATA-060 (خلاصه جریان) | تأیید نسبی | `frontend/src/hooks/useMarketData.ts:638-648` | isError/isLoading برگردانده می‌شوند، اما catch خالی و null دوحالته است. |
| DATA-061 (تقویم اقتصادی) | تأیید شد | `frontend/src/hooks/useMarketData.ts:679-684` | success:false → warn → []؛ خطا از «بدون رویداد» تفکیک نمی‌شود. |
| DATA-062 (sparkline با success=true) | رد شد | `apps/api/endpoints/market.py:239` | سومین بار همین ادعا؛ کد فعلی `success=result.success` است. |
| DATA-063 (MAX(id) برای آخرین snapshot) | تأیید شد | `brsapi/services/query_service.py:111` | مکان ادعا (۱۴۰-۱۶۶) جابه‌جا شده، محتوا درست است. |
| DATA-064 (limit قبل از join) | تأیید شد | `brsapi/services/query_service.py:123-128` | limit روی زیرکوئری نمادها اعمال و سپس join انجام می‌شود. |
| DATA-065 (ابهام symbol/ins_id) | تأیید نسبی | `brsapi/services/query_service.py:312` | یک پارامتر symbol روی دو ستون symbol و ins_id مقایسه می‌شود. |
| DATA-066 (ترتیب تاریخچه شاخص) | تأیید شد | `brsapi/services/query_service.py:407` + `apps/api/endpoints/market.py:473` | DESC در سرویس و reverse در endpoint. |
| DATA-067 (جریان بازار روی ۵۰۰) | تأیید شد | `apps/api/endpoints/market.py:364-365` | limit پیش‌فرض ۵۰۰ و تجمیع روی همان نمونه. |
| DATA-068 (isLive کارت‌ها) | تأیید شد | `frontend/src/hooks/useMarketData.ts:470` | `isLive: rows.length > 0` بدون بررسی سن داده. |

### دستهٔ پنجم: DATA-069 تا DATA-082 (پایش، WebSocket، backfill، سلامت)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-069 (baseUrl=localhost) | تأیید شد | `frontend/src/hooks/useApiMonitor.ts:10` | پیش‌فرض `http://localhost:8000` است. |
| DATA-070 (آنلاین = HTTP 200) | تأیید شد | `frontend/src/hooks/useApiMonitor.ts:26-33` | بدنهٔ /health بررسی نمی‌شود؛ liveness با readiness قاطی می‌شود. |
| DATA-071 (subscription با تغییر نمادها) | تأیید شد | `frontend/src/hooks/useWebSocket.ts:128-133` و effect با deps=[] | subscribe فقط در onopen ارسال می‌شود. |
| DATA-072 (Date.now جای timestamp منبع) | تأیید شد | `frontend/src/hooks/useWebSocket.ts:137` | هر پیام timestamp مرورگر می‌گیرد. |
| DATA-073 (پیام نامعتبر بی‌صدا) | تأیید شد | `frontend/src/hooks/useWebSocket.ts:141` | catch خالی با کامنت Ignore. |
| DATA-074 (خطای polling backfill) | تأیید شد | `frontend/src/hooks/useBackgroundBackfill.ts:63-74` | catch → undefined بدون state خطا. |
| DATA-075 (running بدون تأیید) | تأیید شد | `frontend/src/hooks/useBackgroundBackfill.ts:95` | state پیش از بررسی started تنظیم می‌شود. |
| DATA-076 (خطای شروع backfill) | تأیید شد | `frontend/src/hooks/useBackgroundBackfill.ts:96-103` | catch → undefined. |
| DATA-077 (لغو بدون تأیید) | تأیید شد | `frontend/src/hooks/useBackgroundBackfill.ts:106-113` | نتیجهٔ لغو و وضعیت سرور بازخوانی نمی‌شود. |
| DATA-078 (ناسازگاری ready/full) | تأیید شد | `apps/api/endpoints/health.py:109` | فقط `db_status != ok` مقدار overall را تغییر می‌دهد. |
| DATA-079 (null_check≠null) | تأیید شد | `apps/api/endpoints/monitoring.py:45` | `null_check` همان `staleness < 300` است. |
| DATA-080 (dead-letter صفر کاذب) | تأیید شد | `apps/api/endpoints/ingestion.py:62-64` | `dl_len=0` با suppress و success=True. |
| DATA-081 (SQLite جدا در quotes) | تأیید شد | `apps/api/endpoints/quotes.py:192-196` | engine جدید در هر درخواست و بدون dispose. |
| DATA-082 (افشای str(exc)) | تأیید شد | `apps/api/endpoints/symbols.py:165` | `Server error: {exc}` در پاسخ JSON. |

### دستهٔ ششم: DATA-083 تا DATA-091 (ذخیرهٔ قیمت، اسکن بازار، ارز)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-083 (save_quotes شکست جزئی) | تأیید شد | `services/quote_service.py:132-137` | فقط موفق‌ها شمرده و همیشه `Result.ok(count)` برمی‌گردد. |
| DATA-084 (ingest_historical پیاده‌سازی نشده) | تأیید شد (بدون call-site) | `services/quote_service.py:87-95` | در این نسخه هیچ فراخواننده‌ای ندارد؛ اثر عملی فعلی کم است. |
| DATA-085 (صفر برای فیلد غایب) | تأیید شد | `services/quote_service.py:59-70` | `float(data.get(..., 0))` برای قیمت/حجم/ارزش. |
| DATA-086 (فیلتر اخبار بعد از صفحه‌بندی) | رد شد | `apps/api/endpoints/news.py:179-181` | دسته قبل از `list_all` نرمال و به سرویس پاس می‌شود؛ total هم فیلترشده است. |
| DATA-087 (ناهمگونی fallback اخبار) | رد شد | `apps/api/endpoints/news.py:208-210` | fallback هم از `canonical_category` استفاده می‌کند. |
| DATA-088 (اسکن بدون warm sink) | تأیید شد | `ingestion/market_scan_service.py:55-57` | بدون session_factory  مقدار `_warm_sink` برابر None می‌شود و فقط hot می‌ماند. |
| DATA-089 (scan_once بی‌صدا None) | تأیید شد | `ingestion/market_scan_service.py:128-130` | شکست/خالی بدون لاگ علت برمی‌گردد. |
| DATA-090 (ارز: fallback با timestamp تازه) | تأیید شد | `apps/currency_service/infra/collectors.py:117-119` | fixture + jitter ±۰٫۳٪ و `datetime.now(UTC)`. |
| DATA-091 (خطای ارز فقط در log) | تأیید شد | `apps/currency_service/infra/collectors.py:71-73` و `:96-98` | هر دو collector استثنا را می‌بلعند و None برمی‌گردانند. |

### دستهٔ هفتم: DATA-092 تا DATA-100 (jobها و صف Redis)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-092 (QuoteIngestionJob همیشه موفق) | تأیید شد | `jobs/definitions/market_data_jobs.py:22` | فقط موفق‌ها شمرده می‌شوند؛ `success_result` بی‌قید. |
| DATA-093 (HistoricalDataJob همیشه موفق) | تأیید شد | `jobs/definitions/market_data_jobs.py:35` | با DATA-084 ترکیب می‌شود: تابع همیشه fail است ولی job همیشه سبز. |
| DATA-094 (RealtimeQuoteJob) | تأیید شد | `jobs/definitions/market_data_jobs.py:47` | تعداد موفق گزارش می‌شود، وضعیت نه. |
| DATA-095 (SyncQuotesJob بدون بررسی گزارش) | تأیید شد | `jobs/definitions/sync_jobs.py:117-134` | `success/error` هر دو report نادیده گرفته می‌شود. |
| DATA-096 (ack در finally) | تأیید شد | `jobs/queue_consumer.py:158-164` | `finally: await self._ack_message(...)`. |
| DATA-097 (fallback BRPOP بدون processing) | تأیید شد | `jobs/queue_consumer.py:188-198` | پیام در مسیر BRPOP به processing نمی‌رود. |
| DATA-098 (شکست requeue + ack) | تأیید شد | `jobs/queue_consumer.py:295-299` + `:160-164` | خطای lpush به finally می‌رسد و ack انجام می‌شود. |
| DATA-099 (is_available سطحی) | تأیید شد | `jobs/queue_publisher.py:79-81` و `jobs/queue_consumer.py:100-102` | فقط None نبودن client. |
| DATA-100 (stubهای legacy) | تأیید شد | `jobs/definitions/sync_jobs.py:192-206` | سه تابع `completed` با count=0. |

### دستهٔ هشتم: DATA-101 تا DATA-106 (اتصال scheduler به صف، startup کارگر، از دست رفتن job)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-101 (فقدان fallback برای jobهای BrsApi) | تأیید شد | `brsapi/jobs/registry.py:504-506` + `apps/scheduler/app.py:69` | `publish()` در `_run_handler` بدون بررسی نتیجه صدا زده می‌شود. |
| DATA-102 (worker بدون Redis برای همیشه idle) | تأیید شد | `apps/worker/consumer.py:30-35` + `core/cache.py:108-110` | شکست `initialize()` مقدار `_redis` را None نگه می‌دارد و هیچ retry دوره‌ای نیست. |
| DATA-103 (پیام با token نامعتبر حذف می‌شود) | تأیید شد | `jobs/queue_consumer.py:234-240` + `:165-166` | `return` بدون `_dead_letter` و سپس ack در `finally`. |
| DATA-104 (پیام خراب بدون dead-letter) | تأیید شد | `jobs/queue_consumer.py:227-231` | فقط log و شمارنده؛ مسیر `_dead_letter` فراخوانی نمی‌شود. |
| DATA-105 (سلامت سطحی صف) | تأیید شد | `jobs/queue_consumer.py:104-105` و `jobs/queue_publisher.py:79-81` | هر دو فقط `self._redis() is not None` را می‌سنجند؛ همین شرط شروع worker را کنترل می‌کند. |
| DATA-106 (Redis بدون healthcheck در compose) | تأیید شد | `docker-compose.yml:25-32` + `:44-45` | سرویس redis هیچ healthcheck ندارد و depends_on فقط `service_started` است. |

#### یافته‌های تازه‌ای که هنگام تأیید همین دسته پیدا شد

| # | یافته | محل | چرا مهم است |
|---|---|---|---|
| ۱ | worker image ماژولی را اجرا می‌کند که نقطهٔ ورودی ندارد | `Dockerfile.worker:56` | `python -m apps.worker.app` بلافاصله با کد ۰ خارج می‌شود؛ هیچ jobی مصرف نمی‌شود. |
| ۲ | worker کلاس‌های job را register نمی‌کند | `apps/worker/app.py:32` در برابر `apps/scheduler/app.py:61` | registry در فرآیند worker خالی است؛ هر job صف‌شده «not found» و سپس dead-letter می‌شود. |
| ۳ | نام jobهای BrsApi با کلید registry یکی نیست | `brsapi/jobs/registry.py:119` در برابر `jobs/definitions/brsapi_jobs.py:103` | `brsapi_all_symbols` منتشر می‌شود اما کلید ثبت‌شده `BrsApiAllSymbolsJob` است. |
| ۴ | گیت ساعات بازار در مسیر صف اعمال نمی‌شود | `jobs/definitions/brsapi_jobs.py:41` | با اصلاح نام‌ها، jobها خارج از ساعت بازار هم اجرا می‌شوند و سهمیهٔ رایگان می‌سوزد. |

نکته: DATA-106 همان ردیف `DEP-016` است (Redis بدون healthcheck + `service_started`) و برای پرهیز از تکرار، ردیف تازه‌ای برایش ساخته نشد؛ ادعا در جدول بالا تأیید می‌شود.

### دستهٔ نهم: ROOT-001 تا ROOT-005 (زنجیرهٔ استقرار)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| ROOT-001 (backend کانتینر API نیست) | تأیید شد (با تصحیح خط) | `docker-compose.yml:36-39` + `Dockerfile:41` → پیش‌تر `DEP-001` | ادعا درست است؛ فقط شمارهٔ خط `Dockerfile:14` اشتباه است (فرمان در خط ۴۱ است). |
| ROOT-002 (DSN مناسب کانتینر ندارد) | تأیید و تشدید شد | میزبان: `DATA-012` — پیشوند و scheme: `DEP-021` و `DEP-022` | سه مانع مستقل: پیشوند `INGESTION_`، میزبان `localhost:5433`، و scheme ای که asyncpg رد می‌کند. |
| ROOT-003 (فرمان worker بدون entry point) | تأیید شد (پیش‌تر ثبت) | `Dockerfile.worker:56` → `DEP-020` | خودمان اجرا کردیم: `python -m apps.worker.app` با کد ۰ و بی‌خروجی برمی‌گردد. |
| ROOT-004 (registry در worker پر نمی‌شود) | تأیید شد (پیش‌تر ثبت) | `apps/worker/app.py:32` → `SCH-025` / `SCH-026` | در فرآیند تازه `list_names()` صفر است؛ پس از ثبت ۶۶ job باز هم `brsapi_all_symbols` پیدا نمی‌شود. |
| ROOT-005 (Dockerfile فرانت‌اند غایب) | تأیید شد (با قید) | `docker-compose.yml:117-121` → پیش‌تر `DEP-004` | در حالت پایه درست است؛ اگر override اعمال شود `Dockerfile.dev` موجود است، ولی خود override نامعتبر است. |
| override نامعتبر (نه ادعای ROOT، ولی در همان زنجیره) | تأیید شد (پیش‌تر ثبت) | `docker-compose.override.yml:6` → پیش‌تر `DEP-005` | اجرای واقعی `docker compose config` شکست می‌خورد: سرویس‌های `api`/`admin`/`postgres`/`scheduler` image یا build ندارند. |

### دستهٔ دهم: DATA-151 تا DATA-162 (انتخاب رکورد جاری)

| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-151 (سهام‌داران از کل تاریخ) | تأیید شد — از قبل `DB-009` | `brsapi/services/query_service.py:766` | `percent DESC LIMIT 50` بدون انتخاب آخرین تاریخ گزارش. |
| DATA-152 (معاملات درون‌روزی تکراری/قدیمی) | تأیید شد — از قبل `DB-010` | `brsapi/services/query_service.py:788` | مرتب‌سازی با `created_at`، بدون فیلتر `trade_date` و بدون کلید یکتا. |
| DATA-153 (پاسخ ناقص داده قبلی را حذف می‌کند) | منقضی در محل ذکرشده | `brsapi/services/sync_service.py:1328` | مسیر Gold_Currency عادی اکنون upsert است؛ ادعا به محل قدیمی اشاره دارد. |
| DATA-154 (ثبت موفقیت برای پاسخ خالی) | تأیید شد — از قبل `DATA-041` | `brsapi/services/sync_service.py:388-408` + `repositories/base.py:82-83` | `record()` فقط flush می‌کند و شاخهٔ خالی commit ندارد. |
| DATA-155 (sparkline همیشه success=True) | رد شد — سومین تکرار | `apps/api/endpoints/market.py:239` | کد فعلی `success=result.success` است (قبلاً `DATA-031/046/062`). |
| DATA-156 (آخرین شاخص با created_at) | تأیید شد — از قبل `DB-006` | `brsapi/services/query_service.py:385` | مدل `fetched_at` دارد ولی query از `MAX(created_at)` می‌آید. |
| DATA-157 (truncate قبل از اعتبارسنجی) | منقضی در محل ذکرشده | `brsapi/services/sync_service.py:1468` → پیش‌تر `DATA-044` | truncate در مسیر Pro بخش‌به‌بخش هنوز هست؛ الگوی کلی در `:465` باقی است. |
| DATA-158 (قیمت جاری کالا با تاریخچه) | تأیید شد — از قبل `DB-011` | `brsapi/services/query_service.py:644` | `latest_only` پیش‌فرض False و `market_dashboard` آن را نمی‌دهد. |
| DATA-159 (چند نسخه از یک رمزارز) | تأیید شد — از قبل `DB-012` | `brsapi/services/query_service.py:713-720` | بدون dedup و بدون on_conflict؛ هر sync ردیف تازه می‌سازد. |
| DATA-160 (تکرار قراردادهای بورس کالا) | تأیید شد — از قبل `DB-013` | `brsapi/services/query_service.py:601-623` | همهٔ ردیف‌ها بدون انتخاب آخرین نسخه برمی‌گردند. |
| DATA-161 (fallback اتصال نماد) | تأیید شد — از قبل `DB-014` | `brsapi/services/query_service.py:304` | `ins_id` در snapshot `nullable=False` است، پس شرط `IS NULL` هرگز برقرار نمی‌شود. |
| DATA-162 (heatmap فقط ۵۰۰ نماد) | تأیید شد — از قبل `API-006` | `apps/api/endpoints/market.py:261` | `limit=500` ثابت و کش هم با کلید `enriched-heatmap:500`. |

ده مورد از این دوازده ادعا از قبل ردیف کاتالوگ دارند (DB-006، DB-009…DB-014، API-006، DATA-041/044)؛ دو مورد به محل قدیمی اشاره می‌کنند و یک مورد (sparkline) سومین بار رد می‌شود. فقط یک ردیف تازه ساخته شد: `DATA-052` (truncation کل جدول به‌ازای هر نماد).

### دستهٔ یازدهم: DATA-168 تا DATA-184 (نمایش و محاسبات)

هر ۱۷ ادعای این دسته از قبل ردیف کاتالوگ دارند؛ هیچ ردیف تازه‌ای ساخته نشد. شماره‌خط‌های گزارش به نسخهٔ قدیمی‌تر اشاره می‌کنند (مثلاً isLive از ۴۲۳-۴۷۰ به ۲۸۱/۳۱۳ و heatmap از ۱۰۶ به ۱۲۰).

| ادعا | وضعیت | محل واقعی امروز | توضیح |
|---|---|---|---|
| DATA-168 (heatmap فقط ۱۰۰ نماد) | تکراری — `API-005` | `apps/api/endpoints/market.py:120` | همان سقف ثابت ۱۰۰ و بدون پارامتر limit. |
| DATA-169 (خلاصه صنایع: ۲۰۰ و avg=0) | تکراری — `API-009` + `DATA-044` | `services/market_service.py:109,135` | سقف ۲۰۰ و `sec["avg_change"] = 0`. |
| DATA-170 (MACD fast>slow) | تکراری — `API-014` | `services/market_service.py:501` | `offset = slow - fast` بدون اعتبارسنجی رابطه‌ای. |
| DATA-171 (Ichimoku ناهم‌تراز) | تکراری — `API-015` | `services/market_service.py:668-671` | senkou/chikou بدون شیفت و با طول‌های متفاوت. |
| DATA-172 (Stochastic K/D) | تکراری — `API-016` | `services/market_service.py:562` | D از SMA روی K ساخته می‌شود و کوتاه‌تر است. |
| DATA-173 (فیلد صنعت) | تکراری — `API-010` | `services/market_service.py:125` | مدل `sector` می‌دهد، کد `sector_name`/`industry` می‌خواند. |
| DATA-174 (macro بدون کلید data) | تکراری — `API-018` | `services/market_service.py:907` | `Result.ok` بدون data و با success. |
| DATA-175 (isLive از وجود ردیف) | تکراری — `FE-006` | `useMarketData.ts:281, 313` (نه ۴۲۳-۴۷۰) | هر دو hook مقدار را از طول آرایه می‌سازند. |
| DATA-176 (fixture ارز با زمان تازه) | تکراری — `DATA-090` | `apps/currency_service/infra/collectors.py:112-115` | `or fixture.free` سپس `timestamp=datetime.now(UTC)`. |
| DATA-177 (خطای ارز بلعیده می‌شود) | تکراری — `DATA-091` | `collectors.py:72,97` | هر دو collector فقط warning و None برمی‌گردانند. |
| DATA-178 (تاریخچه پیاده‌سازی نشده) | تکراری — `DATA-084` | `services/quote_service.py:94-96` | `Historical ingestion not implemented yet` و بدون call-site. |
| DATA-179 (صفر برای فیلد غایب) | تکراری — `DATA-085` | `services/quote_service.py:59-70` | الگوی `data.get(..., 0)` برای قیمت و حجم. |
| DATA-180 (SyncQuotesJob همیشه موفق) | تکراری — `DATA-095` | `jobs/definitions/sync_jobs.py:109-130` | `success/error` هر دو report نادیده گرفته می‌شود. |
| DATA-181 (RealtimeQuoteJob) | تکراری — `SCH-012` | `jobs/definitions/market_data_jobs.py:47` | فقط موفق‌ها شمرده می‌شوند و `success_result` بی‌قید برمی‌گردد. |
| DATA-182 (stubهای legacy) | تکراری — `SCH-019` | `jobs/definitions/sync_jobs.py:192-206` | سه تابع `completed` با count=0. |
| DATA-183 (سلامت سطحی Redis) | تکراری — `SCH-018`/`SCH-024` | `jobs/queue_publisher.py:80` + `jobs/queue_consumer.py:105` | فقط None نبودن client. |
| DATA-184 (فقدان پیام در retry) | تکراری — `SCH-016`/`DATA-098` | `jobs/queue_consumer.py:165-166, 286-303` | خطای lpush به `finally` می‌رسد و ack انجام می‌شود. |

#### شواهد اجرایی محدود (بدون بالا آوردن سرویس‌ها)

- `python -m apps.worker.app` در همین محیط با کد ۰ و بدون هیچ خروجی برمی‌گردد؛ یعنی همان CMD ایمیج worker هیچ حلقه‌ای اجرا نمی‌کند.
- در یک فرآیند تازه، `job_registry.list_names()` برابر ۰ و `get('SyncQuotesJob')` برابر `None` است.
- پس از `register_module(jobs.definitions)` تعداد ۶۶ job ثبت می‌شود، اما `get('brsapi_all_symbols')` هنوز `None` است (تأیید نامطابقی نام صف و کلید registry).
- `docker compose config` با خطای `service "api" has neither an image nor a build context specified: invalid compose project` برمی‌گردد؛ یعنی ترکیب فایل پایه و override معتبر نیست.
- `asyncpg.create_pool('postgresql+asyncpg://...')` با `ClientConfigurationError: scheme is expected to be either "postgresql" or "postgres"` رد می‌شود.


---

## روش تولید و محدودیت‌ها

1. ردیف‌های «تأییدشده» با خواندن همان فایل و همان خط در این نسخه نوشته شده‌اند.
2. ردیف‌های ruff با اجرای `ruff check --select E,F,W,B,S,SIM,UP,C4,RET,ASYNC,PL,PT,RUF,I,N` روی
   `brsapi apps ingestion jobs core domain services api repositories providers orchestration monitoring integrations contracts schemas config` تولید شده‌اند.
3. ردیف‌های eslint با اجرای `eslint src -f json` روی `frontend/src` تولید شده‌اند.
4. ردیف‌های «الگو» با اسکن regex روی همان درخت‌ها ساخته شده‌اند؛ هر ردیف الگوی واقعی را در خط واقعی نشان می‌دهد،
   اما قضاوت درباره شدت آن نیازمند بررسی زمینه است.
5. این گزارش **اثبات اجرایی محیط شما نیست**: نه سرویس‌ها اجرا شده‌اند و نه دیتابیس/Redis واقعی خوانده شده است.
   برای قطعی‌کردن علت، خروجی `docker compose ps -a`، لاگ سرویس‌ها و `MAX(fetched_at)` جدول snapshot لازم است.
