# مرحلهٔ ۲ — منبع/Parser: شاهد اجرا (۲۹ اکتبر ۲۰۲۶)

دامنه: رفتار end-to-end کلاینت BrsApi در برابر 3xx/402/429/5xx/timeout، بودجه/backoff/circuit-breaker،
ماتریس «کهنه/خارج از دامنه» برای هر parser، و موارد DS-08…12.

محیط: **آفلاین**. هیچ درخواست واقعی به BrsApi/TSETMC زده نشد. لایهٔ HTTP با `httpx.MockTransport`
و governor/limiter جعلی جایگزین شد؛ هیچ mutation روی DB عملیاتی انجام نشد.

---

## ۱) ماتریس وضعیت HTTP (پیش/پس)

| پاسخ | رفتار قبلی | رفتار فعلی | کد `Result.error_code` | HTTP مجدد |
|---|---|---|---|---|
| 200 | parse | بدون تغییر | — | — |
| 302 | block + cooldown | بدون تغییر (cooldown) | `provider_blocked` | ۰ |
| **301/303/307/308** | `http_error` بدون cooldown | block + cooldown (همان سیاست 302) | `provider_blocked` | ۰ |
| **402** | `http_error` بدون cooldown | ترمینال، بدون retry | `quota_exhausted` | ۰ |
| **401/403/451** | `http_error` | ترمینال، بدون retry | `provider_blocked` | ۰ |
| 429 | retry با Retry-After | بدون تغییر | `retries_exhausted` در پایان | ۳ |
| **408/500** | `http_error` بدون retry | retry با Retry-After/backoff | `retries_exhausted` در پایان | ۳ |
| 502/503/504 | retry | بدون تغییر | `retries_exhausted` | ۳ |
| 404 و سایر 4xx | `http_error` | بدون تغییر | `http_error` | ۰ |
| timeout | retry (۱.۵^n) | بدون تغییر | `timeout` | ۳ |
| network error | retry | بدون تغییر | `network_error` | ۳ |
| بودجهٔ soft / daily / cooldown | fail-fast | بدون تغییر | `budget_soft_limit` / `quota_exhausted` / `provider_blocked` | ۰ |
| **breaker باز** | هرگز رخ نمی‌داد (نگاه کنید به DS-13) | بدون HTTP | `circuit_open` | ۰ |

فایل: `brsapi/client.py` (`_REDIRECT_STATUSES`, `_RETRYABLE_STATUSES`, `_QUOTA_STATUSES`,
`_BLOCKED_STATUSES`). نگاشت `circuit_open → provider_blocked` در
`brsapi/services/sync_service.py::_FETCH_OUTCOME_BY_CODE`.

## ۲) DS-13 — circuit breaker مرده بود (P1، رفع شد)

`fetch()` تابع `_do_fetch` را در `CircuitBreaker.call` می‌پیچید، اما `_do_fetch` **همهٔ** خطاهای مورد انتظار
را به `Result.fail` تبدیل می‌کند و هرگز raise نمی‌کند؛ پس breaker هر فراخوانی را «موفق» می‌دید،
`failure_count` همیشه صفر می‌ماند و یک provider از کار افتاده تا ابد با retry کامل کوبیده می‌شد.

اصلاح: `fetch()` وضعیت breaker را قبل از ارسال بررسی می‌کند (`circuit_open`, بدون HTTP) و نتیجه را
به‌صورت صریح گزارش می‌دهد: موفق → `record_success`، ناموفق → `record_failure`. تست‌ها:
`test_breaker_opens_after_repeated_failures_and_stops_http`،
`test_breaker_does_not_count_successes`، `test_success_after_recovery_window_probes_and_closes`.

## ۳) ماتریس «کهنه/خارج از دامنه» به تفکیک لایه

| لایه | مسئولیت | مرجع تست |
|---|---|---|
| Transport | status → کد خطا/retry | `tests/unit/brsapi/test_client_status_handling.py` |
| Parser | `date` خام حفظ می‌شود؛ فقط candlestick ستون Gregorian می‌سازد و فقط داخل دامنهٔ ۱۲۰۰..۱۵۹۹ | `tests/unit/brsapi/test_source_domain_matrix.py` |
| Ingestion | نرمال‌سازی + قرنطینهٔ تاریخ/OHLC | `tests/unit/brsapi/test_history_fetch_quality.py` |

یافتهٔ DS-15 (رفع شد): `TsetmcParser._jalali_to_gregorian` هر سه‌قسمتِ عددی را Jalali می‌خواند؛
یک تاریخ Gregorian مثل `2026-09-14` بی‌صدا به قرن ۲۷ میلادی تبدیل می‌شد. اکنون از
`brsapi.quality.normalize_jalali_date` (دامنهٔ سال، رقم فارسی، جداکننده‌ها) استفاده می‌کند و
خارج از دامنه `(None, None)` برمی‌گرداند؛ رشتهٔ خام برای audit حفظ می‌شود.

DS-05 (تکمیل): قیمت‌های nullable در مسیر history دیگر با پیش‌فرض `0` پر نمی‌شوند —
`TsetmcParser._history_item`، `parse_history_real_legal`، `parse_candlesticks` و
`GoldCurrencyProParser.parse_daily_history` مقدار غایب را `None` می‌دهند.

## ۴) DS-08…12

| ID | وضعیت | شاهد |
|---|---|---|
| DS-08 | **FIXED** (پیش از این برش، در tree توسط کار هم‌زمان) | `ImeParser._ensure_list` → `unrecognised_envelope` |
| DS-09 | **FIXED** (در tree، uncommitted) | `_probe_tables` هر دو جدول را probe می‌کند و ابهام را log می‌کند؛ `test_news_tag_symbol_mapper.py` سبز |
| DS-10 | **FIXED** (در tree) | guard `int()` روی شمارنده‌های کدال |
| DS-11 | **FIXED** (commit `997de6c2`) | `close_price: ("pClosing", "closingPrice", "close")` — بدون `lastPrice` |
| DS-12 | **FIXED (این برش)** | `sentiment_error` شمارش می‌شود؛ `stats["sentiment_errors"]`؛ تست `test_sentiment_failure_is_counted_and_does_not_fail_the_run` |

## ۵) یافته‌های جدید باز

| ID | شدت | عنوان | وضعیت |
|---|---|---|---|
| DS-14 | P1 | `ImeParser._int/_float` و `CryptoParser._int/_float` مقدار نامعتبر را `0` می‌کنند (نشت DS-05) | **BLOCKED** — هر دو فایل در حال ویرایش توسط agent هم‌زمان‌اند؛ طبق §۷ تغییر نکردم |
| DS-16 | P2 | کندل روزانه (`candle_daily*`) بدون `date` با تاریخ «امروز» مهر می‌خورد، در حالی که مهر زدن فقط برای `candle_intraday` مستند است | **باز** — نیازمند تصمیم (ستون `date` NOT NULL است؛ حذف ردیف یا خالی گذاشتن) |

## ۶) اجرای تست (خروجی خام)

| مجموعه | نتیجه |
|---|---|
| `tests/unit/brsapi/test_client_status_handling.py` | ۲۸ passed |
| `tests/unit/brsapi/test_source_domain_matrix.py` | ۴۹ passed |
| `tests/unit/brsapi` (کل دایرکتوری، شامل `test_history_fetch_quality`، `test_sync_*`) | ۲۸۴ passed |
| `tests/unit/test_brsapi_budget_governor.py` + `test_brsapi_readiness.py` | بخشی از همان ۲۸۴ |
| `tests/unit/test_brsapi_candlesticks.py` + `tests/unit/services/test_market_service*.py` + `tests/unit/ingestion` | ۱۶۳ passed |
| `tests/unit/services/test_news_ingestion_skips.py` | ۶ passed |
| `tests/unit/jobs/test_news_ingestion_job_outcome.py` + scheduler (۲ فایل) + `test_news_category.py` | ۳۴ passed |

محدودیت‌ها: هیچ پاسخ واقعی BrsApi تست نشد (ممنوعیت §۷)؛ یک اجرای ناخواستهٔ RSS در نخستین نگارش
تست sentiment رخ داد و بلافاصله با patch کردن provider آفلاین شد (هیچ نوشتنی در DB نداشت چون
`session=None` بود)؛ DS-14 به‌دلیل ویرایش هم‌زمان باز است؛ migration/DB در این مرحله دخیل نبود.
