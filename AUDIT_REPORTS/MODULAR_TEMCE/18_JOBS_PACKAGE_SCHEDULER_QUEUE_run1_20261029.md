# ممیزی بستهٔ `jobs/` — زمان‌بندی، Dispatcher، Queue، Lock و Dedup

- **تاریخ:** 2026-10-29
- **نسخهٔ گزارش:** run1
- **دامنه:** `jobs/` (هستهٔ dispatch/registry/scheduler/queue/locking/dedup) + `apps/scheduler` + bridge دیسپچر BrsApi.
- **شاخه:** `integration/golddesk-fixes`
- **HEAD (شروع ممیزی این نشست):** `be8b4ff4839ee1e2bdacd791e7be176044e1eebd`
  - توجه: در ابتدای این نشست HEAD برابر `90597e05b9f4328bcd82ee819a31ba5c55413c12` بود؛ عامل دیگری در فاصلهٔ میان‌نشست‌ها commit `be8b4ff4` را ایجاد کرده است. هیچ‌یک از این تغییرات توسط این ممیزی ایجاد یا بازنویسی نشده‌اند.
- **وضعیت working tree:** بسیار آلوده و در حال تغییر هم‌زمان (`staged=138`, `unstaged=145`, `untracked=70` در snapshot `t13-jobs.txt`).

> این گزارش گزارش‌های قبلی را بازنویسی نمی‌کند. snapshot: `AUDIT_REPORTS/MODULAR_TEMCE/_snapshots/t13-jobs.txt`.

---

## ۱. خلاصهٔ مدیریتی

بستهٔ `jobs/` ساختار سه‌گانهٔ نسبتاً کاملی دارد: `JobRegistry`/`job_registry` (ثبت کلاس‌ها)، `JobDispatcher` (اجرا + lock + dedup)، `JobQueuePublisher`/`JobQueueConsumer` (حالت صف توزیع‌شده با Redis + dead-letter) و `JobLocking` (قفل توزیع‌شدهٔ owner-safe با Lua).

وضعیت کلی:

- **۱ باگ P1 اصلاح شد** — «dedup مانع retry در مسیر صف» (J1).
- **۱ نقطهٔ کیفی مستند شد (P2، بدون تغییر رفتار)** — مسیر `TimeoutError`/پاسخ خالی در bridge دیسپچر BrsApi و رویداد «موفقیت کاذب در پیام خالی» (J2).
- **یافته‌های ساختاری مستند (P3)** — ماژول‌های stub یتیم در ریشهٔ `jobs/` (J3).
- هیچ‌کدام از یافته‌ها به دیتابیس عملیاتی، Redis یا provider زندهٔ بیرونی نیاز نداشتند؛ در نتیجه این بخش کاملاً **آفلاین و قابل‌راستی‌آزمایی** است.

---

## ۲. وضعیت واقعی Git

- HEAD/شاخه در `t13-jobs.txt` ثبت شده است.
- تغییرات staged/unstaged/untracked عامل‌های دیگر در `jobs/` (در حین این ممیزی توسط agentهای دیگر):
  - `jobs/definitions/news_jobs.py` (M)
  - `jobs/job_dispatcher.py` (M — عمدتاً بخش brsapi-direct توسط این ممیزی دست‌نخورده ماند)
  - `jobs/job_result.py` (M)
  - `jobs/news_sync.py` (M)
  - `jobs/queue_consumer.py` (M)
- در `jobs/job_dispatcher.py` تنها بخش `dispatch()` (پاکت dedup) توسط این ممیزی اصلاح شد؛ بخش `_dispatch_brsapi_direct_job` دست‌نخورده ماند تا با کار هم‌زمان تلاقی نداشته باشد.

---

## ۳. موجودی بررسی‌شده

| محور | فایل | وضعیت |
|---|---|---|
| dispatch/registry | `jobs/job_dispatcher.py`, `jobs/job_registry.py`, `jobs/registry.py` | ✅ بررسی |
| مدل‌های job | `jobs/base_job.py`, `jobs/job_context.py`, `jobs/job_result.py` | ✅ بررسی |
| queue | `jobs/queue_publisher.py`, `jobs/queue_consumer.py` | ✅ بررسی |
| locking/dedup/retry | `jobs/locking.py`, `jobs/deduplication.py`, `jobs/retry_policy.py` | ✅ بررسی |
| scheduler | `jobs/scheduler.py`, `apps/scheduler/app.py`, `apps/scheduler/__main__.py` | ✅ بررسی |
| registry تعاریف | `jobs/definitions/__init__.py` (+ ۲۴ ماژول در `jobs/definitions/`) | ✅ بررسی |
| gate بازار | `jobs/market_hours.py` | ✅ بررسی |
| stubهای ریشه | `jobs/cleanup.py` و سایر ماژول‌های تک‌تابعی | ✅ بررسی (P3) |

فایل‌های بررسی‌نشده (خارج از دامنهٔ این نشست، برای حوزه‌های دیگر): جزئیات داخلی providerهای BrsApi در `brsapi/jobs/` و منطق تک‌تک jobها در `jobs/definitions/*` (هرکدام domain جداست).

---

## ۴. یافته‌ها

### J1 — P1 (اصلاح‌شده) — dedup مانع retry و مسیر dead-letter در حالت صف می‌شد

**فایل:** `jobs/job_dispatcher.py` خط ۴۷–۵۱ (نسخهٔ HEAD/قبل از اصلاح).

**شواهد کد (قبل):**
```python
dedup_key = f"{job_name}:{context.job_id}"
if await self._deduplicator.is_duplicate(dedup_key):
    logger.warning("Dedup: job %s already dispatched", dedup_key)
    return JobResult.failure("Duplicate job", job_name=job_name)
await self._deduplicator.mark(dedup_key)
```

**شرایط بازتولید (آفلاین، با کامپوننت‌های واقعی):**
```python
ctx = JobContext(job_id="job-occ-1", job_name="FlakyJob")
await d.dispatch("FlakyJob", context=ctx)   # شکست موقت → JobResult.failure("boom")
await d.dispatch("FlakyJob", context=ctx)   # retry همان occurrence
```
خروجی واقعی قبل از اصلاح: بار دوم `error='Duplicate job'` با اینکه job هرگز اجرا نشد.

**علت ریشه‌ای:** کلید dedup = `job_name:job_id` با TTL پیش‌فرض ۳۶۰۰ ثانیه. در حالت صف، `jobs/queue_consumer.py::_requeue` **همان payload** (همان `job_id`) را با `attempt` افزایش‌یافته دوباره روی صف می‌گذارد. چون `job_dispatcher.dispatch(job_name, params, context)` همیشه context را از consumer دریافت می‌کند، وقوع بعدی (retry) دقیقاً همان کلید را می‌دهد و در بازهٔ TTL «تکراری» تلقی و به‌صورت بی‌صدا رد می‌شود.

**اثر:** retry بی‌اثر می‌شد؛ در `queue_consumer._handle_message` این پاسخِ failure غیر-benign است و طبق `_BENIGN_ERROR_MARKERS` («Duplicate» جزو markers است) به‌عنوان **processed** شمرده می‌شد و مسیر dead-letter هرگز اجرا نمی‌شد. یعنی «شکست پایدار ذخیره‌سازی/پردازش» می‌توانست پنهان بماند.

**چرا dedup اینجا ارزش ندارد:** occurrenceها در صف از قبل توسط BRPOPLPUSH (یک‌بار مصرف) و قفل توزیع‌شدهٔ `job:<name>` (owner-safe) سریالایز می‌شوند.

**اصلاح (حداقلی، فقط مسیرِ contextِ فراخوان):** اگر `context` توسط فراخوان داده شده باشد (worker/queue)، dedup رد می‌شود؛ فقط dispatchهای درون‌فرایندیِ بدون context (که خودشان job_id می‌سازند) dedup می‌شوند. این کارکرد `JobDeduplicator` و تست‌های موجود آن را حفظ می‌کند.

**تست‌ها:**
- ابتدا RED: `tests/unit/jobs/test_job_dispatcher.py::TestCallerSuppliedOccurrenceId` → `2 failed, 1 passed` (exit 1).
- پس از اصلاح GREEN: همان فایل → `10 passed` (exit 0).
- **تست integration (چرا باگ از دست رفته بود):** مسیر retry→dead-letter را یک `FakeDispatcher` پوشش می‌داد که نمی‌تواند نقصِ داخلِ dispatcher واقعی را بازتولید کند. تست جدید `tests/unit/jobs/test_queue.py::test_real_dispatcher_retries_same_job_id_not_treated_as_duplicate` از `JobDispatcher` و `JobDeduplicator` **واقعی** استفاده می‌کند و ثابت می‌کند occurrence با همان `job_id` در تلاش دوم دوباره اجرا و در نهایت dead-letter می‌شود. ✅ `1 passed`.

**معیار بستن مورد:** retry با همان `job_id` دوباره اجرا شود و کلید `Duplicate` نگیرد؛ dispatchِ بدون context همچنان dedup شود. ✅ برآورده شد.

---

### J2 — P2 (مستند، بدون تغییر) — پیام خالی/TimeoutError در bridge دیسپچر BrsApi

**فایل:** `jobs/job_dispatcher.py::_dispatch_brsapi_direct_job` (bخش هم‌زمانِ عامل دیگر — دست‌نخورده ماند).

**نکته:** وقتی `registry.run_job(name)` مقدار `None` برگرداند، هم‌اکنون به‌صورت `JobResult.skipped_result(...)` با دلیل «not due (market-hours gate)» گزارش می‌شود. اما `None` می‌تواند ناشی از «پاسخ خالی معتبر» یا «موفقیت کاذب» نیز باشد (همان الگوی J2 در گزارش ۱۲/۱۳). تفکیک دقیق این سه حالت نیازمند مشاهدهٔ رفتار واقعی `BrsApiJobRegistry.run_job` است که در این محیطِ آفلاین قابل بازتولید قطعی نبود.

**وضعیت:** ثبت‌شده به‌عنوان دین تکنیکال؛ **PASS اعلام نمی‌شود** تا در محیط دارای provider/DB بازبینی شود.

---

### J3 — P3 (مستند) — ماژول‌های stub یتیم در ریشهٔ `jobs/`

**فایل‌ها:** `jobs/cleanup.py` (`CleanupJob` → `Result.ok({"cleaned": 0})`), `jobs/codal_sync.py` (`Result.ok({"records": 0})`), `jobs/signal_generation.py` (`Result.ok({"signals": []})`), `jobs/reports_publish.py`, `jobs/reconciliation.py`, `jobs/backtest_run.py`, `jobs/model_retraining.py`, `jobs/macro_sync.py`, `jobs/market_sync.py`, `jobs.fund_sync.py`, `jobs/market_data_jobs.py`.

**شواهد:** هیچ‌یک از این ماژول‌ها هیچ importerی در مخزن ندارند (جست‌وجوی `--fixed-strings` بدون نتیجه به‌جز خودِ فایل)، و در registry (`jobs/definitions/__init__.py`) ثبت نشده‌اند. نسخهٔ پویا/واقعی آن‌ها در `jobs/definitions/<domain>_jobs.py` وجود دارد (مثلاً `CodalSyncJob`, `SignalGenerationJob`, `ModelTrainingJob`).

**ریسک:** `jobs/news_sync.py::NewsSyncJob` قبلاً توسط عامل دیگر به سمت fail-closed اصلاح شده (`Result.fail("not_implemented: ...")`)، اما بقیهٔ stubها هنوز `Result.ok(...)` با «۰ رکورد» برمی‌گردانند که اگر روزی سیم‌کشی شوند، «موفقیت کاذب» تولید می‌کنند. چون هیچ‌جا import نمی‌شوند، در حال حاضر ریسک عملیاتی فعال ندارند.

**پیشنهاد (نیازمند تصمیم محصول):** حذف ماژول‌های stub یتیم یا یکسان‌سازی آن‌ها با الگوی fail-closed `news_sync.py`. خارج از دامنهٔ اصلاح حداقلیِ این نشست نگه داشته شد.

---

## ۵. بررسی‌های سالم (بدون یافته)

- **ثبت تعاریف:** `JobRegistry.register_module(jobs.definitions)` در `apps/scheduler/app.py::start()` تمام کلاس‌های `BaseJob` را کشف می‌کند؛ بررسی واقعی: **۶۶ job ثبت شد**. تمام نام‌های زمان‌بندی‌شده در `apps/scheduler/app.py` (Sync*/News*/Fund*/Gold*/Screener*/… و `BrsApiReadyCheckJob`) در registry موجودند — هیچ «job تعریف‌نشده در scheduler» یافت نشد.
- **قفل توزیع‌شده:** `jobs/locking.py` از `SET NX PX` + Lua compare-and-delete/extend استفاده می‌کند و در نبود Redis به in-memory با همان سمانتیک برمی‌گردد. `RedisJobLock` نیز owner-safe است.
- **بازآرایی dedup:** `JobDeduplicator` ساده و درست است؛ تست‌هایش (شامل مرزِ TTL) پاس می‌شوند.
- **Scheduler:** jobهای APScheduler در حالت صف مسیر publish→worker و در غیر آن مسیر in-process را می‌روند (`jobs/queue_publisher.py` با fallback صریح در نبود Redis).

---

## ۶. فرمان‌ها و نتایج واقعی

| فرمان | نتیجه | exit |
|---|---|---|
| `python -m pytest tests/unit/jobs/test_job_dispatcher.py -q -p no:cacheprovider` (قبل از اصلاح) | `2 failed, 1 passed` | 1 |
| `python -m pytest tests/unit/jobs/test_job_dispatcher.py -q -p no:cacheprovider` (بعد از اصلاح) | `10 passed` | 0 |
| `python -m pytest tests/unit/jobs/test_queue.py -q -p no:cacheprovider` | `10 passed` (شامل تست integration جدید) | 0 |
| `python -m pytest tests/unit/jobs -q -p no:cacheprovider` | `221 passed` | 0 |
| `python -m pytest tests/unit/jobs tests/unit/test_job_queue_stats_api.py tests/unit/test_job_queue_replay_api.py tests/unit/test_job_queue_dead_letter_summary.py tests/test_brsapi_job_registry.py -q -p no:cacheprovider` | `291 passed` | 0 |
| `python -m ruff check jobs/job_dispatcher.py tests/unit/jobs/test_job_dispatcher.py tests/unit/jobs/test_queue.py` | `All checks passed!` | 0 |
| بازتولید دستی retry (کامپوننت‌های واقعی) | `run1 success=False error='boom'` → `retry` قبل: `error='Duplicate job'`؛ بعد: اجرای مجدد | — |

محیط: Python 3.11.9، pytest 9.1.1، `PYTHONUTF8=1`. اجرای تست با `-p no:cacheprovider`.

---

## ۷. فایل‌های تغییرکرده در این نشست

- `jobs/job_dispatcher.py` — اصلاح J1 (پاکت dedup برای context فراخوان).
- `tests/unit/jobs/test_job_dispatcher.py` — افزودن `TestCallerSuppliedOccurrenceId` (۳ تست) + import `JobContext`.
- `tests/unit/jobs/test_queue.py` — افزودن تست integration مسیر retry→dead-letter با dispatcher واقعی.

هیچ فایل دیگری لمس نشد. تغییرات سایر عامل‌ها حفظ شد.

---

## ۸. موارد باز / مسدود

- **BLOCKED (محیط):** آزمون واقعی چند-فرایندی/Redis برای retry و dead-letter end-to-end، و راستی‌آزمایی live رفتار `BrsApiJobRegistry.run_job` (J2). در این محیط Redis و DB در دسترس نبودند.
- **OPEN (P2):** تفکیک دقیق `None` (پاسخ خالی معتبر / خطای منبع / موفقیت کاذب) در bridge دیسپچر.
- **OPEN (P3):** stubهای یتیم `jobs/*.py` — نیازمند تصمیم محصول.

---

## ۹. نتیجهٔ نهایی این مرحله

**PASS محدود و مستند** برای دامنهٔ «هستهٔ dispatch/queue/locking/dedup/scheduler»:
- باگ P1 (J1) با تستِ ابتدا RED و سپس GREEN اصلاح شد.
- رگرسیون این دامنه (۲۹۱ تست مرتبط) بدون خطا گذشت.
- موارد BLOCKED/OPEN صادقانه اعلام شدند و به‌اشتباه PASS نشدند.

این PASS صرفاً معتبرِ همین دامنهٔ آفلاین است و به‌منزلهٔ تأیید کل سامانه نیست.
