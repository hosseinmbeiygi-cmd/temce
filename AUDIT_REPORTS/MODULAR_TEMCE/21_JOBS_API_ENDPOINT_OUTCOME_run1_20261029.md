# ممیزی اندپوینت `/jobs` — پنهان‌سازی خطای DB در قالب «موفقیت با لیست خالی»

- **تاریخ:** 2026-10-29
- **نسخهٔ گزارش:** run1
- **دامنه:** `apps/api/endpoints/jobs.py` (اندپوینت‌های `GET /jobs`, `/jobs/scheduler`, `/jobs/scheduler/{name}/run`, `/jobs/queue/*`) و مصرف‌کنندهٔ فرانت‌اند.
- **شاخه/HEAD:** `integration/golddesk-fixes`, HEAD=`be8b4ff4839ee1e2bdacd791e7be176044e1eebd` (بدون تغییر).
- snapshot: `_snapshots/t17-jobs-api.txt`.

> این گزارش گزارش‌های ۱۸/۱۹/۲۰ و پیش‌ازآن را بازنویسی نمی‌کند.

---

## ۱. خلاصهٔ مدیریتی

اندپوینت‌های `/jobs/*` وضعیت اجرای جاب‌ها و صف توزیع‌شده را به ادمین نشان می‌دهند. خواهر‌اندپوینت‌ها (`/jobs/scheduler` و `/jobs/queue/stats`) در خطا به‌درستی `success=False` برمی‌گردانند؛ اما `GET /jobs` (`list_jobs`) در بلوک `except` مقدار **`success=True` با `items: []`** برمی‌گرداند که «خطای خواندن DB» را از «هیچ جابی وجود ندارد» تفکیک‌ناپذیر می‌کند.

**یک باگ P2 یافت و اصلاح شد، به‌همراه یک کد بی‌اثر:**

- **J5 (P2):** مسیر خطای `list_jobs` خطای منبع را با موفقیت-خالی پنهان می‌کرد.
- **J6 (P3):** عبارت بی‌اثرِ `row[9]` در `_row_to_dict` (بدون انتساب/اثر) حذف شد.

---

## ۲. یافتهٔ J5 — P2 (اصلاح‌شده)

**فایل:** `apps/api/endpoints/jobs.py::list_jobs` (بلوک `except`).

**شواهد کد (قبل):**

```python
except Exception:
    logger.exception("Failed to fetch jobs")
    return ApiResponse[dict[str, Any]](
        success=True,                     # ← خطا به‌عنوان موفقیت
        data={"items": [], "total": 0, ...},
    )
```

**شرایط بازتولید (آفلاین):** یک session که در `execute` استثنا می‌دهد و صدا زدن مستقیم `jobs_mod.list_jobs(session=_FailingSession())`.
خروجی واقعی قبل از اصلاح: `response.success is True` با `items=[]`.

**علت ریشه‌ای:** عدم تمایز میان «موفقیتِ خالی معتبر» و «خطای خواندن منبع» در پوشهٔ پاسخ؛ مشابه همان کنتراستی که خواهر‌اندپوینت‌ها از قبل حل کرده‌اند (منشور §۸).

**اثر:** ادمین/فرانت‌اند یک DB خراب یا query خطادار را به‌شکل «لیست خالی سالم» می‌دید؛ هشدار/مانیتورینگ فعال نمی‌شد.

**اصلاح (حداقلی):** مسیر خطا اکنون `success=False` و `error={"message": "Failed to fetch jobs"}` برمی‌گرداند (هم‌شکل با `/jobs/scheduler` و `/jobs/queue/stats`). مسیر موفق دست‌نخورده ماند.

**بررسی مصرف‌کننده:** در `frontend/src/lib/api.ts` منطقِ `apiGet` صریحاً `success === false` (یا `error`/`detail`) را «خطای منبع» تلقی می‌کند؛ پس فرانت‌اند صفحهٔ `/jobs` اکنون به‌جای «خالیِ گمراه‌کننده»، حالت خطا نشان می‌دهد — مطابق قرارداد مستند.

**معیار بستن مورد:** خطای DB باید `success=False` بدهد؛ مسیر موفق سبز بماند. ✅ برآورده شد.

---

## ۳. یافتهٔ J6 — P3 (اصلاح‌شده)

**فایل:** `apps/api/endpoints/jobs.py::_row_to_dict`.
عبارت تنها‌ایستادهٔ `row[9]` (بدون اثر/انتساب) که پیش از ساخت dict اجرا می‌شد، حذف شد. مقدار `created_at` همان‌طور که بود از `row[9]` ساخته می‌شود.

---

## ۴. فرمان‌ها و نتایج واقعی

| فرمان | نتیجه | exit |
|---|---|---|
| `python -m pytest tests/unit/test_jobs_list_endpoint_outcome.py -q -p no:cacheprovider` (قبل) | `1 failed, 1 passed` | 1 |
| `python -m pytest tests/unit/test_jobs_list_endpoint_outcome.py -q -p no:cacheprovider` (بعد) | `2 passed` | 0 |
| `python -m pytest tests/unit/test_jobs_list_endpoint_outcome.py tests/unit/test_job_queue_stats_api.py tests/unit/test_job_queue_replay_api.py tests/unit/test_job_queue_dead_letter_summary.py tests/unit/test_queue_analysis_api.py -q -p no:cacheprovider` | `58 passed` | 0 |
| `python -m ruff check apps/api/endpoints/jobs.py tests/unit/test_jobs_list_endpoint_outcome.py` | `All checks passed!` | 0 |

محیط: Python 3.11.9، pytest 9.1.1، `PYTHONUTF8=1`.

---

## ۵. فایل‌های تغییرکرده در این نشست (این مرحله)

- `apps/api/endpoints/jobs.py` — `success=False` + `error` در مسیر خطای `list_jobs` (J5)؛ حذف `row[9]` بی‌اثر (J6).
- `tests/unit/test_jobs_list_endpoint_outcome.py` (جدید) — دو تست: خطای DB ⇒ `success=False`، و مسیر موفق.

هیچ تست موجودی به رفتار قدیمی وابسته نبود (جست‌وجو شد). کار هم‌زمانِ دیگران حفظ شد.

---

## ۶. موارد باز / مسدود

- **BLOCKED (محیط):** اجرای واقعی `/jobs` روی PostgreSQL (این محیط DB نداشت).
- **تیک‌آف هم‌خانواده:** بررسی مشابه پنهان‌سازی خطا (`return success=True` با دادهٔ خالی در `except`) در سایر اندپوینت‌ها نیازمند پویش مستقل است (خارج از این دامنه).

---

## ۷. نتیجهٔ نهایی این مرحله

**PASS محدود و مستند** برای دامنهٔ «اندپوینت `/jobs`»:
- باگ P2 (پنهان‌سازی خطای منبع) و کد بی‌اثر P3 با تستِ ابتدا RED و سپس GREEN اصلاح شدند.
- رگرسیون مرتبط (۵۸ تست) و ruff سبز.
- موارد BLOCKED صادقانه اعلام و PASS نشدند.

این PASS صرفاً برای همین دامنه است و به‌معنای تأیید کل سامانه نیست.
