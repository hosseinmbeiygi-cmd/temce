# TEMCE — گزارش مرحلهٔ ۳ و رگرسیون (Run1, 2026-10-29)

> نام فایل عمداً یکتاست. مسیر `MASTER_AUDIT_AND_REMEDIATION_PLAN_run1.md` در
> ۱۱:۰۷:۵۳ توسط یک نویسندهٔ هم‌زمان بازنویسی شد؛ این سند آن را دست نمی‌زند.

- **برنچ:** `integration/golddesk-fixes`
- **HEAD:** `90597e05b9f4328bcd82ee819a31ba5c55413c12`
- **بازهٔ اجرا:** ۰۹:۴۶ تا ۱۱:۳۰ (+۰۳:۳۰)
- **وضعیت:** `PARTIAL` — ۵ اصلاح با تست؛ ۲۴۱ تست سبز در درخت فعلی؛ ادامه `BLOCKED`

## ۱. اصلاحات

| شناسه | شدت | فایل | تغییر | تست |
|---|---|---|---|---|
| TEMCE-WRK-001 | P1 | `Dockerfile.worker:60` | اجرای `python -m apps.worker` به‌جای ماژول بدون entrypoint | `test_worker_image_runs_package_entrypoint` |
| TEMCE-WRK-002 | P1 | `apps/worker/app.py` | `_register_jobs()` و فراخوانی در `start()` | `test_worker_registers_job_definitions` |
| TEMCE-WRK-003 | P1 | `jobs/job_dispatcher.py:72` | استفاده از `get_brsapi_job_registry()` + `run_job()` به‌جای allow-list ثابت | `tests/unit/jobs/test_dispatcher_brsapi_jobs.py` |
| TEMCE-WRK-006 | P1 | `jobs/job_result.py`, `jobs/queue_consumer.py` | `skipped_result()` + شمارش skip بدون retry/dead-letter | `test_consumer_counts_skipped_job_without_retry` |
| TEMCE-SEC-001 | P1 | `tests/e2e/test_gold_session_reload.py:37` | حذف رمز واقعی QA → `GOLD_E2E_PASSWORD` + skip | `test_check_secrets_and_gold_scope.py` (۲۱ passed) |

جانبی: `TEMCE-SEC-002` (توکن ساختگی `fake-`) و `TEMCE-API-001` (فیلد مستند
`outcome` در تست قرارداد `sync-nav-all`).

**اقدام مالک:** رمز QA در git history ثبت شده و باید rotate شود.

## ۲. شواهد تست (درخت فعلی، ۱۱:۲۹)

```
python -m pytest tests/unit/jobs tests/unit/test_worker_app.py \
  tests/unit/test_check_secrets_and_gold_scope.py \
  tests/unit/test_brsapi_sync_nav_all_endpoint.py -q -p no:cacheprovider
→ 241 passed in 80.99s, exit 0
```

```
python -m ruff check <9 فایل تغییریافته>  → All checks passed, exit 0
npm --prefix frontend test -- --run src/__tests__/GoldApiLayer.test.ts
→ 9 passed in 17.35s, exit 0
```

پروب `python -m apps.worker`:

```
Worker registered 66 job classes and 32 BrsApi jobs
Worker consumer starting
Queue mode disabled or Redis unavailable — worker idle
```

`Redis … invalid username-password pair` → e2e صف `BLOCKED`.

## ۳. رگرسیون گسترده (موقت)

```
python -m pytest tests/unit -q -p no:cacheprovider
→ 108 failed, 6543 passed, 50 skipped, 47 deselected, 156 warnings in 1012.46s, exit 1
```

**هشدار اعتبار:** اجرا از ۱۰:۳۵ تا ۱۱:۲۲ طول کشید و با بازهٔ تغییرات
هم‌زمان (۱۰:۳۲–۱۱:۲۰) هم‌پوشانی دارد؛ baseline پایدار نیست.

- ۳ مورد از ۱۰۸ در همین اجرا رفع شد.
- ۱۰۵ مورد با `Cannot connect to PostgreSQL … localhost:5432/market` متوقف
  می‌شوند (نمونه: `test_endpoints`، `test_symbols_page_size`، `test_trades_e2e`،
  `test_backend_api_edge_cases`).
- سرویس `postgresql-x64-18` متوقف است ولی پورت ۵۴۳۲ پاسخ می‌دهد؛ DB/اعتبارنامهٔ
  `market` منطبق نیست. هیچ سرویس/DB تغییر نکرد.

## ۴. محیط ناپایدار — BLOCKED

فایل‌های تغییرکرده توسط نویسندهٔ دیگر در پنجرهٔ ممیزی:

`apps/api/dependencies.py` (10:36) · `apps/api/endpoints/portfolios.py` (10:38) ·
`brsapi/client.py` (10:34) · `brsapi/parsers/tsetmc.py` (10:32) ·
`domain/options/probability.py` (11:00) · `repositories/portfolio_repository.py` (10:37) ·
`services/gold/black76_engine.py` (11:00) · `services/market_service.py` (10:56) ·
`services/portfolio_service.py` (10:42) · `src/gold_desk/api.py` (10:36) ·
`frontend/src/app/admin/page.tsx` (11:19)

گزارش مادر نیز ۱۱:۰۷:۵۳ بازنویسی شد. طبق بخش ۳.۴ پرامپت اصلاحات متوقف شد.
فایل‌های این اجرا سالم‌اند (تأیید محتوا ۱۱:۲۷).

## ۵. وضعیت مراحل

| # | مرحله | وضعیت |
|---|---|---|
| A | تثبیت وضعیت (۳ snapshot) | ✅ |
| B | اولویت‌بندی P0/P1 | ✅ |
| ۱ | حفاظت Git | ✅ (بدون reset/clean/stash/commit) |
| ۲ | منبع داده و Parser | ⚠️ سطحی؛ `TseRealtimeProvider` مصرف‌کننده ندارد |
| ۳ | Scheduler/Worker/Queue | ✅ کد+تست؛ e2e صف ⛔ Redis |
| ۴ | DB/Repository | ⛔ PostgreSQL |
| ۵ | API/Cache | ⚠️ یک تست قرارداد |
| ۶ | Frontend/WS | ⚠️ لایهٔ envelope از قبل سیم‌کشی شده |
| ۷ | Docker/Deploy | ⚠️ `docker compose config --quiet` = 0 (هشدار `version`) |
| ۸ | Data quality/NAV | ⛔ |
| ۹ | خبر/صندوق/نماد | ⛔ |
| ۱۰ | مالی/اختیار/بک‌تست | ⚠️ نقطه‌ای |
| ۱۱ | امنیت | ⚠️ اسکن secret پاک؛ authz/IDOR بررسی نشد |
| ۱۲ | یکپارچه‌سازی | ⚠️ رگرسیون ناپایدار |

## ۶. کارهای باقی‌مانده

1. توقف نویسندهٔ هم‌زمان و تثبیت tree.
2. PostgreSQL معتبر و تکرار `tests/unit` برای baseline واقعی.
3. Redis معتبر برای e2e صف.
4. مراحل ۴، ۸، ۹، ۱۱ و بازبینی `backtesting/` و `orchestration/`.
5. rotate رمز QA.

---

## ۷. مرحلهٔ ۱۰ب — صحت موتور بک‌تست (دامنه‌ای که دیگران پوشش نمی‌دادند)

`backtesting/` در گزارش مادر به‌عنوان «بررسی‌نشده» علامت خورده بود و هیچ
تغییری از نویسندهٔ دیگر در آن دیده نشد. دامنه: موتور بار-محور، شبیه‌ساز اجرا،
حسابداری نقدی و FIFO.

### ۷.۱ یافته‌ها

| شناسه | شدت | فایل | وضعیت |
|---|---|---|---|
| BT-CASH-001 | P1 | `backtesting/engine/execution_simulator.py` | **رفع شد** — خرید اصل پول را دو بار کم می‌کرد (یک‌بار در `execute`، یک‌بار در `PortfolioAccounting.apply_fill`). |
| BT-CASH-002 | P1 | `backtesting/engine/backtest_engine.py` | **رفع شد** — فروش بیش از موجودی، بابت سهمی که خریده نشده بود نقدینگی واریز می‌کرد. |
| BT-TIME-001 | P2 | `backtesting/engine/execution_simulator.py` | **رفع شد** — `timestamp` فیل با ساعت واقعی سیستم زده می‌شد، نه زمان کندل اجرا. |
| BT-TEST-001 | P2 | `tests/unit/backtesting/test_tick_cutoff.py` | **رفع شد** — تست به `transactions_data/` وابسته بود و در نبود داده به‌جای skip، fail می‌داد. |

شاهد پیش از اصلاح (تاریخچهٔ جریان نقدی برای یک خرید ۱ سهمی):

```
[{'type': 'withdraw', 'amount': 100.0, ...balance 9900.0},
 {'type': 'withdraw', 'amount': 100.0, ...balance 9800.0}]   ← دو بار کسر
```

و برای فروش ۵ سهم وقتی فقط ۱ سهم موجود بود:

```
{'type': 'deposit', 'amount': 495.6, 'reason': 'sell SYM', 'balance': 10395.6}   ← ساخت نقدینگی
```

### ۷.۲ آنچه بررسی شد و سالم بود

- `BacktestSimulator` (موتور کانونی و مصرف‌شده در `services/backtest_service`) قاعدهٔ
  «single-charge» را رعایت می‌کند: Broker فقط هزینه را حساب می‌کند و
  `PortfolioManager` تنها یک‌بار نقدینگی را جابه‌جا می‌کند.
- `execution_timing` پیش‌فرض `next_open` است → سیگنال بار t در open بار t+1 پر
  می‌شود؛ look-ahead پیش‌فرض وجود ندارد.
- `consume_lots_fifo` و `lots_avg_price` درست‌اند (PnL تحقق‌یافته در برابر
  lotهای قدیمی، به‌ترتیب FIFO).
- `config/backtest_costs.yaml` جدول هزینهٔ ۱۴۰۵ را با نرخ‌های سهام/فرابورس/اوراق دارد.

### ۷.۳ شواهد تست

```
python -m pytest tests/unit/backtesting -q -p no:cacheprovider
→ 395 passed, 1 skipped in 12.43s, exit 0

python -m ruff check backtesting/engine/backtest_engine.py \
  backtesting/engine/execution_simulator.py \
  tests/unit/backtesting/test_engine_cash_accounting.py \
  tests/unit/backtesting/test_tick_cutoff.py
→ All checks passed, exit 0
```

فایل تست جدید: `tests/unit/backtesting/test_engine_cash_accounting.py` (۶ تست).

### ۷.۴ محدودیت صریح

موتور اصلاح‌شده (`BacktestEngine`) در `backtesting/runner.py` با برچسب
«legacy — diagnostics smoke only» ثبت شده است؛ بنابراین این اصلاح **صحت یک موتور
قدیمی** را برمی‌گرداند و ادعای بهبود PnL تولیدی نمی‌شود. موتور کانونی سالم بود.
نکتهٔ باز (اصلاح‌نشده): `CommissionModel` برای فروش همیشه جدول کانونیکال را
اعمال می‌کند و `broker_pct` تزریق‌شده را برای فروش نادیده می‌گیرد — عمدی و
مستند است، ولی برای کاربر API غافلگیرکننده است.
