# ممیزی پویش «موفقیت کاذب در except» — اندپوینت‌های API

- **تاریخ:** 2026-10-29
- **نسخهٔ گزارش:** run1
- **دامنه:** پویش تمام اندپوینت‌های API (و به‌دنبال آن کل درخت تولید) برای الگوی «`return ... success=True` در بلوک `except`» که خطای منبع را با موفقیت-خالی پنهان می‌کند.
- **شاخه/HEAD:** `integration/golddesk-fixes`, HEAD=`be8b4ff4839ee1e2bdacd791e7be176044e1eebd` (بدون تغییر).
- snapshot: `_snapshots/t18-success-false.txt`.

> این گزارش گزارش‌های ۱۸–۲۱ و پیش‌ازآن را بازنویسی نمی‌کند.

---

## ۱. خلاصهٔ مدیریتی

پس از یافتن یک مورد در `/jobs` (گزارش ۲۱)، یک پویش دقیق و ساختاری (نه heuristic تقریبی) در `apps/api/endpoints/*.py` انجام شد تا هر جایی که یک بلوک `except` مستقیماً `success=True` برمی‌گرداند شناسایی شود.

نتیجه: **۲ مورد** (دقیقاً همان الگو) یافت و اصلاح شد؛ سپس پویش در کل درخت تولید (`apps/services/jobs/brsapi/core/src/ingestion/orchestration`) تکرار شد و **۰ مورد** باقی ماند.

- **J7 (P2، اصلاح‌شده):** `GET /analysis/correlations` — خطای خواندن snapshot با `success=True` پنهان می‌شد.
- **J8 (P2، اصلاح‌شده):** `GET /codal/{code}/financials` — خطای خواندن جدول صورت‌های مالی با `success=True` پنهان می‌شد.

---

## ۲. روش پویش (قابل‌بازتولید)

یک اسکریپت آفلاینِ مبتنی بر توکنیزه‌کردن، برای هر `except`، بدنهٔ همان بلوک را تا کاهش indentation جدا می‌کند و تنها در صورتی علامت می‌زند که **اولین `return` داخلِ همان except** شامل `success=True` باشد:

```
precise hits (except-block returns success=True): 2
  apps/api/endpoints/analysis.py:45
  apps/api/endpoints/codal.py:364
...
repo-wide except-block returns success=True: 0
```

(نسخهٔ ساده‌لوحانه‌تر که پنجرهٔ ثابت را می‌دید، ۱۶۷ نتیجهٔ مثبتِ کاذب می‌داد؛ الگوی دقیق تنها ۲ مورد واقعی را جدا کرد.)

---

## ۳. یافتهٔ J7 — P2 (اصلاح‌شده)

**فایل:** `apps/api/endpoints/analysis.py::analysis_correlations` (بلوک except).

**قبل:**
```python
except Exception:
    logger.exception("Correlations: snapshot fetch failed")
    return ApiResponse(success=True, data={"categories": [], "source": "unavailable"})
```

**بازتولید (آفلاین):** فراخوانی مستقیم با `brsapi`ی که `get_latest_snapshots` را با `RuntimeError` می‌شکند → قبل از اصلاح: `response.success is True`.

**اصلاح:** `success=False` + `error={"message": "Correlations: snapshot source unavailable"}` و حفظ `source: "unavailable"` در data.

**اثر مصرف‌کننده:** صفحهٔ `frontend/src/app/correlations/page.tsx` قبلاً در هر خطا به `MOCK_CATEGORIES` برمی‌گشت (نمایش دادهٔ دموی استاتیک بدون اعلام). با `success=False` این حالت دیگر «موفقیت» تلقی نمی‌شود و مرز داده واقعی/دمو از بین نمی‌رود.

---

## ۴. یافتهٔ J8 — P2 (اصلاح‌شده)

**فایل:** `apps/api/endpoints/codal.py::financial_reports` (خط ۳۶۴).

**قبل:**
```python
except Exception:
    logger.exception("Failed to load real financials for %s", code)
    return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "quarters": []})
```

**اصلاح:** `success=False` + `error={"message": f"Failed to load financials for {code}"}` با حفظ ساختار data.

**اثر مصرف‌کننده:** صفحهٔ `frontend/src/app/symbol/[symbol]/page.tsx` قبلاً یک DB خراب را به‌شکل «این نماد صورت مالی ندارد» نشان می‌داد.

---

## ۵. فرمان‌ها و نتایج واقعی

| فرمان | نتیجه | exit |
|---|---|---|
| پویش ساختاری اندپوینت‌ها (اسکریپت آفلاین) | `2` مورد | 0 |
| پویش ساختاری کل درخت تولید (پس از اصلاح) | `0` مورد | 0 |
| `python -m pytest tests/unit/test_endpoint_success_false_on_source_error.py -q -p no:cacheprovider` (قبل) | `2 failed` | 1 |
| `python -m pytest tests/unit/test_endpoint_success_false_on_source_error.py -q -p no:cacheprovider` (بعد) | `2 passed` | 0 |
| `python -m ruff check apps/api/endpoints/analysis.py apps/api/endpoints/codal.py tests/unit/test_endpoint_success_false_on_source_error.py` | `All checks passed!` | 0 |
| `python -m pytest tests/unit/test_endpoints.py …` | `14 failed, 5 passed` | 1 |

**توضیح شکست‌های `test_endpoints.py`:** همهٔ ۱۴ شکست با پیام `RuntimeError: Cannot connect to PostgreSQL` رخ می‌دهند — تست‌های وابسته به DB که در این محیط (بدون PostgreSQL) از قبل **BLOCKED** هستند و ارتباطی با تغییرات این نشست ندارند (تأیید با اجرای تک‌تک `test_codal_financials`).

محیط: Python 3.11.9، pytest 9.1.1، `PYTHONUTF8=1`.

---

## ۶. فایل‌های تغییرکرده در این نشست (این مرحله)

- `apps/api/endpoints/analysis.py` — `success=False` در مسیر خطای `analysis_correlations` (J7).
- `apps/api/endpoints/codal.py` — `success=False` در مسیر خطای `financial_reports` (J8).
- `tests/unit/test_endpoint_success_false_on_source_error.py` (جدید) — دو تست RED→GREEN.

هیچ تستی به رفتار قبلی وابسته نبود. کار هم‌زمانِ دیگران حفظ شد.

---

## ۷. موارد باز / مسدود

- **BLOCKED (محیط):** اجرای واقعی این اندپوینت‌ها روی PostgreSQL (`tests/unit/test_endpoints.py` — ۱۴ تست DB).
- **پوشش:** پویش ساختاری نشان می‌دهد هیچ مورد دیگری از «`success=True` در except» در درخت تولید باقی نمانده؛ اما این تضمینِ کاملِ «عدم پنهان‌سازی خطا» نیست (الگوهای دیگر مثل `Result.ok([])` در لایه‌های دیگر جداگانه بررسی می‌شوند).

---

## ۸. نتیجهٔ نهایی این مرحله

**PASS محدود و مستند** برای دامنهٔ «پویش موفقیت کاذب در اندپوینت‌ها»:
- ۲ باگ P2 هم‌خانوادهٔ `/jobs` یافت و با تستِ RED→GREEN اصلاح شد.
- پویش ساختاری نشان داد در کل درخت تولید موردی باقی نمانده.
- شکست‌های رگرسیون صرفاً DB-وابسته و از قبل BLOCKED بودند و به‌اشتباه به این تغییر نسبت داده نشدند.

این PASS صرفاً برای همین دامنه است و به‌معنای تأیید کل سامانه نیست.
