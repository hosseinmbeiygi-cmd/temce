# اجرای integration و E2E در محیط ایزوله — شواهد

**تاریخ:** 2026-10-26 · **شاخه:** `integration/golddesk-fixes` · **commit:** `90597e05`

## 1. محیط ایزوله‌ای که ساخته شد

| جزء | مقدار | یادداشت |
|---|---|---|
| Postgres | `PostgreSQL 18.4` محلی، دیتابیس `phase0_it_20261026` | schema-only dump از دیتابیس اپ (`my_first_db`)؛ ۲۴۰ جدول، extensionهای `timescaledb` و `pg_trgm` |
| Redis | همان سرور محلی (`7.2.12`)، **DB 13** | DB 0 (داده اپ) دست‌نخورده ماند |
| Broker/Celery | همان Redis DB 13 از طریق `REDIS_URL`/`CELERY_BROKER_URL` | worker واقعی با `--pool=solo` |
| اپ | ASGI in-process با `httpx.ASGITransport` | بدون سرور زنده |
| اسرار | از `core.config` خوانده و فقط در env فرزند تزریق شد | هیچ مقدار حساسی چاپ نشد |

اسکریپت‌های موقت: `_audit_tmp/make_itest_db.py` (ساخت DB + dump/restore)، `_audit_tmp/run_pytest_env.py` (تزریق env و اجرای pytest). دیتابیس ایزوله پس از پایان کار قابل `DROP` است.

> محدودیت: دیتابیس ایزوله **بدون داده** است (schema-only). تست‌هایی که به تاریخچه قیمت، مدل آموزش‌دیده یا داده بازار نیاز دارند در این محیط قابل ارزیابی نیستند؛ این محدودیت در نتایج علامت‌گذاری شده است.

## 2. نتیجه اجرا

| مجموعه | فرمان | نتیجه | زمان |
|---|---|---|---|
| integration | `run_pytest_env.py tests/integration -q -m "not performance"` | **۴۴ passed، ۶ failed** | ۴۹.۸ ثانیه |
| e2e | `run_pytest_env.py tests/e2e -q -m "not performance"` | **۳۵ passed، ۶ failed، ۱ skipped** | ۱۹۶.۵ ثانیه |

اجرای اولیه integration با `REDIS_URL=localhost` ‏**۴۲ passed / ۸ failed / ۱۳۷ ثانیه** بود؛ پس از تغییر نام میزبان Redis به `127.0.0.1` دو تست Celery سبز شد و زمان کل ۸۷ ثانیه کاهش یافت (بخش ۳.۱).

خروجی خام: `integration-suite.txt`، `e2e-suite.txt` (همین پوشه).

## 3. علت‌یابی شکست‌ها

### 3.1. تأییدشده — تایم‌اوت اتصال precompute به Redis و گم‌شدن خاموش رویدادها

- `precompute/redis_client.py:72-78` کلاینت را با `socket_connect_timeout=2.0` روی آدرس `localhost` می‌سازد.
- روی این میزبان، اتصال به `localhost:6379` حدود **۲.۰۶ ثانیه** طول می‌کشد (تلاش IPv6 و fallback)، در حالی که `127.0.0.1` در **۰.۰۱ ثانیه** وصل می‌شود.
- نتیجه: هر اتصال precompute به تایم‌اوت ۲ ثانیه می‌خورد → `publish_event`/`save_result` استثنا می‌دهند → `except` آن را می‌بلعد (لاگ `debug`, شمارنده breaker) → زنجیره `SUCCESS` گزارش می‌کند ولی **صفر رویداد قرارداد** و **صفر نتیجه hot-layer** ثبت می‌شود.
- شاهد مستقیم: لاگ worker برای `it-celery-full` مقدار `13/13 SUCCESS` دارد، ولی `EventCapture` صفر رویداد دید (assert `== 13` شکست خورد).
- اثبات علت: با تغییر تنها `localhost` → `127.0.0.1` در `REDIS_URL`، همان ماژول **۴ passed در ۱۲.۱۸ ثانیه** شد.
- ثبت: ISSUE-121.

### 3.2. تأییدشده — `AUTH_DISABLED` مسیر `get_current_user` را پوشش نمی‌دهد

- `apps/api/auth.py:26-36` فلگ `AUTH_DISABLED` را می‌خواند، اما `apps/api/dependencies.py:246-259` (`get_current_user`) همیشه Bearer معتبر می‌خواهد؛ `_require_user` در `apps/api/router.py:20` از همین تابع استفاده می‌کند.
- در نتیجه ۷ تست مسیرهای محافظت‌شده (`backtests`، `screener`) با **401** شکست می‌خورند حتی با `AUTH_DISABLED=true`.
- اثبات اینکه مشکل صرفاً احراز هویت است: با توکن معتبر (`create_access_token`) همان دو endpoint پاسخ **200** می‌دهند (`_audit_tmp/auth_probe.py`).
- ثبت: ISSUE-122 (ناسازگاری فلگ) و ISSUE-123 (نبود fixture احراز هویت در تست‌های E2E/integration).

### 3.3. تأییدشده — تست معیوب در `test_signal_voting.py`

`fixed` و `broken` به‌صورت generator ساخته شده‌اند و با `>` مقایسه می‌شوند → `TypeError`؛ این assertion از ابتدا هرگز معتبر نبوده است (`tests/integration/test_signal_voting.py:445-456`). ثبت: ISSUE-124.

### 3.4. تأییدشده — drift نام استراتژی

`VoteResult.strategy` مقدار `ml_weighted` و `MarketSignal.source` مقدار `voting_ml_weighted` برمی‌گرداند، در حالی که تست‌ها `weighted`/`voting_weighted` انتظار دارند (`test_signal_voting.py:101`، `:338`). ثبت: ISSUE-125.

### 3.5. تأییدشده — خطای تاریخ شمسی در بارگذاری تاریخچه بک‌تست

در اجرای integration این خطا ثبت شد:

```text
Failed to load historical data for فولاد: asyncpg.DataError: invalid input for query argument $2:
'1402-10-11' ('str' object has no attribute 'toordinal')
```

سپس API خطای واقعی را پنهان می‌کند و `No historical data found for فولاد` برمی‌گرداند؛ یعنی کاربر «نبود داده» می‌بیند نه «خطای پارامتر تاریخ». ثبت: ISSUE-126 — این مورد مستقل از خالی‌بودن دیتابیس ایزوله یک نقص واقعی است.

### 3.6. محدودیت محیط (باگ محصول نیست)

| تست | علت شکست | دسته |
|---|---|---|
| `test_backtest_flow` | دیتابیس ایزوله بدون تاریخچه قیمت | نبود داده |
| `test_ml_inference_flow` | هیچ مدل آموزش‌دیده‌ای در DB ایزوله نیست | نبود داده |
| `test_screener_endpoint` | 401؛ نیازمند توکن | ISSUE-123 |
| `backtests/*` در E2E (۶ مورد) | 401؛ نیازمند توکن | ISSUE-123 |

## 4. بازتولید

```bash
# 1) ساخت دیتابیس ایزوله + restore schema
venv/Scripts/python.exe _audit_tmp/make_itest_db.py

# 2) اجرای مجموعه‌ها با env ایزوله (DB ایزوله + Redis DB 13)
venv/Scripts/python.exe _audit_tmp/run_pytest_env.py tests/integration -q -m "not performance"
venv/Scripts/python.exe _audit_tmp/run_pytest_env.py tests/e2e -q -m "not performance"

# 3) پاک‌سازی
#    DROP DATABASE phase0_it_20261026;
#    redis-cli -n 13 FLUSHDB
```
