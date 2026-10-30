# بستهٔ دهم — موانع اجرای job در مسیر صف

- **تاریخ بررسی:** 2026-10-27
- **دامنه:** کد فعلی مخزن (برنچ `integration/golddesk-fixes`)، نه فایل ZIP
- **روش:** بررسی ایستا + چند اجرای ماژول‌سطح؛ هیچ سرویس، دیتابیس یا Redis بالا نیامد

## خلاصهٔ مدیریتی

هر چهار ادعای این بسته در کد فعلی برقرار است و هر کدام از قبل ردیف کاتالوگ دارند.
یک حلقهٔ مفقود هم پیدا شد که قبلاً جدا ثبت نشده بود: در مسیر صف **هیچ پلی** به
`BrsApiJobRegistry.run_job` وجود ندارد؛ تنها تابع‌های GoldDesk پوشش داده شده‌اند.

نتیجهٔ عملی: حتی اگر Scheduler با موفقیت پیام را در Redis بگذارد، Worker امروز
نمی‌تواند آن job را پیدا کند؛ پیام به retry و سپس dead-letter می‌رود و داده تازه نمی‌شود.

## ادعاها

| ادعا | وضعیت | محل واقعی امروز | ردیف کاتالوگ |
|---|---|---|---|
| ۱. ثبت‌نشدن jobها در Worker | تأیید شد + تأیید اجرایی | `apps/worker/app.py:32` در برابر `apps/scheduler/app.py:61` | `SCH-025` |
| ۲. نبود مسیر اجرای BrsApi در Worker | تأیید شد | `jobs/job_dispatcher.py:83` و `:88`؛ `jobs/queue_consumer.py:276-282` | `SCH-026` + `SCH-028` |
| ۳. ناهمسانی fallback برای BrsApi | تأیید شد | `apps/scheduler/app.py:35-46` در برابر `:67-70` | `SCH-020` |
| ۴. Worker روشن ولی بدون مصرف | تأیید شد | `apps/worker/consumer.py:30-35` + `apps/worker/app.py:33` | `SCH-021` و `SCH-024` |

### توضیح ادعای ۲ (دو نقص جدا)

1. **نام‌ها تطبیق نمی‌شوند:** Scheduler نام `brsapi_all_symbols` را منتشر می‌کند،
   ولی `JobRegistry.register` کلید را از `job_class.__name__` می‌سازد
   (`BrsApiAllSymbolsJob`).
2. **پل اجرایی وجود ندارد:** `_dispatch_brsapi_direct_job` فقط
   `GOLD_DESK_JOB_FUNCTIONS` را می‌شناسد و برای بقیه `None` برمی‌گرداند. `run_job`
   که گیت ساعات بازار و مسیر endpointها را دارد، تنها از مسیر in-process
   (`brsapi/jobs/registry.py:508`) و اجرای دستی (`:461`) صدا زده می‌شود.

پس اصلاح نام‌ها به‌تنهایی کافی نیست.

## زنجیرهٔ شکست

```
Scheduler (queue mode)
   └─ publish("brsapi_all_symbols")  →  job:queue
        └─ Worker: job_registry خالی  →  "Job … not found"
             └─ retry × max_retries  →  job:dead
                  └─ snapshot تازه نمی‌شود؛ UI همان داده قدیمی را «زنده» نشان می‌دهد
```

و یک شکست زودتر از این زنجیره: ایمیج worker اصلاً حلقهٔ اجرا ندارد
(`Dockerfile.worker:56` → `python -m apps.worker.app`).

## شواهد اجرایی که در همین محیط گرفته شد

| بررسی | نتیجه |
|---|---|
| `python -m apps.worker.app` | خروج با کد ۰ و بدون خروجی → هیچ حلقه‌ای اجرا نمی‌شود |
| `job_registry.list_names()` در فرآیند تازه | `0` و `get('SyncQuotesJob')` = `None` |
| پس از `register_module(jobs.definitions)` | ۶۶ job ثبت شد، ولی `get('brsapi_all_symbols')` هنوز `None` |
| `docker compose config` | `service "api" has neither an image nor a build context specified: invalid compose project` |
| `asyncpg.create_pool('postgresql+asyncpg://…')` | `ClientConfigurationError: scheme is expected to be either "postgresql" or "postgres"` |

## سه بررسی که روی سرور لازم است

این سه مورد **اجرا نشد**؛ دیمن Docker در این محیط بالا نبود
(`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`).
روی سرور خودتان با همین ترتیب اجرا کنید:

```bash
# 0) آیا worker اصلاً پایدار است؟
docker ps -a --format 'table {{.Names}}\t{{.Status}}'

# 1) آیا پیام‌ها «not found» می‌خورند؟
docker logs --tail=500 tse_worker 2>&1 | grep -nE "not found|dead-letter|rejected message"

# 2) عمق صف و صف مرده (نام‌ها پیش‌فرض‌اند: job:queue / job:dead)
docker exec -it tse_redis redis-cli -a "$DEV_REDIS_PASSWORD" LLEN job:queue
docker exec -it tse_redis redis-cli -a "$DEV_REDIS_PASSWORD" LLEN job:dead

# 3) تازگی داده در برابر آخرین اجرای موفق
docker exec -it tse_timescaledb psql -U quant_dev -d tse_quant \
  -c "select max(fetched_at) from brsapi_symbol_snapshots;"
```

تفسیر:

- اگر `tse_worker` در وضعیت `Restarting` است → ادعای CMD ایمیج (بستهٔ نهم) علت اصلی است.
- اگر worker پایدار است ولی `LLEN job:queue` بالا و `job:dead` هم بالا می‌رود →
  ادعای ۱ و ۲ (registry و نام‌ها) علت اصلی است.
- اگر `job:queue` خالی و `job:dead` صفر است ولی snapshot قدیمی است → مشکل در
  Scheduler/انتشار یا منبع، نه در Worker.
- اگر `max(fetched_at)` تازه است ولی UI قدیمی نشان می‌دهد → مشکل مسیر خواندن است، نه ingestion.

## ترتیب اصلاح پیشنهادی

1. `Dockerfile.worker` → `python -m apps.worker` (یا افزودن بلوک `__main__`).
2. ثبت `jobs.definitions` در startup خود Worker (مشترک با Scheduler).
3. نگاشت صریح نام صف به job، همراه با پل `BrsApiJobRegistry.run_job` تا گیت ساعات بازار حفظ شود.
4. retry/backoff برای اتصال Redis در Worker + معیار readiness واقعی (`ping`، نه وجود client).
5. سپس اصلاح زنجیرهٔ Compose (بستهٔ نهم) و بازبینی تازگی داده.

## محدودیت

- این گزارش از کد است، نه از محیط عملیاتی شما؛ هیچ job واقعی اجرا و هیچ صف واقعی خوانده نشد.
- شماره‌خط‌ها مربوط به همین نسخه است و با تغییر فایل جابه‌جا می‌شود.
- اگر استقرار فعلی از image یا Compose دیگری استفاده می‌کند، باید با همان تنظیمات تطبیق داده شود.
