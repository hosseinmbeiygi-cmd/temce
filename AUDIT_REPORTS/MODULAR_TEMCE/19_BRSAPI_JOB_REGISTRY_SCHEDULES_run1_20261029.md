# ممیزی رجیستری و زمان‌بندی جاب‌های BrsApi — گیت ساعات بازار، cron و ثبت APScheduler

- **تاریخ:** 2026-10-29
- **نسخهٔ گزارش:** run1
- **دامنه:** `brsapi/jobs/registry.py` (کلاس `BrsApiSyncJob`، `BrsApiJobRegistry`, `BRsAPI_SYNC_JOBS`, `run_job`, `_run_direct_job`, `register_with_apscheduler`)، `brsapi/jobs/gold_desk_jobs.py` (جاب‌های تابعی GoldDesk) و مصرف‌کننده‌ها در `jobs/job_dispatcher.py` و `apps/scheduler/app.py`.
- **شاخه/HEAD:** `integration/golddesk-fixes`, HEAD=`be8b4ff4839ee1e2bdacd791e7be176044e1eebd` (بدون تغییر در این نشست).
- snapshot: `AUDIT_REPORTS/MODULAR_TEMCE/_snapshots/t15-brsapi-registry.txt`.

> این گزارش گزارش‌های ۱۸ و پیش‌ازآن را بازنویسی نمی‌کند.

---

## ۱. خلاصهٔ مدیریتی

رجیستری BrsApi هستهٔ ingestion دوره‌ای بازار است و دو منبع حقیقت دارد:

1. `BRsAPI_SYNC_JOBS` (جاب‌های endpoint-محور، ۲۶ عدد) + `GOLD_DESK_JOBS` (جاب‌های تابعی، ۶ عدد) که در `get_brsapi_job_registry()` ثبت می‌شوند.
2. `apps/scheduler/app.py` که در حالت queue فقط trigger می‌کند و `run_handler` را روی publisher تنظیم می‌کند؛ در غیر آن، جاب‌های BrsApi درون‌فرایندی اجرا می‌شوند.

نتیجهٔ ممیزی: **ساختار سالم است** (۳۲ جابِ یکتا، ۲۵ جابِ فعال، بدون تکرارِ نام/id، همهٔ crontabها معتبر، گیت ساعات بازار روی همهٔ جاب‌های realtime برقرار است). یک گارد رگرسیونِ آفلاین افزوده شد تا این invariants در آینده نشکنند.

هیچ باگ فعالِ P0/P1 در این دامنه یافت نشد. موارد زیر به‌عنوان دین تکنیکال/تصمیم محصول مستند شدند:

- **R1 (P3):** پرچمِ `forced` در dataclass هرگز استفاده نمی‌شود.
- **R2 (P3):** جاب `gold_daily_history` صریحاً no-op است.
- **R3 (P2، BLOCKED برای بازبینی زنده):** bridge dispatcher مقدار `None` از `run_job` را همیشه «skip ساعات بازار» تفسیر می‌کند، در حالی که `None` حالت‌های دیگری هم دارد.

---

## ۲. موجودی بررسی‌شده

| محور | مرجع | نتیجه |
|---|---|---|
| ثبت جاب‌ها | `get_brsapi_job_registry()` | ۳۲ جاب یکتا (۲۶ endpoint + ۶ GoldDesk) |
| فعال/غیرفعال | `enabled`/`disabled` | ۲۵ فعال / ۷ غیرفعال |
| cronها | int (interval) و str (crontab) | ۲۲ interval + ۱۰ crontab، همه معتبر |
| گیت ساعات بازار | `market_hours_only`, `codal_window` | ۹ جاب گیت‌دار؛ Codal پنجرهٔ ۰۸:۰۰–۱۸:۰۰ |
| ثبت APScheduler | `register_with_apscheduler()` | ۲۵ جاب، id یکتا، بدون خطای trigger |
| جاب‌های تابعی GoldDesk | `gold_desk_jobs.GOLD_DESK_JOB_FUNCTIONS` | ۶ تابع، پایدار |

---

## ۳. یافته‌ها

### R1 — P3 (مستند، بدون تغییر) — پرچمِ مردهٔ `forced`

**فایل:** `brsapi/jobs/registry.py` خط ۶۷ — فیلد `forced: bool = field(default=False, repr=False)` در `BrsApiSyncJob` تعریف شده اما هیچ‌جا خوانده یا مقداردهی نمی‌شود (جست‌وجو: تنها محلِ وقوع همین تعریف است). مقدار «force» در عمل از پارامتر تابع `run_job(force=…)` می‌آید، نه این فیلد.

**اثر:** ندارد (کد مرده). پیشنهاد: حذف فیلد یا مستندسازی دلیل نگه‌داشتن آن.

### R2 — P3 (مستند) — جاب `gold_daily_history` عمداً no-op است

**فایل:** `brsapi/jobs/gold_desk_jobs.py:293`:
```python
async def job_gold_daily_history(force: bool = False) -> None:
    """Backfill روزانه historical bubble ..."""
    logger.info("gold_daily_history: started (placeholder — no-op)")
```
هر شب ۲۱:۰۰ زمان‌بندی می‌شود و در `_run_direct_job` به‌عنوان **موفقیت** گزارش می‌شود (تابع بدون خطا برمی‌گردد؛ `SyncReport.success=True`). یعنی جابِ زمان‌بندی‌شده «موفق» است ولی هیچ کاری نمی‌کند. یک تست (`tests/unit/test_gold_desk_job_registry.py`) صرفاً وجود و قابل‌فراخوانی‌بودن آن را می‌سنجد، نه اثرش.

**اثر:** «موفقیت کاذب» در گزارش جاب (بدون مصرف داده). نیازمند تصمیم محصول: پیاده‌سازی واقعی یا حذف از زمان‌بندی.

### R3 — P2 (مستند/BLOCKED برای بازبینی زنده) — تفسیر یکسانِ `None` در bridge

**فایل:** `jobs/job_dispatcher.py::_dispatch_brsapi_direct_job` (بخشِ هم‌زمانِ عامل دیگر — این ممیزی آن را تغییر نداد). حالاتِ زیر همگی `None` برمی‌گردانند:
- `job.endpoint_config is None` و تابعِ gold ناشناخته در `_run_direct_job`؛
- جاب‌های `*_history_24h`/`*_daily_history` وقتی هیچ نمادPro یافت نشود؛
- `sync_gold_currency_pro` که لیست خالی برگرداند؛
- بسته‌بودنِ گیت ساعات بازار.

از این‌ها فقط مورد آخر «skip مشروع» است؛ اما bridge همه را با `JobResult.skipped_result(reason="not due (market-hours gate)")` برچسب می‌زند. تفکیک دقیق نیازمند مشاهدهٔ رفتار واقعی در محیط دارای DB/provider است → **BLOCKED**.

---

## ۴. بررسی‌های سالم (PASS با شاهد)

بررسی واقعی (آفلاین، با کامپوننت واقعی rجیستری + APScheduler):

```
total jobs registered: 32 ; unique: 32 ; duplicate names: []
enabled: 25 ; disabled: 7
realtime jobs missing gate: []
brsapi_codal market_only/codal_window: True True
bad cron entries: []
registered in APScheduler: 25 ; unique ids: 25 ; dup ids: []
```

- **یکتایی نام:** هیچ دو جاب هم‌نامِ ثبت‌شده‌ای نیست (اگر بود، `register_many` یکی را بی‌صدا جایگزین می‌کرد).
- **گیت ساعات بازار:** همهٔ ۸ جاب realtime + `brsapi_codal` پرچم `market_hours_only` دارند؛ Codal با `codal_window=True` از پنجرهٔ ۰۸:۰۰–۱۸:۰۰ استفاده می‌کند.
- **cronها:** ۲۲ interval مثبت + ۱۰ crontab که همه با `CronTrigger.from_crontab(..., Asia/Tehran)` پارس می‌شوند.
- **ثبت APScheduler:** ۲۵ جاب با id یکتا؛ ثبت بدون start و بدون خطا.

---

## ۵. فرمان‌ها و نتایج واقعی

| فرمان | نتیجه | exit |
|---|---|---|
| بازتولید دستی invariantها (پایتون inline) | همه سالم؛ خروجی بالا | 0 |
| `python -m pytest tests/unit/test_brsapi_registry_schedule_invariants.py -q -p no:cacheprovider` | `5 passed` | 0 |
| `python -m pytest tests/test_brsapi_job_registry.py tests/unit/test_gold_desk_job_registry.py tests/unit/jobs/test_scheduler_app.py tests/unit/test_brsapi_registry_schedule_invariants.py -q -p no:cacheprovider` | `49 passed` | 0 |
| `python -m ruff check tests/unit/test_brsapi_registry_schedule_invariants.py` | `All checks passed!` | 0 |

محیط: Python 3.11.9، pytest 9.1.1، `PYTHONUTF8=1`.

---

## ۶. فایل‌های تغییرکرده در این نشست (این مرحله)

- `tests/unit/test_brsapi_registry_schedule_invariants.py` (جدید) — گاردِ آفلاین برای یکتایی نام، اعتبار cron، تداومِ گیت ساعات بازار realtime/Codal و یکتایی id در APScheduler.

هیچ فایل تولیدی تغییر نکرد (هیچ باگِ فعالی یافت نشد). کارِ هم‌زمانِ دیگران در `brsapi/jobs/registry.py` حفظ شد.

---

## ۷. موارد باز / مسدود

- **OPEN (P2):** تفکیک حالاتِ مختلف `None` در bridge dispatcher (R3) — نیازمند DB/provider زنده.
- **OPEN (P3):** حذف فیلد مردهٔ `forced` (R1)؛ تصمیم محصول دربارهٔ no-op بودن `gold_daily_history` (R2).
- **BLOCKED (محیط):** آزمون زندهٔ gیت با ساعت واقعی تهران و آزمون end-to-end جاب‌های مستقل بدون Redis/DB.

---

## ۸. نتیجهٔ نهایی این مرحله

**PASS محدود و مستند** برای دامنهٔ «رجیستری و زمان‌بندی جاب‌های BrsApi»:
- ساختار رجیستری سالم و همهٔ invariants حیاتی (یکتایی، cron معتبر، گیت ساعات بازار) با شاهدِ اجرای واقعی تأیید شدند.
- یک گارد رگرسیون آفلاین افزوده شد (۵ تست).
- موارد باز/BLOCKED صادقانه اعلام شدند و PASS نشدند.

این PASS صرفاً برای همین دامنهٔ آفلاین است و به‌معنای تأیید کل سامانه نیست.
