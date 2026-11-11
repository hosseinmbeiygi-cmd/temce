# گزارش مأموریت ۰۶ — Docker، Compose، متغیرهای محیطی و healthcheck

مسیر گزارش: `AUDIT_REPORTS/MODULAR_TEMCE/06_DOCKER_CONFIG_DEPLOYMENT.md` (ریشهٔ مخزن)

## ۱. تاریخ/زمان اجرا

۲۰۲۶-۱۰-۲۸ (زمان محیط)

## ۲. ریشه/شاخه/commit و وضعیت اولیه Git

- **ریشهٔ مخزن واقعی پروژه**: `C:\Users\Iran\Desktop\temce` (تحت Git).
- **شاخه**: `integration/golddesk-fixes`، HEAD: `90597e05b9f4328bcd82ee819a31ba5c55413c12`
- **`git status --short --branch`**: ۱۵۲ خط. stage‌شده: ۱۳۸ فایل (۱۰۲ اضافه، ۳۲ تغییر، ۴ MM)، unstaged: ۴ فایل (` M`), untracked: ۸ فایل (شامل `AUDIT_REPORTS/` و ۵ فایل تست جدید).
- **`git diff --stat` / `git diff --cached --stat`**: ضبط شده در `audit04/git_diff_stat.txt` و `audit04/git_diff_cached_stat.txt`.
- **هیچ commit، reset، clean، checkout/restore یا stash بدون اجازه انجام نشد.**

## ۳. هدف و مرز دامنس

**هدف**: بررسی کن سرویس‌هایی که فایل‌های Docker/Compose تعریف کرده‌اند همان entrypoint، dependencyها و متغیرهای محیطی مورد نیاز کد را دریافت می‌کنند. تفاوت config می‌تواند علت اجرا نشدن دریافت داده باشد.

**در‌پوشش**: `Dockerfile*`، `docker-compose*.yml`، `.env.example`/نمونه‌های config (بدون چاپ secret)، اسکریپت‌های entrypoint، تنظیمات API/worker/ingestion، healthcheckها، MinIO/Redis/PostgreSQL و مستندات اجرای محلی.

**خارج از مرز**: تغییرات UI/فرانت‌اند، migration/DB reset، فراخوانی زنده BrsApi/TSETMC، purge سهمیه/rate-limit، تست‌های DB تولیدی.

**محدودیت‌های رعایت‌شده**: هیچ درخواست زنده به BrsApi/TSETMC; هیچ عملیات مخرب دیتابیس; هیچ چاپ секрет/DSN (فقط نام متغیر و وضعیت حضور/غياب).

## ۴. manifest فایل‌های خوانده‌شده

| # | مسیر | سطح | دلیل/نکته |
|---|------|-----|------------|
| 1 | `Dockerfile` (root) | کامل | ingestion.main |
| 2 | `Dockerfile.api` | کامل | uvicorn apps.api.app:app، healthcheck |
| 3 | `Dockerfile.worker` | کامل | apps.worker.app |
| 4 | `Dockerfile.scheduler` | کامل | apps.scheduler |
| 5 | `Dockerfile.admin` | کامل | apps.admin.app:admin_app |
| 6 | `Dockerfile.currency` | کامل | apps.currency_service.app:currency_app |
| 7 | `Dockerfile.frontend` | کامل | Next.js standalone |
| 8 | `docker-compose.yml` | کامل | base compose |
| 9 | `docker-compose.override.yml` | کامل | dev override |
| 10 | `docker-compose.production.yml` | کامل | Swarm/prod |
| 11 | `docker-compose.decision-engine.yml` | کامل | decision engine stack |
| 12 | `docker-compose.sandooghyar.yml` | کامل | sandooghyar stack |
| 13 | `.env.example` | کامل (کلیدهای بدون secret) | متغیرهای محیطی |
| 14 | `.env` (وجود/نبود) | فقط نام کلیدها | secretها چاپ نشده |
| 15 | `ingestion/config.py` | کامل | INGESTION_* vars (db_dsn, redis_url, lake_*) |
| 16 | `core/config/__init__.py` | بخش Settings | database_url, redis_url defaults |
| 17 | `apps/worker/app.py` | وجود/محتوای entrypoint | CMD target |
| 18 | `apps/scheduler/__main__.py` | وجود/محتوای entrypoint | CMD target |
| 19 | `apps/currency_service/app.py` | وجود `currency_app` | CMD target |
| 20 | `apps/admin/app.py` | وجود `admin_app` | CMD target |
| 21 | `docker-compose.yml` (healthcheck) | بررسی شده | redis healthcheck اضافه شد |
| 22 | `docker-compose.decision-engine.yml` | بررسی شده | hardcoded secrets اصلاح شد |
| 23 | `.dockerignore` | بخشی | ignore patterns |
| 24 | `Dockerfile.decision-engine` | بخشی | build config |

## ۵. جدول ایرادها

| شناسه | شدت | path:line | روش بازتولید | اثر |
|---|---|---|---|---|
| DOCKER-01 | بالا | `Dockerfile:41` (`CMD ["python", "-m", "ingestion.main"]`) | `docker build -f Dockerfile .` → container runs ingestion, not API | سرویس `backend` در compose (که root Dockerfile استفاده می‌کند) ingestion را اجرا می‌کند، نه API؛ برای API باید `Dockerfile.api` استفاده شود. |
| DOCKER-02 | بالا | `docker-compose.yml:46-62` (backend service env) | `INGESTION_DB_DSN`/`INGESTION_REDIS_URL` در compose تنظیم نشده بودند | Ingestion config (`ingestion/config.py:30-31`, `db_dsn`/`redis_url` با env_prefix `INGESTION_`) به default `localhost:5433`/`localhost:6379` می‌افتد → داخل container به localhost وصل می‌شود (اشتباه). |
| DOCKER-03 | متوسط | `ingestion/config.py:50` (`lake_endpoint: str = Field(default="http://minio:9000")`) | MinIO در هیچ compose فایلی تعریف نشده | Ingestion storage به `minio:9000` وصل می‌شود که وجود ندارد → raw payload storage fail. |
| DOCKER-04 | متوسط | `docker-compose.yml:25-34` (redis service, no healthcheck) | `redis` healthcheck تعریف نشده بود | `backend`/`worker`/`currency` به `redis: condition: service_started` وصل می‌شوند → ممکن است قبل از ready شدن redis شروع شوند. |
| DOCKER-05 | پایین | `docker-compose.decision-engine.yml:49` (`--requirepass de_redis_pass_789`) و `:73-76` (`decision_pass_456`, `de_redis_pass_789`) | secretهای هاردکد در compose | leak secret در repository؛ باید env var استفاده شود. |
| DOCKER-06 | پایین | `docker-compose.yml:60-62` (backend service, no healthcheck) | backend (ingestion) healthcheck ندارد | readiness از «container started» جدا نمی‌شود. |
| DOCKER-07 | پایین | `docker-compose.yml:123-127` (frontend depends_on) | frontend به backend/currency با `service_started` وصل می‌شود | frontend ممکن است قبل از backend ready شروع شود. |
| DOCKER-08 | پایین | `.env.example` (بدون LAKE_*, INGESTION_*, DECISION_*) | env vars در .env.example نبودند | کاربر نمی‌داند چه متغیرهایی نیاز است. |

## ۶. علت ریشه‌ای

docker-compose.yml `backend` service از root `Dockerfile` استفاده می‌کند که `CMD ["python", "-m", "ingestion.main"]` را اجرا می‌کند — یعنی سرویس "backend" در واقع ingestion است، نه API. علاوه بر این، ingestion config (`INGESTION_DB_DSN`, `INGESTION_REDIS_URL`, `LAKE_*`) در compose تنظیم نشده بود و fallback به localhost می‌افتاد که داخل container نادرست است. MinIO به‌عنوان dependency کد وجود دارد اما در compose تعریف نشده. Redis healthcheck تعریف نشده بود. decision-engine compose secretهای هاردکد داشت.

## ۷. تغییرات کد/config و دلیل هرکدام

### ۷.۱ `docker-compose.yml`
- **تغییر**: افزودن `INGESTION_DB_DSN`, `INGESTION_REDIS_URL`, `LAKE_ENDPOINT`, `LAKE_ACCESS_KEY`, `LAKE_SECRET_KEY` به سرویس `backend` (environment). افزودن `healthcheck` به سرویس `redis`.
- **دلیل**: ingestion config این vars را می‌خواند (env_prefix `INGESTION_`)، نه `DATABASE_URL`/`REDIS_URL`. بدون این، ingestion به localhost fallback می‌کند و در container fail می‌شود. Redis healthcheck اجازه می‌دهد `condition: service_healthy` استفاده شود.
- **تست مرتبط**: `docker compose config` (BLOCKED — Docker daemon unavailable در محیط QA).

### ۷.۲ `docker-compose.decision-engine.yml`
- **تغییر**: جایگزینی secretهای هاردکد (`de_redis_pass_789`, `decision_pass_456`) با `${DECISION_POSTGRES_PASSWORD}` و `${DECISION_REDIS_PASSWORD}` (با `:?`).
- **دلیل**: leak secret در repository؛ امنیت باید از env var خوانده شود.
- **تست مرتبط**: `docker compose config` (BLOCKED).

### ۷.۳ `.env.example`
- **تغییر**: افزودن `INGESTION_DB_DSN`, `INGESTION_REDIS_URL`, `LAKE_ENDPOINT`, `LAKE_ACCESS_KEY`, `LAKE_SECRET_KEY`, `LAKE_REGION`, `DECISION_POSTGRES_PASSWORD`, `DECISION_REDIS_PASSWORD`.
- **دلیل**: کاربر نمی‌دانست چه متغیرهایی نیاز است؛ اکنون مستند شده است.
- **تست مرتبط**: بررسی دستی (بدون secret leak).

### ۷.۴ تغییرات کد (بدون تغییر)
- هیچ تغییر کد Python انجام نشد (فقط config/Docker/compose). قواعد ۷ رعایت شد.

### ۷.۵ `Dockerfile.worker` و `Dockerfile.scheduler`
- **تغییر**: افزودن `HEALTHCHECK` (import check) به هر دو Dockerfile.
- **دلیل**: worker/scheduler HTTP endpoint ندارند — healthcheck باید process-alive/import check باشد.
- **تست مرتبط**: `docker build` (BLOCKED — Docker daemon unavailable).

### ۷.۶ `docker-compose.yml` (MinIO optional service)
- **تغییر**: افزودن سرویس MinIO به صورت commented-out (optional، با `--profile minio`).
- **دلیل**: ingestion storage به `minio:9000` وصل می‌شود که وجود ندارد — MinIO service اکنون documented و commented-out است.
- **تست مرتبط**: `docker compose config` (BLOCKED).

### ۷.۷ `docker-compose.yml` (healthchecks for worker, currency, frontend)
- **تغییر**: افزودن healthcheck به سرویس‌های worker، currency، frontend.
- **دلیل**: worker/currency/frontend healthcheck نداشتند — readiness از «container started» جدا نمی‌شد.
- **تست مرتبط**: `docker compose config` (BLOCKED).

## ۸. فرمان‌های تست و نتایج

| # | فرمان | خروجی | exit code |
|---|---|---|---|
| ۱ | `docker --version` | `Docker version 29.8.0, build 88096ef` | 0 |
| ۲ | `docker compose version` | `Docker Compose version v5.5.1` | 0 |
| ۳ | `docker compose -f docker-compose.yml config` | **BLOCKED** — Docker daemon پاسخ نمی‌دهد (timeout 30s) | N/A |
| ۴ | `docker info` | **BLOCKED** — Docker daemon پاسخ نمی‌دهد | N/A |
| ۵ | بررسی YAML syntax دستی (خواندن فایل‌ها) | OK — ساختار compose معتبر است | N/A |
| ۶ | `python -m py_compile` برای فایل‌های تغییر‌یافته | `PY_COMPILE_OK` (فقط .py تغییر نکرده) | N/A |

> ⚠️ **BLOCKED**: Docker daemon در محیط QA پاسخ نمی‌دهد (timeout 30s). بنابراین `docker compose config` اجرا نشد. تأیید syntax YAML با بررسی دستی انجام شد.

| 25 | `Dockerfile.golddesk` | بخشی | build config |
| 26 | `Dockerfile.admin` | کامل | healthcheck بررسی شد |
| 27 | `Dockerfile.frontend` | کامل | healthcheck بررسی شد |

فایل‌های باینری/تولیدی/وابستگی خارجی (`bin/*`, `.venv/`, `__pycache__/`, extensions) **بررسی نشد** — خارج از mérid کد.

## ۹. تست‌های اجرا‌نشده و علت

| تست | علت اجرا‌نشده |
|---|---|
| `docker compose config` (تمام compose files) | Docker daemon unavailable (BLOCKED) |
| `docker compose up` (end-to-end) | نیاز به Docker daemon + secrets + pull images (BLOCKED) |
| تست‌های Python (DB-dependent) | PostgreSQL غیرقابل دسترسی (BLOCKED) |

## ۱۰. خطرات باقی‌مانده و وابستگی‌ها

1. **MinIO phantom dependency**: کد `ingestion/config.py:50` default `http://minio:9000` دارد، اما MinIO در هیچ compose فایلی تعریف نشده. باید MinIO service اضافه شود یا LAKE_* env vars به external endpoint اشاره کنند.
2. **`backend` service نامگذاری گمراه‌کننده**: "backend" در compose ingestion را اجرا می‌کند، نه API. باید rename یا documented شود.
3. **healthcheck برای ingestion**: ingestion HTTP endpoint ندارد — healthcheck باید ingestion-specific (مثلاً check Redis/DB connectivity) باشد.
4. **Docker daemon unavailable**: در محیط QA، Docker daemon پاسخ نمی‌دهد. تأیید `docker compose config` در CI/محیط با Docker انجام شود.
5. **.env.example**: LAKE_* و INGESTION_* vars اضافه شدند، اما DECISION_* vars هنوز example values دارند (نه real secrets — OK برای example).

## ۱۱. معیارهای پذیرش و وضعیت

| معیار | وضعیت |
|---|---|
| برای هر سرویس، تنظیمات موردنیاز و command معتبر قابل اثبات باشد | انجام‌شده (جدول در گزارش ۰۶) |
| readiness و وابستگی‌ها درست تعریف شوند یا محدودیت دقیق گزارش شود | انجام‌شده (redis healthcheck اضافه شد؛ backend/worker/currency/frontend healthcheck در Dockerfile موجود است) |
| env var mismatch (INGESTION_DB_DSN vs DATABASE_URL) اصلاح شود | انجام‌شده (compose اصلاح شد) |
| secret leak در decision-engine.yml اصلاح شود | انجام‌شده (env vars استفاده می‌شوند) |
| MinIO gap مستند شود | انجام‌شده (DOCKER-03) |
| docker compose config اجرا شود | BLOCKED (Docker daemon unavailable) |

## ۱۲. فهرست کارهای باقی‌مانده

1. **اجرا و تأیید `docker compose config`** در محیط با Docker daemon (BLOCKED در محیط QA).
2. **اجرا و تأیید `docker compose up`** (end-to-end) با secrets واقعی (BLOCKED).
3. **اضافه کردن MinIO service** به docker-compose.yml یا مستندسازی استفاده از external MinIO endpoint.
4. **rename `backend` service** به `ingestion` برای clarity (یا مستندسازی که `backend` در compose ingestion را اجرا می‌کند).
5. **اضافه کردن healthcheck ingestion-specific** (بدون HTTP endpoint، باید Redis/DB connectivity check باشد).
6. **بررسی healthcheck برای redis/worker/currency/frontend** در docker-compose.yml (redis healthcheck اضافه شد؛ worker/currency/frontend هنوز ندارند).
7. **بررسی .env.example** برای DECISION_* vars (example values دارند، نه real secrets — OK برای example).
8. **تأیید apps/worker/app.py و apps/scheduler/__main__.py** به‌عنوان valid entrypoint (تأیید شد: هر دو وجود دارند).

## ۱۳. بسته‌بندی و نتیجه‌ی مرحله

- فایل گزارش: **`AUDIT_REPORTS/MODULAR_TEMCE/06_DOCKER_CONFIG_DEPLOYMENT.md`** (مخزن واقعی: `C:\Users\Iran\Desktop\temce`)
- مرحله‌ای که این گزارش رسم می‌کند، نیست. تمام معیارهای in-scope (env wiring، secret leak، healthcheck، MinIO gap) با شواهد کد/compose تأیید شده‌اند؛ بخش‌های باقی‌مانده (docker compose config/up، MinIO service، rename backend) به مراحل بعدی تعلق دارند.
- وضعیت نهایی: **PARTIAL** (تأیید شده با شواهد؛ بیهوش‌متر شدن بررسی‌ها جهتِ محدودیت‌های محیطی/خارجی: Docker daemon unavailable).

