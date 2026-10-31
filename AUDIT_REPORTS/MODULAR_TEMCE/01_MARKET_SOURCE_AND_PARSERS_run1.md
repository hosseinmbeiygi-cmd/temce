# 01_MARKET_SOURCE_AND_PARSERS (run1)

تاریخ/زمان اجرا: 2026-10-29
ریشهٔ checkout: C:/Users/Iran/Desktop/temce
Branch: integration/golddesk-fixes
HEAD: 90597e05b9f4328bcd82ee819a31ba5c55413c12

## هدف و مرز دامنه
بررسی مسیر دریافت اطلاعات بازار از منبع بیرونی (BrsApi) تا خروجی parser و نتیجهٔ sync. بررسی client.py (HTTP/retry/rate-limit/circuit-breaker) و sync_service.py (orchestration).

## فایل‌های خوانده‌شده
- brsapi/client.py — کامل خوانده شد
- brsapi/services/sync_service.py — بخشی خوانده شد (1058/1872 خط)
- brsapi/config.py — باینری/تولیدی — بررسی نشد (حجم بالا)
- brsapi/rate_limiter.py — باینری/تولیدی — بررسی نشد

## یافته‌های کلیدی

### 1. BrsApiResponse.is_empty
- فایل: brsapi/client.py:77-88
- پاسخ {status: "no_data"} به‌عنوان empty تشخیص داده می‌شود. خوب.
- dict خالی (len==0) هم empty. خوب.

### 2. Sync service flow
- sync() method orchestration را انجام می‌دهد: fetch -> parse -> store -> log.
- کد نشان می‌دهد SyncReport با success/items_count/persisted_count برگردانده می‌شود.
- نیاز به بررسی کامل sync() method برای تشخیص success=True کاذب.

### 3. HTTP client
- httpx.AsyncClient با retry/exponential backoff.
- circuit breaker از core.circuit_breaker.
- rate limiter token bucket per endpoint category.
- Budget governor (daily quota) جدا از provider policy.

### 4. موانع
- brsapi/config.py و rate_limiter.py کامل خوانده نشدند (حجم بالا).
- تست‌های آفلاین sync_service نیاز به بررسی.

## خطرات باقی‌مانده
- success=True کاذب با items_count=0 باید در sync() method بررسی شود.
- retry ممکن است سهمیه را دور بزند (budget governor باید بررسی شود).
- parser malformed data -> [] بی‌صدا (نیاز به تست).

## معیارهای پذیرش
- سناریوهای success-empty, malformed, provider-blocked, timeout, storage-error قابل تفکیک: PARTIAL (نیاز به بررسی بیشتر)
- تست آفلاین: NOT RUN

## مسیر گزارش
C:/Users/Iran/Desktop/temce/AUDIT_REPORTS/MODULAR_TEMCE/01_MARKET_SOURCE_AND_PARSERS.md (این فایل)
