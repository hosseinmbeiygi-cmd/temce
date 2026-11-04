# ممیزی مستقل مرحله ۱۱ ـ آزمون نهایی، هماهنگی بین‌لایه‌ای و Release Gate

## ۱) مسیر گزارش نهایی این مرحله
**گزارش اصلی:** AUDIT_REPORTS/MODULAR_TEMCE/11_TESTS_CROSS_LAYER_RELEASE_GATE.md  
**وضعیت وجود فایل:** وجود دارد (14616 بایت، آخرین ویرایش 2026-10-29 00:28)

## ۲) فایل‌های بررسی‌شده / بررسی‌نشده
### بررسی‌شده (با دلیل)
| فایل | وضعیت | دلیل |
|---|---|---|
| AUDIT_REPORTS/MODULAR_TEMCE/11_TESTS_CROSS_LAYER_RELEASE_GATE.md | کامل خوانده شد | گزارش هدف این مرحله |
| AUDIT_REPORTS/MODULAR_TEMCE/00_BASELINE_AND_GIT_STATE.md | کامل خوانده شد | baseline و وضعیت اولیه |
| rsapi/repositories/base.py | کامل خوانده شد | بررسی 
eeds_sync() |
| ingestion/parser/library_parsers.py | کامل خوانده شد + ویرایش شده | اصلاح parse و shape check |
| ingestion/parser/__init__.py | کامل خوانده شد | بررسی ParsedEvent/Parser |
| rontend/src/hooks/useMarketData.ts | کامل خوانده شد | بررسی freshness logic |
| rontend/src/lib/api-envelope.ts | کامل خوانده شد | بررسی isDataAsOfFresh() و future skew |
| 	ests/unit/repositories/test_sync_log_repository.py | کامل خوانده شد | اجرا و تایید 15 تست |
| 	ests/unit/parsers/test_library_parser_errors.py | کامل خوانده شد + ایجاد شده | تست‌های جدید |

### بررسی‌نشده / محدود
| فایل | وضعیت | دلیل |
|---|---|---|
| ingestion/parser/tsetmc_parsers.py | بخشی خوانده شد | نیاز به بررسی عمیق‌تر برای None→0 mapping در سناریوهای خاص |
| rsapi/services/sync_service.py, ingestion/worker.py | بخشی خوانده شد | بررسی cross-layer کامل انجام نشد |
| تست‌های integration/e2e | بررسی نشد | نیاز به DB/Redis/service و محدودیت محیط |
| BrsApi live endpoints | بررسی نشد (BLOCKED) | ممنوعیت دسترسی زنده و cooldown |

## ۳) جدول الزام‌ها
| الزام | شاهد | نتیجه | کار باقی‌مانده |
|---|---|---|---|
| ریشه/branch/HEAD/Git ثبت شده | git status --short --branch، baseline | PASS | — |
| گزارش در مسیر صحیح نوشته شده | AUDIT_REPORTS/MODULAR_TEMCE/11_TESTS_CROSS_LAYER_RELEASE_GATE.md | PASS | — |
| حفظ تغییرات کاربر (staged/unstaged) | git diff --stat، git diff --cached --stat | PASS | — |
| عدم درخواست زنده BrsApi | بررسی کد/لاگ | PASS | — |
| عدم افشای secret | بررسی خروجی‌ها | PASS | — |
| 
eeds_sync() تست‌شده | pytest: 15/15 PASSED | PASS | — |
| freshness آینده رد شده | pi-envelope.ts:isDataAsOfFresh() + useMarketData.ts:isRowFresh() | PASS | — |
| تمایز empty vs error parsers | اصلاح + تست‌های جدید | PARTIAL | نیاز به تست‌های بیشتر برای سناریوهای واقعی |
| تست‌های اجراشده با exit code ثبت شده | pytest output | PASS | — |
| ماتریس ۱۲ مرحله در گزارش | موجود در گزارش | PASS | — |

## ۴) اصلاحات انجام‌شده
| فایل | diff خلاصه | دلیل | تست مرتبط |
|---|---|---|---|
| ingestion/parser/library_parsers.py | بهبود parse(): لاگ exception برای JSON نامعتبر، بررسی isinstance(data, dict) با warning برای shape غیر dict | شفاف‌تر کردن تمایز invalid/empty، بهبود observability بدون تغییر رفتار (همچنان []) | 	ests/unit/parsers/test_library_parser_errors.py (4 تست) |
| 	ests/unit/parsers/test_library_parser_errors.py | فایل جدید با ۴ تست | پوشش سناریوهای empty/invalid/html/non-dict | اجرا شده و PASSED |

## ۵) فرمان‌های تست و نتایج واقعی
| فرمان | موفق | ناموفق | اجرا‌نشده | exit code | توضیح |
|---|---|---|---|---|---|
| python -m pytest tests/unit/repositories/test_sync_log_repository.py -v | 15 | 0 | 0 | 0 | همهٔ تست‌های needs_sync پاس شدند |
| python -m pytest tests/unit/parsers/test_library_parser_errors.py -v | 4 | 0 | 0 | 0 | تست‌های خطای parser پاس شدند |
| python -m pytest tests/unit/parsers/test_library_parser_errors.py tests/unit/repositories/test_sync_log_repository.py -v | 19 | 0 | 0 | 0 | مجموع پاس شد |

## ۶) وضعیت نهایی
**وضعیت: PARTIAL**

**دلیل:**
- موارد حیاتی (needs_sync، freshness آینده) با شواهد کافی تأیید شده‌اند.
- تمایز empty vs error در _BaseLibParser بهبود یافته و تست شده است.
- اما پوشش cross-layer (integration/e2e)، بررسی عمیق‌تر TSETMC parsers و اثبات end-to-end زنده انجام نشده‌اند. همچنین گزارش‌های قبلی همچنان باید به‌صورت کامل بررسی شوند تا مطمئن شویم همهٔ blockerها بسته شده‌اند.

## ۷) فهرست کارهای باقی‌مانده
1. **Parser تکمیلی**: تست‌های بیشتر برای TsetmcMarketWatchParser (HTML redirect/Suspend.php، missing fields، partial data)
2. **Pipeline integration**: بررسی sync_service و ingestion/worker در برابر خطاهای parse (اطمینان از ثبت صحیح status/error)
3. **Cross-layer tests**: اجرای/افزودن تست‌های آفلاین end-to-end (mocked source → parse → persist → API response)
4. **Freshness/UI**: بررسی کامل useMarketData در سناریوهای واقعی (cache، data_as_of، fetched_at ترکیبی)
5. **Environment validation**: در صورت دسترسی، docker compose config و smoke import برای API/worker
6. **BrsApi live**: در صورت آزاد شدن دسترسی، بررسی cooldown/retry بدون دستکاری محدودیت‌ها
