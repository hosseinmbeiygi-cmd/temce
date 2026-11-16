# قسمت ۰۶ — صف جاب، زمانبند، قفل توزیعشده و workerها

| | |
|---|---|
| **مبنای اندازهگیری** | `73a6c52d` (`fix(monitoring): use settings.job_queue_dead_letter instead of hardcoded key`) — همان مبنای قسمت ۰۵؛ HEAD بین دو قسمت جابهجا نشد. |
| **وضعیت worktree** | همچنان ۱۰۴ فایل Dirty (بدون تغییر نسبت به قسمت ۰۵). فایلهای محوری این قسمت (`apps/scheduler/app.py`, `apps/worker/*`, `jobs/*`) در `git status` **جزو فایلهای اصلاحشده نیستند** — یعنی شواهد زیر هم در HEAD کامیتشده و هم در worktree معتبراند. |
| **تعهد** | فقط فایلهای Markdown تحلیلی ساخته/ویرایش شدند. **هیچ فایل کد، پیکربندی، تست یا compose تغییر نکرد.** |
| **زبان** | فارسی (هماهنگ با سری) |

---

## ۱ — فهرست فایلها و ابعاد (شمارش واقعی، فقطخواندنی)

| درخت | فایل `.py` | مجموع خط | یادداشت |
|---|---:|---:|---|
| `jobs/` | ۵۹ | ~۵٬۶۷۵ | شامل `definitions/` (۲۶ فایل) |
| `apps/scheduler/` | ۳ | ۴۴۸ | `app.py`, `__main__.py`, `__init__.py` |
| `apps/worker/` | ۵ | ۱۶۴ | `app.py`, `consumer.py`, `error_policy.py`, ... |
| `apps/strategy_worker/` | ۱ | **۲** | نقطه ورود مرده قدیمی (لایه ۱۵۶ همچنان پابرجا) |
| `apps/decision_engine/` | ۱ | ۱۷۵ | خارج از محدوده، صرفاً ثبت شد |
| `brsapi/jobs/registry.py` | ۱ | ۱٬۸۴۶ | رجیستری موازی BrsApi |

شمارش ایستای پیکربندی زمانبند: **۳۳ فراخوانی `add_job` (همگی یونیک)**، **۷۰ ورودی `__all__`** در `jobs/definitions/__init__.py`، **۲۶ فایل** در بسته `jobs/definitions/`، و **۴ فراخوانی بدون `max_instances` صریح**.

---

## ۲ — ردیابی جریان اجرا

### ۲‑الف — مسیر «صف» (زمانی که `JOB_QUEUE_ENABLED=true` باشد)
```
SchedulerApp.start()                     apps/scheduler/app.py:59
  ├─ job_registry.register_module(job_definitions)   → ۷۰ کلاس BaseJob
  ├─ register_all_brsapi_jobs()          → رجیستری BrsApi (فعالها)
  ├─ if _queue_enabled: brsapi_registry.run_handler = lambda n: publisher.publish(n)
  └─ APScheduler.add_job(wrapper, trigger, max_instances=1, ...)
       └─ _execute(job_name)              app.py:35
            ├─ publish() → LPUSH job:queue {job_name, params, job_id, token, ttl, ...}
            │                          jobs/queue_publisher.py:86-121
            └─ (اگر publish برگرداند None) → job_dispatcher.dispatch() درونفرایند  ← JOB-11
────────────────────────────────────────────────────────────────────────────
WorkerApp.start()                        apps/worker/app.py:27
  ├─ _register_jobs()  (رجیستریها فرایندمحلیاند → باید اینجا هم پر شوند)
  ├─ await get_cache().initialize()
  └─ WorkerConsumer.start()              apps/worker/consumer.py:24
       └─ if consumer.is_available: consumer.start()   ← فقط Redis چک میشود، نه flag
            └─ _consume_loop()          jobs/queue_consumer.py:140
                 ├─ set worker lease (ex=lease_seconds)
                 ├─ _recover_orphaned_messages()   ← فقط یکبار، در startup
                 └─ while running:
                      expire(lease) → _claim_message() [BRPOPLPUSH → processing:<id>]
                      → _handle_message(raw)
                          ├─ json + auth token + job_name
                          ├─ _dispatch() → JobDispatcher.dispatch()
                          │     ├─ job_registry.get(name) ──┐
                          │     │   └─ None → _dispatch_brsapi_direct_job()  ← بیرون از قفل! (JOB-03)
                          │     └─ (BaseJob) → hold(c_lock) + Semaphore(10) + job.run()
                          └─ success / skipped / benign → processed++
                              failure → _handle_failure → _requeue(attempt+1) | _dead_letter
                      └─ finally: _ack_message() [LREM processing]   ← unconditional (JOB-04)
```

### ۲‑ب — مسیر واقعی **production** (یافته محوری)
`docker-compose.production.yml` حامل `ENV: production`، `DISABLE_SCHEDULER_IN_API: "1"`، `api: replicas: 2`، `worker: replicas: 2` و یک `scheduler` اختصاصی است — ولی **هیچ `JOB_QUEUE_ENABLED` و `JOB_QUEUE_TOKEN` ندارد**. `job_queue_enabled` در `core/config/__init__.py:307` پیشفرض **`False`** دارد. نتیجه:

```
scheduler (تک رپلیکا) ── run_handler=None ──► APScheduler مستقیماً run_job()/dispatch() را
                                              در همان فرایند اجرا میکند (in-process)
worker × 2 ── Redis وصل است ──► JobQueueConsumer.start() فعال میشود
                               ──► BRPOP روی job:queueای که هرگز پیامی نمیگیرد  (بیکار)
```
یعنی قفل توزیعشده، lease، dead-letter و retry صف — تمام ابزارهایی که قسمت ۰۱ بهعنوان نقطه قوت ثبت کرده — **در محیط تولید در مدار نیستند**.

---

## ۳ — سیاست شکست (گامبهگام)

| گام | سیاست | محل |
|---|---|---|
| `publish` (Redis.down / استثناء) | **fail-open ← درونفرایند**، `None` برمیگرداند | `queue_publisher.py:98-121` + `app.py:41-46` |
| قفل توزیعشده (خطای Redis) | **fail-closed**: «قفلی که مالکیتش ثابت نشد → job اجرا نشود» | `locking.py:96-98` |
| قفل (Redis در دسترس نیست) | تخریب به قفل درونحافظهای با همان معنا | `locking.py:164-174` |
| تمدید قفل | heartbeat هر `ttl/3`؛ از دست رفتن مالکیت → **هشدار ولی job ادامه مییابد** (غیرانحصاری) | `locking.py:221-232` |
| claim پیام | `BRPOPLPUSH` به `processing:<worker_id>` (lease) | `queue_consumer.py:173-198` |
| ACK | **همیشه** در `finally`، حتی اگر requeue شکست خورده باشد | `queue_consumer.py:163-166` |
| retry | ۳ تلاش، **بدون هیچ تأخیر/backoff**، `LPUSH` فوری به صف اصلی | `queue_consumer.py:291-307` |
| dead-letter | `LPUSH job:dead` + هشدار آستانه با cooldown Redis + تلگرام | `queue_consumer.py:309-331` |
| پیام بد / توکن نامعتبر / بینی `job_name` | حذف ساکت + شمارنده | `queue_consumer.py:226-250` |
| `BaseJob.run` استثناء | تبدیل به `JobResult.failure` (پرتاب نمیشود) | `base_job.py:43-46` |
| زمانبند APScheduler | `max_instances=1` صریح روی ۲۹ تا از ۳۳ job | `apps/scheduler/app.py` |

> **تضاد جالب با قسمت ۰۵:** `BrsApiBudgetGovernor` بدون Redis به «حافظه» تخریب میشود و **شمارنده را ریست میکند (fail-open)** (ING-07)، ولی `JobLocking` بدون Redis **fail-closed** میکند. دو زیرسیستم روی همان وابستگی، دو سیاست متضاد دارند.

---

## ۴ — یافتهها (`JOB-01` … `JOB-14`)

| شناسه | شدت | خط دقیق | عنوان | اثر عملی | جهت اصلاح |
|---|---|---|---|---|---|
| **JOB-01** | 🔴 بحرانی | `config.py:307` + `docker-compose.production.yml:20-33,86-106` | **صف در production خاموش است؛ scheduler تک نقطه شکست** | `JOB_QUEUE_ENABLED` پیشفرض `False` و compose تولید آن را ست نمیکند (فقط compose توسعه در `:58,124` ست کرده). scheduler اختصاصی تمام ۳۳+ job را درونفرایند اجرا میکند؛ ۲ رپلیکای `worker` بیکار BRPOP میکنند؛ قفل توزیعشده / lease / dead-letter / retry صف هرگز بهکار نمیروند. ترکیب با `DISABLE_SCHEDULER_IN_API=1` یعنی **اگر scheduler بیفتد هیچ jobی اجرا نمیشود**. | `JOB_QUEUE_ENABLED=true` و `JOB_QUEUE_TOKEN` را در compose تولید الزامی کنید؛ همزمان `validate_production()` گیتی برای این دو کلید بیفزایید. |
| **JOB-02** | 🟠 بالا | `apps/worker/consumer.py:24-32` + `queue_consumer.py:72,234` + `queue_publisher.py:64` | **worker به flag وابسته نیست + صف بدون احراز هویت** | `WorkerConsumer.start()` فقط `consumer.is_available` (یعنی Redis وصل است) را چک میکند، **نه `settings.job_queue_enabled`** — برخلاف docstring خودش («queue mode disabled → worker idle»). در production توکن خالی است، پس `if self._token and ...` هیچ بررسی انجام نمیدهد؛ publisher هم توکن **تصادفی per-process** میسازد. صف Redis برای هر عامل روی شبکه داخلی قابل تزریق job است و worker آن را اجرا میکند. `job_queue_stats` صادقانه `auth_enabled: false` میدهد. | شرط `job_queue_enabled` را به consumer اضافه کنید؛ توکن را در production الزامی و از طریق secret تزریق کنید؛ در صورت نبود توکن، consumer fail-closed کند. |
| **JOB-03** | 🟠 بالا | `job_dispatcher.py:36-44` در مقابل `:63` | **مسیر BrsApi بیرون از قفل توزیعشده / dedup / semaphore** | `_dispatch_brsapi_direct_job()` در خط ۴۱، **قبل از** `hold()` خط ۶۳ فراخوانی میشود. تمام jobهای `brsapi_*` در رجیستری BrsApiاند نه `JobRegistry`، پس **بدون قفل، بدون dedup، بدون retry policy و بدون محدودیت همزمانی** اجرا میشوند — دقیقاً همان jobهایی که سهمیه BrsApi مصرف میکنند (ING-07/ING-08). پیام تکراری یا بازیابی orphan میتواند همان درخواست سهمیهبر را دوباره بفرستد. | قفل را پیش از شاخهبندی بگیرید (روی `job_name` برای هر دو مسیر)، یا `run_job` خودش را idempotent/قفلدار کنید. |
| **JOB-04** | 🟠 بالا | `queue_consumer.py:163-166, 301-315` | **ACK unconditional + requeue best-effort ⇒ از دست رفتن دائمی پیام** | `_ack_message` (حذف از `processing`) در `finally` **بیقیدوشرط** اجرا میشود. `_requeue` و `_dead_letter` در صورت `client is None` ساکت `return` میکنند و استثناءها را نمیگیرند. اگر Redis در لحظه requeue خطا دهد، پیام هم از processing حذف شده و هم به صف/dead نرسیده → **at-most-once ناخواسته**. | ACK را مشروط کنید: فقط پس از موفقیت dispatch یا موفقیت `_requeue`/`_dead_letter`؛ در غیر این صورت پیام را در `processing` نگه دار تا بازیابی orphan آن را برگرداند. |
| **JOB-05** | 🟡 متوسط | `queue_consumer.py:152, 204-223, 122-136` | **بازیابی پیامهای یتیم فقط یکبار در startup** | `_recover_orphaned_messages()` تنها یکبار در ابتدای `_consume_loop` صدا میشود. `stop()` فقط کلید lease را پاک میکند و پیامهای `processing:<خودش>` را برنمیگرداند. اگر یک worker کرش کند و worker تازهای start نشود (یا آخرین worker خاموش شود)، پیامها تا ابد در لیست processing معلق میمانند؛ lease ۶۰۰s منقضی میشود ولی کسی بهصورت دورهای بررسی نمیکند. | بازیابی را به یک تیک دورهای (مثلاً هر ۶۰s) در حلقه اصلی منتقل کنید؛ `stop()` پیش از پاک کردن lease، پیامهای خودش را requeue کند. |
| **JOB-06** | 🟡 متوسط | `queue_consumer.py:301-307` + `retry_policy.py` | **retry بدون backoff؛ `JobRetryPolicy` عملاً مرده است** | `_requeue` بلافاصله `LPUSH` میکند؛ ۳ تلاش در چند میلیثانیه پشتسرهم. در حالی که `JobRetryPolicy` با `base_delay=10s`, `backoff_factor=2`, `jitter=True` و `await wait()` کامل نوشته شده، ولی در dispatcher **فقط `clear_retries()`** (خط ۷۴) استفاده میشود — چهار متد `should_retry/get_delay/record_retry/wait` بیکاراند. یک خطای گذرای ۳۰ ثانیهای (DB/شبکه) هر ۳ تلاش را میسوزاند → dead-letter بی دلیل. | `wait()` سیاست را پیش از `LPUSH` فراخوانی کنید (با jitter)، یا سیاست مرده را حذف کنید تا دو منبع حقیقت وجود نداشته باشد. |
| **JOB-07** | 🟡 متوسط | `apps/api/endpoints/jobs.py:262-288` | **آمار صف، وضعیت فرایند API را نشان میدهد نه workerها** | `job_queue_stats` از `get_job_queue_consumer()` **درون فرایند API** singleton میگیرد؛ consumer در API هرگز `start()` نمیشود، پس `processed/failed/dead_lettered` همیشه صفر و `running=false` است حتی وقتی workerها فعالاند. docstring محدودیت را میداند ولی همچنان بهعنوان «stats» ارائه میشود → اپراتور فکر میکند صف مرده است. | شاخصها را در Redis مشترک ذخیره کنید یا صریحاً `source: "api-process (not worker)"` و هشدار بدهید. |
| **JOB-08** | 🟡 متوسط | `apps/worker/app.py:6,16` + `jobs/scheduler.py:28,124` | **دو سیاست شکست / دو زمانبند موازی، هردو مرده** | `ErrorPolicy` در `WorkerApp` ساخته میشود ولی **هیچ استفادهای** ندارد (منطق واقعی در `queue_consumer._handle_failure` است). `jobs/scheduler.py` یک `JobScheduler` مستقل + singleton `scheduler = JobScheduler()` دارد که تنها مصرفکنندهاش `tests/unit/jobs/test_scheduler.py` است. | حذف یا ادغام؛ در غیر این صورت اصلاح retry در آینده ممکن است در فایل اشتباه انجام شود. |
| **JOB-09** | 🟡 متوسط | `jobs/definitions.py` (۱۵ خط) در مقابل `jobs/definitions/` (۲۶ فایل) | **تداخل نام: فایل مرده با self-import بالقوه** | پایتون پکیج را بر ماژول همنام مقدم میدارد، بنابراین `from jobs import definitions` همیشه `__init__.py` بسته را میگیرد و `definitions.py` **هرگز وارد نمیشود**. بدتر، محتوای آن `from jobs.definitions import BackfillHistoricalDataJob` است — اگر روزی پکیج حذف/جابهجا شود، تبدیل به **import دوری از خودش** میشود. | فایل shim را حذف کنید؛ آن کلاس همین حالا مستقیماً در `definitions/__init__.py` از `services.history_backfill_service` وارد میشود. |
| **JOB-10** | 🟡 متوسط | `apps/scheduler/app.py:73-76, 89-90` | **ناهماهنگی `max_instances` + ادعای مستندی مشکوک** | ۴ job نخست (`SyncInstrumentsJob`, `SyncQuotesJob`, `SyncSnapshotsToQuotesJob`, `SyncCodalJob`) فاقد `max_instances` صریحاند، در حالی که ۲۹ تای بعدی دارند. کامنت خط ۸۹-۹۰ میگوید «APScheduler default is 3» — در حالی که پیشفرض مستند APScheduler برابر `1` است. | چهارتا را صریح کنید؛ کامنت را اصلاح کنید. (مرز روش: نسخه نصبشده APScheduler اجرا/راستیآزمایی نشد → این تناقض مستند/کد است، نه حکم قطعی رفتار زماناجرا.) |
| **JOB-11** | 🟢 کم | `apps/scheduler/app.py:35-46` | **fallback شکست «به سمت تکرار» است، نه fail-closed** | اگر `publish()` به `None` برگردد (Redis down)، scheduler درونفرایند `dispatch` میکند. در production با `DISABLE_SCHEDULER_IN_API=1` فقط یک producer هست، ولی در compose توسعه یا پیکربندی ناقص (چند رپلیکای scheduler) هر رپلیکا جداگانه اجرا میکند → تکثیر N باره. | در حالت چندرپلیکا، شکست publish را fail-closed کنید (لاگ + رها کردن tick) نه in-process. |
| **JOB-12** | 🟢 کم | `apps/scheduler/app.py:404-410` | **Redis init بدون await، بلافاصله `start()`** | `asyncio.create_task(get_cache().initialize())` و سپس بیدرنگ `self.start()`. در پنجره کوتاه پیش از وصل Redis، `JobLocking` به قفل درونحافظهای تخریب میکند و `publish` ممکن است fail کند → fallback درونفرایند (JOB-11). خود کد پذیرفته، ولی ترتیب غیرقطعی است. | `await initialize()` یا گارد «ready» پیش از ثبت jobها. |
| **JOB-13** | 🟢 کم | `job_dispatcher.py:46` | **رشته mojibake در کامنت** | `republished unchanged on retry â€”` ( UTF8 mis-decode ). بیضرر، ولی همان آلودگی رشتهای است که در گزارش ۱۶۰ لایهای و قسمت ۰۳ پاکسازی شد. | جایگزینی با `—` / `-`. |
| **JOB-14** | 🟢 کم | `job_dispatcher.py:31,67` | **`Semaphore(10)` عملاً بیاثر** | dispatcher محدودیت همزمانی ۱۰ دارد، ولی consumer یک حلقه **ترتیبی** است که `_handle_message` را `await` میکند → حداکثر همزمانی ۱. پیچهای همزمانی بدون اثر. | یا consumer را concurrent کنید، یا semaphore را به محل واقعی اعمال/حذف کنید. |

---

## ۵ — نقاط قوت تأییدشده

1. **قفل توزیعشده واقعاً محکم است:** `SET NX PX` اتمیک، `Lua` compare-and-del / compare-and-pexpire (فقط مالک آزاد/تمدید کند)، heartbeat هر `ttl/3`، و **fail-closed** هنگام خطای Redis (`locking.py:96-98`). تخریب به قفل درونحافظهای هم همان معنا را حفظ میکند.
2. **طراحی lease درست:** `BRPOPLPUSH` به `job:queue:processing:<worker_id>` + کلید lease هر worker → کرش، پیام را گم نمیکند (کاستی فقط در دورهای نبودن بازیابی است، JOB-05).
3. **dead-letter کامل:** آستانه `dl_alert_threshold`، cooldown Redis `alert:dl_threshold`، ارسال تلگرام با `suppress(Exception)` تا مسیر درخواست نشکند (`queue_consumer.py:317-331`).
4. **بازخوانی HEAD:** کامیت `73a6c52d` دقیقاً کلید هاردکد `job:dead` را به `settings.job_queue_dead_letter` تبدیل کرده (`queue_consumer.py:71`) — یکی از هشدارهای قدیمی گزارش عرضی بسته شد.
5. **`WorkerApp._register_jobs`** مشکل واقعی «رجیستری فرایندمحلی» را درست تشخیص داده و رفع کرده؛ کامنتش دقیقاً مینویسد worker مستقل قبلاً هر پیام را `Job <name> not found` میکرد.
6. **`EX-13` بسته شد:** `DISABLE_SCHEDULER_IN_API` واقعاً در `apps/api/app.py:979` خوانده میشود و compose تولید آن را ست کرده؛ تکثیر «هر API رپلیکا + scheduler» حذف شده است.
7. **idempotency بکفیلها:** `SyncNavAllJob` دو بار در روز (صبح + بعد از بستهشدن) با توضیح صریح «هزینه سهمیه صفر»؛ چهار بکفیل fulmarket با فاصله ۳۰ دقیقهای و `progress/cancel_requested` (`brsapi/jobs/registry.py`).
8. **تشخیص خطای خوشخیم:** `_BENIGN_ERROR_MARKERS` («Lock not acquired» / «Duplicate») را به `processed` میبرد نه dead-letter، تا قفل توزیعشده صف را پر نکند.

---

## ۶ — تصحیح گزارش اصلی و بازخوانی یافتههای پیشین

### ۶‑الف — تصحیح `DEEP_ANALYSIS_160_LAYERS_2026-11-13.md`
| # | ادعای گزارش عرضی | واقعیت در HEAD `73a6c52d` |
|---|---|---|
| ۱۹ | «Redis job queue with distributed lock + dead-letter» بهعنوان **نقطه قوت فعال** فهرست شده | ابزارها کاملاً ساخته شدهاند ولی **در production غیرفعالاند** (`JOB_QUEUE_ENABLED` ست نشده). باید قید «ساختهشده / وصلنشده» افزوده شود — همان الگویی که قسمت ۰۴ در لایه زیرساخت و قسمت ۰۵ در بودجه پیدا کرد. |
| ۲۰ | لایه ۱۵۶ / EX-13: تکثیر تریگرها توسط `DISABLE_SCHEDULER_IN_API` بسته شد | درست؛ ولی **بهای آن تکنقطهشکست شدن اجراست**: بستن تکثیر، بدون روشن کردن صف، تمام jobها را روی یک scheduler متمرکز کرد (JOB-01). بستن یک ریسک، ریسک تازهای ساخت. |

### ۶‑ب — بازخوانی یافتههای قسمت ۰۵
| یافته | وضعیت |
|---|---|
| `ING-03` (زمانبند ingestion بدون نگهبان بازورود) | **تقویت شد**: APScheduler در این لایه ۲۹/۳۳ job را با `max_instances=1` مهار کرده، ولی ۴ استثناء (JOB-10) و مسیر BrsApi خارج از dispatcher (JOB-03) همچنان بدون مهاراند. |
| `ING-07` (وابستگی بودجه به Redis) | **تضاد سیاست کشف شد**: همان وابستگی در `JobLocking` **fail-closed** است، در `BrsApiBudgetGovernor` **fail-open + ریست شمارنده**. یک وابستگی، دو رفتار متضاد. |
| `CFG-06`, `CFG-17`, `CFG-18` | بدون تغییر؛ همچنان در worktree اصلاحشده / زنده / حلشده در کد (بند ۶ قسمت ۰۵). |

### ۶‑ج — حدسهایی که حین راستیآزمایی **رد شدند** (سنت قسمت ۰۳/۰۴)
1. «لامبدای `run_handler` یک coroutine برمیگرداند و APScheduler آن را await نمیکند» → **رد**: `registry.py:518` صریحاً `await self._run_handler(job_name)` دارد.
2. «`brpoplpush` bytes برمیگرداند ولی `lrem` با str صدا میشود → پیامهای پردازششده دوباره اجرا میشوند» → **رد**: `core/cache.py:97` با `decode_responses=True` میسازد؛ هر دو `str`اند.
3. «`BackfillHistoricalDataJob` چون از `services/` میآید `BaseJob` نیست و ثبت نمیشود → Job not found» → **رد**: `services/history_backfill_service.py:435` آن را `class ...(BaseJob)` تعریف کرده و `definitions/__init__.py` مستقیماً وارد میکند.
4. «`_dispatch_brsapi_direct_job` به allow-list سختکد وابسته است و سایر `brsapi_*`ها گم میشوند» → **رد**: کامنت `job_dispatcher.py:85-88` میگوید allow-list حذف شده و `registry.get()` منبع واحد است.
5. «چهار job بدون `max_instances` حتماً همپوشان میشوند» → **رد مشروط**: پیشفرض APScheduler برابر `1` است؛ مسئله واقعی ناهماهنگی و کامنت نادرست است (JOB-10)، نه همپوشانی قطعی.

---

## ۷ — مرز روش

- **بدون اجرا:** هیچ تستی اجرا نشد، سرور/APScheduler/worker بوت نشد، به Redis یا DB زنده متصل نشدیم، و هیچ `BRPOP`/`LPUSH` واقعی انجام نشد.
- **بدون ادعای زماناجرا:** رفتار قفل، lease، dead-letter و صف فقط از خواندن کد و شمارش ایستا استنتاج شد؛ عمق واقعی `job:queue`، تعداد ۳۰۲ها و وضعیت lease در محیط تولید راستیآزمایی نشد.
- **نسخه وابستگیها:** نسخه نصبشده APScheduler بررسی نشد؛ ادعای «default=3» در کامنت صرفاً بهعنوان تناقض مستند/کد ثبت شد (JOB-10).
- **پوشش:** `jobs/definitions/` (۲۶ فایل / ۷۰ کلاس) بهصورت سطح رجیستری بررسی شد، نه تکتک بدنه `execute()` هر job؛ آن سطح به قسمت ۰۷ (سیگنال/دروازهها) و ۰۸ (بکتست) موکول است.
- **هماهنگی زنده:** HEAD نسبت به قسمت ۰۵ ثابت ماند (`73a6c52d`)، ولی worktree همچنان ۱۰۴ فایل Dirty دارد و فرایند دیگری همزمان در مخزن کار میکند؛ وضعیت را نباید پایدار فرض کرد.

---

## پیوست — ماتریس ریسک تجمیعی (افزودهشده به `README.md`)

| خوشه | یافتهها | شدت مؤثر | اثر مرکب |
|---|---|---|---|
| **P — صف خاموش / تکنقطهشکست اجرا** *(۰۶)* | `JOB-01`, `JOB-02`, `JOB-11`, `JOB-12`, `EX-13` | 🔴 بحرانی | production صف را روشن نمیکند؛ ۲ worker بیکار؛ scheduler تنها مالک ۳۳+ job؛ صف بدون auth |
| **Q — exactly-once ناقص** *(۰۶)* | `JOB-03`, `JOB-04`, `JOB-05`, `JOB-06` | 🟠 بالا | BrsApi بیرون از قفل؛ ACK unconditional؛ بازیابی تکباره؛ retry بدون backoff |
| **R — کد مرده / رجیستری و سیاست موازی** *(۰۶)* | `JOB-07`, `JOB-08`, `JOB-09`, `JOB-10`, `JOB-13`, `JOB-14` | 🟡 متوسط | `ErrorPolicy`/`JobScheduler`/`RetryPolicy`/`definitions.py` مرده؛ stats گمراهکننده |

ترتیب بستن پیشنهادی (بدون تغییر کد، صرفاً اولویت): **`P → N → Q → H → B → M → L → R → I → J → O → E → G → K`**.

---

*فقطخواندنی نسبت به کد · ایستا · بدون اجرای تست کامل، بدون اتصال به DB/Redis زنده، بدون بوت سرور یا worker.*
