# قراردادهای API — فاز صفر

**منبع حقیقت:** کد mount‌شده (`apps/api/router.py` + `apps/api/app.py`) در commit `90597e05`.
**شاهد شمارش:** اجرای واقعی `Router().setup()` و `app.routes` با `GOLD_API_TOKEN_SALT` → **714 route**؛ **103** مسیر یکتای gold.

---

## 1. قواعد عمومی

| موضوع | قرارداد فعلی | شاهد |
|---|---|---|
| Prefix | `/api/v1` (از `settings.api_prefix`) | `core/config/__init__.py:99` |
| Proxy فرانت | `/api/v1/*` → `API_URL` (production: `http://api:8000`) | `frontend/next.config.ts:20-40` |
| Envelope موفق | `{success: true, data: ..., message?, meta?, legal_disclaimer}` | `schemas/common/responses.py:12-24` |
| Envelope خطا | `{success: false, error: {...}, message?}` **یا** `{success:false, error:"string"}` در برخی endpointهای قدیمی | `ErrorResponse` + `grep` نمونه‌ها |
| خطای امن | در production متن داخلی حذف می‌شود | `apps/api/error_handlers.py:26-50` |
| احراز هویت | Bearer JWT + refresh کوکی httpOnly | `frontend/src/lib/api.ts:76-145` |
| سطح عمومی | `_public_read = [Depends(require_user_for_writes)]` (خواندن آزاد، نوشتن نیازمند توکن) | `apps/api/router.py:15,311+` |
| سطح شخصی | `_require_user` روی portfolio/alerts/gold core | `apps/api/router.py:276-301` |
| سطح ادمین | `_require_admin` روی jobs/tests/tables | `apps/api/router.py:582,645` |
| زمان | ISO-8601 با timezone؛ داده طلا `...Z`/`+03:30` بسته به منبع | تست‌های `test_phase1_terminal.py` |

---

## 2. فهرست سطوح (شمارش واقعی)

| Prefix | تعداد route | مالک دامنه | مصرف‌کننده اصلی |
|---|---|---|---|
| `/api/v1/gold` (همه سطوح) | 108 (103 مسیر یکتا) | دستیار ۱ / ۳ | `frontend/src/lib/goldApi.ts`، صفحات `/gold/*` |
| `/api/v1/funds` | 84 | دستیار ۱ | `app/funds` |
| `/api/v1/codal-professional` | 49 | دستیار ۱ | `app/codal` |
| `/api/v1/brsapi` | 44 | دستیار ۱ | هوک‌های `useMarketData` |
| `/api/v1/options` | 39 | دستیار ۱ | `app/options` |
| `/api/v1/backtests` | 33 | دستیار ۱ | `app/backtest` |
| `/api/v1/market` | 22 | دستیار ۱ | داشبورد |
| `/api/v1/auth` | 18 | دستیار ۳ | `lib/api.ts`, `AuthProvider` |
| `/api/v1/ml` | 12 | دستیار ۱ | `app/ml` |

---

## 3. قرارداد طلا (فاز ۰/۱/۲)

| Route | متد | احراز هویت | شکل پاسخ | تست پین‌کننده |
|---|---|---|---|---|
| `/gold/terminal` | GET | `_require_user` | `TerminalResponse` (ticker/physical/funds/certificates/capabilities) | `tests/gold_desk/test_phase1_terminal.py` |
| `/gold/what-if` | POST | `_require_user` | `WhatIfResponse` + `preview_only=true` | همان |
| `/gold/tehran-board` | GET | `_require_user` | ردیف‌های board با `NO_DATA` | `test_phase2_market_coverage.py` |
| `/gold/platforms`, `/gold/returns-matrix`, `/gold/fund-map` | GET | `_require_user` | `phase2_schemas` | همان |
| `/gold/snapshot` | GET | `_require_user` | `value/unit/asOf/source/quality` | `test_phase0_snapshot_*` |
| `/gold/health`, `/gold/assistant-rules`, `/gold/metrics` | GET | عمومی | health/spec | `anonymous_router` |
| `/gold/ws` | WS | توکن داخل سوکت | پیام‌های cadence/as_of | `test_ws_hub.py` |

### 3.1 واحدها (قرارداد صریح)

- همه مقادیر پولی **ریال** مگر فیلد به `_usd` ختم شود (`docs/phase1-gold-parity.md`, `phase1_schemas.py:1-6`).
- BrsApi فیزیکی/ارز **تومان** است و در `phase1._toman_to_rial` تبدیل می‌شود.
- تاریخچه FX در `brsapi_gold_currency_pro_daily_history` **ریال** است؛ تبدیل ×۱۰ ممنوع (تست `test_fx_history_is_already_rial_and_is_never_multiplied_by_ten`).
- `quality` ∈ `LIVE | DELAYED | SAMPLE | EDUCATIONAL | NO_DATA`.
- داده غایب = `null` + `data_gaps`، نه صفر.

### 3.2 ناسازگاری‌های تأییدشده

| ID | ناسازگاری | شاهد | تصمیم لازم |
|---|---|---|---|
| ISSUE-104 | `docs/phase1-ticker-api.md` و `docs/contracts/phase1-gold.json` قرارداد `/gold/ticker` را توصیف می‌کنند؛ چنین route‌ای mount نشده (۰ مسیر ticker از ۱۰۳) | شمارش route + فایل‌های untracked | حذف مستند یا پیاده‌سازی/جایگزینی با `/gold/terminal` |
| ISSUE-113 | `docs/contracts/*.json` هیچ تست یا اعتبارسنجی ندارند و `jsonschema` در وابستگی‌ها نیست | `grep -rn "docs/contracts" tests frontend/src scripts` = بدون نتیجه؛ بدون `jsonschema` در requirements | افزودن تست contract در فاز ۳ |
| ISSUE-114 | `docs/contracts/phase1-gold.json` ساختار **flat** (`price`, `changePct`) دارد، اما `/gold/terminal` ساختار **nested** (`data.ticker[]`) دارد | فایل JSON + `phase1_schemas.py` | یکی به‌عنوان مرجع انتخاب شود |
| ISSUE-101 | `MarginLeg.contract_size` پیش‌فرض 1000 برای leg سهام، معنای «تعداد سهم» را خراب می‌کند | `apps/api/endpoints/options.py:53` | تفکیک صریح share/contract |
| ISSUE-103 | واحد بازده VaR (درصد/اعشاری، روزانه/سالانه) تعریف نشده | `domain/options/var_calculator.py:35-50,150-160` | تعیین قرارداد |

### 3.3 الگوی خطای ناهمگون

- `ApiResponse(success=False, error={"message": ...})` در `apps/api/endpoints/options.py:242`.
- `ApiResponse(success=False, error="...")` (string) در بعضی handlerها دیده می‌شود؛ مصرف‌کننده TypeScript باید هر دو را تحمل کند.
- `frontend/src/lib/api.ts` خطای HTTP را به `Error("HTTP <status>: <body>")` تبدیل می‌کند؛ بدنه ممکن است JSON یا متن باشد.
- **تصمیم پیشنهادی:** `error` همیشه object با کلید `code` و `message`؛ تغییر نیازمند هماهنگی دستیار ۱ و ۲ و تست contract.

---

## 3.4. قرارداد پایگاه داده (وضعیت بررسی‌شده)

| مورد | واقعیت | شاهد |
|---|---|---|
| migrationها | **۸۶** فایل؛ head ثبت‌شده `0115` (از فایل scratch — نیازمند `alembic heads`) | `migrations/versions`, `_alembic_heads.txt` |
| جدول‌های طلا | `gold_snapshots`, `gold_fund_nav`, `gold_score_history`, `gold_holdings`, `gold_dca_plans`, `gold_trades`, `gold_portfolio_values`, `gold_alert_rules`, `gold_alert_events` | `src/gold_desk/models.py:35-209` |
| داده بازار | `brsapi_symbol_snapshots`, `brsapi_historical_daily`, `brsapi_candlesticks`, `brsapi_option_snapshots`, `brsapi_nav_records`, `brsapi_intraday_trades` | `brsapi/models/tsetmc.py` |
| IME | `brsapi_ime_futures`, `brsapi_ime_options`, `brsapi_ime_certificates`, `brsapi_ime_funds` | `brsapi/models/ime.py` |
| کدال | `brsapi_codal_announcements`, `brsapi_codal_attachments` | `brsapi/models/codal.py` |
| unique snapshot | `(symbol, fetched_at)` + upsert | `tsetmc.py:134-140`, `sync_service.py:458-473` |
| soft delete | `gold_holdings.deleted_at`؛ خواندن با `deleted_at IS NULL` | `models.py:154`, `portfolio.py:437-441` |
| pagination | پیش‌فرض ۵۰، سقف ۱۰۰۰ صفحه | `apps/api/pagination.py:5-29` |
| pool | ۲۰ + overflow ۳۰ | `core/config/__init__.py:86-87` |
| rate limit | per-endpoint + fallback `provider_rate_limit_per_minute` (پیش‌فرض ۳۰) | `apps/api/middleware.py:390-501` |
| timeout خارجی | ۳۰s برای BrsApi (قابل تنظیم) | `brsapi/config.py:395` |
| نسخه‌بندی | prefix ثابت `/api/v1`؛ نسخه دوم ندارد | `core/config/__init__.py:99` |
| تراکنش/هم‌زمانی | commit پس از batch؛ race سینک فقط برای snapshot تأیید شد | `sync_service.py:458-478` |
| retention | سیاست حذف/آرشیو تاریخی تأیید نشد | — |

**ریسک‌های DB که تأیید نشدند:** سازگاری همه migrationها با مدل‌ها، وجود index برای همه queryهای سنگین، رفتار rollback، و صحت `ON CONFLICT` برای جدول‌های غیر snapshot. این‌ها در فاز ۳ با DB واقعی بررسی می‌شوند.

---

## 4. قراردادهای داده‌ای مشترک

| موجودیت | محل تعریف | مصرف‌کننده |
|---|---|---|
| `GoldSnapshot`/`GoldPrice` | `frontend/src/types/gold.ts` | `goldApi.ts`, کامپوننت‌ها |
| `Terminal*` | `src/gold_desk/phase1_schemas.py` | `frontend/src/types/phase1.ts` |
| `MarketCoverage*` | `src/gold_desk/phase2_schemas.py` | `frontend/src/types/phase2.ts` |
| `ApiResponse<T>` | `schemas/common/responses.py` | همه endpointها |

**قاعده:** هر تغییر فیلد در یکی از این سه جفت، باید در همان commit جفت مقابل را هم به‌روز کند و در `API_CONTRACTS.md` ثبت شود.

---

## 5. تغییرات نیازمند توافق پیش از اجرا

1. حذف/جایگزینی قرارداد `/gold/ticker` (دستیار ۱ + ۳ + مالک محصول).
2. یکسان‌سازی `error` envelope (دستیار ۱ + ۲ + ۳).
3. تعریف رسمی `time_to_expiry` و `T=0` در قرارداد options (دستیار ۱ + ۳).
4. تعیین معنای `contract_size` برای leg سهام (دستیار ۱ + مالک محصول).
5. هر تغییر در مسیرهای `/gold/*` باید `tests/gold_desk/test_phase0_mount.py` را به‌روز کند.
