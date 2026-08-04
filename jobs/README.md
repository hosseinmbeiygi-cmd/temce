# ⏰ apps/scheduler/ + jobs/ — سیستم زمان‌بندی و Jobهای دوره‌ای

> **آخرین به‌روزرسانی:** ۲۰۲۶-۰۸-۰۱ — فاز ۶

سیستم زمان‌بندی برای همگام‌سازی داده‌های BrsApi، تولید سیگنال، بک‌تست،
و پایش سلامت — با APScheduler، الگوی BaseJob و JobDispatcher.

---

## 🏗️ معماری

```
apps/scheduler/                     jobs/
├── app.py           # SchedulerApp  ├── base_job.py       # کلاس پایه همه jobها
├── __init__.py                      ├── job_registry.py   # ثبت خودکار jobها
├── __main__.py                      ├── job_dispatcher.py # dispatch + locking + semaphore
                                     ├── job_context.py    # context هر job
                                     ├── job_result.py     # نتیجه اجرا
                                     ├── locking.py        # قفل توزیع‌شده (in-memory)
                                     ├── deduplication.py  # جلوگیری از اجرای تکراری
                                     ├── retry_policy.py   # سیاست retry با backoff
                                     ├── registry.py       # singleton job_registry
                                     ├── definitions.py    # re-export stub
                                     └── definitions/      # ۱۷ فایل job definition
                                         ├── sync_jobs.py       # SyncInstruments, SyncQuotes, ...
                                         ├── brsapi_jobs.py     # BrsApiAllSymbols, BrsApiIndex, ...
                                         ├── alert_jobs.py      # EvaluateAlertsJob
                                         ├── news_jobs.py       # NewsIngestionJob
                                         ├── ml_jobs.py         # ModelTraining, BatchInference, ...
                                         ├── signal_jobs.py     # SignalGeneration, SignalEvaluation
                                         ├── recommendation_jobs.py
                                         ├── backtest_jobs.py
                                         ├── screener_jobs.py
                                         ├── codal_jobs.py
                                         ├── macro_jobs.py
                                         ├── market_data_jobs.py
                                         ├── reference_jobs.py
                                         ├── analytics_jobs.py
                                         ├── housekeeping_jobs.py
                                         ├── __init__.py        # همه ۴۵+ job class
```

### جریان اجرا

```
SchedulerApp.start()
  ├── job_registry.register_module(job_definitions)   ← کشف خودکار همه کلاس‌های BaseJob
  ├── register_all_brsapi_jobs().register_with_apscheduler(...)  ← jobهای BrsApi
  ├── add_job("SyncInstrumentsJob", interval=24h)     ← jobهای legacy
  ├── add_job("BackfillHistoricalDataJob", cron 2AM)  ← پر کردن داده‌های تاریخی
  └── scheduler.start()                                ← شروع APScheduler

APScheduler triggers → job_dispatcher.dispatch(name)
  ├── _registry.get(name)           ← lookup کلاس job
  ├── _deduplicator.is_duplicate()  ← جلوگیری از اجرای تکراری
  ├── _locking.acquire(lock_key)    ← قفل توزیع‌شده (max 1 instance)
  └── job.run(context)              ← execute() + error handling
```

---

## 📋 Jobهای زمان‌بندی‌شده

| Job | Trigger | توضیح |
|-----|---------|-------|
| `SyncInstrumentsJob` | هر ۲۴ ساعت | همگام‌سازی نمادهای TSETMC |
| `SyncQuotesJob` | هر ۲ دقیقه | قیمت/حجم + شاخص‌ها |
| `SyncSnapshotsToQuotesJob` | هر ۲ دقیقه | کپی snapshotها به quotes |
| `SyncCodalJob` | هر ۶ ساعت | اطلاعیه‌های کدال |
| `CodalAttachmentDownloadJob` | هر ۱۵ دقیقه | دانلود پیوست‌های کدال |
| `SyncNavAllJob` | هر روز ۸:۳۰ | NAV صندوق‌ها |
| `NewsIngestionJob` | هر ۱۰ دقیقه | دریافت اخبار RSS |
| `EvaluateAlertsJob` | هر ۲ دقیقه | بررسی هشدارهای کاربر |
| `BackfillHistoricalDataJob` | هر روز ۲ صبح | پر کردن داده‌های تاریخی |
| BrsApi jobها (۲۰+) | ۱-۱۵ دقیقه | همگام‌سازی endpointهای BrsApi |

---

## 🐛 اشکالات رفع‌شده در فاز ۶

### 🔴 بحرانی — `close_client()` در jobها کلاینت singleton را میکشت

**مشکل:** `brsapi.client.get_client()` یک **singleton** گلوبال برمی‌گرداند.
همه ۱۳ کلاس job در `sync_jobs.py` و `brsapi_jobs.py` در `finally` خود
`await close_client()` صدا میزدند. اولین jobی که تمام میشد کلاینت singleton
را میبست → jobهای در حال اجرای همزمان crash میکردند (httpx connection قطع).

**رفع:** حذف کامل `close_client()` از همه jobها (۱۳ کلاس). کلاینت singleton
حالا فقط در shutdown عمر lifespan بسته میشود. همچنین `await close_client()`
به `lifespan` shutdown در `apps/api/app.py` اضافه شد.

### 🔴 بحرانی — `BackfillHistoricalDataJob` هرگز اجرا نمیشد

**مشکل:** `SchedulerApp` این job را با `job_dispatcher.dispatch("BackfillHistoricalDataJob")`
اجرا میکرد، اما `JobRegistry` فقط کلاس‌های `jobs/definitions/__init__.py` (پکیج)
را کشف میکرد — و `BackfillHistoricalDataJob` در آن ثبت نشده بود! فقط در
فایل مرده `jobs/definitions.py` وجود داشت که توسط Python import نمیشد
(پکیج `definitions/` اولویت داشت).

**رفع:** `BackfillHistoricalDataJob` از `services/history_backfill_service`
import شد و به `__all__` در `jobs/definitions/__init__.py` اضافه شد.

### 🟡 پاکسازی — فایل مرده `jobs/definitions.py`

فایل `jobs/definitions.py` همزمان با پکیج `jobs/definitions/` وجود داشت.
Python همیشه پکیج را import میکند → فایل مرده بود.
حالا به یک re-export stub تبدیل شده که از پکیج import میکند (backward compatibility).

---

## 🧪 تست‌ها

| فایل تست | تعداد | توضیح |
|----------|-------|-------|
| `tests/unit/jobs/` | ۴۲ | تست jobهای scheduler (backfill, brsapi, sync, ...) |

> **فاز ۶:** ۴۲ تست پاس ✅ | ruff پاک ✅ | import سالم ✅

---

## ⚠️ محدودیت‌های شناخته‌شده

| # | مشکل | وضعیت | توضیح |
|---|-------|--------|-------|
| ۱ | `JobLocking` in-memory | ❌ | برای multi-process کافی نیست — نیاز به Redis |
| ۲ | `JobDeduplicator` in-memory | ❌ | دیکشنری ساده بدون async lock |
| ۳ | `Semaphore(10)` هاردکد | 🟡 | محدودیت همزمانی ۱۰ job |
