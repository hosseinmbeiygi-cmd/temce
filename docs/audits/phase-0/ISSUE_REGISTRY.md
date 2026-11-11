# رجیستری ایرادها — فاز صفر

**Baseline:** شاخه `integration/golddesk-fixes`، commit `90597e05b9f4328bcd82ee819a31ba5c55413c12` (2026-10-26 09:48:51 +0330).
**قاعده وضعیت:** `بسته‌شده` فقط با شاهد کد + شاهد تست/اجرا. هیچ موردی صرفاً با «اصلاح شد» در متن بسته نشده است.

واژه‌نامه شدت: **Critical** = خرابی/ضرر مالی مستقیم در مسیر فعال · **High** = محاسبه یا دسترسی غلط در مسیر قابل فراخوانی · **Medium** = قرارداد/کیفیت با ریسک آینده · **Low** = بهداشت کد.

---

## 1. بازبینی یافته‌های گزارش‌های قبلی (HIDDEN_ERRORS_REPORT.md)

| ID | یافته قبلی | وضعیت فعلی | شاهد |
|---|---|---|---|
| P-01 | `_stage_time` تعریف‌نشده در `services/quant_signal_orchestrator.py` | **بسته‌شده — اصلاح‌شده** | `grep -c _stage_time` = **0**؛ همه ۲۰ نقطه با `time.monotonic()` (`:660-771`) |
| P-02 | `setState` داخل render در `frontend/src/app/backtest/page.tsx` | **بسته‌شده — اصلاح‌شده** | `:313-322`؛ انتقال به `useEffect` با گارد `strategies !== prevStrategies` |
| P-03 | race زنجیره اختیار + `alert()` در `options/page.tsx` | **بسته‌شده — اصلاح‌شده** | صفحه به ۶۳ خط و کامپوننت‌ها منتقل شده؛ `LiveChainPanel.tsx:20-34` از `signal` و `placeholderData` استفاده می‌کند |
| P-04 | نادیده گرفتن `period` در `core/indicators.py` | **بسته‌شده — بازتولید نشد** | `compute_trend_strength` روی `range(1, period+1)` می‌چرخد (`:241-247`)؛ `compute_rsi/atr/macd` هم period را مصرف می‌کنند |
| P-05 | فرمول `float_turnover_pct` | **بسته‌شده — اصلاح‌شده** | `services/feature_engine.py:509-527`؛ `float_shares_count = shares_count * free_float_pct/100` با clamp 0..100 |
| P-06 | مخرج `net_inst_ratio` | **بسته‌شده — اصلاح‌شده** | `:565-578`؛ همان مخرج شناور + گارد `>1e-9` |
| P-07 | تشخیص covered call در `margin_engine.py` | **باز — جزئی اصلاح‌شده** → ISSUE-101 | منطق `long_stock_qty` درست شده (`:128-134`) اما `contract_size` پیش‌فرض ۱۰۰۰ برای leg سهام باقی است |
| P-08 | `gamma=inf` در `pricing.py` | **بسته‌شده — اصلاح‌شده** | `:166-175`؛ گارد `denom < 1e-12` و `isfinite` |
| P-09 | `cvar=nan` در توزیع بدون tail | **بسته‌شده — اصلاح‌شده** (مسئله واحد جدا) | `var_calculator.py:63-72`، `:130-137`؛ گارد اندازه tail و `isfinite` |
| P-10 | تعداد درج در `brsapi/repositories/base.py` | **بسته‌شده — اصلاح‌شده** | `:329-339`؛ استفاده از `result.rowcount` با fallback مستند |
| P-11 | dedup سینک هرگز اجرا نمی‌شود | **بسته‌شده — اصلاح‌شده** | `sync_service.py:352-355`؛ `dedup_key` شامل `params` |
| P-12 | fallback ساکت به mock در `useMarketData.ts` | **بسته‌شده — بازتولید نشد** | هوک‌ها `isLive/isError` برمی‌گردانند و `LiveDataBanner` مصرف می‌شود؛ import از `market-mock` فقط برای session است (`:14-15`) |
| P-13 | هندل‌نشدن `AbortError` در `api.ts` | **بسته‌شده — اصلاح‌شده** | `:155-186`؛ ترکیب signal و حفظ هویت AbortError |
| P-14 | طوفان ۴۰۱ و logout تکراری | **باز — جزئی** → ISSUE-112 | `_refreshPromise` تک‌پرواز است (`:76-115`) اما `_handle401` (`:120-145`) گارد idempotency ندارد |
| P-15 | قورت دادن خطا در `extractArray` | **باز — جزئی** → ISSUE-111 | `api.ts:307-329` هنوز برای `{success:false}` آرایه خالی برمی‌گرداند؛ `safeExtractArray` فقط لاگ می‌کند |
| P-16 | fallback به `NEXT_PUBLIC_API_URL` در `next.config.ts` | **بسته‌شده — اصلاح‌شده** | `next.config.ts:20-24`؛ فقط `API_URL` یا `api:8000` در production |
| P-17 | عبارت‌های مرده در `tree_pricing.py` | **بسته‌شده — اصلاح‌شده** | `:87-94`؛ `dx = sigma*sqrt(3*dt)` و `nu` محاسبه و استفاده می‌شوند |
| P-18 | race سینک هم‌زمان (INSERT گم‌شده) | **نیازمند بررسی** | upsert فقط برای `SymbolSnapshotModel` فعال است (`sync_service.py:458-473`)؛ برای سایر جدول‌ها شاهد کافی نیست |

---

## 2. ایرادهای تأییدشده جدید

### ISSUE-101 — مارجین صفر برای short call پوشش‌نشده به‌دلیل `contract_size` پیش‌فرض leg سهام

- **شدت:** High (خطای مالی در مسیر API)
- **فایل:** `domain/options/margin_engine.py:35-45` و `:128-134`؛ ورودی API: `apps/api/endpoints/options.py:45-53`
- **شاهد اجرایی (دستور و خروجی واقعی):**
  ```
  stock leg contract_size default: 1000
  strategy: covered_call initial margin: 0.0
  with contract_size=1 -> strategy: multi_leg initial margin: 800000.0
  ```
  سناریو: ۱٬۰۰۰ سهم + ۱۰ قرارداد short call (هر قرارداد ۱۰۰۰ سهم) که **پوشش کامل نیست**، اما مارجین صفر گزارش می‌شود.
- **اثر:** `POST /api/v1/options/professional/margin` می‌تواند پوزیشن naked را covered تشخیص دهد و مارجین صفر برگرداند. فرانت فعلی این endpoint را صدا نمی‌زند (`grep -rn "professional/margin" frontend/src` = بدون نتیجه)، پس مسیر مصرف‌کننده فعلی API/شخص ثالث است.
- **مالک پیشنهادی:** دستیار ۱
- **راهکار پیشنهادی:** برای leg نوع `STOCK` پیش‌فرض `contract_size=1` (یا فیلد اجباری `share_count`)، و در API بین «تعداد سهم» و «تعداد قرارداد» تمایز صریح بگذارید. سپس تست رگرسیون.
- **تست پذیرش:** ۱٬۰۰۰ سهم + ۱۰ short call → `strategy_type != covered_call` و مارجین > 0؛ ۱۰٬۰۰۰ سهم + ۱۰ short call → `covered_call` و مارجین 0.
- **وضعیت:** شناسایی‌شده → تأییدشده. اصلاح نشده.

### ISSUE-102 — `implied_volatility` در سررسید صفر `ZeroDivisionError` می‌دهد و همگرایی را بررسی نمی‌کند

- **شدت:** High
- **فایل:** `domain/options/pricing.py:159-202` (بدون گارد `T<=0`)، مصرف‌کننده: `services/options_analytics.py:9,144`
- **شاهد اجرایی:**
  ```
  T= 0.0 RAISED ZeroDivisionError float division by zero
  T= 1e-12 -> 125413.555780698
  ```
- **اثر:** در روز سررسید یا با `time_to_expiry=0` در chain، تحلیل نوسان با ۵۰۰ خطا متوقف می‌شود. برای `T` بسیار کوچک، IV بی‌معنا (۱۲۵٬۴۱۳ برابر) بدون خطا برمی‌گردد.
- **مالک:** دستیار ۱
- **راهکار:** گارد `T <= 0` و `market_price <= intrinsic`، محدودسازی `sigma` به بازه معقول، بررسی `max_iter`/convergence و بازگرداندن `None` یا خطای دامنه.
- **تست پذیرش:** `T=0` → `None`/خطای کنترل‌شده (نه ZeroDivisionError)؛ round-trip روی قیمت شناخته‌شده با خطای < 1e-4؛ `T=1e-6` مقدار متناهی و ≤ سقف تعیین‌شده.
- **وضعیت:** تأییدشده.

### ISSUE-103 — قرارداد واحد بازده در `VaRCalculator` مبهم است (درصد vs اعشاری، روزانه vs سالانه)

- **شدت:** Medium (کد فعلاً مصرف‌کننده بیرونی ندارد)
- **فایل:** `domain/options/var_calculator.py:35-75`، `:95-120`، `:150-175`
- **شاهد:** docstring می‌گوید «Array of historical daily returns (percentage)» اما `var_95 = var_95_pct * portfolio_value`؛ اگر ورودی درصد باشد (مثلاً ۵ برای ۵٪)، نتیجه ۵ برابر ارزش پورتفوی می‌شود. `monte_carlo_var` ورودی را سالانه فرض و بر ۲۵۲ تقسیم می‌کند، در حالی که سایر توابع روزانه‌اند.
- **اثر:** latent؛ به‌محض اتصال به API، VaR با مقیاس اشتباه گزارش می‌شود.
- **مالک:** دستیار ۱ (تعیین قرارداد) + دستیار ۳ (بازبینی قرارداد)
- **راهکار:** ورودی اعشاری روزانه، یا پارامتر `input_unit` اجباری؛ نام‌گذاری فیلدها (`var_95_ratio`); تست واحد.
- **وضعیت:** نیازمند تصمیم (DECISIONS_AND_BLOCKERS).

### ISSUE-104 — مستندات API برای `/gold/ticker` وجود دارد اما route mount نشده است

- **شدت:** Medium
- **فایل مستند:** `docs/phase1-ticker-api.md`، `docs/contracts/phase1-gold.json` (هر دو untracked)
- **شاهد:** شمارش مسیرهای gold = **103**؛ `ticker routes: []`؛ `/gold/terminal` موجود است.
- **اثر:** مصرف‌کننده یا دستیار بعدی ممکن است بر اساس قرارداد ناموجود کد بنویسد؛ تست contract هم وجود ندارد.
- **مالک:** دستیار ۳ (قرارداد) + مالک مستند
- **راهکار:** یا route/قرارداد حذف/آرشیو شود، یا با schema واحد برای `/gold/terminal` جایگزین شود؛ افزودن تست schema.
- **وضعیت:** تأییدشده.

### ISSUE-105 — نام‌های تعریف‌نشده (F821) در دو endpoint

- **شدت:** Medium (فعلاً به‌خاطر `from __future__ import annotations` کرش نمی‌کند)
- **فایل:** `apps/api/endpoints/options_frontend.py:103` (`LiquidityQuote`)، `apps/api/endpoints/symbol_alerts.py:81` (`Any`)
- **شاهد:** `ruff check ... --select F821` خروجی بالا؛ هر دو فایل `from __future__ import annotations` دارند و نام در helper (نه signature endpoint) است.
- **اثر:** هر ابزاری که type hints را resolve کند (`typing.get_type_hints`, بازبینی خودکار، تبدیل به endpoint) با `NameError` می‌شکند؛ همچنین نشانه import ناقص است.
- **مالک:** دستیار ۱
- **راهکار:** import صحیح (`from services.options_signals import LiquidityQuote` در سطح فایل یا `TYPE_CHECKING`؛ `from typing import Any`).
- **تست پذیرش:** `ruff check --select F821` = 0 برای این دو فایل؛ import اپ موفق.
- **وضعیت:** تأییدشده.

### ISSUE-106 — اجرای کامل تست بک‌اند روی Windows قابل اتکا نیست (توقف روی xgboost)

- **شدت:** Medium (شکاف baseline، نه باگ محصول)
- **شاهد:** اجرای `pytest tests/unit` با `--timeout=60` در `tests/unit/ml/test_cv_no_leakage.py::test_fit_excludes_uncovered_rows_from_meta_learner` روی `xgboost ... XGBoosterUpdateOneIter` به Timeout خورد و اجرا ناتمام ماند (لاگ `_audit_out_unit.txt`).
- **اثر:** «سبز بودن» کل بک‌اند قابل ادعا نیست؛ CI لینوکسی مرجع است.
- **مالک:** دستیار ۳ (CI) + دستیار ۱ (تست ML)
- **راهکار:** اجرای ML در job جدا با `pytest-timeout` و `--timeout-method=signal` روی لینوکس؛ یا marker `slow_ml`.
- **وضعیت:** تأییدشده.

### ISSUE-107 — فایل‌های باقی‌مانده و scratch در working tree

- **شدت:** Low
- **شاهد:** `frontend/src/app/gold/components/SummarySection.tsx.bak` (untracked)، `z.py.bak`، `_probe_*.py`، `_tmp_*.py`، `_audit_out_*.txt` در ریشه.
- **اثر:** ریسک commit ناخواسته و سردرگمی مالکیت.
- **مالک:** دستیار ۳ (پاک‌سازی کنترل‌شده با تأیید مالک)
- **وضعیت:** شناسایی‌شده.

### ISSUE-108 — کامنت کهنه «بدون auth» روی روتر شخصی طلا

- **شدت:** Low
- **فایل:** `src/gold_desk/api.py:3` در مقابل `apps/api/router.py:296`
- **اثر:** تغییردهنده بعدی ممکن است گارد را حذف‌شده فرض کند.
- **مالک:** دستیار ۱
- **وضعیت:** تأییدشده.

### ISSUE-109 — زمان import/startup اپ ۲۳.۶ تا ۶۰.۴ ثانیه

- **شدت:** Medium (عملیاتی)
- **شاهد:** `from apps.api.app import app` با `GOLD_API_TOKEN_SALT` → سه اندازه‌گیری: **۶۰.۴s** (اولین/سرد)، **۲۴.۸۷s** و **۲۳.۶۴s** (پروسه جدید، کش گرم)؛ ۷۱۴ route؛ `-X importtime` → **۲۹۸۲ ماژول**.
- **اثر:** cold start کند، ریسک healthcheck و rollout؛ در محیط سرد تا یک دقیقه.
- **مالک:** دستیار ۳ با هماهنگی دستیار ۱
- **راهکار:** پروفایل import (torch/lightgbm/scipy?)، lazy import در endpointها، سنجش دوباره.
- **به‌روزرسانی T15:** پروفایل انجام شد. `integrations/__init__.py` و `integrations/observability/__init__.py` به export تنبل منتقل شدند → `import integrations` از **۱.۶۴s به ۰.۰۲۶s** و OTel دیگر در بوت لود نمی‌شود (~۱.۶s صرفه در هر بوت). هزینه ساختاری باقی‌مانده (۲۶۹۹ ماژول، ۷۱۴ route، ~۱۴s ارزیابی annotation) باز است. جزئیات: `PERFORMANCE_AUDIT.md` بخش ۶.
- **وضعیت:** جزئی اصلاح‌شده (۱.۶s) — باز برای بازطراحی route/annotation.

### ISSUE-110 — importهای تکراری/مرده در `src/gold_desk/macro_news.py`

- **شدت:** Low
- **شاهد:** `ruff --select F811` → `json`, `re`, `asdict`, `dataclass`, `datetime` دوباره import شده‌اند (`:43-47`).
- **وضعیت:** تأییدشده.

### ISSUE-111 — `extractArray` خطای بک‌اند را به «آرایه خالی» تبدیل می‌کند

- **شدت:** Medium
- **فایل:** `frontend/src/lib/api.ts:307-329`؛ `safeExtractArray:333-341`
- **شاهد:** برای `{success:false,error:"..."}` مقدار `[]` برمی‌گردد. هوک‌های جدید `isError` را جدا می‌کنند، اما هر مصرف‌کننده مستقیم `extractArray` خطا را نمی‌بیند.
- **مالک:** دستیار ۲
- **راهکار:** بازگرداندن نتیجه discriminated (`{ok:true,items}`/`{ok:false,error}`) یا الزام استفاده از `safeExtractArray` + شمارش call siteها.
- **وضعیت:** نیازمند بررسی (فهرست call siteها در فاز ۲).

### ISSUE-112 — `_handle401` idempotent نیست

- **شدت:** Low
- **شاهد:** `_handle401` بدون flag ماژول‌سطح (`api.ts:120-145`)؛ refresh تک‌پرواز است اما پس از شکست آن، هر درخواست موازی یک `POST /auth/logout` می‌فرستد.
- **مالک:** دستیار ۲
- **وضعیت:** تأییدشده (اثر محدود: redirect یکسان است).

### ISSUE-113 — فایل‌های قرارداد JSON هیچ تست یا اعتبارسنجی ندارند

- **شدت:** Medium
- **فایل:** `docs/contracts/gold-price-schema.json`، `phase1-gold.json`، `phase3-decision.json`
- **شاهد:** `grep -rln "docs/contracts\|phase1-gold.json\|gold-price-schema" tests frontend/src scripts` = **بدون نتیجه**؛ `jsonschema` در `requirements*.txt` و `pyproject.toml` وجود ندارد.
- **اثر:** قرارداد به‌عنوان سند غیرقابل‌اجرا است؛ drift بدون خطا عبور می‌کند (ISSUE-104/114 نمونه‌های آن‌اند).
- **مالک:** دستیار ۳
- **راهکار:** تست schema با `jsonschema` یا تولید OpenAPI/Pydantic و مقایسه؛ fail در CI.
- **وضعیت:** تأییدشده.

### ISSUE-114 — قرارداد flat در `phase1-gold.json` با پاسخ nested `/gold/terminal` ناسازگار است

- **شدت:** Medium
- **فایل:** `docs/contracts/phase1-gold.json` در برابر `src/gold_desk/phase1_schemas.py`
- **شاهد:** JSON فقط `symbol/name/price/changePct/...` را در ریشه تعریف می‌کند؛ `/gold/terminal` پاسخ `TerminalResponse` با `ticker[]`/`physical[]`/`funds[]`/`certificates[]` است.
- **اثر:** مصرف‌کننده‌ای که JSON را مرجع بگیرد، فیلد اشتباه می‌خواند.
- **مالک:** دستیار ۳ + ۱
- **وضعیت:** تأییدشده (نیازمند D-04).

### ISSUE-120 — هشدار منسوخ‌شدن `middleware` در Next.js 16

- **شدت:** Low
- **شاهد:** `npm run build` → `⚠ The "middleware" file convention is deprecated. Please use "proxy" instead.` (ساخت در نهایت موفق: EXIT=0)
- **اثر:** در نسخه بعدی Next می‌تواند بشکند؛ رفتار فعلی درست است.
- **مالک:** دستیار ۲ (با بازبینی ۳)
- **وضعیت:** تأییدشده (بهبود آینده‌نگر، خارج از دامنه فاز ۱).

### ISSUE-115 — رمز هاردکدشده در تست E2E (گیت اسرار قرمز است)

- **شدت:** Medium (بهداشت امنیتی؛ وضعیت واقعی بودن حساب نامشخص)
- **فایل:** `tests/e2e/test_gold_session_reload.py:37` → `PASSWORD = "GoldQa#2026!pass"`؛ `frontend/src/__tests__/GoldApiLayer.test.ts:14` → `REFRESH_TOKEN = "test-access-token"`
- **شاهد:** `pytest tests/unit/test_check_secrets_and_gold_scope.py::test_working_tree_has_no_hardcoded_secrets` →
  `AssertionError: hardcoded secret found: tests/e2e/test_gold_session_reload.py:37, frontend/src/__tests__/GoldApiLayer.test.ts:14`
- **اثر:** تست گیت امنیتی در baseline قرمز است؛ اگر رمز واقعی باشد باید چرخانده شود. تست فرانت احتمالاً false positive است اما همان تست را هم قرمز می‌کند.
- **مالک:** دستیار ۳
- **راهکار:** حذف رمز از فایل و خواندن از env؛ allowlist دقیق برای توکن تستی فرانت در `scripts/check_secrets.py` (نه در gitleaks کلی).
- **وضعیت:** تأییدشده.

### ISSUE-116 — ۵ تست retry به وضعیت سراسری cooldown کلید BrsApi وابسته‌اند

- **شدت:** Medium (غیرقطعی بودن تست + نشانه اختلال منبع داده)
- **فایل:** `tests/unit/test_brsapi_client_retry.py`
- **شاهد:** ۵ خطای `test_502_*`/`test_504_*`/`test_401_*` با متن:
  `BrsApi key in 302-cooldown (464s left ... 'http://BrsApi.ir/Suspend.php') — server-side usage is above the plan threshold`
  به‌جای پاسخ mock؛ یعنی governor پیش از منطق retry درخواست را رد می‌کند.
- **اثر:** تست واحد به state بیرونی وابسته است؛ نتیجه اجرا در CI/زمان متفاوت تغییر می‌کند. همچنین نشان می‌دهد کلید BrsApi در زمان اجرا در cooldown بوده است (ISSUE-119).
- **مالک:** دستیار ۱ (تست) + دستیار ۳ (جداسازی محیط)
- **راهکار:** mock کردن budget governor/cooldown در fixture یا تزریق state ایزوله؛ ممنوعیت تماس واقعی در unit.
- **وضعیت:** تأییدشده.

### ISSUE-117 — دو تست portfolio با fixture قدیمی می‌شکنند (`SimpleNamespace.id`)

- **شدت:** Low (تست، نه محصول)
- **فایل:** `tests/unit/test_gold_silver_funds_fixes.py:168,185` با `_HoldingsSession` (`:160-165`)
- **شاهد:** `AttributeError: 'types.SimpleNamespace' object has no attribute 'id'`؛ کد `src/gold_desk/portfolio.py:482` از `h.id` برای `holding_ids` استفاده می‌کند.
- **اثر:** baseline قرمز؛ پوشش تست P&L از کار می‌افتد.
- **مالک:** دستیار ۱
- **راهکار:** افزودن `id` به fixture یا `getattr(h, "id", None)` در کد اگر مدل واقعی هم ممکن است null داشته باشد (بررسی شود).
- **وضعیت:** تأییدشده.

### ISSUE-118 — تست cutoff به فایل داده محلی وابسته است

- **شدت:** Low
- **فایل:** `tests/unit/backtesting/test_tick_cutoff.py::test_real_files_respect_cutoff`
- **شاهد:** `AssertionError: expected some days with post-close ticks` / `assert 0 > 0`
- **اثر:** در محیط بدون داده intraday، تست معنادار نیست و baseline را قرمز می‌کند.
- **مالک:** دستیار ۱
- **راهکار:** `pytest.mark.skipif` بر اساس وجود fixture، یا ساخت داده مصنوعی.
- **وضعیت:** تأییدشده.

### ISSUE-119 — کلید BrsApi در زمان اجرا در cooldown سمت ارائه‌دهنده بوده است

- **شدت:** High برای تازگی داده (عملیاتی، نه کد)
- **شاهد:** پیام واقعی در اجرای تست: `BrsApi key in 302-cooldown (464s left, last redirect to 'http://BrsApi.ir/Suspend.php') — server-side usage is above the plan threshold; requests rejected to protect the key`
- **اثر:** اگر این وضعیت در production ادامه یابد، ingestion و قیمت‌های طلا کهنه می‌شوند؛ UI به‌درستی `DELAYED/NO_DATA` نشان می‌دهد اما قابلیت تحلیلی محدود می‌شود.
- **مالک:** مالک محصول (کلید/پلن) + دستیار ۳ (پایش)
- **راهکار:** تأیید وضعیت پلن، بررسی budget governor، هشدار روی cooldown، و جلوگیری از مصرف کلید در تست.
- **وضعیت:** نیازمند بررسی (وضعیت در زمان ممیزی، نه یک نقص کد).

### ISSUE-121 — precompute پس از تایم‌اوت اتصال Redis، رویدادها و نتایج را خاموش دور می‌ریزد

- **شدت:** High (گم‌شدن خاموش نتیجه محاسبات و نقض قرارداد رویداد، در حالی که زنجیره `SUCCESS` گزارش می‌کند)
- **فایل:** `precompute/redis_client.py:55-78` (`socket_connect_timeout=2.0`)، `:113-129` (`except` بلعنده + breaker)، `precompute/config.py:33-37`
- **شاهد (تأییدشده با اجرا):** در integration، worker واقعی برای `it-celery-full` مقدار `{'total': 13, 'success': 13, 'overall_status': 'SUCCESS'}` را در لاگ ثبت کرد، اما `EventCapture` **صفر** رویداد دید (`assert 0 == 13`).
- **اثبات علت:** اندازه‌گیری مستقیم: `localhost:6379` در ۲.۰۶s وصل می‌شود، `127.0.0.1` در ۰.۰۱s؛ با `socket_connect_timeout=2.0` اتصال به `localhost` با `TimeoutError` شکست می‌خورد. با تغییر تنها نام میزبان به `127.0.0.1`، همان ماژول از ۲ failed به **۴ passed در ۱۲.۱۸s** رسید و زمان کل integration از ۱۳۷s به ۵۰s کاهش یافت.
- **رفتار فعلی:** هر خطای Redis فقط در `logger.debug` ثبت و با breaker ۱۰ ثانیه‌ای خاموش می‌شود؛ API/UI ممکن است زنجیره را موفق ببیند در حالی که هیچ رویداد/نتیجه‌ای ذخیره نشده است.
- **رفتار مورد انتظار:** شکست hot-layer باید قابل مشاهده باشد (شمارنده/متریک/لاگ warning با نوع رویداد) و در صورت نبود نتیجه، وضعیت `DELAYED/FAILED` اعلام شود نه `SUCCESS`.
- **ماژول‌های تحت تأثیر:** `precompute` worker، `api` live chain، هر مصرف‌کننده `precompute:events` و `precompute:result:*`.
- **راهکار:** پذیرش host عددی یا افزایش connect timeout بالاتر از تأخیر نام‌گذاری، تفکیک تایم‌اوت connect/read، ارتقای لاگ drop به warning با شمارنده، و fail-closed برای ذخیره نتیجه (با سیاست retry محدود).
- **تست پذیرش:** تست integration که با Redis در دسترس، تعداد رویدادها و نتیجه hot-layer را روی `total` بررسی می‌کند؛ تست منفی که با Redis قطع، وضعیت را `FAILED` می‌بیند نه `SUCCESS`.
- **مالک:** دستیار ۱ (precompute/داده) + دستیار ۳ (پیکربندی/استقرار)
- **وضعیت:** تأییدشده — اصلاح نشده (خارج از دامنه فاز ۰)

### ISSUE-122 — `AUTH_DISABLED` مسیر `get_current_user` را غیرفعال نمی‌کند

- **شدت:** Medium (ناسازگاری پیکربندی/عملیات؛ fail-closed است، حفره امنیتی نیست)
- **فایل:** `apps/api/auth.py:26-36` در برابر `apps/api/dependencies.py:246-259`؛ استفاده در `apps/api/router.py:20`
- **شاهد:** با `AUTH_DISABLED=true`، `_auth_required()` مقدار `False` برمی‌گرداند ولی `GET /api/v1/backtests/strategies` همچنان `401 {"detail":"Not authenticated"}` می‌دهد.
- **اثر:** فلگ مستندشده برای sandbox فقط بخشی از سطح API را باز می‌کند؛ نتیجه، رفتار متناقض بین روت‌های `verify_token` و روت‌های `_require_user` است.
- **رفتار مورد انتظار:** یک منبع حقیقت واحد برای الزام احراز هویت در همه dependencyها.
- **راهکار:** استفاده `get_current_user` از همان `_auth_required()` (یا حذف فلگ و مسیر صریح توکن تستی).
- **تست پذیرش:** تستی که با `AUTH_DISABLED=true` هم روت عمومی و هم روت `_require_user` را بدون توکن ۲۰۰ ببیند؛ و با فلگ خاموش، ۴۰۱.
- **مالک:** دستیار ۳ (امنیت/یکپارچگی)
- **وضعیت:** تأییدشده — اصلاح نشده

### ISSUE-123 — تست‌های E2E/integration مسیرهای محافظت‌شده هیچ fixture احراز هویت ندارند

- **شدت:** Medium (پوشش آزمون؛ ۷ تست در محیط auth-enabled همیشه قرمزند)
- **فایل:** `tests/e2e/test_backtest_api.py:24-29` و `tests/integration/test_screener_endpoint.py:19-23`
- **شاهد:** ۶ شکست E2E و ۱ شکست integration، همه با `401`؛ با توکن معتبر همان endpointها `200` می‌دهند (`_audit_tmp/auth_probe.py`).
- **اثر:** نمی‌توان جریان‌های محافظت‌شده را در CI/محیط واقعی تأیید کرد؛ خطر آنکه رگرسیون واقعی پشت این ۴۰۱ها پنهان بماند.
- **راهکار:** fixture مشترک توکن (کاربر تستی در DB ایزوله) یا dependency override صریح؛ بدون تضعیف احراز هویت production.
- **تست پذیرش:** اجرای همان دو فایل بدون هیچ ۴۰۱، در حالی که تستی جدا ثابت کند بدون توکن ۴۰۱ می‌دهد.
- **مالک:** دستیار ۲ (E2E) با تأیید دستیار ۳
- **وضعیت:** تأییدشده — اصلاح نشده

### ISSUE-124 — مقایسه دو generator با `>` در تست voting (assertion از ابتدا بی‌اثر)

- **شدت:** Low (تست معیوب؛ TypeError)  
- **فایل:** `tests/integration/test_signal_voting.py:445-456`
- **شاهد:** `TypeError: '>' not supported between instances of 'generator' and 'generator'`
- **رفتار مورد انتظار:** شمارش با `sum(1 for ...)` و سپس مقایسه.
- **اثر:** این تست هیچ‌گاه نمی‌توانسته رگرسیون voting را بگیرد؛ پوشش ادعاشده واقعی نیست.
- **مالک:** دستیار ۱ · **وضعیت:** تأییدشده — اصلاح نشده

### ISSUE-125 — drift نام استراتژی بین `VoteResult`/`MarketSignal` و تست‌ها

- **شدت:** Medium (قرارداد قابل مشاهده برای مصرف‌کننده)
- **فایل:** `tests/integration/test_signal_voting.py:101` و `:338`؛ مقدار واقعی `ml_weighted` / `voting_ml_weighted`
- **شاهد:** `AssertionError: assert 'ml_weighted' in ('weighted', 'unanimous')` و `'voting_ml_weighted' in ('voting_weighted','voting_unanimous')`
- **اثر:** هر مصرف‌کننده‌ای که روی نام استراتژی branch می‌زند (UI/گزارش) با مقدار ناشناخته روبه‌رو می‌شود؛ تست‌ها هم منبع حقیقت نیستند.
- **راهکار:** تثبیت enum/لیست مجاز نام استراتژی در قرارداد و به‌روزرسانی هر دو طرف.
- **مالک:** دستیار ۱ + دستیار ۳ · **وضعیت:** تأییدشده — اصلاح نشده

### ISSUE-126 — تاریخ شمسی به‌صورت رشته به asyncpg می‌رود و خطای واقعی به «نبود داده» تبدیل می‌شود

- **شدت:** High (بارگذاری تاریخچه بک‌تست با پارامتر تاریخ خراب می‌شود و علت پنهان می‌ماند)
- **شاهد:** `asyncpg.exceptions.DataError: invalid input for query argument $2: '1402-10-11' ('str' object has no attribute 'toordinal')`؛ سپس پاسخ `No historical data found for فولاد in the specified date range`
- **اثر:** کاربر/تحلیل‌گر «نبود داده» می‌بیند نه «خطای تاریخ»؛ بک‌تست روی بازه‌های شمسی نتیجه معتبر نمی‌دهد.
- **رفتار مورد انتظار:** تبدیل صریح تاریخ شمسی به `date` میلادی قبل از پارامتر bind، و انتشار خطای typed در پاسخ.
- **تست پذیرش:** تست واحد تبدیل تاریخ + تست integration بک‌تست با بازه شمسی که داده دارد.
- **مالک:** دستیار ۱ · **وضعیت:** تأییدشده — اصلاح نشده

### ISSUE-127 — تاریخچه طلا/سکه دوبار با فرمت تاریخ ناهمسان درج شده و `gregorian_date`/`shamsi_date` تاریخ اجرا است

- **شدت:** High (هر فیلتر زمانی روی داده تاریخی نتیجه غلط می‌دهد)
- **شاهد (داده واقعی، فقط خواندن):**
  - `brsapi_gold_currency_pro_daily_history`: ۳۲۱٬۷۳۶ ردیف؛ `date` با دو فرمت `1405/05/01` (۱۶۰٬۲۹۳) و `1405-06-23` (۱۶۱٬۴۴۳).
  - `gregorian_date` فقط ۴ مقدار متمایز دارد: `2026-07-23` (۱۶۰٬۲۹۳ ردیف)، `2026-08-31` (۱۶۰٬۲۹۳)، `2026-09-14` (۸۷۶)، `2026-08-05` (۲۷۴) → همان تاریخ اجرای ingestion.
  - `shamsi_date` نیز تاریخ اجرا است (نماد `AED`: همه ردیف‌ها `1405-06-23` در حالی که `date` از ۰۶-۱۲ تا ۰۶-۲۳ است).
- **اثر:** `count(*) filter (gregorian_date >= current_date - 30) = 0` در حالی که داده ۱۴۰۵-۰۶ موجود است؛ dedup بر اساس `(symbol, gregorian_date)` عملاً همه را یک ردیف می‌بیند؛ بک‌تست/فرشنس با بازه اشتباه کار می‌کند. ناسازگاری OHLC هم رکورد می‌شود (high<low: ۷۴، close خارج بازه: ۹۰، open خارج بازه: ۶۷۶، extreme≤۰: ۶).
- **رفتار مورد انتظار:** نرمال‌سازی یکتای تاریخ شمسی به `date` میلادی در زمان ورود، کلید یکتای `(symbol, trading_date)`، `ingested_at` جدا از `trading_date`، و فلگ کیفیت برای ردیف ناسازگار.
- **راهکار:** migration برای dedup و محاسبه مجدد `gregorian_date` از `date`، اصلاح loader (ISSUE-126 مرتبط)، افزودن constraint یکتا و تست idempotency دو بار ingestion.
- **تست پذیرش:** دو بار ingestion پیاپی → تعداد ردیف ثابت؛ `max(gregorian_date)` با `max(date)` تبدیل‌شده برابر؛ هیچ ردیف `high<low` بدون فلگ.
- **مالک:** دستیار ۱ · **وضعیت:** تأییدشده — اصلاح نشده

### ISSUE-128 — `nav` صندوق‌ها کپی `price_last` است؛ حباب/تخفیف ساختاراً صفر

- **شدت:** High برای تحلیل صندوق طلا (معیار NAV بی‌معنا ولی با ظاهر معتبر)
- **شاهد:** ۵۸۹ صندوق، فقط ۳۲ تا `nav>0`؛ در **۳۲ از ۳۲** مقدار `nav == price_last` و `nav_ne_price = 0`. برای `اطلس` ۱۴ رکورد NAV واقعی تا 2026-10-05 وجود دارد اما `funds.nav` برابر قیمت است.
- **اثر:** توزیع `price/nav-1` برای همه ۳۲ صندوق دقیقاً صفر شد (`p05=p50=p95=0`)؛ هر سیگنال/امتیاز حباب صندوق در UI بی‌اطلاع و گمراه‌کننده است. ۵۵۷ صندوق دیگر هیچ NAV ندارند.
- **رفتار مورد انتظار:** `nav` فقط از `brsapi_nav_records` (تازه‌ترین رکورد ≤ تاریخ snapshot) پر شود؛ در نبود NAV مقدار `NULL` بماند و UI مبنای نمایش را صریح اعلام کند.
- **راهکار:** اصلاح join در سرویس صندوق‌ها، ممنوعیت نوشتن `price` در ستون `nav`، تست: صندوق با NAV واقعی ≠ قیمت باید premium غیرصفر بدهد؛ بدون NAV باید `NULL` و `nav_basis` مشخص باشد.
- **مالک:** دستیار ۱ + دستیار ۲ (نمایش) · **وضعیت:** تأییدشده — اصلاح نشده

### ISSUE-129 — فایل تست جدید (untracked) `test_phase3_adapters.py` با کد فعلی adapterها سازگار نیست

- **شدت:** Medium (کار در جریان؛ اعتبار فاز ۳ را زیر سؤال می‌برد)
- **شاهد:** `pytest tests/gold_desk/test_phase3_adapters.py` → ۵ failed / ۹ passed (اجرا به‌تنهایی)، و در اجرای کامل `tests/gold_desk` ۹ failed / ۴۳۹ passed. نمونه‌ها: `assert 'DELAYED' == 'LIVE'`، `assert 'brsapi' == 'unknown'` (برای ورودی خالی)، `quality == 'SAMPLE'`.
- **کنترل علیت:** همان فایل با نسخه **HEAD** پکیج `integrations` (بدون تغییر T15) هم ۵ شکست داد → ربطی به تغییر lazy import ندارد. مجموعه شکست بین دو اجرا تفاوت داشت (وابسته به ترتیب/حالت مشترک).
- **اثر:** نمی‌توان به «سبز بودن» این تست‌ها استناد کرد؛ فایل هنوز commit نشده و ممکن است با نسخه adapter هم‌زمان تغییر کند.
- **راهکار:** تثبیت قرارداد adapterها (quality/freshness/source)، حذف وابستگی به حالت مشترک بین تست‌ها، سپس commit و اجرای تکرارپذیر.
- **مالک:** دستیار ۱ · **وضعیت:** تأییدشده — اصلاح نشده

---

## 2.5. ماتریس اولویت (احتمال × اثر × هزینه × وابستگی)

| ID | احتمال وقوع | اثر مالی/عملیاتی | گستره | هزینه اصلاح | وابستگی | اولویت |
|---|---|---|---|---|---|---|
| ISSUE-101 | متوسط (نیاز به leg سهام) | **بالا** (مارجین صفر) | API اختیار | کم | D-01 | **P0** |
| ISSUE-102 | بالا (روز سررسید) | **بالا** (500 در تحلیل IV) | options analytics | کم | — | **P0** |
| ISSUE-115 | قطعی (تست قرمز) | متوسط (افشای رمز) | CI/امنیت | کم | — | **P0** |
| ISSUE-116 | قطعی در محیط فعلی | متوسط (تست غیرقطعی) | ۵ تست | متوسط | — | P1 |
| ISSUE-119 | بالا (cooldown فعلی) | **بالا** (تازگی داده) | ingestion | عملیاتی | پلن کلید | **P0 (عملیاتی)** |
| ISSUE-104/113/114 | بالا (drift) | متوسط | قرارداد | متوسط | D-03/D-04 | P1 |
| ISSUE-111 | متوسط | متوسط (خطا پنهان) | UI | متوسط | — | P1 |
| ISSUE-117/118 | قطعی | کم (تست) | تست | کم | — | P2 |
| ISSUE-109 | قطعی | متوسط (startup) | API | متوسط | پروفایل | P2 |
| ISSUE-121 | بالا (پیکربندی فعلی) | **بالا** (گم‌شدن خاموش نتیجه/رویداد) | precompute/API | کم | — | **P0** |
| ISSUE-127 | قطعی (داده فعلی) | **بالا** (فیلتر زمانی/dedup غلط) | تاریخچه طلا/سکه | متوسط | ISSUE-126 | **P0** |
| ISSUE-128 | قطعی (۳۲/۳۲) | **بالا** (سیگنال حباب صندوق بی‌معنا) | صندوق/GoldDesk | متوسط | — | **P0** |
| ISSUE-126 | بالا (بازه شمسی) | **بالا** (بک‌تست بی‌نتیجه) | backtest | متوسط | — | **P0** |
| ISSUE-122/123 | قطعی | متوسط (پوشش آزمون/پیکربندی) | auth/E2E | متوسط | — | P1 |
| ISSUE-125 | متوسط | متوسط (قرارداد) | signals | کم | — | P1 |
| ISSUE-124 | قطعی | کم (تست) | تست | کم | — | P2 |
| ISSUE-105/108/110/120 | کم | کم | کیفیت کد | کم | — | P3 |

**ترتیب پیشنهادی:** ISSUE-121/126 (شواهد اجرایی، اثر مستقیم بر داده) → ISSUE-101/102 (با تست) → ISSUE-115/116/117/124 (سبزکردن baseline) → ISSUE-122/123/125 (auth/قرارداد) → ISSUE-111/112 (فرانت) → قرارداد (104/113/114) → عملکرد (109) → پاک‌سازی (105/107/108/110/120).

---

## 3. موارد مشکوک (بدون شاهد کافی — نباید به‌عنوان باگ قطعی گزارش شوند)

| ID | موضوع | چرا مشکوک است | بررسی لازم |
|---|---|---|---|
| S-01 | race سینک برای جدول‌های غیر از snapshot | upsert فقط برای snapshot دیده شد | جست‌وجوی `ON CONFLICT` در همه repositoryها + تست هم‌زمانی |
| S-02 | `Date.now()`/`new Date()` داخل render در کامپوننت‌های قدیمی | گزارش قبلی ادعا کرده؛ بازبینی همه موارد انجام نشد | جست‌وجوی هدفمند در فاز ۲ |
| S-03 | `key={index}` در جداول اختیار | گزارش قبلی؛ کد صفحه بازنویسی شده | بازبینی کامپوننت‌های جدید |
| S-04 | بارگذاری تصاویر با `<img>` در صفحات crypto | گزارش قبلی؛ اندازه اثر LCP اندازه‌گیری نشد | Lighthouse در فاز ۲ |
| S-05 | کوئری سنگین `funds` با `queryKey` طولانی | گزارش قبلی؛ رفتار refetch اندازه‌گیری نشد | پروفایل شبکه در فاز ۲ |
| S-06 | صحت ضرایب مارجین/قرارداد طبق مقررات SEO/IME | منبع رسمی در repo نیست | تأیید مالک محصول (DECISIONS) |
| S-07 | گزارش freshness برای ۱۳ منبع، ۲ query به ازای هر منبع (۲۶ query) | `freshness._probe`؛ زمان واقعی روی جدول بزرگ اندازه‌گیری نشد | پروفایل روی DB واقعی |

---

## 3.5. قالب اجباری ثبت موارد جدید

هر ISSUE جدید باید این فیلدها را داشته باشد (موارد موجود بخشی از آن‌ها را در متن دارند و در به‌روزرسانی بعدی کامل می‌شوند):

```text
ID / عنوان / شدت / احتمال وقوع / اثر / شواهد / فایل:خط / مراحل بازتولید
رفتار فعلی / رفتار مورد انتظار / علت ریشه‌ای (یا «فرضیه»)
ماژول‌های تحت تأثیر / ریسک خود اصلاح / ماژول‌های وابسته
راهکار / تست پذیرش / مالک / وضعیت / commit / بازبین
```

قاعده: اگر «علت ریشه‌ای» اثبات نشده، با برچسب «فرضیه» ثبت شود؛ اگر تست پذیرش وجود ندارد، وضعیت نمی‌تواند `بسته‌شده` شود.

---

## 4. جمع‌بندی شمارش

- بازبینی‌شده از گزارش قبلی: **۱۸** مورد → ۱۴ اصلاح‌شده/بازتولیدنشده، ۳ جزئی، ۱ نیازمند بررسی.
- ایراد ثبت‌شده جدید: **۲۹** (High: ۷ شامل ISSUE-119/121/126/127/128؛ Medium: ۱۴ شامل ISSUE-129؛ Low: ۸).
- مشکوک: **۶**.
- شکست‌های baseline تست واحد: **۹** (۵ BRS retry، ۲ portfolio fixture، ۱ secret gate، ۱ tick cutoff).
- شکست‌های integration/E2E در محیط ایزوله: **۱۲** (۶+۶) که ۲ مورد آن با اصلاح نام میزبان Redis سبز شد؛ ۷ مورد auth (ISSUE-122/123)، ۲ مورد داده‌ای/محیطی، ۳ مورد تست/قرارداد (ISSUE-124/125).
- هیچ مورد Critical تأییدشده در مسیر فعال فعلی پیدا نشد؛ ISSUE-101 و ISSUE-102 در صورت فراخوانی API به High تبدیل می‌شوند.
