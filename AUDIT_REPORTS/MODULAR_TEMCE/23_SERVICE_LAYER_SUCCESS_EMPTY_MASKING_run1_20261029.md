# ۲۳ — پوشش ماسک‌شدن خطای منبع با `Result.ok` در لایهٔ سرویس

**تاریخ:** 2026-10-29
**دامنه:** اسکن ساختاری `except → Result.ok(...)` در `services/`, `apps/`, `jobs/`, `brsapi/`, `orchestration/`, `ingestion/`, `domain/`, `repositories/`, `providers/`, `monitoring/`
**وضعیت کل مرحله:** PARTIAL (۲ اصلاح انجام شد؛ بقیه مستند/مسدود)
**نسخهٔ گزارش:** run1 — گزارش‌های قبلی بازنویسی نشدند.

---

## ۱. وضعیت Git (snapshot)

| فیلد | مقدار |
|---|---|
| branch | `integration/golddesk-fixes` |
| HEAD در شروع این مرحله | `be8b4ff4839ee1e2bdacd791e7be176044e1eebd` |
| HEAD هنگام نوشتن گزارش | `6e0ac36d8b9d94eb4395a68356e51414d44a9361` (کامیت هم‌زمان عامل دیگر) |
| snapshot | `_snapshots/t19-service-layer.txt` و `_snapshots/t20-service-layer.txt` |

عامل دیگری در میانهٔ مرحله کامیت `fix(audit): close P0/P1 findings...` را ثبت کرد. تغییرات working-tree من حفظ شد و پس از کامیت دوباره تأیید شد (diff دقیقاً همان ۲۲ درج/۴ حذف روی دو فایل سرویس).

---

## ۲. روش

اسکن AST روی تمام `ExceptHandler`هایی که با `return Result.ok(...)` یا `return` بی‌مقدار پایان می‌یابند. مجموعاً ۲۳ نقطه در ۱۰ ماژول. هر مورد از نظر «آیا خطای منبع با موفقیت خالی ماسک می‌شود؟» و «آیا مصرف‌کننده دارد؟» و «آیا تست آن را قفل کرده؟» بررسی شد.

---

## ۳. یافته‌ها

### J9 (P1) — ماسک خطای DB در تاریخچهٔ اردربوک

- **فایل:** `services/orderbook_service.py` (قبل از اصلاح خط ۱۵۴–۱۵۶)
- **مسیر مصرف:** `GET /orderbooks/{symbol}/history` → `apps/api/endpoints/orderbooks.py:30` که `success=result.success` را مستقیماً در پوش‌نامهٔ API می‌گذارد.
- **شاهد (RED):** با `session.execute` ناکام، `Result(value=[], error=None, success=True, error_code=None)` برگردانده می‌شد؛ یعنی خطای جدول `brsapi_historical_daily` به‌صورت «تاریخچه‌ای وجود ندارد» به فرانت‌اند می‌رفت.
- **علت ریشه‌ای:** `except Exception: return Result.ok([])` بدون هیچ سیگنال تمایزدهنده.
- **اصلاح:** بازگشت `Result.fail(f"Failed to fetch orderbook history for {symbol}: {exc}", code="source_error")`.
- **تست:** `tests/unit/services/test_orderbook_history_error_surfacing.py` — ۲ تست (خطا → `success=False`/`error_code="source_error"`؛ موفقیت → rows).

### J10 (P1/P3) — «healthy» کاذب در داشبورد مانیتورینگ

- **فایل:** `services/monitoring_service.py` (`get_alerts` خط ۱۹۱–۱۹۳، `get_dashboard` خط ۲۰۰–۲۱۰)
- **شاهد (RED):** با منبع سلامتِ خطادار، payload دارای `'alerts': []` و `'status': 'healthy'` بود (`get_alerts` → `Result.ok([])`، سپس `status = "healthy" if not alerts.value else ...`).
- **علت ریشه‌ای:** یکسان‌سازی «خطای خواندن هشدارها» با «هیچ هشدار فعالی وجود ندارد».
- **اصلاح:** `get_alerts` روی خطا `Result.fail(..., code="source_error")`؛ `get_dashboard` در صورت `not alerts.success` وضعیت `degraded` و `success=False` برمی‌گرداند (هرگز `healthy` با منبع خطادار).
- **تست:** `tests/unit/services/test_monitoring_service_false_healthy.py` — ۲ تست.
- **ریسک/دامنه:** `MonitoringService` هیچ واردکننده‌ای در مخزن ندارد (`rg` روی همهٔ `.py` جز مستندات فقط خودِ تعریف را یافت؛ بدون route، بدون تست). لذا اثر عملیاتی فعلی صفر است؛ به همین دلیل علاوه بر اصلاح، به‌عنوان P3 بدهی معماری (کلاس یتیم) نیز ثبت می‌شود.

### موارد بررسی‌شدهٔ بدون تغییر (با دلیل)

| فایل | خط | حکم | دلیل |
|---|---|---|---|
| `services/trade_service.py` | ۳۰، ۸۸ | بدون تغییر | قرارداد موجود در `tests/unit/test_trades_e2e.py::test_trade_service_returns_empty_when_all_sources_fail` عمداً `success=True`/`[]` را می‌خواهد (graceful degradation مقصود محصول). |
| `services/signal_service.py` | ۷۸، ۱۴۱ | بدون تغییر | `bulk_generate` روی خطا مجموعهٔ خالی برمی‌گرداند؛ قرارداد فعلی محصول، تغییر نیازمند تصمیم است. |
| `services/signal_accuracy_tracker.py` | ۲۳۹، ۲۹۷ | بدون تغییر | از قبل با `_count_unavailable_read` (اصلاح audit S2) عدم‌دسترس بودن را می‌شمارد؛ خطای خالی بی‌صدا نیست. |
| `services/watchlist_service.py` | ۲۲۹ | بدون تغییر | مالکیت از طرف عامل دیگر (dialect-aware، ارجاع Alembic 0117). |
| `services/auto_retrain_pipeline.py` | ۲۸۱، ۵۳۴ | بدون تغییر | بازگشت report در مسیر جزئی‌شکست احتمالاً عمدی است؛ نیازمند تصمیم محصول. |
| `providers/reference/codal/attachment_extractor.py` | ۳۴، ۵۲، ۶۳ | بدون تغییر | `Result.ok("... requires PyPDF2")` خود یک پیام صریح عدم‌وابستگی است، نه دادهٔ جعلی؛ ضمناً این کلاس هیچ مصرف‌کنندهٔ عملیاتی ندارد. |

---

## ۴. معیارهای پذیرش مرحله

| معیار | نتیجه |
|---|---|
| تست RED قبل از اصلاح برای J9 و J10 نوشته شد | PASS |
| تست‌ها پس از اصلاح سبز شدند | PASS (۴/۴) |
| ruff روی فایل‌های تغییریافته | PASS (`All checks passed!`) |
| رگرسیون سرویس‌ها بدون رگرسیون جدید | PASS (رگرسیون جدید صفر؛ ۱۳ خطای قبلی تفکیک شد) |
| هیچ تستی تضعیف/حذف نشد | PASS |

---

## ۵. شواهد آزمون (فرمان‌ها، exit code)

| فرمان | نتیجه |
|---|---|
| `python -m pytest tests/unit/services/test_orderbook_history_error_surfacing.py tests/unit/services/test_monitoring_service_false_healthy.py -q` | ۴ passed، exit 0 |
| ترکیب ۴ فایل تست این + مرحلهٔ قبل (`test_endpoint_success_false... `، `test_jobs_list_endpoint_outcome...`) | ۸ passed، exit 0 |
| `python -m pytest tests/unit/services -q` | 3271 passed، 25 skipped، **13 failed** |
| `ruff check` روی ۴ فایل تغییریافته | exit 0 |

### تفکیک ۱۳ خطای رگرسیون سرویس‌ها (هیچ‌کدام مربوط به این تغییر نیست)

- ۷ خطا در `test_adjusted_price_reader.py` — علت: `asyncpg.exceptions.InvalidPasswordError` (PostgreSQL در دسترس نیست) → **BLOCKED**.
- ۶ خطا در `test_indicator_calculation.py` (stochastic/ichimoku) — قرارداد فعلی تابع کلید `offset` را برمی‌گرداند ولی تست انتظار ندارد؛ بدهی موجود، مستقل از این تغییر.

---

## ۶. فایل‌های تغییرکرده در این مرحله

- `services/orderbook_service.py` (اصلاح J9)
- `services/monitoring_service.py` (اصلاح J10)
- `tests/unit/services/test_orderbook_history_error_surfacing.py` (جدید)
- `tests/unit/services/test_monitoring_service_false_healthy.py` (جدید)

---

## ۷. موارد باز / مسدود

- **BLOCKED:** اعتبارسنجی Repository/DB برای J9 نیازمند PostgreSQL (فعلاً `localhost:5432` پاسخ نمی‌دهد). تست‌ها با session جعلی درون‌حافظه‌ای اجرا شدند.
- **باز (P3):** `MonitoringService` کلاس یتیم است؛ تصمیم دربارهٔ حذف/اتصال نیازمند تأیید مالک محصول.
- **باز:** بقیهٔ نقاط `Result.ok([])` طبق جدول بند ۳ به‌عنوان عمدی/قفل‌شده باقی ماندند و تغییر نکردند.

---

## ۸. قدم بعدی پیشنهادی

۱. پس از فراهم‌شدن PostgreSQL، تست‌های Repository برای `orderbook_service.get_history` و اجرای کامل `tests/unit/services`.
۲. ارزیابی decision-record برای قراردادهای `trade_service`/`signal_service` (success-empty در برابر fail+reason).
۳. ادامهٔ دامنه‌های بی‌مالک: `brsapi/services/sync_service.py` (مسیر ترکیبی طلا)، و hookهای freshness فرانت‌اند.
