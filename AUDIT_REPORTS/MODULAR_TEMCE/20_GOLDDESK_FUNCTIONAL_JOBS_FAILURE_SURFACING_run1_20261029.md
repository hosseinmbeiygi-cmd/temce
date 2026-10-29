# ممیزی جاب‌های تابعی GoldDesk — پنهان‌سازی خطا و «موفقیت کاذب»

- **تاریخ:** 2026-10-29
- **نسخهٔ گزارش:** run1
- **دامنه:** `brsapi/jobs/gold_desk_jobs.py` (شش جاب تابعی `gold_*`) و مسیر اجرای آن‌ها در `brsapi/jobs/registry.py::_run_direct_job` / `run_job_now`، به‌همراه مصرف‌کننده‌ها (`apps/api/endpoints/jobs.py`, `scripts/run_gold_desk_jobs.py`, `jobs/job_dispatcher.py`).
- **شاخه/HEAD:** `integration/golddesk-fixes`, HEAD=`be8b4ff4839ee1e2bdacd791e7be176044e1eebd` (بدون تغییر).
- snapshot: `_snapshots/t16-golddesk-jobs.txt`.

> این گزارش گزارش‌های ۱۸/۱۹ و پیش‌ازآن را بازنویسی نمی‌کند.

---

## ۱. خلاصهٔ مدیریتی

شش جاب تابعی GoldDesk (`gold_snapshot`, `gold_score_persist`, `gold_alert_evaluate`, `gold_fund_nav`, `gold_portfolio_value`, `gold_daily_history`) هر شبانه‌روز توسط scheduler/queue اجرا می‌شوند و snapshot و جدول‌های `gold_*` را پر می‌کنند.

**یک باگ P2 (موفقیت کاذب) یافت و اصلاح شد:** هر تابع `job_gold_*` استثناها را با `logger.exception(...)` می‌بلعید و هرگز re-raise نمی‌کرد. چون `_run_direct_job` «نبودِ استثنا» را موفقیت تلقی می‌کند، هر خطای واقعی (DB down، خطای snapshot، خطای cache) به‌صورت **`success=True`** گزارش می‌شد. این هم گزارش‌های `[OK]` جعلی در API/CLI می‌ساخت و هم مسیر retry/dead-letter صف را بی‌اثر می‌کرد.

اصلاح: پنج جاب (همهٔ مواردی که بدنهٔ try/except دارند) پس از ثبت لاگ، استثنا را دوباره `raise` می‌کنند؛ `_run_direct_job` آن را به `SyncReport(success=False, error=…)` تبدیل می‌کند. جاب ششم (`gold_daily_history`) صرفاً no-op است (بدون try/except) و دست‌نخورده ماند.

---

## ۲. یافتهٔ اصلاح‌شده (J4 — P2)

**فایل:** `brsapi/jobs/gold_desk_jobs.py` — پنج بلوکِ `except Exception as exc:` در `job_gold_snapshot` (خط ۷۵), `job_gold_score_persist`, `job_gold_alert_evaluate`, `job_gold_fund_nav`, `job_gold_portfolio_value`.

**شواهد کد (قبل):**

```python
try:
    async for session in get_session():
        snap = await snapshot_service.build_snapshot(session)
        ...
        break
except Exception as exc:
    logger.exception("gold_snapshot failed: %s", exc)   # فقط لاگ؛ خروج بی‌خطا

async def _run_direct_job(...):
    try:
        await fn(force=force)          # تابع هرگز استثنا نمی‌دهد → «موفق»
    except Exception as exc:
        success = False
        error = str(exc)
    return SyncReport(endpoint=job_name, success=success, ...)
```

**شرایط بازتولید (آفلاین، واقعی):** با patch کردن `snapshot_service.build_snapshot` به تابعی که `RuntimeError` می‌دهد و صدا زدن `registry._run_direct_job("gold_snapshot")`.
خروجی واقعی قبل از اصلاح: `report.success = True | error = None`.

**علت ریشه‌ای:** الگوی «لاگ و بلعِ استثنا» در سطح تابع جاب با قرارداد موفقیتِ `_run_direct_job` (exception ⇒ failure) ناسازگار است؛ خطای پنهان‌شده در قالبِ موفقیت به بالا منتقل می‌شد.

**اثر:**
- گزارش `[OK] gold_snapshot` حتی وقتی snapshot ساخته نشده؛
- در حالت صف مسیر retry/dead-letter هرگز فعال نمی‌شد؛
- نبودِ دادهٔ تازه به‌عنوان «موفقیت» پنهان می‌شد (نقض تفکیک «موفقیت دارای داده» از «خطای منبع»).

**اصلاح (حداقلی):** افزودن `raise` به پنج بلوکِ except با کامنتِ دلیل. هیچ تغییر رفتاری دیگری (persist/cache/broadcast) انجام نشد.

**تست‌ها:**
- RED: `tests/unit/test_gold_desk_job_failure_surfacing.py` → `2 failed, 1 passed` (exit 1).
- GREEN: همان فایل → `3 passed` (exit 0).
- تست با `get_session`ِfake انجام می‌شود تا به PostgreSQL نیاز نباشد.

**معیار بستن مورد:** خطای داخل جاب باید `success=False` بدهد؛ مسیر موفق باید سبز بماند؛ API/CLI نباید خطا را پنهان کنند. ✅ برآورده شد.

---

## ۳. یافته‌های مرتبط (مستند)

- **R2 (باز، P3):** `gold_daily_history` عمداً no-op است (بدون تغییر؛ تصمیم محصول).
- **R3 (باز، P2/BLOCKED):** تفسیر یکسانِ `None` در bridge dispatcher (نیازمند DB زنده).

نکتهٔ ریشه‌ای مشترک J4 و R2: مسیر جاب‌های تابعی هیچ سیگنال شکستی به بالا نمی‌داد. با اصلاح J4 مسیر خطای واقعی باز شد؛ R2 (no-op عمدی) هم‌چنان «موفق» گزارش می‌شود و باید یا پیاده شود یا از زمان‌بندی/گزارش حذف شود.

---

## ۴. بررسی سلامت مصرف‌کننده‌ها (بدون شکست)

- `apps/api/endpoints/jobs.py::run_scheduler_job` → `registry.run_job_now(job_name)` را در try/except صدا می‌زند و `success` را منتقل می‌کند؛ با اصلاح اخیر خطا اکنون به‌درستی به `ApiResponse(success=False)` می‌رسد.
- `scripts/run_gold_desk_jobs.py` → بر اساس `result["success"]` شمارش FAIL و exit code می‌سازد؛ اکنون خطاها واقعی شمرده می‌شوند.
- `jobs/job_dispatcher.py::_dispatch_brsapi_direct_job` → `SyncReport(success=False)` را به `JobResult.failure(...)` تبدیل می‌کند ⇒ مسیر retry/dead-letter صف فعال می‌شود.
- `src/gold_desk/api.py:653` → فقط `len(GOLD_DESK_JOBS)` را می‌خواند؛ تحت تأثیر قرار نمی‌گیرد.

---

## ۵. فرمان‌ها و نتایج واقعی

| فرمان | نتیجه | exit |
|---|---|---|
| بازتولید دستی: `_run_direct_job("gold_snapshot")` با `build_snapshot` معیوب (قبل از اصلاح) | `report.success = True`, `error = None` | 0 |
| `python -m pytest tests/unit/test_gold_desk_job_failure_surfacing.py -q -p no:cacheprovider` (قبل) | `2 failed, 1 passed` | 1 |
| `python -m pytest tests/unit/test_gold_desk_job_failure_surfacing.py -q -p no:cacheprovider` (بعد) | `3 passed` | 0 |
| `python -m pytest tests/unit/test_gold_desk_job_registry.py tests/unit/jobs/test_gold_fund_nav_persist.py tests/unit/test_gold_desk_job_failure_surfacing.py tests/unit/test_brsapi_registry_schedule_invariants.py -q -p no:cacheprovider` | `18 passed` | 0 |
| رگرسیون GoldDesk: `tests/unit/jobs/test_gold_macro_jobs.py tests/unit/jobs/test_gold_options_jobs.py` + موارد بالا | `38 passed` | 0 |
| `python -m ruff check brsapi/jobs/gold_desk_jobs.py tests/unit/test_gold_desk_job_failure_surfacing.py` | `All checks passed!` | 0 |

محیط: Python 3.11.9، pytest 9.1.1، `PYTHONUTF8=1`.

---

## ۶. فایل‌های تغییرکرده در این نشست (این مرحله)

- `brsapi/jobs/gold_desk_jobs.py` — افزودن `raise` به پنج بلوکِ except (J4).
- `tests/unit/test_gold_desk_job_failure_surfacing.py` (جدید) — سه تست: گزارش شکست در `_run_direct_job`، انتقال شکست به `run_job_now`، و سبزماندن مسیر موفق.

هیچ فایل دیگری لمس نشد؛ کار هم‌زمانِ دیگران حفظ شد.

---

## ۷. موارد باز / مسدود

- **OPEN (P3):** پیاده‌سازی یا حذف `gold_daily_history` (R2).
- **OPEN (P2):** تفکیک حالات `None` در bridge dispatcher (R3) — نیازمند DB/provider زنده.
- **BLOCKED (محیط):** اجرای واقعی جاب‌ها با PostgreSQL/Redis؛ رفتار جاب‌های صف end-to-end.

---

## ۸. نتیجهٔ نهایی این مرحله

**PASS محدود و مستند** برای دامنهٔ «جاب‌های تابعی GoldDesk»:
- باگ P2 (موفقیت کاذب به‌واسطهٔ پنهان‌سازی استثنا) با تستِ ابتدا RED و سپس GREEN اصلاح شد.
- رگرسیون مرتبط (۳۸ تست) و ruff سبز.
- موارد باز/BLOCKED صادقانه اعلام و به‌اشتباه PASS نشدند.

این PASS صرفاً برای همین دامنه است و به‌معنای تأیید کل سامانه نیست.
