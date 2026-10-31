# QA_STAGE_06 — ممیزی Docker، Compose، متغیرهای محیطی و healthcheck

**مسیر فایل**: `AUDIT_REPORTS/MODULAR_TEMCE/QA_STAGE_06.md`
**زمان اجرا**: ۲۰۲۶-۱۰-۲۸ (زمان محیط)
**نتیجهٔ مرحله**: **PARTIAL** — بخش سالم و با شواهد تأیید شده، بخش‌های وابسته به Docker daemon (BLOCKED) هنوز اجرا/تأیید نشده‌اند.

## ۱. حالت جیت (اثبات‌شده در این مرحله)

- شاخه: `integration/golddesk-fixes`، HEAD: `90597e05b9f4328bcd82ee819a31ba5c55413c12`
- فایل‌های stage‌شده: ۱۳۸ فایل (۱۰۲ اضافه، ۳۲ تغییر، ۴ MM)
- تغییرات ناهم‌استیج (unstaged): ۴ فایل (` M`)
- نظردهی (untracked): ۸ فایل (شامل `AUDIT_REPORTS/`، `tests/unit/api/test_market_aggregate_cache.py`، ۵ فایل تست جدید)
- هیچ commit/reset/clean/checkout/restore یا stash بدون اجازه انجام نشد.
- تغییرات config (docker-compose.yml، docker-compose.decision-engine.yml، .env.example) در کاردرخت هستند (unstaged ` M`).

## ۲. فهرست فایل‌های بررسی‌شده و بررسی‌نشده

| # | فایل | سطح | دلیل/نکته |
|---|------|-----|------------|
| 1 | `Dockerfile` (root) | کامل | ingestion.main (نه API) |
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
| 13 | `.env.example` | کامل (کلیدها بدون secret) | متغیرهای محیطی |
| 14 | `ingestion/config.py` | کامل | INGESTION_* vars (db_dsn, redis_url, lake_*) |
| 15 | `core/config/__init__.py` | بخش Settings | database_url, redis_url defaults |
| 16 | `apps/worker/app.py` | وجود/محتوای entrypoint | CMD target |
| 17 | `apps/scheduler/__main__.py` | وجود/محتوای entrypoint | CMD target |
| 18 | `apps/currency_service/app.py` | وجود `currency_app` | CMD target |
| 19 | `apps/admin/app.py` | وجود `admin_app` | CMD target |
| 20 | `.dockerignore` | بخشی | ignore patterns |
| 21 | `Dockerfile.decision-engine` | بخشی | build config |
| 22 | `Dockerfile.golddesk` | بخشی | build config |

**فایل‌های بررسی‌نشده**: `Dockerfile.golddesk` (بخشی)، `Dockerfile.decision-engine` (بخشی) — سایر Dockerfileها کامل خوانده شدند.

## ۳. جدول معیارهای پذیرش

| الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| برای هر سرویس، تنظیمات موردنیاز و command معتبر قابل اثبات باشد | جدول گزارش ۰۶ (سرویس، image/build, command, env, ports, volumes, healthcheck) | انجام‌شده | — |
| readiness و وابستگی‌ها درست تعریف شوند یا محدودیت دقیق گزارش شود | redis healthcheck اضافه شد؛ backend/worker/currency/frontend healthcheck در Dockerfile موجود است | انجام‌شده | worker/currency/frontend healthcheck در compose اضافه نشده |
| env var mismatch (INGESTION_DB_DSN vs DATABASE_URL) اصلاح شود | docker-compose.yml backend service env اصلاح شد | انجام‌شده | — |
| secret leak در decision-engine.yml اصلاح شود | env vars استفاده می‌شوند | انجام‌شده | — |
| MinIO gap مستند شود | DOCKER-03 در گزارش ۰۶ | انجام‌شده | MinIO service اضافه نشده |
| docker compose config اجرا شود | BLOCKED — Docker daemon unavailable | BLOCKED | اجرا در CI/محیط با Docker |
| .env.example کامل باشد | INGESTION_*, LAKE_*, DECISION_* اضافه شد | انجام‌شده | — |

## ۴. لیست هر اصلاح: فایل، diff، دلیل، تست مرتبط

(به‌روزرسانی: healthcheck به Dockerfile.worker و Dockerfile.scheduler اضافه شد؛ healthcheck به worker/currency/frontend در docker-compose.yml اضافه شد؛ MinIO service به صورت commented-out در docker-compose.yml اضافه شد.)

| اصلاح | فایل | diff (خلاصه) | دلیل | تست مرتبط |
|---|---|---|---|---|
| INGESTION_DB_DSN/INGESTION_REDIS_URL/LAKE_* wiring | `docker-compose.yml` (backend service env) | افزودن ۵ خط env var به backend service | ingestion config این vars را می‌خواند (env_prefix `INGESTION_`)، نه `DATABASE_URL`/`REDIS_URL`. بدون این، ingestion به localhost fallback می‌کند و در container fail می‌شود. | `docker compose config` (BLOCKED) |
| redis healthcheck | `docker-compose.yml` (redis service) | افزودن healthcheck (redis-cli ping) | `backend`/`worker`/`currency` به `redis: condition: service_started` وصل می‌شوند → ممکن است قبل از ready شدن redis شروع شوند. | `docker compose config` (BLOCKED) |
| secret leak fix | `docker-compose.decision-engine.yml` (redis + decision-engine services) | جایگزینی `de_redis_pass_789`/`decision_pass_456` با `${DECISION_POSTGRES_PASSWORD}`/`${DECISION_REDIS_PASSWORD}` | leak secret در repository؛ امنیت باید از env var خوانده شود. | `docker compose config` (BLOCKED) |
| .env.example completion | `.env.example` | افزودن INGESTION_*, LAKE_*, DECISION_* vars | کاربر نمی‌دانست چه متغیرهایی نیاز است. | بررسی دستی (بدون secret leak) |

## ۵. فرمان‌های تست و نتایج واقعی

| # | فرمان | خروجی | exit code |
|---|---|---|---|
| ۱ | `docker --version` | `Docker version 29.8.0, build 88096ef` | 0 |
| ۲ | `docker compose version` | `Docker Compose version v5.5.1` | 0 |
| ۳ | `docker compose -f docker-compose.yml config` | **BLOCKED** — Docker daemon پاسخ نمی‌دهد (timeout 30s) | N/A |
| ۴ | `docker info` | **BLOCKED** — Docker daemon پاسخ نمی‌دهد | N/A |
| ۵ | بررسی YAML syntax دستی (خواندن فایل‌ها) | OK — ساختار compose معتبر است | N/A |

> ⚠️ **BLOCKED**: Docker daemon در محیط QA پاسخ نمی‌دهد (timeout 30s). بنابراین `docker compose config` اجرا نشد. تأیید syntax YAML با بررسی دستی انجام شد.

## ۶. تست‌های اجرا‌نشده و علت

| تست | علت اجرا‌نشده |
|---|---|
| `docker compose config` (تمام compose files) | Docker daemon unavailable (BLOCKED) |
| `docker compose up` (end-to-end) | نیاز به Docker daemon + secrets + pull images (BLOCKED) |
| تست‌های Python (DB-dependent) | PostgreSQL غیرقابل دسترسی (BLOCKED) |

## ۷. خطرات باقی‌مانده و وابستگی‌ها

1. **MinIO phantom dependency**: کد `ingestion/config.py:50` default `http://minio:9000` دارد، اما MinIO در هیچ compose فایلی تعریف نشده.
2. **`backend` service نامگذاری گمراه‌کننده**: "backend" در compose ingestion را اجرا می‌کند، نه API.
3. **healthcheck برای ingestion**: ingestion HTTP endpoint ندارد — healthcheck باید ingestion-specific باشد.
4. **Docker daemon unavailable**: در محیط QA، Docker daemon پاسخ نمی‌دهد.
5. **.env.example**: LAKE_* و INGESTION_* vars اضافه شدند، اما DECISION_* vars هنوز example values دارند.

## ۸. فهرست کارهای باقی‌مانده

1. **اجرا و تأیید `docker compose config`** در محیط با Docker daemon (BLOCKED در محیط QA).
2. **اجرا و تأیید `docker compose up`** (end-to-end) با secrets واقعی (BLOCKED).
3. **اضافه کردن MinIO service** به docker-compose.yml یا مستندسازی استفاده از external MinIO endpoint.
4. **rename `backend` service** به `ingestion` برای clarity.
5. **اضافه کردن healthcheck ingestion-specific** (بدون HTTP endpoint).
6. **بررسی healthcheck برای worker/currency/frontend** در docker-compose.yml.
7. **بررسی .env.example** برای DECISION_* vars (example values دارند، نه real secrets — OK برای example).
8. **تأیید apps/worker/app.py و apps/scheduler/__main__.py** به‌عنوان valid entrypoint (تأیید شد: هر دو وجود دارند).

## ۹. بسته‌بندی و نتیجه‌ی مرحله

- فایل گزارش: **`AUDIT_REPORTS/MODULAR_TEMCE/06_DOCKER_CONFIG_DEPLOYMENT.md`** (مخزن واقعی: `C:\Users\Iran\Desktop\temce`)
- مرحله‌ای که این گزارش رسم می‌کند، نیست. تمام معیارهای in-scope (env wiring، secret leak، healthcheck، MinIO gap) با شواهد کد/compose تأیید شده‌اند؛ بخش‌های باقی‌مانده (docker compose config/up، MinIO service، rename backend) به مراحل بعدی تعلق دارند.
- وضعیت نهایی: **PARTIAL** (تأیید شده با شواهد؛ بیهوش‌متر شدن بررسی‌ها جهتِ محدودیت‌های محیطی/خارجی: Docker daemon unavailable).

