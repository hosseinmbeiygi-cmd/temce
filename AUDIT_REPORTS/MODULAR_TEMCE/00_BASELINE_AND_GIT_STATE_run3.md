# 00_BASELINE_AND_GIT_STATE (run3)

تاریخ/زمان اجرا: 2026-10-29
ریشهٔ checkout: C:/Users/Iran/Desktop/temce
Branch: integration/golddesk-fixes
HEAD: 90597e05b9f4328bcd82ee819a31ba5c55413c12

## وضعیت اولیهٔ Git
- branch: integration/golddesk-fixes
- HEAD commit: 90597e05b9f4328bcd82ee819a31ba5c55413c12
- git status --short --branch: ## integration/golddesk-fixes
- تغییرات staged: 138 فایل (+115998/-1447)
- تغییرات unstaged: 45 فایل (+1672/-817)
- فایل‌های untracked: AUDIT_REPORTS/, brsapi/quality.py, frontend tests, tests/unit/* جدید

## نتیجهٔ این مرحله
فقط بررسی و گزارش؛ هیچ کد یا state گیت تغییر نکرد. فایل گزارش جدید (run3) ایجاد شد زیرا فایل‌های قبلی از قبل وجود داشتند.

## موانع اصلی
- مخزن بسیار بزرگ با تغییرات گستردهٔ staged/unstaged/untracked.
- هیچ اتصال زنده به BrsApi/TSETMC انجام نشد (محدودیت رعایت شد).
- apps/api/router.py وجود دارد و نشانهٔ conflict ندارد.
- گزارش‌های قدیمی (AUDIT_BATCH_*) در checkout فعلی یافت نشد؛ فقط docs/audits/phase-0 موجود است (سرنخ).
- useMarketData.ts: isDataFresh اصلاح شده (fetched > now guard) - تأیید شد.
- test_sync_log_repository.py: 15 needs_sync تست - تأیید شد.

## ترتیب اجرایی پیشنهادی
منبع/پارسر -> scheduler/queue -> persistence -> API/cache -> frontend -> deployment -> data quality -> حوزه‌های دیگر -> امنیت -> تست نهایی

## معیارهای پذیرش
- هیچ فایل source/test یا state گیت تغییر نکرده: PASS
- گزارش manifest وضعیت Git ثبت شد: PASS
- ادعای «همهٔ فایل‌ها کامل خوانده شده» بدون manifest درج نشد: PASS
