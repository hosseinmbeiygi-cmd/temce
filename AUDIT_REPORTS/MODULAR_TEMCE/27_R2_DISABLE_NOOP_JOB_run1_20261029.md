# ۲۷ — R2: غیرفعال‌سازی job no-op زمان‌بندی‌شدهٔ gold_daily_history

**تاریخ:** 2026-10-29
**دامنه:** brsapi/jobs/gold_desk_jobs.py + رجیستری BrsApi
**وضعیت:** DONE (اصلاح + تست RED→GREEN)
**نسخه:** run1 — گزارش‌های قبلی بازنویسی نشدند.

---

## ۱. Git

| فیلد | مقدار |
|---|---|
| HEAD (شروع) | fc51c74b |

## ۲. یافته (R2 — بازبینی‌شده)

- فایل: brsapi/jobs/gold_desk_jobs.py
- job: gold_daily_history (cron="0 21 * * *")
- کد: تابع job_gold_daily_history فقط لاگ می‌کرد و برمی‌گشت (placeholder no-op).
- اثر: _run_direct_job یک تابعی که نرمال برمی‌گردد را success=True گزارش می‌کند → هر شب 21:00 یک job سبز در scheduler ثبت می‌شد که هیچ داده‌ای نمی‌نوشت (false-green عملیاتی؛ همان الگوی «موفقیت کاذب» که در گزارش‌های ۲۰–۲۳ بسته شد).
- شدت: P2 (سیگنال عملیاتی گمراه‌کننده) — نه P0/P1 چون چیزی خراب نمی‌کرد، فقط دروغ می‌گفت.

## ۳. علت ریشه‌ای

یک job غیرعملیاتیِ صریح در زمان‌بندی فعال ثبت شده بود و مکانیزم داخلی برای «not implemented» وجود ندارد؛ تنها راه مجموعاً ساده و سازگار با کد موجود، مکانیزم enabled رجیستری است (۷ job دیگر از قبل enabled=False دارند).

## ۴. اصلاح (کمینه و سازگار)

1. در GOLD_DESK_JOBS، توصیف‌گر gold_daily_history → enabled=False + description="(DISABLED) Daily historical bubble backfill — placeholder, not implemented".
2. docstring تابع و لاگ آن صریح شد: logger.warning("gold_daily_history: NOT IMPLEMENTED — no historical backfill performed").
3. تابع و نگاشت GOLD_DESK_JOB_FUNCTIONS دست‌نخورده ماندند (برای فراخوانی on-demand و پیاده‌سازی آینده).

نتیجه: job در رجیستری ثبت و قابل‌فراخوانی می‌ماند، اما دیگر زمان‌بندی نمی‌شود.

## ۵. تست (RED → GREEN)

- تست جدید در tests/unit/test_brsapi_registry_schedule_invariants.py:
  test_unimplemented_placeholder_job_is_not_scheduled → asserts GOLD_DESK_JOBS["gold_daily_history"].enabled is False.
- RED: قبل از اصلاح، enabled=True → شکست.
- GREEN: بعد از اصلاح، ۶ تست فایل سبز.

## ۶. شواهد آزمون

| فرمان | نتیجه |
|---|---|
| pytest tests/unit/test_brsapi_registry_schedule_invariants.py -q | قبل: 1 failed/5 passed → بعد: 6 passed، exit 0 |
| pytest tests/unit/jobs -q | 222 passed، exit 0 |
| ruff check (۲ فایل) | exit 0 |
| لاگ startup | "Scheduler started with 24 BrsApi jobs" (قبلاً 25) |

## ۷. معیارهای پذیرش

| معیار | نتیجه |
|---|---|
| تست RED قبل/ GREEN بعد | PASS |
| job همچنان ثبت‌شده و روی رجیستری موجود | PASS (test_gold_desk_job_registry سبز) |
| رگرسیون jobs | PASS (222 passed) |
| هیچ تستی تضعیف نشد | PASS |

## ۸. باقی‌مانده

- پیاده‌سازی واقعی backfill تاریخی (نیازمند BrsApi history + DB) → BLOCKED/محصولی.
- R1 (پرچم مردهٔ forced) و R3 (ابهام None در bridge) هنوز باز.