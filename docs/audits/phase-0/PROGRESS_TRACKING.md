# سیستم پیگیری پیشرفت — فاز صفر

**روش:** یک جدول Markdown در همین فایل به‌عنوان منبع حقیقت + (اختیاری) تبدیل هر ردیف به issue در GitHub. هیچ ابزار جدیدی اضافه نمی‌شود.

---

## 1. فیلدهای هر کار

| فیلد | توضیح |
|---|---|
| `ID` | یکتا: `ISSUE-xxx` یا `P-xx` |
| `Title` | عنوان کوتاه |
| `Description` | شرح و اثر |
| `Severity` | Critical / High / Medium / Low |
| `Owner` | دستیار ۱/۲/۳ یا مالک محصول |
| `Status` | یکی از وضعیت‌های بخش ۲ |
| `DependsOn` | IDs وابسته |
| `Files` | مسیرهای دقیق |
| `Acceptance` | معیار پذیرش قابل سنجش |
| `Test` | فرمان/نام تست |
| `Review` | بازبینی‌شده توسط چه کسی |
| `Commit` | هش commit اصلاح (وقتی موجود شد) |

---

## 2. وضعیت‌ها و قواعد گذار

```
شناسایی‌شده → نیازمند بررسی → تأییدشده → آماده اجرا → در حال انجام
   → اصلاح‌شده → تست‌شده → بازبینی‌شده → بسته‌شده
                      ↘ مسدودشده
                      ↘ ردشده با دلیل (با ثبت دلیل)
```

| وضعیت | شرط ورود |
|---|---|
| شناسایی‌شده | شاهد اولیه موجود |
| نیازمند بررسی | شاهد کافی برای قطعیت نیست |
| تأییدشده | شاهد کد/اجرا + مسیر دقیق |
| آماده اجرا | مالک، تصمیم‌های وابسته و تست پذیرش مشخص |
| اصلاح‌شده | commit موجود |
| تست‌شده | خروجی تست پذیرش ضمیمه |
| بازبینی‌شده | بازبین مستقل تأیید کرده |
| بسته‌شده | **فقط** با شاهد اصلاح + نتیجه تست (یا توضیح مستند محدودیت) |
| مسدودشده | مانع بیرونی مشخص (DB، کلید، تصمیم) |
| ردشده با دلیل | بازتولید نشد یا خارج از دامنه؛ دلیل ثبت شود |

> برای ISSUEهای Critical/High، بستن بدون تست معتبر مجاز نیست.

---

## 3. جدول شروع (Snapshot فاز ۰)

| ID | Title | Sev | Owner | Status | Depends | Files | Acceptance/Test |
|---|---|---|---|---|---|---|---|
| P-01 | `_stage_time` NameError | Critical | ۱ | **بسته‌شده** (اصلاح در HEAD) | — | `services/quant_signal_orchestrator.py` | `grep -c _stage_time` = 0 |
| P-02 | setState در render بک‌تست | High | ۲ | **بسته‌شده** | — | `frontend/src/app/backtest/page.tsx` | `:313-322` + vitest |
| P-03 | race/alert صفحه اختیار | High | ۲ | **بسته‌شده** | — | `app/options/page.tsx`, `components/LiveChainPanel.tsx` | signal + placeholderData |
| P-04 | period در indicators | High | ۱ | **بسته‌شده** (بازتولید نشد) | — | `core/indicators.py` | بازبینی خطی + تست‌های موجود |
| P-05 | float_turnover_pct | High | ۱ | **بسته‌شده** | — | `services/feature_engine.py` | `:509-527` |
| P-06 | net_inst_ratio | High | ۱ | **بسته‌شده** | — | `services/feature_engine.py` | `:565-578` |
| P-07 | covered call / contract_size | High | ۱ | **باز** → ISSUE-101 | D-01 | `domain/options/margin_engine.py` | تست سناریوی ۱٬۰۰۰ سهم |
| P-08 | gamma=inf | High | ۱ | **بسته‌شده** | — | `domain/options/pricing.py` | گارد `:166-175` |
| P-09 | CVaR NaN | Medium | ۱ | **بسته‌شده** | — | `domain/options/var_calculator.py` | گارد tail |
| P-10 | bulk_insert count | Medium | ۱ | **بسته‌شده** | — | `brsapi/repositories/base.py` | `:329-339` |
| P-11 | dedup سینک | Medium | ۱ | **بسته‌شده** | — | `brsapi/services/sync_service.py` | `:352-355` |
| P-12 | mock fallback | High | ۲ | **بسته‌شده** (بازتولید نشد) | — | `hooks/useMarketData.ts` | `isLive/isError` + banner |
| P-13 | AbortError | Medium | ۲ | **بسته‌شده** | — | `lib/api.ts` | `:181-186` |
| P-14 | طوفان ۴۰۱ | Medium | ۲ | **باز** → ISSUE-112 | — | `lib/api.ts` | تست موازی 401 |
| P-15 | extractArray خطا | Medium | ۲ | **باز** → ISSUE-111 | — | `lib/api.ts` | تست `{success:false}` |
| P-16 | next.config fallback | Medium | ۲ | **بسته‌شده** | — | `next.config.ts` | `:20-40` |
| P-17 | tree_pricing مرده | Medium | ۱ | **بسته‌شده** | — | `domain/options/tree_pricing.py` | `:87-94` |
| P-18 | race سینک | Medium | ۱ | **نیازمند بررسی** | — | `sync_service.py` | تست هم‌زمانی همه جدول‌ها |
| ISSUE-101 | مارجین covered call | High | ۱ | تأییدشده / آماده اجرا | D-01 | `margin_engine.py`, `options.py` | تست ۱٬۰۰۰ سهم vs ۱۰٬۰۰۰ |
| ISSUE-102 | IV در T=0 | High | ۱ | تأییدشده | — | `pricing.py`, `options_analytics.py` | تست T=0 و round-trip |
| ISSUE-103 | واحد VaR | Medium | ۱+۳ | نیازمند تصمیم | D-02 | `var_calculator.py` | تست واحد |
| ISSUE-104 | `/gold/ticker` ناموجود | Medium | ۳ | تأییدشده | D-03 | `docs/phase1-ticker-api.md` | تست schema |
| ISSUE-105 | F821 | Medium | ۱ | تأییدشده | — | `options_frontend.py`, `symbol_alerts.py` | ruff F821 = 0 |
| ISSUE-106 | تست ML روی Windows | Medium | ۳ | تأییدشده | — | `tests/unit/ml` | اجرای CI لینوکس |
| ISSUE-107 | فایل‌های bak/scratch | Low | ۳ | شناسایی‌شده | BL-01 | ریشه repo | حذف کنترل‌شده |
| ISSUE-108 | کامنت auth کهنه | Low | ۱ | تأییدشده | — | `src/gold_desk/api.py:3` | اصلاح متن |
| ISSUE-109 | import ۶۰ ثانیه | Medium | ۳ | نیازمند بررسی | — | `apps/api/app.py` | پروفایل import |
| ISSUE-110 | import تکراری macro_news | Low | ۱ | تأییدشده | — | `src/gold_desk/macro_news.py` | ruff F811 |
| ISSUE-111 | extractArray | Medium | ۲ | تأییدشده | — | `lib/api.ts` | تست vitest |
| ISSUE-112 | `_handle401` | Low | ۲ | تأییدشده | — | `lib/api.ts` | تست موازی |
| ISSUE-113 | قرارداد JSON بدون تست | Medium | ۳ | تأییدشده | D-04 | `docs/contracts` | تست schema |
| ISSUE-114 | flat vs nested | Medium | ۳ | تأییدشده | D-04 | `docs/contracts/phase1-gold.json` | تصمیم + تست |
| ISSUE-115 | رمز هاردکد E2E | Medium | ۳ | تأییدشده | — | `tests/e2e/test_gold_session_reload.py` | secret gate سبز |
| ISSUE-116 | تست retry وابسته به cooldown | Medium | ۱ | تأییدشده | — | `tests/unit/test_brsapi_client_retry.py` | اجرای deterministic |
| ISSUE-117 | fixture بدون id | Low | ۱ | تأییدشده | — | `tests/unit/test_gold_silver_funds_fixes.py` | دو تست P&L سبز |
| ISSUE-118 | تست cutoff وابسته به داده | Low | ۱ | تأییدشده | — | `tests/unit/backtesting/test_tick_cutoff.py` | skipif/داده مصنوعی |
| ISSUE-119 | cooldown کلید BrsApi | High (عملیاتی) | مالک محصول | نیازمند بررسی | — | provider | تأیید پلن + هشدار |
| ISSUE-120 | هشدار middleware منسوخ Next 16 | Low | ۲ | تأییدشده | — | `frontend/src/middleware.ts` | هشدار build رفع شود |

---

## 4. به‌روزرسانی

- پس از هر تسک، فقط ردیف مربوطه تغییر می‌کند و `Commit` پر می‌شود.
- در پایان هر فاز، شمارش `Status`ها در گزارش فاز ثبت می‌شود.
- این فایل جای گزارش فاز را نمی‌گیرد؛ فقط وضعیت را نگه می‌دارد.
