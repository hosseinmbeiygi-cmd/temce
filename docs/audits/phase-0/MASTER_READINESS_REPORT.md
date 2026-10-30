# گزارش اصلی آمادگی — فاز صفر

**تاریخ ممیزی:** 2026-10-26 (محلی +03:30)
**شاخه:** `integration/golddesk-fixes`
**Baseline commit:** `90597e05b9f4328bcd82ee819a31ba5c55413c12` — «feat(phase0): unify gold engine and ship fail-closed trust labels» — 2026-10-26 09:48:51 +0330
**دامنه:** ممیزی، مستندسازی، اجرای تست‌های مجاز، تعیین مالکیت و gates. **هیچ قابلیت جدیدی ساخته نشد و هیچ فرمول مالی تغییر نکرد.**

---

## 1. خلاصه وضعیت

- پروژه یک پلتفرم FastAPI + Next.js با **۷۱۴ route** مونت‌شده و **۱۰۳ مسیر gold** است؛ نه یک پروژه کوچک. چهار سطح موازی طلا دارد.
- بخش قابل‌توجهی از یافته‌های گزارش قبلی (`HIDDEN_ERRORS_REPORT.md`) در HEAD **واقعاً اصلاح شده** و با کد تأیید شد (۱۴ مورد بسته، ۳ مورد جزئی، ۱ مورد نیازمند بررسی).
- **دو ایراد مالی جدید تأیید شد** که در گزارش قبلی کامل بسته نشده بودند:
  - **ISSUE-101:** مارجین صفر برای short call پوشش‌نشده به‌دلیل `contract_size` پیش‌فرض ۱۰۰۰ برای leg سهام.
  - **ISSUE-102:** `implied_volatility` در `T=0` با `ZeroDivisionError` می‌شکند و همگرایی ندارد.
- baseline تست بک‌اند **سبز نیست**: ۹ شکست واقعی (۵ مورد وابسته به cooldown کلید BrsApi، ۲ fixture قدیمی، ۱ گیت اسرار، ۱ داده محلی).
- baseline فرانت **سبز است**: ۵۸۳ تست، TypeScript بدون خطا، ESLint بدون error (۱۷۹ warning).
- **T13 — اولین اجرای واقعی integration/E2E** در محیط ایزوله (Postgres schema-only + Redis DB 13): integration **۴۴ passed / ۶ failed**، E2E **۳۵ passed / ۶ failed / ۱ skipped**. چهار شکست تأییدشده ریشه‌یابی شد: گم‌شدن خاموش رویدادهای precompute (ISSUE-121)، ناسازگاری `AUTH_DISABLED` (ISSUE-122)، تست معیوب generator (ISSUE-124)، تاریخ شمسی/نبود داده در بک‌تست (ISSUE-126).
- **T14 — پروفایل داده واقعی**: `gregorian_date` تاریخ اجراست نه تاریخ معامله (ISSUE-127)؛ `nav` صندوق‌ها در ۳۲/۳۲ مورد برابر `price_last` است و حباب ساختاراً صفر می‌شود (ISSUE-128).
- **T15 — پروفایل startup**: ۲۶۹۹ ماژول و ۷۱۴ route؛ زنجیره eager `integrations` با export تنبل از **۱.۶۴s به ۰.۰۲۶s** رسید (کد تغییر کرد، تست‌های هدفمند سبز).
- فاز صفر **تکمیل شد** و ورود به فاز ۱ **مشروط** است (بخش ۷).

---

## 2. وضعیت پایه (Git)

| مورد | مقدار |
|---|---|
| Branch | `integration/golddesk-fixes` |
| HEAD | `90597e05` |
| فایل‌های tracked تغییرکرده | **۱۲** (۱۰ مورد قبلی + `integrations/__init__.py` و `integrations/observability/__init__.py` برای export تنبل) |
| مسیرهای untracked | **۳۳** |
| Submodule | `InkGist` dirty (`git status` = ` m`) |
| Stashهای موجود | ۳ مورد (دست نخورد) |
| Commit محلی/merge/push | انجام نشد |

تغییرات فعلی متعلق به کار جاری طلا (phase 0/1/2) است و **حفظ شده‌اند**. هیچ reset/checkout/clean اجرا نشد.

---

## 3. ساختار واقعی (شواهد شمارش)

| بخش | عدد |
|---|---|
| API routes کل | ۷۱۴ |
| gold routes (یکتا) | ۱۰۳ |
| فایل Python/TS/TSX: `apps`/`src`/`core`/`services`/`domain`/`brsapi` | 179 / 73 / 168 / 269 / 219 / 75 |
| فرانت `frontend/src` | ۴۷۲ |
| تست‌ها `tests` | ۵۶۲ فایل |
| migrationها | ۸۶ فایل (head ثبت‌شده ۰۱۱۵ — نیازمند تأیید مجدد) |
| سرویس‌های compose | timescaledb, redis, backend, worker, currency, frontend |

معماری کامل و جریان داده در `ARCHITECTURE_MAP.md`.

---

## 4. وضعیت تست‌ها (اجرای واقعی، نه ادعا)

| فرمان | نتیجه |
|---|---|
| `pytest --collect-only -q` | ۷۴۷۸ از ۷۵۲۷ collect؛ ۴۹ deselected؛ ۱۰۰.۹۴s |
| `pytest tests/unit --ignore=…/ml --ignore=…/performance` | **۹ failed، ۶۳۶۷ passed، ۲۱ skipped**؛ ۷۲۱.۸۶s |
| `pytest tests/unit` (با ml) | **ناتمام** (توقف xgboost روی Windows) |
| `pytest tests/gold_desk` | **۴۳۴ passed، ۱ skipped، EXIT=0**؛ ۱۱۰.۰۲s |
| `pytest tests/gold_desk tests/unit/api/test_golddesk_http.py` | معادل ۴۴۴ (۴۳۴ + ۱۰) → ادعای handoff سازگار |
| `npx vitest run` | **۵۵ فایل / ۵۸۳ تست passed**؛ ۱۰۰.۸۸s |
| `npx tsc --noEmit` | **exit 0** |
| `npm run build` | **موفق، EXIT=0** (Turbopack، ≈۵ دقیقه) |
| `npx eslint src` | **۰ error / ۱۷۹ warning** |
| `ruff check src/gold_desk core services domain brsapi apps` | **۹۲ error** (۲ F821، ۵ I001، ۵ B905، …) |
| import اپ | **۷۱۴ route**؛ ۲۳.۶–۶۰.۴s (گرم/سرد) |

جزئیات شکست‌ها و طبقه‌بندی در `TEST_STRATEGY.md` و `ISSUE_REGISTRY.md`.

---

## 5. مهم‌ترین ریسک‌ها

| رتبه | ریسک | شاهد | مالک |
|---|---|---|---|
| ۱ | مارجین صفر برای پوزیشن naked (ISSUE-101) | اجرای مستقیم: `covered_call` با مارجین 0 برای ۱٬۰۰۰ سهم + ۱۰ call | ۱ |
| ۲ | کرش تحلیل IV در سررسید (ISSUE-102) | `ZeroDivisionError` با `T=0` | ۱ |
| ۳ | قرمز بودن گیت اسرار (ISSUE-115) | رمز هاردکد در `tests/e2e/...:37` | ۳ |
| ۴ | وابستگی تست‌ها/داده به کلید BrsApi در cooldown (ISSUE-116/119) | پیام `Suspend.php` در ۵ تست | مالک محصول + ۳ |
| ۵ | drift مستندات/قرارداد (ISSUE-104/113/114) | `/gold/ticker` وجود ندارد؛ JSON contract بدون تست | ۳ |
| ۶ | startup ۲۳.۶–۶۰.۴ ثانیه (ISSUE-109) | import ۷۱۴ route / ۲۹۸۲ ماژول | ۳ |
| ۷ | baseline قرمز (۹ تست) | خروجی T2 | ۱+۳ |
| ۸ | گم‌شدن خاموش رویداد/نتیجه precompute (ISSUE-121) | worker گزارش `13/13 SUCCESS`، اما صفر رویداد؛ با `127.0.0.1` ۴ تست سبز | ۱+۳ |
| ۹ | تاریخ معامله نامعتبر/تکراری در تاریخچه طلا (ISSUE-127) | ۳۲۱٬۷۳۶ ردیف؛ `gregorian_date` فقط ۴ مقدار متمایز = تاریخ اجرا | ۱ |
| ۱۰ | NAV برابر قیمت و حباب صفر (ISSUE-128) | ۳۲/۳۲ صندوق `nav == price_last`؛ `p05=p50=p95=0` | ۱+۲ |
| ۱۱ | ۷ تست محافظت‌شده با 401 در محیط auth-enabled (ISSUE-122/123) | با توکن معتبر همان endpointها 200 | ۲+۳ |

---

## 6. آنچه واقعاً بررسی شد و آنچه نشد

### بررسی‌شده (با شاهد مستقیم)
- Git status/log/branches/stash و diff.
- ساختار و شمارش فایل‌ها، routeها، تست‌ها، migrationها.
- ۱۸ یافته گزارش قبلی، یک‌به‌یک با کد HEAD.
- `core/indicators.py`، `services/feature_engine.py`، `services/quant_signal_orchestrator.py`، `domain/options/{pricing,margin_engine,var_calculator,tree_pricing}.py`، `brsapi/{repositories/base,sync_service}.py`، `frontend/{lib/api,hooks/useMarketData,lib/goldApi,next.config}.ts`، صفحه بک‌تست و کامپوننت زنجیره اختیار.
- `src/gold_desk` (phase1/phase2/engine/mount) و تست‌های gold.
- **ممیزی عددی فرمول‌ها** با پیاده‌سازی مستقل: RSI، ATR، MACD، Black-Scholes، برابری put-call، طلای ۱۸ عیار، سکه، VaR/CVaR پارامتریک.
- **شمارش الگوهای فرانت** (۱۵۲ صفحه، `key=index`، `alert`، `<img>`، وضعیت‌ها) و **microbenchmark** محاسبات + اندازه‌گیری startup.
- compose، nginx، config امنیتی، CI workflow.

### بررسی‌نشده / محدود
- **همه ۱۰٬۰۰۰+ فایل خوانده نشد**؛ ممیزی عمقی روی فایل‌های نام‌برده + شمارش کل انجام شد. ادعای «کل پروژه بررسی شد» داده نمی‌شود.
- `tests/integration` و `tests/e2e` **در T13 روی دیتابیس ایزوله اجرا شدند** (بدون تغییر داده اپ)؛ با این حال ۲ تست به‌دلیل نبود تاریخچه/مدل آموزش‌دیده در DB خالی قابل ارزیابی نبودند و ۷ تست به‌دلیل نداشتن fixture احراز هویت قرمز ماندند.
- `tests/performance` و `tests/load` اجرا نشدند.
- رفتار runtime رابط کاربری (مرورگر واقعی) بررسی نشد؛ فقط تست‌های JSX/TS و build.
- `tests/unit/ml` اجرا نشد (ISSUE-106).
- gitleaks و اسکن تاریخچه اجرا نشد (گیت داخلی `check_secrets` اجرا شد و قرمز است).
- هیچ تست نفوذ یا عملیات روی سرویس واقعی انجام نشد.
- پوشه‌های بزرگ legacy (`code_dump`, `backtesting`, `ml`, `_audit_out`, `BrSapi_Forecasting`) فقط از نظر ساختار/شمارش دیده شدند.

---

## 7. نتیجه آمادگی فاز بعد

**فاز صفر: تکمیل‌شده.**
**شروع فاز ۱: مشروط — «آماده» به معنی فراهم بودن کنترل‌ها است، نه سالم بودن پروژه.**

### شروط لازم پیش از شروع اصلاحات
1. **BL-01:** مالک، کار جاری را commit یا stash کند تا baseline مشترک تمیز شود (بدون حذف کار).
2. **BL-02:** ۵ تست BrsApi از حالت وابسته به cooldown خارج و ۲ fixture portfolio اصلاح شود تا «سبز شدن» قابل سنجش باشد.
3. **BL-04:** تصمیم D-01 (معنای `contract_size` سهام) و D-02 (واحد VaR) گرفته شود.
4. **BL-03:** وضعیت کلید BrsApi و پلن تأیید شود.

### اقدام بلافاصله بعد از فاز صفر
**دستیار ۱** در شاخه `fix/backend-finance` ابتدا تست‌های ISSUE-101 و ISSUE-102 را بنویسد (قرمز)، سپس اصلاح کند؛ **دستیار ۳** به‌طور موازی تست‌های وابسته به محیط (ISSUE-116، ISSUE-117) و گیت اسرار (ISSUE-115) را ایزوله/سبز کند. فاز ۲ تا تثبیت قرارداد داده شروع نشود.

---

## 8. مستندات ایجادشده

| فایل | محتوا |
|---|---|
| `MASTER_READINESS_REPORT.md` | همین گزارش |
| `BASELINE.md` | وضعیت محیط، Git، وابستگی‌ها، سرویس‌ها و محدودیت‌های تحویل |
| `ARCHITECTURE_MAP.md` | ماژول‌ها، وابستگی، جریان داده، نقاط شکست |
| `CAPABILITY_INVENTORY.md` | ۳۴ قابلیت با وضعیت پیاده‌سازی/اعتبارسنجی و شاهد |
| `ISSUE_REGISTRY.md` | ۱۸ یافته قبلی + ۲۰ ایراد جدید با شاهد و مالک |
| `FINANCIAL_FORMULA_AUDIT.md` | ۱۶ فرمول تأییدشده با محاسبه مستقل + ایرادها + موارد اعتبارسنجی‌نشده |
| `DATA_QUALITY_AUDIT.md` | منابع، تازگی، fail-closed و ریسک‌های داده |
| `API_CONTRACTS.md` | routeها، envelope، واحدها، ناسازگاری‌ها |
| `FRONTEND_AUDIT.md` | صفحات، وضعیت‌ها، الگوهای مشکوک، عملکرد |
| `PERFORMANCE_AUDIT.md` | اندازه‌گیری startup/build/تست و microbenchmark |
| `TEST_STRATEGY.md` | baseline واقعی، ۹ شکست، ماتریس تست |
| `SECURITY_REVIEW_PLAN.md` | سطح حمله، چک‌لیست، محدودیت‌ها |
| `ROADMAP.md` | فاز ۰ تا ۷ + gates |
| `DECISIONS_AND_BLOCKERS.md` | تصمیم‌های باز، ابهام فرمولی، موانع |
| `WORK_OWNERSHIP.md` | دامنه سه دستیار + فایل‌های مشترک + قواعد |
| `THREE_ASSISTANTS_RUNBOOK.md` | ترتیب اجرا، شاخه، ادغام، گزارش |
| `PROGRESS_TRACKING.md` | سیستم پیگیری + snapshot وضعیت |

## 9. پیوست — وضعیت دقیق working tree در زمان ممیزی

خروجی `git status --porcelain` پیش از افزودن `docs/audits/` (بدون هیچ تغییر از سوی این ممیزی):

```text
 M InkGist
 M docs/handoff.md
 M docs/phase0-gold-foundation.md
 M frontend/src/__tests__/GoldFrontendSurfaces.test.tsx
 M frontend/src/app/globals.css
 M frontend/src/app/gold/layout.tsx
 M frontend/src/components/gold/DataTrustBadge.tsx
 M frontend/src/lib/goldApi.ts
 M frontend/src/types/gold.ts
 M src/gold_desk/api.py
?? docs/contracts/
?? docs/data-sources-phase0.md
?? docs/data-sources-phase1.md
?? docs/data-sources-phase2.md
?? docs/data-sources-phase3.md
?? docs/phase1-certificate-api.md
?? docs/phase1-funds-api.md
?? docs/phase1-gold-parity.md
?? docs/phase1-physical-api.md
?? docs/phase1-ticker-api.md
?? docs/phase1-what-if-api.md
?? docs/phase2-market-coverage.md
?? docs/phase3-decision-assistant.md
?? docs/phase3-disclaimer-fa.md
?? docs/phase3-vocabulary-fa.md
?? frontend/src/__tests__/GoldMarketCoverage.test.tsx
?? frontend/src/__tests__/GoldTerminalPhase1.test.tsx
?? frontend/src/app/gold/components/Phase2Overview.tsx
?? frontend/src/app/gold/components/SummarySection.tsx.bak
?? frontend/src/app/gold/coverage/
?? frontend/src/app/gold/terminal/
?? frontend/src/types/phase1.ts
?? frontend/src/types/phase2.ts
?? src/gold_desk/phase1.py
?? src/gold_desk/phase1_schemas.py
?? src/gold_desk/phase2.py
?? src/gold_desk/phase2_schemas.py
?? tests/fixtures/phase1-fund-no-nav.json
?? tests/fixtures/phase1-fund-snapshot.json
?? tests/fixtures/phase1-ticker-snapshot.json
?? tests/fixtures/phase1-what-if-snapshot.json
?? tests/gold_desk/test_phase1_terminal.py
?? tests/gold_desk/test_phase2_market_coverage.py
```

این وضعیت مطابق با تغییرات ابتدای گفتگو است و در طول ممیزی دست‌نخورده باقی ماند؛ تنها افزوده، پوشه `docs/audits/phase-0/` است.

---

**شواهد خام اجرا:** `docs/audits/phase-0/evidence/unit-baseline-failures.txt`، `gold-suite.txt`، `route-inventory.txt`، `frontend-build.txt`، `startup-measurements.txt`. لاگ کامل ۱.۹ مگابایتی تست واحد عمداً نگه داشته نشد؛ خلاصه و فهرست شکست‌ها در همان پوشه است. برای بازتولید، فرمان‌های `TEST_STRATEGY.md` اجرا شود.
