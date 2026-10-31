# ۴۲ — بستن آدیت run1: وضعیت نهایی و نقشهٔ commit — ۳۰ اکتبر ۲۰۲۶

**دامنه:** گزارش‌های ۳۲ تا ۴۱. هیچ commit/stage انجام نشده است.
**قاعده:** درخت مشترک است؛ `git add -A` ممنوع. فایل‌های mixed باید با بازبینی مالک
یا hunk-level staging جدا شوند.

---

## ۱) وضعیت نهایی یافته‌ها

| ID | موضوع | وضعیت | گزارش |
|---|---|---|---|
| AUD-DB-01 / DB-02 | دستیابی DB خالی به head | **FIXED** | 34، 33، 30/31 |
| AUD-API-01 | operationId تکراری | **FIXED** | 35 |
| AUD-API-02 | قرارداد بدون security scheme | **FIXED** | 35 |
| AUD-ARCH-01 | چرخه‌های وابستگی | **FIXED** (۰ چرخه + گارد) | 37، 38، 41 |
| AUD-SEC-01 | الزام salt | **FIXED** (DECIDED: gate حفظ شد) | 41 |
| AUD-FE-01 | هشدارهای ESLint | **PARTIAL** (169→137، ۰ خطا) | 39 |
| AUD-TEST-01 | collection وابسته به DB | **PARTIAL** (collection پاک؛ اجرای DB نیازمند DSN) | 36 |
| AUD-DATA-01 | کهنگی داده‌های محلی | **PARTIAL** (DECIDED: LEGACY) | 40 |

## ۲) ماتریس تأیید نهایی

| حوزه | شاهد | نتیجه |
|---|---|---|
| DB | `upgrade head` روی `tse_quant` خالی + `current` + اجرای دوم | exit 0؛ `0119`؛ ۲۰۳ جدول؛ ۰ migration در اجرای دوم |
| DB tests | drift + ۷ تست gold | ۳/۳ و **۵۶/۵۶** |
| API | `app.openapi()` | ۶۷۱ مسیر؛ ۰ operationId تکراری؛ `bearerAuth`؛ ۵۵۱/۷۰۶ secured |
| API tests | تست‌های هدفمند با DSN | **۵۷/۵۷** |
| ARCH | AST scan + گارد | ۰ چرخه؛ `test_no_import_cycles` پاس |
| Backtesting | `pytest tests/unit/backtesting` | **۳۹۵ passed / ۱ skipped** |
| Frontend | `eslint` + `tsc` + `vitest` | ۰ خطا / ۱۳۷ هشدار؛ tsc پاس؛ **۵۸۶/۵۸۶** |
| Collection | `pytest tests --collect-only` | exit 0؛ ۸۱۵۸ تست؛ ۰ خطا |
| تأیید یکپارچه | ۶ فایل تست کلیدی | **۴۹ passed / ۱ skipped** |

## ۳) نقشهٔ commit پیشنهادی (اجرا نشده)

> فایل‌های «mixed» از قبل تغییر داشتند؛ stage کردن کل فایل، کار ویرایشگر هم‌زمان را هم
> شامل می‌شود. برای آن‌ها نیاز به بازبینی/`git add -p` توسط مالک است.

### C1 — DB-02 (پاک)

```
migrations/versions/0004b_core_baseline.py        (new)
migrations/versions/0005_add_performance_indexes.py
migrations/versions/0006_add_missing_updated_at.py
migrations/versions/0011_add_price_volume_columns.py
migrations/versions/0012_saved_filters.py
migrations/versions/0099_signal_arch_align.py
migrations/env.py
migrations/README.md
```

### C2 — API contract + وارونگی core (بخشی mixed)

```
core/agg_invalidation.py                 (new)
apps/api/openapi_security.py             (new)
apps/api/app.py                          (پاک، ۲ خط)
apps/api/endpoints/market_watch.py       (پاک، ۱ خط)
apps/api/endpoints/market.py             (MIXED — از قبل تغییر داشت)
brsapi/services/sync_service.py          (MIXED — از قبل تغییر داشت)
tests/unit/test_sync_service_persistence_scope.py
```

### C3 — معماری backtesting (پاک)

```
backtesting/constants.py
backtesting/event_types.py               (new)
backtesting/clock.py                     (new)
backtesting/position_manager.py          (new)
backtesting/portfolio/manager.py         (new)
backtesting/engine/clock.py
backtesting/engine/event_builder.py
backtesting/engine/position_manager.py
backtesting/engine/portfolio.py
backtesting/portfolio/__init__.py
backtesting/market/rule_engine.py
backtesting/strategies/context.py
backtesting/strategies/engine.py
backtesting/microstructure/microstructure_engine.py
tests/unit/test_no_import_cycles.py      (new)
```

### C4 — فرانت (بخشی mixed)

```
frontend/eslint.config.mjs
۱۶ فایل با حذف دایرکتیو eslint-disable بی‌استفاده (کامنت‌محور)
  از جمله frontend/src/app/indicators/page.tsx که ویرایشگر هم‌زمان هم داشت
```

### C5 — مستندات و تست‌های اسکریپتی

```
README.md
docs/env-vars.md
src/gold_desk/api_token.py
tests/test_screener_flow.py
tests/test_sync_2.py
crypto_data/README.md                    (new, untracked)
```

`data/top50_funds_intraday/README.md` ساخته شد اما `data/` در `.gitignore` است و
commit نمی‌شود (مستند محلی باقی می‌ماند).

### گزارش‌های آدیت

`AUDIT_REPORTS/MODULAR_TEMCE/32..42` و `evidence/*` هنوز untracked هستند؛ طبق
convention بدون دستور صریح stage نمی‌شوند.

## ۴) باقی‌مانده‌های باز (خارج از C1–C5)

- **FE-01:** ۱۰۰ متغیر بی‌استفادهٔ واقعی و ۲۹ هشدار `exhaustive-deps` (نیازمند بررسی موردی).
- **TEST-01:** اجرای تست‌های DB نیازمند `DATABASE_URL` است؛ CI باید ست کند.
- **DATA-01:** تازه‌سازی snapshot‌ها به provider وابسته و مجاز نیست.
- **Redis live:** `NOAUTH` (محیطی).
- **حالت آفلاین `0007/0026`:** نیازمند approval جدا.

## ۵) تصمیم لازم

برای commit فقط باید بگویی **«commit»** و مشخص کنی کدام گروه‌ها (C1..C5) و آیا
گزارش‌های آدیت هم stage شوند. بدون آن هیچ stage/commit انجام نمی‌شود.
