"""Ninth batch: findings that verify the ROOT-001…ROOT-005 deployment chain.

Only genuinely new defects are emitted here. The rest of the chain already has
rows in the catalog (DEP-001, DEP-004, DEP-005, DEP-020, SCH-025/026, DATA-012)
and is referenced from the appendix instead of being duplicated.
"""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append({"cat": cat, "file": file, "anchor": anchor, "occ": occ, "title": title,
                  "sev": sev, "status": status, "impact": impact, "fix": fix})


# ROOT-002 — بخش تازه: نام متغیرهای محیطی
add("DEP", "ingestion/config.py", r'model_config = \{"env_prefix": "INGESTION_"', 1,
    "تنظیمات ingestion پیشوند `INGESTION_` دارد ولی compose فقط `DATABASE_URL`/`REDIS_URL` می‌دهد",
    "P1", "تأییدشده",
    "`db_dsn` و `redis_url` به مقدار پیش‌فرض برمی‌گردند (`localhost:5433/marketdb` و "
    "`localhost:6379`)؛ یعنی حتی اگر سرویس ingestion درست بالا بیاید، به سرویس‌های Compose وصل نمی‌شود.",
    "تنظیم `INGESTION_DB_DSN`/`INGESTION_REDIS_URL` در سرویس مربوطه یا هم‌نام کردن پیشوند "
    "با متغیرهای موجود.")

# بستهٔ دهم — نبود پل به BrsApiJobRegistry.run_job در مسیر صف
add("SCH", "jobs/job_dispatcher.py", r"if job_name not in GOLD_DESK_JOB_FUNCTIONS:", 1,
    "در مسیر صف هیچ پلی به `BrsApiJobRegistry.run_job` وجود ندارد؛ فقط gold_desk پوشش داده شده",
    "P1", "تأییدشده",
    "`_dispatch_brsapi_direct_job` فقط `GOLD_DESK_JOB_FUNCTIONS` را می‌شناسد و برای بقیه None "
    "برمی‌گرداند؛ `run_job` که گیت ساعات بازار را دارد فقط از مسیر in-process/مدیریتی صدا زده "
    "می‌شود. پس حتی با ثبت registry در worker، jobهای endpoint اجرا نمی‌شوند.",
    "افزودن پل صریح: اگر نام در BrsApiJobRegistry هست، همان `run_job` (با گیت) اجرا شود.")

# بستهٔ یازدهم — truncation کل جدول به‌ازای هر نماد در history 24h Pro
add("DATA", "brsapi/services/sync_service.py", r"truncate_first=True,", 1,
    "همگام‌سازی ۲۴ساعتهٔ Pro جدول را برای هر نماد از صفر می‌سازد",
    "P1", "تأییدشده",
    "`sync()` وقتی `truncate_first` true است `TRUNCATE TABLE` می‌زند و بلافاصله commit می‌کند "
    "(`:465`، `:478`). registry این تابع را در حلقه روی تا ۲۰ نماد صدا می‌زند؛ پس بعد از هر "
    "اجرا فقط ردیف‌های آخرین نماد در جدول می‌ماند. جاب disabled است ولی از manage API قابل اجراست.",
    "حذف/upsert محدود به همان نماد با کلید یکتا (symbol, time) به‌جای TRUNCATE، یا staging.")

# ROOT-002 — بخش تازه: scheme ای که asyncpg رد می‌کند
add("DEP", "ingestion/db/session.py", r"self\._pool = await asyncpg\.create_pool\(", 1,
    "DSN با scheme `postgresql+asyncpg` بدون تبدیل به asyncpg داده می‌شود و رد می‌شود",
    "P1", "تأییدشده",
    "`IngestionConfig.db_dsn` پیش‌فرض `postgresql+asyncpg://…` دارد و validator فقط `str(v)` "
    "است. اجرای واقعی: `ClientConfigurationError: invalid DSN: scheme is expected to be "
    "either \"postgresql\" or \"postgres\", got 'postgresql+asyncpg'`. پس تعیین درست میزبان "
    "هم کافی نیست.",
    "حذف `+asyncpg` از DSN پیش‌فرض/مستندات یا تبدیل scheme پیش از `create_pool`.")
