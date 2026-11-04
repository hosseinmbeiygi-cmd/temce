# راهبرد تست — فاز صفر

**محیط اندازه‌گیری:** Windows 11، bash (Git Bash)، Node `v24.16.0`، npm `11.13.0`.
**مفسر Python مورد استفاده:** `venv/Scripts/python.exe` = **Python 3.11.9** (وابستگی‌ها نصب).
**هشدار محیطی:** `.venv/Scripts/python.exe` روی **Python 3.14.6** است و `fastapi`/`pytest` ندارد → برای اجرای تست استفاده نشد.

---

## 1. Baseline اجراشده (خروجی واقعی)

| # | فرمان | نتیجه | زمان |
|---|---|---|---|
| T1 | `venv/Scripts/python.exe -m pytest --collect-only -q` | **7478 از 7527** تست collect شد؛ 49 deselected | 100.94s |
| T2 | `pytest tests/unit --ignore=tests/unit/ml --ignore=tests/unit/performance -q --timeout=90 --timeout-method=thread` | **9 failed, 6367 passed, 21 skipped, 46 deselected** | 721.86s (12:01) |
| T3 | `pytest tests/unit` (کامل، شامل ml) | **ناتمام** — توقف روی `tests/unit/ml/test_cv_no_leakage.py` در `XGBoosterUpdateOneIter` با Timeout 60s | > 5 دقیقه |
| T4 | `pytest tests/gold_desk/test_phase1_terminal.py tests/gold_desk/test_phase2_market_coverage.py -q` | **70 passed** | 117.66s |
| T5 | `pytest tests/gold_desk` (کامل) | **434 passed, 1 skipped, EXIT=0** | 110.02s |
| T6 | `cd frontend && npx vitest run --reporter=dot` | **55 فایل، 583 تست passed** | 100.88s |
| T7 | `cd frontend && npx tsc --noEmit` | **خروجی خالی = exit 0** | چند ثانیه |
| T8 | `cd frontend && npx eslint src` | **0 error، 179 warning** | ~30s |
| T9 | `venv/Scripts/python.exe -m ruff check src/gold_desk core services domain brsapi apps` | **92 error** (۲ F821، ۵ I001، ۵ B905، …) | ~20s |
| T10 | `from apps.api.app import app` با `GOLD_API_TOKEN_SALT` | **714 route**؛ import **60.4s سرد / 23.64–24.87s گرم** | 60.4s (اولین) |
| T11 | `pytest tests/gold_desk/test_phase1_terminal.py` + `test_phase2_market_coverage.py` (تکرار هدفمند) | **70 passed** | 117.66s |
| T12 | `cd frontend && npm run build` | **موفق، EXIT=0** (Next.js 16.2.9/Turbopack؛ compile ۲.۱ دقیقه + TypeScript ۹۰s + تولید صفحات) | ≈ ۵ دقیقه |

**نتیجه:** baseline بک‌اند «سبز» نیست. ۹ شکست واقعی + یک گیت امنیتی قرمز وجود دارد.

خلاصه شواهد: `evidence/unit-baseline-failures.txt` (فهرست FAILED + شمارش)، `evidence/gold-suite.txt` (۴۳۴ passed)، `evidence/route-inventory.txt` (توزیع ۷۱۴ route).

> تطبیق با handoff: گزارش `docs/handoff.md` عدد **۴۴۴ passed** را برای فرمان `pytest tests/gold_desk tests/unit/api/test_golddesk_http.py` ثبت کرده است. `tests/unit/api/test_golddesk_http.py` دقیقاً **۱۰ تست** دارد (collect-only) و ۴۳۴ + ۱۰ = ۴۴۴ → ادعای handoff با شواهد بازتولید و سازگار است.

---

## 2. تحلیل ۹ شکست

| تست | دسته | علت واقعی (شاهد) | مالک |
|---|---|---|---|
| `test_brsapi_client_retry.py::test_502_is_retried_then_succeeds` | محیط/ایزولاسیون | governor کلید BrsApi پیش از retry رد می‌کند: `BrsApi key in 302-cooldown (464s left … Suspend.php)` | ۱ |
| `…::test_502_exhausted_retries_fails` | همان | همان | ۱ |
| `…::test_504_is_retried` | همان | همان | ۱ |
| `…::test_502_exhausted_logs_full_attempt_count_and_skips_last_sleep` | همان | همان | ۱ |
| `…::test_401_is_not_retried` | همان | همان | ۱ |
| `test_check_secrets_and_gold_scope.py::test_working_tree_has_no_hardcoded_secrets` | امنیت | رمز هاردکدشده در `tests/e2e/test_gold_session_reload.py:37` و توکن تستی در `frontend/src/__tests__/GoldApiLayer.test.ts:14` | ۳ |
| `test_gold_silver_funds_fixes.py::test_missing_price_is_unknown_not_false_zero` | drift تست/کد | `SimpleNamespace` بدون `id`؛ کد `portfolio.py:482` از `h.id` استفاده می‌کند | ۱ |
| `…::test_priced_holding_computes_pnl` | همان | همان | ۱ |
| `backtesting/test_tick_cutoff.py::test_real_files_respect_cutoff` | داده محلی | `expected some days with post-close ticks` / `assert 0 > 0` | ۱ |

این ۹ مورد در `ISSUE_REGISTRY.md` به‌عنوان ISSUE-115…ISSUE-118 ثبت شده‌اند. ISSUE-119 (cooldown کلید) وضعیت عملیاتی است، نه شکست تست.

---

## 2.5. اجرای ایزوله integration/E2E (T13)

| مجموعه | passed | failed | skipped | زمان |
|---|---|---|---|---|
| `tests/integration` | ۴۴ | ۶ | ۰ | ۴۹.۸s |
| `tests/e2e` | ۳۵ | ۶ | ۱ | ۱۹۶.۵s |

محیط: PostgreSQL 18.4 محلی با دیتابیس **schema-only** `phase0_it_20261026` (۲۴۰ جدول، TimescaleDB) و Redis DB 13. Broker/worker واقعی Celery. هیچ داده‌ای از دیتابیس اپ (۵۱GB) تغییر نکرد و هیچ سرور زنده‌ای لازم نشد (ASGI in-process).

شکست‌های تأییدشده و ثبت‌شده: ISSUE-121 (Redis/precompute)، ISSUE-122/123 (auth)، ISSUE-124 (تست معیوب generator)، ISSUE-125 (drift نام استراتژی)، ISSUE-126 (تاریخ شمسی در بارگذاری تاریخچه). شکست‌های ناشی از خالی‌بودن DB (تاریخچه/مدل) به‌عنوان محدودیت محیط گزارش شدند، نه باگ.

جزئیات و دستور بازتولید: `evidence/isolated-itest-run.md`.

---

## 3. آنچه اجرا نشد و چرا

| حوزه | وضعیت | دلیل |
|---|---|---|
| `tests/unit/ml` | اجرا نشد (T3 ناتمام) | xgboost روی Windows با timeout thread کل اجرا را متوقف می‌کند (ISSUE-106) |
| `tests/integration` | **اجرا شد (T13)** — ۴۴ passed، ۶ failed، ۴۹.۸s | دیتابیس ایزوله `phase0_it_20261026` + Redis DB 13 (بخش ۲.۵) |
| `tests/e2e` | **اجرا شد (T13)** — ۳۵ passed، ۶ failed، ۱ skipped، ۱۹۶.۵s | همان محیط ایزوله، ASGI in-process؛ ۶ شکست به‌دلیل نبود توکن (ISSUE-123) |
| `tests/performance`, `tests/load` | اجرا نشد | نیاز به محیط پایدار؛ خارج از دامنه فاز ۰ |
| تست‌های `needs_db` | در T13 با `-m "not performance"` اجرا شدند | در محیط ایزوله اجرا شدند تا داده محلی تغییر نکند؛ منبع: `evidence/isolated-itest-run.md` |
| `npm run build` | **اجرا شد — موفق** (T12) | — |
| gitleaks | اجرا نشد | ابزار نصب نبود؛ گیت داخلی `check_secrets` به‌جای آن اجرا شد و قرمز است |
| تست contract JSON | وجود ندارد | ISSUE-113 |

---

## 3.5. CI موجود (خوانده‌شده از workflow، اجرا نشد)

`.github/workflows/ci.yml` روی push/PR به `main`/`develop`:

- `ruff check . --output-format=github` (خط ۹۹) → با ۹۲ خطای زیرمجموعه محلی، **احتمالاً قرمز**؛ وضعیت آخرین اجرا در دسترس نبود.
- `pytest tests/unit --timeout=60 -x -v` با PostgreSQL/Redis سرویس (خط ۲۶۵).
- `pytest tests/gold_desk --timeout=120 -v` با `GOLD_API_TOKEN_SALT=ci-only-salt-not-a-real-secret` (خط ۲۸۲).
- `pytest tests/integration/test_celery_chain_broker.py --timeout=300` (خط ۳۰۲).
- فرانت: `npx tsc --noEmit` (خط ۱۴۹) و `npx vitest run` (خط ۱۵۴).
- اسکن اسرار جد Ignore: `.github/workflows/secrets-scan.yml`.

نتیجه: CI از نظر پیکربندی، همان تست‌هایی را اجرا می‌کند که در این ممیزی اجرا شد، اما روی **لینوکس** و با **PostgreSQL/Redis سرویس**. تفاوت اصلی، همان ISSUE-106 (رفتار xgboost روی Windows) است.

---

## 4. ماتریس تست (مالک و معیار)

| حوزه | موارد | مالک | فرمان | معیار قبولی |
|---|---|---|---|---|
| دامنه/مالی | pricing، margin، VaR، tree | ۱ | `pytest tests/unit/domain tests/unit/options -q` | همه سبز + تست مرزی جدید برای ISSUE-101/102 |
| سرویس‌ها | feature_engine، orchestrator | ۱ | `pytest tests/unit/services -q` | سبز؛ بدون F821 |
| داده/سینک | brsapi، upsert، dedup | ۱ | `pytest tests/unit/test_brsapi* tests/unit/brsapi -q` | بدون تماس واقعی؛ deterministic |
| طلا | phase0/1/2 | ۱ | `pytest tests/gold_desk -q` | همه سبز؛ mount guard سبز |
| فرانت | کامپوننت/هوک/صفحه | ۲ | `npx vitest run` | ۵۸۳+ سبز |
| Type | کل فرانت | ۲ | `npx tsc --noEmit` | exit 0 |
| Lint فرانت | ESLint | ۲ | `npx eslint src` | ۰ error |
| Lint بک‌اند | ruff | ۳ (گیت) / ۱ (اصلاح) | `ruff check .` | ۰ error یا baseline مستند |
| API contract | schema/mount | ۳ | تست جدید + `pytest tests/gold_desk/test_phase0_mount.py` | بدون duplicate `(path,method)` |
| امنیت | auth/secrets/rate limit | ۳ | تست‌های موجود + اسکنر داخلی | secret gate سبز |
| یکپارچگی | DB/Redis واقعی | ۳ | `pytest tests/integration -q` | در CI لینوکس سبز |
| E2E | جریان طلا/لاگین | ۳ | `pytest tests/e2e -q` | حداقل جریان snapshot و session |

---

## 5. تست‌های الزامی پیش از اصلاح (Minimum safe set)

1. **ISSUE-101:** تست `covered_call` با سهام ۱٬۰۰۰ و ۱۰ short call → مارجین > 0؛ و ۱۰٬۰۰۰ سهم → صفر.
2. **ISSUE-102:** `implied_volatility(..., T=0)` → رفتار تعریف‌شده (نه ZeroDivisionError)؛ round-trip IV با خطای < 1e-4.
3. **ISSUE-105:** `ruff --select F821` روی دو فایل = 0.
4. **ISSUE-111:** تست Vitest که پاسخ `{success:false}` را به خطای قابل‌نمایش تبدیل کند.
5. **ISSUE-115:** اجرای `test_working_tree_has_no_hardcoded_secrets` سبز.
6. **ISSUE-117:** fixture با `id` یا کد مقاوم به null؛ دو تست P&L سبز.
7. **ISSUE-104/113:** تست schema برای قرارداد gold (پس از انتخاب مرجع).

---

## 6. قواعد اجرای تست برای سه دستیار

- روی Windows: همیشه `--timeout=90 --timeout-method=thread` و پرهیز از اجرای `tests/unit/ml` در همان پروسه.
- ML و performance فقط در CI لینوکس (`--timeout-method=signal`).
- هیچ تست واحد اجازه تماس شبکه واقعی ندارد؛ governor و client باید mock شوند.
- قبل از ادعای «سبز»، خروجی خلاصه pytest (تعداد passed/failed) در گزارش فاز ضمیمه شود.
- بعد از هر merge، T2/T4/T6/T7 دوباره اجرا شوند.
