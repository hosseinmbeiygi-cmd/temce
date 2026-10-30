"""Hand-verified findings for the temce audit.

Each entry is anchored to a real code fragment; the report builder resolves the
anchor to an exact line number and quotes the real source line, so no location
in the final report is guessed.
"""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append(
        dict(cat=cat, file=file, anchor=anchor, occ=occ, title=title, sev=sev,
             status=status, impact=impact, fix=fix)
    )


# ───────────────────────────── DEP: deployment wiring ─────────────────────────────
add("DEP", "Dockerfile", r'CMD \["python", "-m", "ingestion.main"\]', 1,
    "ایمیج اصلی به‌جای FastAPI موتور ingestion را اجرا می‌کند",
    "P0", "تأییدشده",
    "سرویس backend روی پورت 8000 هیچ API‌ای سرو نمی‌کند؛ فرانت‌اند پاسخ نمی‌گیرد.",
    "برای سرویس backend از Dockerfile.api یا command صریح uvicorn استفاده شود.")
add("DEP", "docker-compose.yml", r"dockerfile: Dockerfile$", 1,
    "سرویس backend روی Dockerfile اصلی (بدون uvicorn) ساخته می‌شود",
    "P0", "تأییدشده",
    "ترکیب Compose پایه، API را بالا نمی‌آورد.",
    "dockerfile: Dockerfile.api و command uvicorn تنظیم شود.")
add("DEP", "docker-compose.yml", r"NEXT_PUBLIC_API_URL=http://backend:8000", 1,
    "آدرس داخلی Docker به‌عنوان آدرس عمومی API به فرانت تزریق می‌شود",
    "P0", "تأییدشده",
    "مرورگر کاربر نمی‌تواند نام backend را resolve کند؛ درخواست‌ها شکست می‌خورند.",
    "NEXT_PUBLIC_API_URL حذف و مسیر نسبی /api/v1 با rewrite سمت سرور Next استفاده شود.")
add("DEP", "docker-compose.yml", r"context: \./frontend", 1,
    "کانتکست build فرانت به پوشه‌ای اشاره می‌کند که Dockerfile ندارد",
    "P0", "تأییدشده",
    "docker compose build frontend با خطا متوقف می‌شود.",
    "از dockerfile: ../Dockerfile.frontend با context ریشه، یا افزودن frontend/Dockerfile استفاده شود.")
add("DEP", "docker-compose.override.yml", r"^  api:", 1,
    "override سرویس api را بدون image/build تعریف می‌کند",
    "P0", "تأییدشده",
    "docker compose config با «service api has neither image nor build» شکست می‌خورد.",
    "سرویس api با build/Dockerfile.api در فایل پایه تعریف شود.")
add("DEP", "docker-compose.override.yml", r"^  admin:", 1,
    "سرویس admin فقط در override تعریف شده و در فایل پایه وجود ندارد",
    "P0", "تأییدشده",
    "ترکیب Compose نامعتبر است؛ admin هرگز بالا نمی‌آید.",
    "سرویس admin با image و build در فایل پایه اضافه شود.")
add("DEP", "docker-compose.override.yml", r"^  scheduler:", 1,
    "سرویس scheduler بدون image/build در override تعریف شده",
    "P0", "تأییدشده",
    "زمان‌بند مستقل در استقرار Compose اجرا نمی‌شود.",
    "سرویس scheduler با Dockerfile.scheduler در فایل پایه تعریف شود.")
add("DEP", "docker-compose.override.yml", r"^  postgres:", 1,
    "override سرویس postgres را تعریف می‌کند ولی فایل پایه نام سرویس را timescaledb گذاشته",
    "P1", "تأییدشده",
    "پورت دیتابیس دو بار bind می‌شود یا سرویس اضافی/بی‌استفاده ساخته می‌شود.",
    "نام سرویس‌ها یکسان‌سازی شود (postgres یا timescaledb).")
add("DEP", "docker-compose.production.yml", r"NEXT_PUBLIC_API_URL: http://nginx/api/v1", 1,
    "در تولید آدرس API به نام داخلی nginx تنظیم شده است",
    "P1", "تأییدشده",
    "اگر این متغیر در باندل مرورگر درج شود، مرورگر nginx را resolve نمی‌کند.",
    "مسیر نسبی /api/v1 استفاده شود و پروکسی در همان دامنه بماند.")
add("DEP", "docker-compose.production.yml", r"driver: cloudstor:aws", 1,
    "volume درایور مخصوص Swarm/cloudstor دارد",
    "P2", "تأییدشده",
    "docker compose معمولی نمی‌تواند این volume را بسازد.",
    "برای Compose از درایور local و برای Swarm فایل جدا استفاده شود.")
add("DEP", "docker-compose.production.yml", r"^  observability:", 1,
    "شبکه observability به‌صورت external تعریف شده و باید از قبل وجود داشته باشد",
    "P2", "تأییدشده",
    "استقرار روی میزبان تازه با خطای network not found متوقف می‌شود.",
    "شبکه در همان فایل ساخته یا precondition در اسکریپت استقرار بررسی شود.")
add("DEP", "docker-compose.production.yml", r"replicas: 2", 1,
    "API در تولید دو replica دارد و هر replica زمان‌بند درون‌فرایندی می‌سازد",
    "P0", "تأییدشده",
    "دو زمان‌بند موازی به‌علاوه سرویس scheduler = سه نقطه اجرای وظایف و مصرف سه‌برابر سهمیه.",
    "زمان‌بندی فقط در سرویس scheduler انجام شود و در API غیرفعال گردد.")
add("DEP", "docker-compose.yml", r"^version: '3.8'", 1,
    "کلید version در Compose v2 منسوخ است",
    "P3", "تأییدشده",
    "هشدار منسوخ‌شدن در هر اجرا.",
    "حذف کلید version.")
add("DEP", "docker-compose.yml", r"image: timescale/timescaledb:latest-pg15", 1,
    "ایمیج دیتابیس با تگ latest-pg15 پین نشده",
    "P2", "تأییدشده",
    "ارتقای ناخواسته ایمیج می‌تواند داده/رفتار را بشکند.",
    "تگ دقیق نسخه + digest پین شود.")
add("DEP", "docker-compose.yml", r"container_name: tse_backend", 1,
    "container_name ثابت امکان scale کردن سرویس را می‌گیرد",
    "P2", "تأییدشده",
    "docker compose up --scale backend=N با تعارض نام شکست می‌خورد.",
    "حذف container_name و اتکا به نام سرویس.")
add("DEP", "docker-compose.yml", r"condition: service_started", 1,
    "backend فقط به شروع Redis (نه سالم بودن آن) وابسته است",
    "P2", "تأییدشده",
    "در اولین ثانیه‌ها اتصال Redis شکست می‌خورد و قفل/صف بی‌صدا غیرفعال می‌شود.",
    "healthcheck برای redis و condition: service_healthy اضافه شود.")
add("DEP", "Dockerfile", r"COPY \*\.py \./", 1,
    "همه اسکریپت‌های ریشه وارد ایمیج تولید می‌شوند",
    "P2", "تأییدشده",
    "فایل‌های موقت (z.py، fix_*.py، probe‌ها) در ایمیج اجرایی حاضرند و سطح حمله را بالا می‌برند.",
    "فقط entrypoint‌های لازم کپی شوند.")
add("DEP", "Dockerfile", r"^USER app", 1,
    "ایمیج اصلی healthcheck ندارد",
    "P2", "تأییدشده",
    "Docker/ orchestrator وضعیت سرویس را تشخیص نمی‌دهد.",
    "HEALTHCHECK مشابه Dockerfile.api اضافه شود.")
add("DEP", "Dockerfile", r"COPY services/ \./services/", 1,
    "ایمیج اصلی پوشه‌های reports/storage/tabdeal/app را کپی نمی‌کند",
    "P2", "نیازمند آزمون",
    "اگر ingestion به این پکیج‌ها import داشته باشد، در کانتینر ImportError رخ می‌دهد.",
    "فهرست COPY با Dockerfile.api یکسان شود.")

# ───────────────────────────── DATA: source + fetch ─────────────────────────────
add("DATA", "brsapi/config.py", r"enabled: bool = Field\(", 1,
    "کلید اصلی BrsApi به‌صورت پیش‌فرض فعال است اما در .env.example مستند نشده",
    "P0", "تأییدشده",
    "اپراتور نمی‌داند کلید توقف وجود دارد؛ در حالت مسدودی سهمیه، خطاهای تکراری تولید می‌شود.",
    "BRSAPI_ENABLED در .env.example با توضیح و پیش‌فرض امن مستند شود.")
add("DATA", "brsapi/client.py", r"if not brsapi_settings\.enabled:", 1,
    "در حالت disabled هیچ درخواست زنده‌ای زده نمی‌شود و فقط خطا برمی‌گردد",
    "P0", "تأییدشده",
    "با BRSAPI_ENABLED=false داده هرگز تازه نمی‌شود؛ API همچنان داده قدیمی می‌دهد.",
    "پایش صریح روی این حالت + نمایش هشدار در UI و health.")
add("DATA", "brsapi/client.py", r'"error": "BrsApi disabled via BRSAPI_ENABLED=false', 1,
    "health check در حالت disabled خطا برمی‌گرداند نه وضعیت degraded",
    "P1", "تأییدشده",
    "مانیتورینگ بین «سرویس خراب» و «عمداً غیرفعال» تفاوت نمی‌گذارد.",
    "وضعیت DB_ONLY به‌عنوان حالت مشخص در health گزارش شود.")
add("DATA", "brsapi/config.py", r"global_daily_limit: int = Field\(default=4000", 1,
    "سقف روزانه ۴۰۰۰ درخواست با نظرات کد درباره سقف واقعی ۵۰۰۰ هم‌راستا نیست",
    "P1", "تأییدشده",
    "یا زودتر از موعد متوقف می‌شود یا سهمیه واقعی را رد می‌کند.",
    "سقف بر اساس پلن واقعی در یک منبع واحد تعریف شود.")
add("DATA", "ingestion/main.py", r"self\._parsers\.register\(TsetmcMarketWatchParser\(\)\)", 1,
    "فقط ۷ پارسر ثبت می‌شود در حالی که ۱۲ منبع در همان فایل ثبت می‌شوند",
    "P1", "تأییدشده",
    "برای ifb/ime_energy/options/futures/codal پارسر وجود ندارد و داده خام بی‌استفاده می‌ماند.",
    "برای هر منبع فعال، پارسر متناظر ثبت یا منبع غیرفعال شود.")
add("DATA", "ingestion/main.py", r'"ifb": IFBSource\(self\._http\)', 1,
    "منبع ifb در فهرست منابع هست ولی پارسر آن در رجیستری نیست",
    "P1", "تأییدشده",
    "پاسخ دریافت و در lake ذخیره می‌شود اما رکوردی در دیتابیس ساخته نمی‌شود.",
    "افزودن پارسر IFB یا حذف منبع از enabled_sources.")
add("DATA", "ingestion/worker.py", r'logger\.warning\("No parser for source=%s endpoint=%s"', 1,
    "نبودن پارسر فقط warning است و جریان با موفقیت ادامه می‌یابد",
    "P1", "تأییدشده",
    "دریافت داده بدون ذخیره ساختاریافته، بی‌صدا «موفق» شمرده می‌شود.",
    "شمارش خطا و گزارش شکست در متریک ingestion.")
add("DATA", "ingestion/worker.py", r"count \+= len\(events\)", 1,
    "شمارنده رویدادها حتی وقتی نوشتن در دیتابیس شکست خورده افزایش می‌یابد",
    "P0", "تأییدشده",
    "گزارش «تعداد رکورد ذخیره‌شده» کاذب است و مشکل داده قدیمی را پنهان می‌کند.",
    "شمارش فقط پس از write موفق.")
add("DATA", "ingestion/worker.py", r'logger\.exception\("Failed to write event for %s", instrument_id\)', 1,
    "در except از متغیر تعریف‌نشده instrument_id استفاده می‌شود",
    "P0", "تأییدشده",
    "NameError داخل except خطای اصلی را می‌پوشاند و مسیر خطا کاملاً مبهم می‌شود.",
    "استفاده از ins_id و ثبت exc_info.")
add("DATA", "ingestion/worker.py", r"if self\._identity and self\._storage:", 1,
    "نوشتن رویداد به وجود هم‌زمان identity resolver و storage مشروط شده",
    "P1", "تأییدشده",
    "اگر یکی از این دو مقدار None باشد، هیچ داده‌ای نوشته نمی‌شود ولی ingestion ادامه می‌دهد.",
    "در startup صریحاً fail شود یا حالت بدون DB اعلام گردد.")
add("DATA", "ingestion/lake/__init__.py", r'or self\._config\.lake_secret_key == "minioadmin"', 1,
    "راه‌اندازی ingestion به MinIO با اعتبار پیش‌فرض وابسته است",
    "P0", "تأییدشده",
    "در محیطی که MinIO وجود ندارد (Compose پایه) موتور قبل از دریافت داده متوقف می‌شود.",
    "MinIO به compose اضافه یا lake اختیاری/محلی شود.")
add("DATA", "ingestion/config.py", r'default="postgresql\+asyncpg://postgres:postgres@localhost:5433/marketdb"', 1,
    "DSN پیش‌فرض ingestion به localhost:5433 اشاره می‌کند",
    "P0", "تأییدشده",
    "داخل کانتینر localhost وجود ندارد؛ اتصال دیتابیس شکست می‌خورد.",
    "خواندن DATABASE_URL مشترک یا اجبار INGESTION_DB_DSN در compose.")
add("DATA", "ingestion/config.py", r'lake_endpoint: str = Field\(default="http://minio:9000"\)', 1,
    "آدرس lake پیش‌فرض به سرویس minio اشاره می‌کند که در Compose نیست",
    "P0", "تأییدشده",
    "startup ingestion با خطای اتصال متوقف می‌شود.",
    "سرویس minio اضافه یا مقدار از env اجباری شود.")
add("DATA", "ingestion/config.py", r"enabled_sources: list\[SourceType\] = Field\(", 1,
    "پیش‌فرض enabled_sources همه منابع است، از جمله منابع بدون پارسر",
    "P1", "تأییدشده",
    "بار اضافی روی منابع و ذخیره داده خام بدون استفاده.",
    "پیش‌فرض فقط منابع دارای پارسر.")
add("DATA", "brsapi/services/query_service.py", r'func\.max\(SymbolSnapshotModel\.id\)\.label\("max_id"\)', 1,
    "انتخاب «آخرین snapshot» بر اساس MAX(id) است نه fetched_at",
    "P0", "تأییدشده",
    "با backfill یا درج نامرتب، رکورد قدیمی‌تر با id بزرگ‌تر به‌عنوان جاری نمایش داده می‌شود.",
    "استفاده از fetched_at با tie-break روی id (مثل get_latest_snapshots).")
add("DATA", "brsapi/services/query_service.py", r"_SNAPSHOT_SCAN_WINDOW = 50_000", 1,
    "پنجره اسکن ثابت ۵۰٬۰۰۰ رکوردی، نمادهای قدیمی‌تر را حذف می‌کند",
    "P1", "تأییدشده",
    "نمادی که در این پنجره رکورد ندارد بی‌صدا از heatmap حذف می‌شود (نه خطا، نه نشانه).",
    "پنجره بر اساس تعداد چرخه/زمان محاسبه شود و حذف گزارش گردد.")
add("DATA", "brsapi/services/query_service.py", r"get_enriched_snapshots JOIN failed — falling back to simple snapshots", 1,
    "شکست JOIN باعث بازگشت بی‌صدا به داده غنی‌نشده می‌شود",
    "P1", "تأییدشده",
    "کاهش کیفیت داده (eps/pe/sector) بدون هیچ خطای قابل مشاهده.",
    "متریک fallback و هشدار در پاسخ API.")
add("DATA", "brsapi/services/sync_service.py", r'conflict_target = \["symbol", "fetched_at"\] if on_conflict_update else None', 1,
    "upsert روی (symbol, fetched_at) با timestamp ثانیه‌ای انجام می‌شود",
    "P1", "نیازمند آزمون",
    "دو چرخه در یک ثانیه، رکورد دوم را روی اولی می‌نویسد و داده از دست می‌رود.",
    "کلید یکتا با دقت میکروثانیه یا شناسه چرخه.")
add("DATA", "jobs/definitions/sync_jobs.py", r"class SyncQuotesJob\(BaseJob\)", 1,
    "همگام‌سازی quotes هر ۲ دقیقه دو درخواست به سهمیه محدود می‌زند",
    "P1", "تأییدشده",
    "۲۱۰ اجرا در روز × ۲ درخواست × ۳ زمان‌بند، بخش بزرگی از سهمیه ۴۰۰۰ را می‌بلعد.",
    "کاهش فرکانس، اجرای تک‌نمونه و شمارش مصرف در متریک.")
add("DATA", "jobs/definitions/sync_jobs.py", r"if not is_tehran_market_open\(\):", 1,
    "خارج از ساعت بازار، job «موفق» گزارش می‌شود بدون انجام کاری",
    "P2", "تأییدشده",
    "داشبورد تصور می‌کند همگام‌سازی انجام شده؛ در واقع داده ثابت مانده است.",
    "وضعیت skipped صریح در پاسخ و متریک.")

# ─────────────── DATA (deep dive: independent ingestion engine) ───────────────
add("DATA", "ingestion/main.py", r'"tsetmc_options": TsetmcOptionSource\(self\._http\),', 1,
    "منابع options و futures برای هر نماد درخواست می‌زنند اما هیچ پارسری برای آن‌ها ثبت نشده",
    "P0", "تأییدشده",
    "با ~۱۰۰۰ نماد، دو هزار درخواست در هر tick فقط برای دور ریختن پاسخ مصرف می‌شود و هیچ رکوردی ذخیره نمی‌گردد.",
    "یا پارسر این دو منبع اضافه شود یا از enabled_sources حذف شوند.")
add("DATA", "ingestion/worker.py", r"for ins_id in self\._instrument_ids:", 1,
    "برای منابع trade/orderbook/options/futures هر tick روی همه نمادها حلقه می‌زند",
    "P0", "تأییدشده",
    "با interval پیش‌فرض ۱۵ ثانیه و ~۱۰۰۰ نماد، هر tick هزاران درخواست HTTP تولید می‌کند؛ صف هرگز تمام نمی‌شود و داده عقب می‌افتد.",
    "round-robin/صف کار با سهمیه per-tick و متریک backlog.")
add("DATA", "ingestion/sources/tsetmc.py", r"if self\._instruments is not None:", 1,
    "کش فهرست نمادها هرگز منقضی یا refresh نمی‌شود",
    "P1", "تأییدشده",
    "نماد جدید/حذف‌شده بعد از اولین دریافت وارد فهرست نمی‌شود؛ تازه‌سازی ساعتی worker بی‌اثر است.",
    "TTL یا force refresh برای فهرست نمادها.")
add("DATA", "ingestion/sources/tsetmc.py", r'logger\.exception\("Failed to fetch instrument list"\)', 1,
    "شکست دریافت فهرست نمادها فهرست خالی برمی‌گرداند و یک ساعت retry نمی‌شود",
    "P1", "تأییدشده",
    "worker با فهرست خالی، برای منابع per-instrument هیچ درخواستی نمی‌فرستد و بی‌صدا بی‌کار می‌ماند.",
    "تفکیک خطا از فهرست خالی + retry کوتاه‌تر.")
add("DATA", "ingestion/worker.py", r"results\[name\] = -1", 1,
    "شکست یک منبع فقط -1 در دیکشنری نتیجه می‌شود و مصرف‌کننده آن را نمی‌بیند",
    "P1", "تأییدشده",
    "scheduler نتیجه ingest_all را دور می‌ریزد؛ شکست همگام‌سازی هیچ متریک/هشداری ندارد.",
    "ثبت متریک موفقیت/شکست per-source.")
add("DATA", "ingestion/worker.py", r"if ins_id:", 1,
    "اگر identity resolver شناسه را پیدا نکند، شناسه خارجی (insCode) به‌عنوان instrument_id نوشته می‌شود",
    "P1", "تأییدشده",
    "نوشتن در جدول با FK به instruments.id شکست می‌خورد و فقط لاگ می‌شود → رکورد ذخیره نمی‌شود.",
    "در صورت resolve نشدن، رکورد را quarantine/رد و شمارش کن.")
add("DATA", "ingestion/retry.py", r"retryable_exceptions: tuple\[type\[Exception\], \.\.\.\] = \(", 1,
    "مجموعه خطاهای قابل retry شامل خطاهای اتصال aiohttp نیست",
    "P1", "تأییدشده",
    "ClientConnectorError/DNS از ConnectionError پایتون ارث نمی‌برد؛ اختلال کوتاه بدون retry یک tick را از بین می‌برد.",
    "افزودن aiohttp.ClientError و حفظ CancelledError.")
add("DATA", "ingestion/parser/tsetmc_parsers.py", r"now = datetime\.now\(UTC\)\.isoformat\(\)", 1,
    "زمان رویداد از لحظه parse گرفته می‌شود، نه لحظه fetch",
    "P1", "تأییدشده",
    "سن داده و تأخیر منبع قابل محاسبه نیست و replay زمان واقعی را از دست می‌دهد.",
    "پاس دادن fetch_time از payload به parser.")
add("DATA", "ingestion/parser/tsetmc_parsers.py", r'"volume": int\(rec\.get\("qTotTran5J", 0\)\),', 1,
    "تبدیل int روی مقدار خام می‌تواند برای یک رکورد خراب exception بدهد",
    "P1", "تأییدشده",
    "کل parse همان payload دور ریخته می‌شود و همه رکوردهای سالم هم ذخیره نمی‌شوند.",
    "اعتبارسنجی per-record و quarantine.")
add("DATA", "ingestion/parser/tsetmc_parsers.py", r"except Exception:\s*$", 1,
    "خطای تبدیل عدد در _to_decimal بی‌صدا None می‌شود",
    "P2", "تأییدشده",
    "مقدار نامعتبر از مقدار ناموجود قابل تفکیک نیست؛ کیفیت داده قابل سنجش نیست.",
    "خطای validation با نام فیلد و شمارنده.")
add("DATA", "ingestion/storage/__init__.py", r"ON CONFLICT \(instrument_id, trade_date\) DO UPDATE SET", 1,
    "upsert روزانه fetched_at را به‌روزرسانی نمی‌کند",
    "P1", "تأییدشده",
    "پس از اصلاح داده، زمان آخرین دریافت قدیمی می‌ماند و پایش تازگی گمراه می‌شود.",
    "fetched_at = NOW() در SET.")
add("DATA", "ingestion/storage/__init__.py", r"ON CONFLICT DO NOTHING", 1,
    "ON CONFLICT DO NOTHING بدون کلید یکتای طبیعی هیچ تکراری را حذف نمی‌کند",
    "P1", "تأییدشده",
    "چون id خودافزا تکراری نمی‌شود، هر polling رکورد جدید می‌سازد و ON CONFLICT هرگز فعال نمی‌شود.",
    "کلید یکتا بر هویت واقعی رکورد.")
add("DATA", "ingestion/storage/__init__.py", r"INSERT INTO market_snapshots", 1,
    "جدول snapshot فقط append می‌شود و upsert ندارد",
    "P1", "تأییدشده",
    "با هر poll یک ردیف جدید برای هر نماد؛ جدول هم تاریخچه و هم «وضعیت جاری» را قاطی می‌کند.",
    "upsert وضعیت جاری یا partition/retention صریح.")
add("DATA", "ingestion/storage/__init__.py", r'data\.get\("first_price"\) or data\.get\("open"\)', 1,
    "ستون open از first_price پر می‌شود که قیمت اولین معامله است نه open روزانه",
    "P2", "تأییدشده",
    "شاخص‌های OHLC روی داده نادرست محاسبه می‌شوند.",
    "نگاشت صریح open از منبع یا NULL.")
add("DATA", "ingestion/db/models.py", r'trade_ticks = sa\.Table\(', 1,
    "جدول trade_ticks کلید یکتای طبیعی ندارد",
    "P2", "تأییدشده",
    "تکرار polling به رکوردهای تکراری و آمار دوباره‌شماری منجر می‌شود.",
    "UniqueConstraint روی (instrument_id, trade_date, ...).")
add("DATA", "ingestion/db/models.py", r'sa\.Index\("ix_market_snapshots_instrument"', 1,
    "market_snapshots فقط index غیریکتا دارد",
    "P2", "تأییدشده",
    "هیچ قیدی از درج چند snapshot برای یک نماد در یک چرخه جلوگیری نمی‌کند.",
    "کلید (instrument_id, snapshot_at) یا upsert.")
add("DATA", "ingestion/db/models.py", r'sa\.Index\("ix_orderbook_events_instrument_side"', 1,
    "orderbook_events شناسه snapshot/زمان گروهی ندارد",
    "P2", "تأییدشده",
    "سطوح عمق بازار چند چرخه با هم مخلوط می‌شوند و «عمق فعلی» قابل استخراج مطمئن نیست.",
    "snapshot_id مشترک برای هر fetch.")
add("DATA", "ingestion/sources/tsetmc.py", r"ClosingPrice/GetClosingPriceHistory", 1,
    "منبعی با نام tsetmc_trades در واقع تاریخچه قیمت پایانی روزانه می‌گیرد",
    "P2", "تأییدشده",
    "نام/معنا ناهماهنگ است؛ مصرف‌کننده ممکن است داده روزانه را با tick اشتباه بگیرد.",
    "تغییر نام منبع یا مستندسازی صریح.")

# ───────────────────────────── SCH: schedulers and jobs ─────────────────────────────
add("SCH", "apps/api/app.py", r"scheduler_app = SchedulerApp\(\)", 1,
    "هر replica از API یک SchedulerApp می‌سازد",
    "P0", "تأییدشده",
    "با دو replica، وظایف چند بار ثبت و اجرا می‌شوند.",
    "زمان‌بند فقط در سرویس scheduler و پشت feature flag.")
add("SCH", "apps/scheduler/__main__.py", r"app = SchedulerApp\(\)", 1,
    "سرویس scheduler جداگانه هم همان وظایف را ثبت می‌کند",
    "P0", "تأییدشده",
    "منبع سوم اجرای وظایف و مصرف سهمیه.",
    "حذف زمان‌بند درون API یا غیرفعال‌کردن سرویس مستقل.")
add("SCH", "apps/scheduler/app.py", r'trigger="interval", minutes=2\)', 1,
    "فاصله ۲ دقیقه‌ای برای SyncQuotesJob بدون توجه به سهمیه واقعی",
    "P1", "تأییدشده",
    "احتمال اشباع سهمیه و دریافت 302/خطا در ساعات ابتدایی روز.",
    "بودجه‌محور کردن فرکانس (adaptive interval).")
add("SCH", "apps/scheduler/app.py", r'EvaluateAlertsJob", trigger="interval", minutes=2', 1,
    "ارزیابی هشدارها هر ۲ دقیقه در هر سه نمونه اجرا می‌شود",
    "P2", "تأییدشده",
    "بار تکراری روی دیتابیس و Redis.",
    "قفل توزیع‌شده اجباری و interval تطبیقی.")
add("SCH", "apps/scheduler/app.py", r"Scheduler could not enqueue %s — falling back to in-process dispatch", 1,
    "اگر صف Redis در دسترس نباشد، بی‌صدا به اجرای درون‌فرایندی برمی‌گردد",
    "P0", "تأییدشده",
    "در محیط چندنمونه‌ای هر replica کار را خودش اجرا می‌کند → اجرای تکراری و مصرف چندبرابر.",
    "سیاست صریح fail-closed یا قفل اجباری در fallback.")
add("SCH", "apps/api/app.py", r'if not await _with_startup_lock\("brsapi_sync", "brsapi-sync"\):', 1,
    "همگام‌سازی کامل BrsApi در startup API اجرا می‌شود",
    "P1", "تأییدشده",
    "هر بار ری‌استارت/دیپلوی، همگام‌سازی سنگین و مصرف سهمیه.",
    "انتقال به job دوره‌ای یا اجرای فقط با فلگ.")
add("SCH", "apps/api/app.py", r"reports = await service\.sync_all\(session\)", 1,
    "در startup همه endpointها پشت سر هم فراخوانی می‌شوند",
    "P1", "تأییدشده",
    "زمان بالا آمدن سرویس طولانی و در صورت خطا سه بار تکرار می‌شود.",
    "اجرای غیرهمزمان پس از ready شدن سرویس.")
add("SCH", "ingestion/scheduler.py", r"tz = timezone\(timedelta\(hours=3, minutes=30\)\)", 1,
    "منطقه زمانی به‌صورت ثابت +۳:۳۰ کدنویسی شده و market_timezone نادیده گرفته می‌شود",
    "P1", "تأییدشده",
    "تغییر تنظیمات زمانی اثر ندارد؛ مرزهای بازه بازار ممکن است اشتباه باشد.",
    "استفاده از ZoneInfo(config.market_timezone).")
add("SCH", "ingestion/scheduler.py", r"if self\._in_market_hours\(\):", 1,
    "تمام callbackها خارج از ساعت بازار کنار گذاشته می‌شوند",
    "P1", "تأییدشده",
    "منابع شبانه‌روزی (اخبار/کریپتو) هم متوقف می‌شوند.",
    "ساعت بازار per-source به‌جای global gate.")
add("SCH", "apps/scheduler/app.py", r'hours=24\)', 1,
    "SyncInstrumentsJob هر ۲۴ ساعت اجرا می‌شود",
    "P2", "نیازمند آزمون",
    "نماد جدید تا یک روز در سیستم دیده نمی‌شود.",
    "اجرای روزانه در ساعت مشخص + قابلیت دستی.")

# ───────────────────────────── DB: storage / queries ─────────────────────────────
add("DB", "brsapi/models/tsetmc.py", r"fetched_at: Mapped\[datetime \| None\] = mapped_column\(DateTime, index=True\)", 1,
    "ستون fetched_at بدون timezone ذخیره می‌شود",
    "P1", "تأییدشده",
    "مقایسه زمان‌ها بین سرویس‌ها/سرورها می‌تواند جابه‌جا شود و تازگی را خراب نشان دهد.",
    "DateTime(timezone=True) و ذخیره UTC.")
add("DB", "brsapi/models/tsetmc.py", r'UniqueConstraint\("symbol", "fetched_at", name="uq_snap_symbol_fetched"\)', 1,
    "کلید یکتا بر (symbol, fetched_at) با دقت ثانیه",
    "P1", "تأییدشده",
    "چرخه‌های هم‌ثانیه روی هم نوشته می‌شوند.",
    "دقت میکروثانیه یا شناسه چرخه در کلید.")
add("DB", "brsapi/models/tsetmc.py", r"created_at: Mapped\[datetime\] = mapped_column\(DateTime, server_default=func\.now\(\), index=True\)", 1,
    "created_at از ساعت دیتابیس و fetched_at از ساعت اپلیکیشن پر می‌شود",
    "P2", "تأییدشده",
    "اختلاف ساعت دو منبع، تحلیل تازگی را نامعتبر می‌کند.",
    "یک منبع زمان واحد.")
add("DB", "brsapi/services/query_service.py", r"\.order_by\(func\.max\(SymbolSnapshotModel\.trade_value\)\.desc\(\)\.nullslast\(\)\)", 1,
    "ترتیب/محدودسازی روی max(trade_value) داخل زیرکوئری گروه‌بندی‌شده اعمال می‌شود",
    "P2", "نیازمند آزمون",
    "ممکن است نمادهای با ارزش معاملات بالا همیشه انتخاب شوند و بقیه از خروجی حذف گردند.",
    "مرتب‌سازی نهایی روی snapshot انتخاب‌شده انجام شود.")
add("DB", "brsapi/services/query_service.py", r"\.limit\(limit\)", 1,
    "محدودیت limit روی زیرکوئری گروه‌بندی انجام می‌شود نه روی نتیجه نهایی",
    "P2", "نیازمند آزمون",
    "تعداد ردیف نهایی با limit هم‌خوان نیست.",
    "limit پس از join اعمال شود.")

# ───────────────────────────── CACHE ─────────────────────────────
add("CACHE", "apps/api/endpoints/market.py", r"_AGG_CACHE: dict\[str, tuple\[float, Any\]\] = \{\}", 1,
    "کش aggregate در حافظه هر replica است",
    "P1", "تأییدشده",
    "دو کاربر روی دو replica می‌توانند داده با سن متفاوت ببینند.",
    "کش مشترک (Redis) یا حذف کش محلی.")
add("CACHE", "apps/api/endpoints/market.py", r"_AGG_TTL = 300\.0", 1,
    "TTL پنج‌دقیقه‌ای با polling ۳۰ ثانیه‌ای فرانت هم‌خوان نیست",
    "P2", "تأییدشده",
    "تا ۵ دقیقه پاسخ تکراری/قدیمی با success=True سرو می‌شود.",
    "TTL کوتاه‌تر یا برچسب as_of در پاسخ.")
add("CACHE", "apps/api/endpoints/market.py", r'cached = _agg_cache_get\("enriched-heatmap:500"\)', 1,
    "هیت‌مپ کش‌شده هیچ زمان تولیدی همراه ندارد",
    "P1", "تأییدشده",
    "فرانت نمی‌تواند سن داده را تشخیص دهد.",
    "افزودن generated_at و as_of به پاسخ.")
add("CACHE", "apps/api/endpoints/market.py", r'"board": s\.get\("board", ""\),', 1,
    "پاسخ heatmap فاقد fetched_at هر نماد است",
    "P0", "تأییدشده",
    "تشخیص «زنده» از «قدیمی» در کل مسیر UI ممکن نیست.",
    "افزودن fetched_at و age_seconds به هر سلول.")
add("CACHE", "apps/api/endpoints/market.py", r'return ApiResponse\[list\[dict\[str, Any\]\]\]\(success=True, data=cells\)', 1,
    "پاسخ خالی/قدیمی با success=True برگردانده می‌شود",
    "P1", "تأییدشده",
    "خطای داده از «بازار خالی» قابل تفکیک نیست.",
    "success=false برای نبود داده تازه یا افزودن فیلد freshness.")

# ───────────────────────────── API ─────────────────────────────
add("API", "apps/api/endpoints/market.py", r'summary="Enriched market heatmap"', 1,
    "endpoint هیت‌مپ فقط از دیتابیس می‌خواند و هیچ fallback زنده‌ای ندارد",
    "P1", "تأییدشده",
    "اگر sync متوقف باشد، پاسخ موفق اما کهنه است.",
    "پاسخ شامل وضعیت همگام‌سازی و زمان آخرین موفقیت.")
add("API", "apps/api/endpoints/market.py", r"end = date\.today\(\)\.isoformat\(\)", 1,
    "بازه تاریخ با date.today محلی محاسبه می‌شود",
    "P2", "تأییدشده",
    "در سرور با TZ متفاوت، بازه یک روز جابه‌جا می‌شود.",
    "محاسبه در Asia/Tehran یا UTC صریح.")
add("API", "apps/api/endpoints/market.py", r"limit: int = Query\(2000, ge=50, le=5000\)", 1,
    "treemap تا ۵۰۰۰ نماد را از دیتابیس می‌خواند و در حافظه گروه‌بندی می‌کند",
    "P2", "تأییدشده",
    "پاسخ سنگین و فشار روی DB در هر کش‌میش.",
    "پیش‌تجمیع در job یا کش مشترک.")
add("SEC", "apps/api/app.py", r"allow_origins=settings\.cors_origins,", 1,
    "CORS از تنظیمات می‌آید و allow_credentials=True است",
    "P1", "تأییدشده",
    "اگر CORS_ORIGINS=* تنظیم شود، مرورگر کوکی را رد می‌کند و نشست می‌شکند.",
    "اعتبارسنجی صریح: ستاره با credentials ممنوع.")
add("SEC", "core/config/api.py", r'cors_origins: list\[str\] = Field\(default=\["\*"\], alias="CORS_ORIGINS"\)', 1,
    "یک کلاس تنظیمات دوم با پیش‌فرض * برای CORS وجود دارد",
    "P1", "تأییدشده",
    "بسته به اینکه کدام settings ایمپورت شود، پیش‌فرض امن یا باز است.",
    "حذف کلاس تکراری و تک‌منبع‌سازی تنظیمات.")
add("SEC", "core/config/__init__.py", r'secret_key: str = Field\(default="change-me-in-production"', 1,
    "SECRET_KEY پیش‌فرض committed دارد",
    "P0", "تأییدشده",
    "اگر env ست نشود، توکن‌ها با کلید عمومی قابل جعل‌اند.",
    "حذف پیش‌فرض و fail-fast در همه محیط‌ها.")
add("SEC", "apps/api/app.py", r'docs_url="/docs",', 1,
    "مستندات OpenAPI در تولید هم فعال است",
    "P2", "نیازمند آزمون",
    "سطح حمله و افشای ساختار داخلی.",
    "غیرفعال‌سازی docs در production.")
add("API", "core/config/__init__.py", r'errors\.append\("OTLP_ENDPOINT should be configured for observability in production"\)', 1,
    "پیکربندی observability فقط هشدار است نه خطا",
    "P2", "تأییدشده",
    "در تولید بدون trace، عیب‌یابی داده قدیمی تقریباً غیرممکن می‌شود.",
    "الزام یا هشدار قابل مشاهده در health.")

# ───────────────────────────── FE ─────────────────────────────
add("FE", "frontend/src/lib/api.ts", r"const API_BASE_URL = process\.env\.NEXT_PUBLIC_API_URL \|\| '/api/v1';", 1,
    "آدرس API از متغیر NEXT_PUBLIC خوانده می‌شود که در زمان build درج می‌شود",
    "P0", "تأییدشده",
    "تغییر مقدار در runtime روی باندل مرورگر اثر ندارد؛ آدرس اشتباه تا ابد می‌ماند.",
    "استفاده از مسیر نسبی و پروکسی سمت سرور.")
add("FE", "frontend/src/lib/api.ts", r"export function extractArray<T = unknown>", 1,
    "اگر ساختار پاسخ ناشناخته باشد آرایه خالی برمی‌گردد",
    "P1", "تأییدشده",
    "خطای ساختاری به «فهرست خالی» تبدیل می‌شود و علت واقعی دیده نمی‌شود.",
    "پرتاب خطا یا نتیجه discriminated union.")
add("FE", "frontend/src/lib/api.ts", r"export function safeExtractArray", 1,
    "خطای backend فقط console.warn می‌شود و خروجی خالی برمی‌گردد",
    "P1", "تأییدشده",
    "کاربر داده خالی می‌بیند بدون پیام خطا.",
    "صعود خطا تا سطح UI و نمایش وضعیت.")
add("FE", "frontend/src/hooks/useMarketData.ts", r"function useEnrichedHeatmap", 1,
    "هیت‌مپ فقط success:false را warn می‌کند",
    "P1", "تأییدشده",
    "شکست دریافت از «بازار بدون داده» تفکیک نمی‌شود.",
    "isError واقعی و پیام قابل مشاهده.")
add("FE", "frontend/src/hooks/useMarketData.ts", r'console\.warn\("\[useEnrichedHeatmap\] backend returned success:false"', 1,
    "هشدار کنسول تنها واکنش به پاسخ ناموفق است",
    "P1", "تأییدشده",
    "خطا در محیط کاربر دیده نمی‌شود.",
    "state خطا + retry/بنر.")
add("FE", "frontend/src/hooks/useMarketData.ts", r"isLive: cells\.length > 0", 1,
    "وجود یک رکورد برای زنده بودن کافی است",
    "P0", "تأییدشده",
    "داده چند روزه «زنده» نمایش داده می‌شود؛ همان شکایت اصلی کاربر.",
    "isLive بر اساس سن fetched_at و موفقیت آخرین sync.")
add("FE", "frontend/src/hooks/useMarketData.ts", r"refetchInterval: 30_000,", 1,
    "بازخوانی ۳۰ ثانیه‌ای بدون توجه به تازگی منبع",
    "P2", "تأییدشده",
    "بار اضافی روی API بدون تازه‌تر شدن داده.",
    "interval تطبیقی با age داده.")
add("FE", "frontend/src/hooks/useMarketData.ts", r"refetchInterval: 600_000,", 1,
    "برخی بخش‌ها ۱۰ دقیقه یک‌بار بازخوانی می‌شوند",
    "P3", "تأییدشده",
    "ناهم‌گونی سن داده بین ویجت‌ها.",
    "سیاست refresh یکسان و مستند.")
add("FE", "frontend/next.config.ts", r"const apiUrl = process\.env\.API_URL", 1,
    "پروکسی Next به http://api:8000 پیش‌فرض می‌شود",
    "P1", "تأییدشده",
    "در محیطی که سرویس API نام دیگری دارد، همه درخواست‌ها 502 می‌شوند.",
    "اجبار API_URL در production یا fail در startup.")
add("FE", "frontend/next.config.ts", r"const currencyUrl = process\.env\.CURRENCY_API_URL", 1,
    "پروکسی ارز به سرویس currency وابسته است که ممکن است بالا نباشد",
    "P2", "تأییدشده",
    "بخش ارز بی‌صدا خالی می‌شود.",
    "fallback و پیام خطای صریح.")
add("FE", "frontend/src/lib/api.ts", r"const REQUEST_TIMEOUT_MS = 60_000;", 1,
    "timeout پیش‌فرض ۶۰ ثانیه برای همه درخواست‌ها",
    "P3", "تأییدشده",
    "در شبکه کند، کاربر تا یک دقیقه منتظر می‌ماند.",
    "timeout کوتاه‌تر برای خواندن و بلندتر فقط برای sync.")
add("FE", "frontend/src/lib/api.ts", r"const LONG_TIMEOUT_MS = 600_000;", 1,
    "timeout ۱۰ دقیقه‌ای برای مسیرهای sync",
    "P3", "تأییدشده",
    "درخواست‌های طولانی منابع سرور را قفل می‌کنند.",
    "انتقال به job + polling وضعیت.")

# ───────────────────────────── SEC ─────────────────────────────
add("SEC", "frontend/src/lib/goldApi.ts", r"\?token=\$\{encodeURIComponent\(token\)\}", 1,
    "توکن دسترسی برای WebSocket به‌صورت query parameter ارسال می‌شود",
    "P2", "تأییدشده",
    "توکن در لاگ سرور/پروکسی ثبت می‌شود.",
    "استفاده از subprotocol یا کوکی.")
add("DATA", "docs/brsapi-sync-status-report.md", r"`BRSAPI_ENABLED=false` \(DB-only\)", 1,
    "گزارش داخلی تأیید می‌کند دریافت زنده در حالت DB-only متوقف بوده",
    "P1", "تأییدشده",
    "شاهد تاریخی برای قدیمی شدن داده؛ نیازمند تأیید وضعیت امروز.",
    "بررسی مقدار فعلی و وضعیت سهمیه پیش از هر تغییر.")
add("DATA", "docs/brsapi-sync-status-report.md", r"HTTP 302", 1,
    "پاسخ 302 به فایل حجیم نشانه اشباع سهمیه بوده است",
    "P1", "تأییدشده",
    "فعال‌سازی بدون بررسی سهمیه، خطاهای بیشتر تولید می‌کند.",
    "پروب سهمیه قبل از فعال‌سازی.")

# ───────────────────────────── OBS ─────────────────────────────
add("OBS", "apps/api/router.py", r'\{"path": "/health", "tag": "Health"', 1,
    "health سرویس تازگی داده را نمی‌سنجد",
    "P1", "تأییدشده",
    "سرویس سالم گزارش می‌شود در حالی که داده روزها قدیمی است.",
    "health شامل last_sync_at, data_age, source_status.")
add("OBS", "core/config/__init__.py", r'errors\.append\("CORS_ORIGINS must be restricted in production"\)', 1,
    "اعتبارسنجی تولید فقط بخشی از ریسک‌ها را می‌گیرد و به تازگی داده کاری ندارد",
    "P2", "تأییدشده",
    "استقرار می‌تواند «سالم» باشد ولی هیچ داده تازه‌ای نداشته باشد.",
    "افزودن precondition تازگی داده به چک‌لیست استقرار.")
