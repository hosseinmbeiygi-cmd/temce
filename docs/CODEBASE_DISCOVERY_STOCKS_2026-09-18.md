# گزارش کاوش خودکار کدبیس — ماژول سهام بورس تهران

> تاریخ کاوش: ۱۸ سپتامبر ۲۰۲۶ · branch: `main` · کامیت مبنا: `1bd0f9e24816e24ad14c85b077da1e1a6c74a405`
> دامنه: پاسخ به تمام جاهای `[پر کن]` **سند مشخصات فنی کامل — ماژول سهام بورس تهران** بر اساس کد واقعی.
> نسخه عمومی (۶ ماژول): `docs/CODEBASE_DISCOVERY_2026-09-16.md` (کامیت `f8add5a3`) — این سند مکمل و به‌روزرسانی متمرکز همان است.
> **قانون:** هیچ فرضی زده نشده. هرچه در کد پیدا نشد، صریحاً «یافت نشد» علامت خورده است. هیچ فیلدی حدس زده نشده.
> نشانه‌ها: `📸` واقعیت تأییدشده از کد · `❓` یافت نشد · `⚠️` تناقض/ریسک · `🔴` نیازمند تصمیم تیم

---

## ۱️⃣ معماری کلی

### ۱-۱. بک‌اند

| مورد | مقدار واقعی | منبع |
|---|---|---|
| زبان | Python `>=3.11` | `pyproject.toml:10` |
| فریم‌ورک | FastAPI `>=0.109` + `uvicorn[standard]>=0.25` | `requirements.txt:1-2` |
| اعتبارسنجی | `pydantic>=2.5` + `pydantic-settings>=2.1` | `requirements.txt:3-4` |
| ORM | SQLAlchemy `>=2.0` (async) + درایور `asyncpg>=0.29` و `aiosqlite>=0.20` | `requirements.txt:7,21-22` |
| Migration | Alembic `>=1.13` — **۵۵ فایل** در `migrations/versions/`؛ آخرین: `0054_news_module_foundation.py` | `ls migrations/versions/` |
| Scheduler | APScheduler `>=3.10` | `apps/scheduler/app.py` |
| Queue | Redis `LPUSH job:queue` + consumer سفارشی (`jobs/queue_publisher.py`, `apps/worker/`). **Celery در `requirements.txt:14` اعلام شده ولی هیچ Celery-app فعالی در کد یافت نشد** | — |
| Cache | `redis>=5.0` + `redis[hiredis]` | `requirements.txt:12,28` |
| Auth | `pyjwt>=2.8` | `requirements.txt:23` |
| Observability | `sentry-sdk[fastapi]>=2.0`، `opentelemetry-*>=1.22`، `prometheus-client>=0.19` | `requirements.txt:17-19,24` |
| JSON | `orjson>=3.9` | `requirements.txt:20` |
| Object storage | `minio>=7.2` | `requirements.txt:27` |
| کتابخانه‌های بازار ایران | `finpy-tse>=1.2`، `tsetmc>=0.58`، `tehran-stocks>=2.0`، `tse-utils>=1.1` | `requirements.txt:31-34` |
| Excel (ورود کدال) | `openpyxl>=3.1` | `requirements.txt:54` |
| ML (اختیاری) | scikit-learn/xgboost/lightgbm/catboost/torch/shap — کامنت‌شده، نصب با `pip install .[ml]` | `requirements.txt:37-43`, `pyproject.toml:41-49` |
| Dev | pytest/pytest-asyncio/pytest-cov/ruff/mypy/pre-commit | `pyproject.toml:50-57` |

مقادیر پیش‌فرض اندیکاتورها در کد (نه فرض سند): `RSI=14`، `MACD=12/26/9`، `Bollinger=20/2.0`، `EMA span=12`، `SMA=20`، `ATR=14`، `volume_ma=20` — `core/config/indicators.py:9-22` (prefix env: `INDICATOR_`).

### ۱-۲. فرانت‌اند

| مورد | مقدار واقعی | منبع |
|---|---|---|
| فریم‌ورک | **Next.js `16.2.9`** (App Router) + **React `19.2.4`** | `frontend/package.json:19-21` |
| زبان | TypeScript `^5` | `frontend/package.json:40` |
| استایل | **Tailwind CSS 4** (`tailwindcss@^4` + `@tailwindcss/postcss@^4`) — CSS Modules / Styled Components / Emotion: ❓ **یافت نشد** | `frontend/package.json:27,39` |
| State management | **TanStack React Query `^5.101.0`** (state سرور) + ۲ React Context (`lib/auth-context.tsx`, `lib/nav-config.tsx`) + ۱ store دست‌ساز با `useSyncExternalStore` (`stores/precomputeStore.ts`). Redux / Zustand / Vuex: ❓ **یافت نشد** | `frontend/src/stores/`, `frontend/src/lib/` |
| نمودار | **`recharts@^3.8.1`** (نمودار آماری) + **`lightweight-charts@^5.2.0`** (کندل/معاملاتی) | `frontend/package.json:17,22` |
| کتابخانه اندیکاتور تکنیکال (npm) | ❓ **یافت نشد** — سند فرض کرده `technicalindicators` موجود است؛ موجود نیست. محاسبه اندیکاتور فعلاً صرفاً سمت بک‌اند است | `frontend/package.json` |
| UI کمکی | `lucide-react@^1.28.0`، `framer-motion@^12.43.0`، `sonner@^2.0.7`، `xlsx@^0.18.5` | `frontend/package.json:15-18,23-24` |
| Sentry | `@sentry/nextjs@^10.74.0` (guard با `SENTRY_AUTH_TOKEN`) | `frontend/package.json:14`, `frontend/next.config.ts:45-58` |
| تست | **Vitest `^4.1.9`** + `@testing-library/react@^16.3.2` + `jsdom@^29.1.1` + `@vitejs/plugin-react@^6.0.3` (environment: `jsdom`) | `frontend/vitest.config.ts:7-11` |
| Lint | ESLint `^9` + `eslint-config-next@16.2.9` | `frontend/package.json:36-37` |
| مسیر alias | `@/*` → `./src/*` | `frontend/tsconfig.json:21-23` |
| Proxy API | rewrite سمت سرور Next.js: `/api/v1/*` → `API_URL` (Docker: `http://api:8000`)؛ `API_URL` هیچ‌گاه به مرورگر لو نمی‌رود (`NEXT_PUBLIC_*` نیست) | `frontend/next.config.ts:17-40` |
| Currency proxy | `/api/v1/currency/*` → `CURRENCY_API_URL` (Docker: `http://currency:8002`) — **قبل از catch-all** | `frontend/next.config.ts:32-34` |

⚠️ **بدهی فوری:** `/package.json` در ریشه پروژه فقط دو وابستگی دارد (`framer-motion`, `lucide-react`) و هیچ script ندارد — فرانت‌اند واقعی در `frontend/package.json` است. این فایل گمراه‌کننده است.
### ۱-۳. دیتابیس

- **PostgreSQL + افزونه TimescaleDB** — image: `timescale/timescaledb:latest-pg15` (`docker-compose.yml:5`)
- **Redis 7.0-alpine** (`docker-compose.yml:25`) + `dump.rdb` در ریشه
- `daily_history` و `candlesticks` واقعاً hypertable هستند: `create_hypertable('daily_history','trade_date', chunk_time_interval => 30 days)` و `create_hypertable('candlesticks','time', chunk_time_interval => 7 days)` — `migrations/versions/0001_initial_schema.py:128,164`
- اتصال: `DATABASE_URL`، pool `DB_POOL_MIN_SIZE=5` / `DB_POOL_MAX_SIZE=20` (`core/config/database.py`؛ `.env.example:19-31`)
- ️ **دوگانگی schema:** `core/database.py:128-131` — در production فقط Alembic؛ در non-production علاوه بر Alembic، `Base.metadata.create_all` هم اجرا می‌شود (منبع schemaهای خارج از کنترل Alembic).

### ۱-۴. ساختار پوشه‌ها (نمای درختی کلیدی)

```
temce/
├── apps/                       ← اپ‌های FastAPI
│   ├── api/                    ← API اصلی
│   │   ├── app.py              ← ساخت اپ (۱۱۱۶ خط) + cron orchestrator + /metrics
│   │   ├── router.py           ← ثبت همه routerها (۶۱۹ خط)
│   │   ├── auth.py  dependencies.py  middleware.py  pagination.py  metrics.py  error_handlers.py
│   │   └── endpoints/          ← ۷۲ فایل endpoint
│   ├── scheduler/              ← APScheduler (jobها)
│   ├── worker/                 ← consumer صف Redis
│   ├── funds/                  ← سرویس مستقل صندوق‌ها (adapters/metrics/scoring)
│   ├── currency_service/       ← سرویس مستقل ارز/طلا (port 8002)
│   ├── admin/  gateway/  decision_engine/  ml_worker/  ingestion_worker/  analytics_worker/
├── core/                       ← زیرساخت مشترک
│   ├── config/                 ← ۱۶ فایل تنظیمات گروهبندی‌شده (providers, indicators, ml, ...)
│   ├── security/ (permissions, ime_rbac)  ·  enums/ (rbac)  ·  rate_limit/  ·  logging/
│   ├── database.py  cache.py  indicators.py  events.py  paths.py  db_utils.py
├── services/                   ← ۱۳۵ سرویس بیزینسی (stock_*, fund_*, news_*, screener_*, ...)
├── models/                     ← ۴۱ فایل ORM (SQLAlchemy)
├── domain/                     ← منطق دامنه (instruments, market_data, ml, options, news)
├── providers/                  ← آداپتور منابع داده
│   ├── realtime/{tsetmc, websocket, marketwatch}  ·  historical/{tsetmc_historical, tse_archive, file_archive, sql_database}
│   ├── reference/{codal, tsetmc, instrument_master, tse_reference, alias_manager, manual}
│   ├── base/  capabilities/  health/  web_scraping/  funds/  codal/  macro/
├── brsapi/                     ← یکپارچه‌سازی BrsApi (client, config, rate_limiter, models/, services/, jobs/, pipelines/)
├── src/indicators/             ← پکیج محاسباتی خالص (general, stocks, scoring, specs, trend_momentum, advanced)
├── backtesting/                ← موتور بک‌تست (engine, composer, corporate_actions.py, metrics, optimization)
├── jobs/                       ← چارچوب job (base_job, registry, dispatcher, definitions/, queue_*)
├── migrations/versions/        ← ۵۵ migration
├── schemas/  repositories/  contracts/  reports/  ml/  scripts/  tests/
└── frontend/                   ← Next.js (src/app با ~۷۰ روت، src/components، src/lib، src/stores)
```

### ۱-۵. لایه‌های موازی که هنگام توسعه سهام باید روشن شوند

⚠️ در کد **سه لایه موازی** برای یک مفهوم وجود دارد و سند باید تکلیفشان را روشن کند:

| لایه | نمونه | نقش |
|---|---|---|
| `models/` (ORM) | `models/market_data.py` → `SymbolModel`, `DailyHistoryModel` | ORM رسمی |
| `brsapi/models/` (ORM دوم) | `brsapi/models/tsetmc.py` → `SymbolSnapshotModel`, `CandlestickModel` | ORM اختصاصی لایه BrsApi |
| `domain/` (entity) | `domain/market_data/quote.py`, `domain/instruments/instrument.py` | entity خالص (fixtureها از این‌ها ساخته میشوند) |

 `tests/fixtures/sample_quotes.py` از `domain.market_data.quote.Quote` استفاده می‌کند، در حالی که API از `models/quote.py` و `brsapi_symbol_snapshots` میخواند — دو مسیر موازی برای یک مفهوم.

---

## ۲️⃣ مدل داده فعلی

### ۲-۱. هویت نماد — `symbols`

📸 **اسکیمای واقعی** (`migrations/versions/0001_initial_schema.py:20-39` + `models/market_data.py:22-41`):

```sql
CREATE TABLE symbols (
    id            BIGINT PRIMARY KEY,
    symbol        VARCHAR(20) NOT NULL UNIQUE INDEX,   -- ⚠️ مدل ORM: String(50)
    name          VARCHAR(200),
    isin          VARCHAR(50) INDEX,
    market_type   VARCHAR(20),
    asset_class   VARCHAR(20) INDEX,
    industry      VARCHAR(200),                        -- ⚠️ مدل ORM: String(100)
    industry_id   INTEGER,
    total_shares  BIGINT,
    base_volume   BIGINT,
    eps           NUMERIC,
    pe            NUMERIC,
    tick_size     NUMERIC,
    lot_size      INTEGER DEFAULT 1,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);
```

➕ **ستون‌های افزودنی migration `0052`** روی همین جدول (همه nullable — `0052_tse_stocks_enterprise.py:25-36`):

| ستون | نوع | توضیح کد |
|---|---|---|
| `isin` | `VARCHAR(20)` | ⚠️ این ستون **از قبل در `0001` وجود داشت** (`VARCHAR(50)`) — این `ADD COLUMN` تکراری است (نیاز به بررسی: الگوی `IF NOT EXISTS` در migration) |
| `market_segment` | `VARCHAR(30)` | `bourse1\|bourse2\|ifb1\|ifb2\|base_yellow\|base_orange\|base_red` |
| `trading_state` | `VARCHAR(30)` | `allowed\|forbidden\|suspended\|auction` |
| `industry_name` | `VARCHAR(100)` | نام صنعت |
| `base_volume` | `BIGINT` | حجم پایه |
| `free_float_pct` | `DOUBLE PRECISION` | درصد شناور آزاد |
| `price_range_pct` | `DOUBLE PRECISION` | دامنه نوسان پویا `1\|2\|5` |

❓ **ستون `code` در جدول `symbols` یافت نشد** — `symbol` نام ستون است. ️ `apps/api/endpoints/stocks_v2.py:478` از `JOIN symbols s ON s.code = t.symbol` استفاده می‌کند که **با migrationها سازگار نیست** (جزئیات در بخش ۹).
### ۲-۲. OHLCV / تاریخچه قیمت — ۴ منبع موازی موجود

📸 **هیچ جدول `stock_ohlcv_daily` در کدبیس یافت نشد.** آنچه واقعاً وجود دارد:

| جدول | منبع | کلید | ستون‌ها | وضعیت |
|---|---|---|---|---|
| `daily_history` | `0001:108-128` + `models/market_data.py:47-64` | PK `(symbol_id, trade_date)` · FK → `symbols.id` · **hypertable روی `trade_date`** | `trade_count`, `trade_volume`, `trade_value`, `price_min/max/yesterday/first/last`, `price_last_change(_pct)`, `price_close`, `price_close_change(_pct)` | ️ **بدون `open`** — OHLC کامل ندارد |
| `candlesticks` | `0001:151-164` | `symbol_id` FK · **hypertable روی `time`** | OHLCV + `candle_type` | کد می‌خواند/می‌نویسد؟ ❓ نویسنده فعال یافت نشد |
| `brsapi_candlesticks` | `brsapi/models/tsetmc.py:481-518` | UQ `(symbol, date, time, candle_type)` · ایندکس `(symbol, gregorian_date, candle_type)` | `open/high/low/close/volume/count` + `candle_type` (`1=realtime, 2=unadjusted, 3=adjusted`) + `gregorian_date DATE` + `shamsi_date VARCHAR(10)` | ✅ **منبع اصلی نمودار کندل** — تنها جدولی که `candle_type` (تعدیل‌شده/نشده) را دارد |
| `brsapi_historical_daily` | `brsapi/models/tsetmc.py:407-442` | PK `(id, date)` (partition سالانه روی `date`) | `trade_count/volume/value`, `price_min/max/yesterday/first/last`, `price_close`, تغییرات | ✅ منبع سری روزانه (⚠️ `date` **`VARCHAR(20)` جلالی** مثل `1404/02/23`) |
| `quotes` | `models/quote.py:8` | `instrument_id` indexed | `price_open/high/low/close/last`, `price_change(_pct)` | برای quote لحظه‌ای |

 مهم: `candle_type` در `brsapi_candlesticks` (`2=unadjusted`, `3=adjusted`) **از قبل یعنی منبع سرویس BrsApi هم داده تعدیل‌شده می‌دهد** — این با فرض سند که «موتور تعدیل باید از صفر ساخته شود» در تناقض نسبی است (🔴 تصمیم تیم #۴).

⚠️ `brsapi_historical_daily.date` و `brsapi_candlesticks.date` هر دو **رشته جلالی** هستند. فیلتر بازه/مرتب‌سازی روی این رشته‌ها باید از `gregorian_date`/`shamsi_date` استفاده کند.

### ۲-۳. عمق بازار (Order Book) — ۴ منبع موازی موجود

📸 **سند جدول `order_book_snapshots` را پیشنهاد می‌کند؛ در کد ۴ مسیر موازی هست:**

| مسیر | منبع | شکل ذخیره | نکته |
|---|---|---|---|
| `brsapi_symbol_snapshots` (۵ سطح) | `brsapi/models/tsetmc.py:90-122` | **۴۵ ستون صریح**: `bid_count_1..5`, `bid_volume_1..5`, `bid_price_1..5`, `ask_count_1..5`, `ask_volume_1..5`, `ask_price_1..5` | ✅ منبع اصلی. UQ `(symbol, fetched_at)` |
| `stock_live_tape.buy_orders_json` / `.sell_orders_json` | `0052` + `models/stock_enterprise.py:61-62` | `TEXT` (JSON) | ✅ snapshot زنده، PK `symbol` (upsert) |
| `stock_order_book_l2` | `0052_tse_stocks_enterprise.py:78-90` + `models/stock_enterprise.py:70-87` | `bids_json`/`asks_json` **`TEXT NOT NULL`** + `obi_5`, `bid_queue_value`, `ask_queue_value` | ✅ UQ `(symbol, captured_at)` · ایندکس `ix_obl_symbol_captured` |
| `orderbook_snapshots` / `orderbooks` | `migrations/versions/0001_initial_schema.py` (legacy) | legacy | ⚠️ نویسنده فعال یافت نشد |
| `GET /orderbooks/{symbol}` | `apps/api/endpoints/orderbooks.py` + `services/orderbook_service.py:1-40` | — | `orderbook_service.py` صریح می‌گوید: «No mock/hardcoded orderbook ... comes directly from the AllSymbols snapshot» |

🔴 **تصمیم تیم #۳:** کدام به‌عنوان «منبع واحد عمق بازار» برای تب ۴؟ (`stock_order_book_l2` جدیدترین و ساخت‌یافته‌ترین است، ولی `brsapi_symbol_snapshots` تنها منبعی است که از سرویس واقعی پر می‌شود.)

### ۲-۴. اطلاعات بنیادی — `stock_fundamentals`  یافت نشد

 آنچه وجود دارد:

| منبع | ستون‌های مرتبط |
|---|---|
| `symbols` | `eps NUMERIC`, `pe NUMERIC`, `total_shares BIGINT`, `base_volume` |
| `symbols` (+`0052`) | `free_float_pct DOUBLE PRECISION`, `industry_name`, `market_segment` |
| `brsapi_symbol_snapshots` | `shares_count`, `base_volume`, `market_value`, `eps`, `pe_ratio`, `sector`, `sector_id` |
| `brsapi_symbol_details` (`tsetmc.py:144-222`) | جزئیات کامل نماد (فایل جدا) |
| `screener_profiles` (`models/screener.py:22-`) | `eps_current`, `eps_prev_year`, `registered_capital`, `industry_pe`, `free_float_shares`, `capital_increase_type`, `capital_increase_pct`, `net_operating_profit`, `accumulated_loss`, `gross_margin`, `nima_rate`, `free_market_rate` + ۱۰۰+ ستون دیگر |

 **ستون `report_date` / `sector VARCHAR(100)` مطابق سند:** `sector` در `brsapi_symbol_snapshots` **هست**؛ `report_date`  یافت نشد.
⚠️ **`free_float_percentage`** (نام سند) ❓ یافت نشد — نام واقعی کد: `free_float_pct` (`symbols`) و `free_float_shares` (`screener_profiles`).

### ۲-۵. رویدادهای شرکتی (کدال) — `stock_corporate_actions`  یافت نشد

📸 آنچه وجود دارد:

| منبع | وضعیت |
|---|---|
| `brsapi_codal_announcements` (`brsapi/models/codal.py:17-53`) | ✅ `symbol VARCHAR(200)`, `company_name`, `title`, `code`, `date_title`, `date_send`, `time_send`, `date_publish` (**`VARCHAR(20)`** + index), `link`, `link_pdf`, `link_excel`, `link_attachment`, `audit_status`, `content_hash` (UQ), `raw_json` |
| `codal_reports` (migration `0001`/`0002`, `models/codal.py`) | گزارش‌های کدال |
| `backtesting/corporate_actions.py` | ✅ **منطق تعدیل موجود است**: `CorporateActionAdjuster.adjust_prices()` و `.adjust_volume()` |
| `domain/market_data/corporate_action.py` | ✅ entity `CorporateAction` با `ActionType`, `ratio`, `adjustment_factor`, `date` |
| `stock_codal_filings` |  **یافت نشد** — در `docs/stock-enterprise-architecture.md:11` ادعا شده ولی در `models/` و `migrations/` وجود ندارد |
| `codal_analysis_reports` / `corporate_actions` |  در `docs/funds/NAV_ARCHITECTURE_V5.md:283` نام برده شده؛ در `migrations/versions/` با نام `corporate_actions` ❓ یافت نشد |

 **نتیجه کلیدی:** هیچ **جدول** رویداد شرکتی ساخت‌یافته و هیچ **ضریب تعدیل ذخیره‌شده** وجود ندارد. `CorporateActionAdjuster` منطق دارد ولی **ورودی‌اش از جایی تأمین نمی‌شود** — نه جدول، نه endpoint، نه اتصال به نمودار. این تأییدکننده «نکته کلیدی فنی» سند است.
### ۲-۶. لایه Enterprise سهام (migration `0052`) — اسکیمای کامل

📸 `stock_live_tape` (PK `symbol`, upsert) — `0052_tse_stocks_enterprise.py:43-74`, `models/stock_enterprise.py:33-67`

```
symbol PK VARCHAR(50) · isin VARCHAR(20) · last_price · close_price · yesterday_price
price_first · price_min · price_max · price_change_pct · close_change_pct
trade_volume BIGINT · trade_value · trade_count BIGINT
buy_real_volume · sell_real_volume · buy_real_count · sell_real_count
buy_real_value · sell_real_value · buy_legal_volume · sell_legal_volume
buy_legal_value · sell_legal_value
buy_orders_json TEXT · sell_orders_json TEXT          ← ۵ مظنه JSON
base_volume BIGINT · allowed_price_min · allowed_price_max
quoted_at TIMESTAMP NOT NULL · fetched_at TIMESTAMP DEFAULT now()
```

📸 `stock_order_book_l2` — `0052:78-91`, `models/stock_enterprise.py:70-87`
`id BIGSERIAL PK · symbol VARCHAR(50) NOT NULL · isin · bids_json TEXT NOT NULL · asks_json TEXT NOT NULL · obi_5 DOUBLE · bid_queue_value DOUBLE · ask_queue_value DOUBLE · captured_at TIMESTAMP NOT NULL` · UQ `(symbol, captured_at)` · Index `ix_obl_symbol_captured`

📸 `stock_indicators_snapshot` (PK `(symbol, trade_date)`) — `models/stock_enterprise.py:90-129` / `0052`
این جدول **از سند جلوتر است** — همه اندیکاتورهای خواسته‌شده و بیشتر را دارد:

```
symbol PK VARCHAR(50) · trade_date PK DATE
rsi_14 DOUBLE · rsi_divergence VARCHAR(10)   -- RD+|RD-|HD+|HD-|none
macd DOUBLE · macd_signal DOUBLE · macd_hist DOUBLE
ema_20 · ema_50 · ema_100 · ema_200 DOUBLE · ema_cross VARCHAR(20)
bb_upper · bb_middle · bb_lower DOUBLE · bb_squeeze BOOLEAN
keltner_upper · keltner_lower DOUBLE
ichimoku_tenkan · kijun · senkou_a · senkou_b DOUBLE · ichimoku_state VARCHAR(20)
atr_14 · mfi_14 · vwap_daily DOUBLE
pivot_standard_json TEXT · pivot_camarilla_json TEXT · pivot_fibonacci_json TEXT
trend_alignment_score DOUBLE · computed_at TIMESTAMP
```

 UQ این جدول `(symbol, trade_date)` است ولی **`symbol` و `trade_date` هر دو PK هم هستند** (تعریف دوگانه PK + UniqueConstraint در `0052:94-100`).

📸 `stock_quant_signals` — `models/stock_enterprise.py:132-165`, UQ `(symbol, signal_date)`, Index `ix_sig_symbol_date`
`action VARCHAR(20) NOT NULL · composite_score · tape_score · tech_score · fund_score · peer_score · macro_score · entry_low · entry_high · stop_loss · target_1/2/3 · risk_reward · kelly_fraction · position_size_pct · market_regime VARCHAR(20) · reasons_pro TEXT · reasons_con TEXT · engine_version VARCHAR(20) · payload_json TEXT`
→ **معادل واقعی جدول `stock_backtest_runs`/پیش‌بینی سند نیست**، ولی «تصمیم‌گیری» سند (حد ضرر/تارگت/R-R/Kelly) را ذخیره می‌کند.

📸 `stock_news_sentiment` — `models/stock_enterprise.py:168-186`, Index `ix_news_symbol_pub (symbol, published_at)`
`symbol VARCHAR(50) · isin · industry VARCHAR(100) · title VARCHAR(500) NOT NULL · body TEXT · source VARCHAR(100) · published_at DateTime · sentiment VARCHAR(10) · sentiment_score DOUBLE · impact_tag VARCHAR(30)`
→ **این جدول دقیقاً همان «فیلتر تگ نماد» تب ۷ سند را پشتیبانی می‌کند** و `published_at` آن برخلاف `news_articles` واقعاً `DateTime` است. ✅

📸 `stock_monthly_sales_production` — `models/stock_enterprise.py:189-211`, UQ `(symbol, jalali_year, jalali_month, product_name)`
`sales_amount · sales_volume · unit_price · sales_mom_pct · sales_yoy_pct · is_all_time_high BOOLEAN · codal_letter_id VARCHAR(50)`

📸 `market_macro_indicators` — `models/stock_enterprise.py:214-232`, UQ `indicator_date`
`usd_nima · usd_free · usd_gap_pct · interbank_rate · akhzar_ytm · total_retail_value · queue_buy_value · queue_sell_value · market_regime VARCHAR(20)`

### ۲-۷. جداول سند که در کدبیس **یافت نشد** (باید از صفر ساخته شوند)

| جدول سند | وضعیت | نزدیک‌ترین معادل موجود |
|---|---|---|
| `stock_ohlcv_daily` | ❓ **یافت نشد** | `brsapi_candlesticks` (OHLCV + `candle_type`) · `brsapi_historical_daily` · `daily_history` |
| `stock_fundamentals` | ❓ **یافت نشد** | `symbols` + `brsapi_symbol_snapshots` + `screener_profiles` |
| `stock_corporate_actions` | ❓ **یافت نشد** | `brsapi_codal_announcements` (غیرساخت‌یافته) + `backtesting/corporate_actions.py` (فقط منطق) |
| `order_book_snapshots` (سند) | ❓ **با این نام یافت نشد** | `stock_order_book_l2` + `stock_live_tape.*_orders_json` + `brsapi_symbol_snapshots` (۵ سطح) |
| `stock_ml_predictions` | ❓ **یافت نشد** | `models/ml.py` → `ml_predictions` (عمومی، نه per-stock) + `ml_symbol_results` |
| `stock_backtest_runs` | ❓ **یافت نشد** | `backtest_runs` (عمومی، `models/backtest.py`) |
| `ingestion_quarantine_stocks` | ❓ **یافت نشد** | `fund_ingestion_quarantine` (فقط صندوق‌ها، `models/fund_enterprise.py:211`) |
| `ingestion_run_logs` | ❓ **یافت نشد** | ✅ جدول `job_runs` (`models/job_run.py`: `job_type`, `status`, `progress_pct`, `started_at`, `completed_at`, `duration_seconds`, `error_message`, `result`) |

### ۲-۸. جدول پل «صندوق‌های دارنده سهم» (تب ۶ سند)

📸 **داده‌اش از قبل هست** — `models/fund_enterprise.py`:

| جدول | ستون کلیدی برای reverse-lookup |
|---|---|
| `fund_holdings` (`:105-130`) | `instrument_symbol VARCHAR(50)`, `instrument_name VARCHAR(200)`, `instrument_isin VARCHAR(20)`, `holding_type VARCHAR(30)`, `quantity`, `book_value`, `market_value`, **`weight_pct`**, `period_end_date` · UQ `(fund_id, period_end_date, holding_type, instrument_symbol)` |
| `fund_portfolio_diffs` (`:133-`) | `instrument_symbol`, `current_period_date` (ورود/خروج پول) |

 `GET /api/stocks/:symbol/fund-holders` سند: ❓ **یافت نشد**. تنها endpoint موجود: `GET /funds/v2/{fund_id}/holdings` (`apps/api/endpoints/funds_v2.py:206`) — یعنی رابطه **صندوق→دارایی** موجود است ولی **سهم→صندوق‌ها** نه.
✅ خبر خوب: با `instrument_symbol` + `instrument_isin` موجود، این endpoint فقط یک query جدید است، نه جدول جدید.
### ۲-۹. کاربران و واچ‌لیست

📸 `users` — `models/user.py:12-40`, migration `0022`-`0024`

```
id VARCHAR(50) PK · username VARCHAR(50) UNIQUE idx · email VARCHAR(255) UNIQUE idx
hashed_password VARCHAR(255) · full_name VARCHAR(100) · phone VARCHAR(20)
roles VARCHAR(255) NOT NULL DEFAULT 'viewer'     ← CSV string، نه جدول جدا
is_active BOOLEAN DEFAULT true · is_verified BOOLEAN DEFAULT false
last_login TIMESTAMP · refresh_token TEXT · metadata TEXT
totp_secret VARCHAR(64) · totp_enabled BOOLEAN · totp_confirmed_at TIMESTAMP
mfa_method VARCHAR(16)   -- totp | email | telegram | None
telegram_chat_id VARCHAR(64)                     ← MFA چندکاربره تلگرام
```

⚠️ **`watchlist` بدون migration:** جدول در runtime توسط `_ensure_table` در `services/watchlist_service.py` ساخته می‌شود — خارج از کنترل Alembic. `domain/watchlists/__init__.py` هم entity جدا دارد (`Watchlist`, `WatchlistItem`, `WatchlistMembership`, `WatchlistTag`). سند بخش ۰ می‌گوید «واچ‌لیست‌های کاربر حذف نمی‌شوند» — پس **قبل از هر توسعه باید به migration منتقل شود** (🔴 تصمیم تیم).

### ۲-۱۰. اسکرینر — فراتر از سند موجود

📸 `models/screener.py` (migration `0008_screener_tables.py` + `0049_screener_profile_filter_columns.py`):

| جدول | نقش | کلید |
|---|---|---|
| `screener_profiles` | یک ردیف per symbol — مدل **۱۱۰ ستونی CANSLIM** | PK `symbol VARCHAR(20)` |
| `screener_snapshots` | سری زمانی اسنپ‌شات‌های intraday (~هر ۲ دقیقه) | — |
| `screener_signals` | نمرات/تصمیم/مدیریت ریسک نهایی | `symbol`, `generated_at` |

ستون‌های کلیدی `screener_signals` (`models/screener.py:166-211`): `final_score`, `adjusted_score`, `raw_score`, `score_fundamental/valuation/institutional/technical/macro/gov_support/liquidity/farabourse/feedstock`, `rule_50_30`, `negative_filters_count`, `stop_loss_price`, `position_size`, `decision`, `entry_price`, `exit_price`, `exit_reason`, `pnl_pct`, `outcome_correct`, `outcome_set_at`.

فیلترهای سند در `screener_profiles` قابل تأمین‌اند: `industry`/`sub_industry` (گروه صنعت)، `industry_pe` (P/E صنعت)، `free_float_shares`، `current_price`، وضعیت نماد.

سرویسهای موجود: `services/screener_service.py` (۷۸۰+ خط), `screener110_service.py`, `smart_screener_v2.py`, `screener_ai_report_service.py`, `mass_scanner_service.py`.
---

## ۳️⃣ منابع داده خارجی (APIها)

📸 **منبع اصلی قیمت/معاملات = BrsApi** (`https://Api.BrsApi.ir`) — کلاینت: `brsapi/client.py`, تعریف endpointها: `brsapi/config.py:50+`

### ۳-۱. منبع قیمت سهام ✅ موجود

| مورد | واقعیت |
|---|---|
| سرویس / دامنه | **BrsApi** — `BRSAPI_BASE_URL` (پیش‌فرض در `.env.example:139`: `https://Api.BrsApi.ir`) |
| نوع | **REST** (`httpx`/`aiohttp`) — WebSocket برای TSETMC ❓ یافت نشد |
| Endpoint قیمت لحظه‌ای | `GET /Tsetmc/AllSymbols.php` → `brsapi/config.py:74-84` (`ALL_SYMBOLS`) · کامنت کد: `2 req / 100s → ~1.2 req/min` |
| Endpoint جزئیات نماد | `GET /Tsetmc/Symbol.php` (`SYMBOL_DETAIL`, `:85-94`) · `3 req / 10s → 18 req/min` |
| Endpoint ریزمعاملات | `GET /Tsetmc/Transaction.php` (`TRANSACTION`, `:125-135`) · `2 req / 10s → 12 req/min` |
| Endpoint شاخص | `GET /Tsetmc/Index.php` (`INDEX`, `:95-104`) |
| Endpoint سهامداران | `GET /Tsetmc/Shareholder.php` (`SHAREHOLDER`, `:171-182`) |
| **TSETMC مستقیم** | `PROVIDER_TSETMC_BASE_URL` (پیش‌فرض `https://tsetmc.com`) — `core/config/providers.py:19` · `TSETMC_BASE_URL` در `.env` · `services/tsetmc_client.py:132` → `/Shareholder/GetInstrumentShareHolderLast/{ins_code}` |
| **TSETMC WebSocket** | `PROVIDER_TSETMC_WS_URL` تعریف شده ولی پیش‌فرض **`None`** — `core/config/providers.py:20` |
| مسیر غیرمستند دیگر | `ml/datasets/loaders.py:37` مستقیماً `https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch` را صدا می‌زند (⚠️ از کلاینت مرکزی BrsApi/TSETMC رد نمی‌شود) |

### ۳-۲. منبع تاریخچه OHLCV ✅ موجود

| مورد | واقعیت |
|---|---|
| Endpoint | `GET /Tsetmc/History.php` — `HISTORY_PRICE` با `type=0` (`:136-146`) و `HISTORY_REALLEGAL` با `type=1` (`:147-158`) · کامنت: `4 req / 10s → 24 req/min` |
| Endpoint کندل | `GET /Tsetmc/Candlestick.php` (`CANDLESTICK`, `:159-170`) · `2 req / 10s → 12 req/min` |
| ستون تعدیل | `candle_type` با مقادیر `1=realtime, 2=unadjusted, 3=adjusted` — `brsapi/models/tsetmc.py:502-504` |
| سهمیه per-day | `BRSAPI_CANDLE_DAILY_MAX_SYMBOLS`, `BRSAPI_CANDLE_REQ_DELAY`, `BRSAPI_HISTORY_PRICE_DAILY_MAX_SYMBOLS`, `BRSAPI_HISTORY_PRICE_REQ_DELAY`, `BRSAPI_HISTORY_REAL_LEGAL_DAILY_MAX_SYMBOLS`, `BRSAPI_HISTORY_REAL_LEGAL_REQ_DELAY` |

### ۳-۳. منبع رویدادهای شرکتی / کدال ✅ موجود (اما غیرساخت‌یافته)

| مورد | واقعیت |
|---|---|
| سرویس ۱ | **BrsApi** → `GET /Codal/Announcement.php` (`CODAL_ANNOUNCEMENT`, `brsapi/config.py:183-198`) · `2 req / 10s → 12 req/min` |
| سرویس ۲ | **CODAL مستقیم** — `PROVIDER_CODAL_BASE_URL` (پیش‌فرض `https://codal.ir`, `core/config/providers.py:21`) · `providers/reference/codal/*` (client, parser, statement_parser, attachment_extractor, throttling) |
| نوع داده | اعلامیه + لینک PDF/Excel/attachment — **هیچ فیلد ساخت‌یافته `action_type` / `price_adjustment_factor` وجود ندارد** |
| محدودیت | `BRSAPI_RATE_LIMIT_CODAL` (نام متغیر؛ مقدار در `.env`) · کامنت `.env.example:157`: `CODAL: 20 req/min` |

### ۳-۴. منبع NAV صندوق‌ها ✅ (لازم برای تب ۶)

`GET /Tsetmc/Nav.php` (`NAV`, `brsapi/config.py:105-114`) · `1 req / 10s → 6 req/min` → جدول `brsapi_nav_records` · سرویس مستقل: `apps/funds/adapters/{tsetmc,codal,fipiran}.py`

### ۳-۵. منبع نرخ دلار/طلا/نقره ✅ (متغیرهای کلان تب ۹)

`GOLD_COIN`, `GOLD_CURRENCY`, `GOLD_COIN_HISTORY` (`brsapi/config.py:271+`) · جداول `brsapi_gold_coin_prices`, `brsapi_gold_currency_pro_prices`, `brsapi_currency_prices`, `brsapi_currency_24h` · سرویس مستقل `apps/currency_service/` (port 8002) · جدول کد: `market_macro_indicators` (`usd_nima`, `usd_free`)

### ۳-۶. منبع اخبار ✅ (تب ۷)

`providers/news/` + `services/news_ingestion.py` + `brsapi_codal_announcements`. جدول نمادمحور: `stock_news_sentiment` با ایندکس `(symbol, published_at)`.

### ۳-۷. منبع داده بازار کالا / آپشن ✅ (خارج از دامنه این سند)

`COMMODITY`, `IME_FUTURES`, `IME_OPTION`, `IME_CERTIFICATE`, `IME_FUND`, `IME_PHYSICAL`, `OPTION` (`/Tsetmc/Option.php`) — جداول `brsapi_commodity_prices`, `brsapi_ime_*`, `brsapi_option_snapshots`.
### ۳-۸. نام متغیرهای محیطی مرتبط (فقط نام — طبق پرامپت، مقادیر گزارش نمی‌شوند)

```
BRSAPI_API_KEY                         BRSAPI_BASE_URL
BRSAPI_REQUEST_TIMEOUT                 BRSAPI_MAX_RETRIES
BRSAPI_CACHE_ENABLED                   BRSAPI_CACHE_TTL_DEFAULT
BRSAPI_ONLY_DURING_MARKET_HOURS        BRSAPI_MARKET_TIMEZONE
BRSAPI_RATE_LIMIT_TSETMC               BRSAPI_RATE_LIMIT_CODAL
BRSAPI_RATE_LIMIT_IME                  BRSAPI_RATE_LIMIT_COMMODITY
BRSAPI_RATE_LIMIT_CRYPTO               BRSAPI_RAW_PAYLOAD_SINK_ENABLED
BRSAPI_GLOBAL_DAILY_LIMIT              BRSAPI_GLOBAL_5MIN_LIMIT
BRSAPI_CANDLE_DAILY_MAX_SYMBOLS        BRSAPI_CANDLE_REQ_DELAY
BRSAPI_SHAREHOLDER_DAILY_MAX_SYMBOLS   BRSAPI_SHAREHOLDER_REQ_DELAY
BRSAPI_HISTORY_PRICE_DAILY_MAX_SYMBOLS BRSAPI_HISTORY_PRICE_REQ_DELAY
BRSAPI_HISTORY_REAL_LEGAL_DAILY_MAX_SYMBOLS  BRSAPI_HISTORY_REAL_LEGAL_REQ_DELAY
BRSAPI_ENABLED
TSETMC_BASE_URL                        CODAL_BASE_URL
PROVIDER_TSETMC_BASE_URL               PROVIDER_TSETMC_WS_URL
PROVIDER_CODAL_BASE_URL                PROVIDER_DEFAULT_TIMEOUT
PROVIDER_MAX_RETRIES                   PROVIDER_RATE_LIMIT_PER_MINUTE
INDICATOR_* (rsi_period, macd_fast/slow/signal, bollinger_period/std,
             atr_period, volume_ma_period, ema_span, sma_span, cache_ttl_seconds)
```

📸 **سهمیه‌بندی واقعی BrsApi در کد** (`brsapi/rate_limiter.py:42-43`): `DEFAULT_GLOBAL_DAILY_LIMIT = 4_000` و `DEFAULT_GLOBAL_5MIN_LIMIT = 1_000` — کامنت کد: «keeps a safety margin below the real-world plan cap (~5,000/day, above which the key gets blocked)». `brsapi/readiness.py` حالت «DB-only mode» را وقتی کلید بلاک شود مدیریت می‌کند.

🔴 **تصمیم تیم:** سهمیه ۴۰۰۰ درخواست/روز برای backfill ۲-۳ ساله روی چند هزار نماد باید محاسبه شود (سند بخش ۱۳) — عدد واقعی سهمیه + تعداد نماد اولویت‌دار باید تعیین شود.

### ۳-۹. Real-time — واقعیت کد در برابر فرض سند

سند بخش ۳-۲ می‌گوید «اگر داده لحظه‌ای WebSocket در دسترس است، throttle ۲۵۰-۵۰۰ms».

📸 واقعیت:
- **WebSocket API موجود است:** `@router.websocket("/market")` در `apps/api/endpoints/websocket.py` → `/ws/market` · دومین WS: `/ws/precompute` (`apps/api/endpoints/precompute_ws.py`) — هر دو زیر prefix `/ws` ثبت شده‌اند (`apps/api/router.py:568-580`).
- زیرساخت WS: `providers/realtime/websocket/{base_ws_client, connection_manager, reconnect, subscriptions, parser, health}.py`
- ⚠️ ولی **جریان داده زنده از BrsApi نمی‌آید** — `SyncQuotesJob` هر **۲ دقیقه** است و جبهه WS بر همین داده سوار می‌شود. یعنی «لحظه‌ای» فعلی ≈ دانه‌بندی ۲ دقیقه‌ای.
- `core/config/providers.py:20` → `tsetmc_ws_url: str | None = None` (WS TSETMC پیکربندی نشده).
- فرانت: `frontend/src/hooks/useWebSocket.ts` موجود؛ `stores/precomputeStore.ts` برای وضعیت precompute.

🔴 **تصمیم تیم:** تب ۴ سند «به‌روزرسانی لحظه‌ای/نزدیک‌به‌لحظه‌ای در صورت وجود داده» می‌خواهد — با سهمیه ۴٬۰۰۰/روز، polling زیر ۲ دقیقه عملاً غیرممکن است. گزینه‌ها: (الف) پذیرش دانه‌بندی ۲ دقیقه، (ب) خرید پلن BrsApi بالاتر، (ج) منبع WS خارجی جدید.
---

## ۴️⃣ Endpointهای API فعلی بک‌اند (مرتبط با سهام)

📸 مجموع route decorator در `apps/api/endpoints/`: **۵۱۵**. همه زیر prefix `/api/v1` (فرانت: `API_PREFIX`/`NEXT_PUBLIC_API_PREFIX` = `/api/v1`).

### ۴-۱. ماژول سهام V2 — «۹ تب» موجود ✅ (نقشه متفاوت با سند)

| متد | مسیر کامل | فایل | نقش |
|---|---|---|---|
| GET | `/api/v1/stocks/v2/{symbol}/tape` | `endpoints/stocks_v2.py:45` | تابلو زنده + ماتریس تابلوخوانی (تب ۱) |
| GET | `/api/v1/stocks/v2/{symbol}/indicators` | `stocks_v2.py:62` | رادار تکنیکال (تب ۲) |
| GET | `/api/v1/stocks/v2/{symbol}/signal` | `stocks_v2.py:71` | کارت سیگنال کوانت (۵ لایه + ریسک) — **persist روزانه idempotent** |
| GET | `/api/v1/stocks/v2/{symbol}/peers` | `stocks_v2.py` | هم‌گروه/صنعت (تب ۳) |
| GET | `/api/v1/stocks/v2/{symbol}/dossier` | `stocks_v2.py` | شناسنامه (تب ۴) |
| GET | `/api/v1/stocks/v2/{symbol}/codal` | `stocks_v2.py` | کدال (تب ۵) |
| GET | `/api/v1/stocks/v2/{symbol}/news` | `stocks_v2.py` | اخبار/سنتیمنت (تب ۶) |
| GET | `/api/v1/stocks/v2/{symbol}/history` | `stocks_v2.py` | تاریخچه (تب ۷) |
| GET | `/api/v1/stocks/v2/{symbol}/history/export.csv` | `stocks_v2.py` | خروجی CSV تاریخچه |
| GET | `/api/v1/stocks/v2/{symbol}/volume-profile` | `stocks_v2.py` | پروفایل حجم (تب ۸) |
| GET | `/api/v1/stocks/v2/market-pulse` | `stocks_v2.py:447` | نبض کلان بازار (تب ۹) |
| GET | `/api/v1/stocks/v2/monitoring` | `stocks_v2.py:506` | سلامت ماژول سهام (P1) |

📸 سرویس پشت این endpointها: `services/stock_read_through.py` — class `StockReadThroughService` با متدهای `get_live_tape`, `get_tape_reading_matrix`, `get_indicators`, `get_full_signal`, `_load_daily_candles`, `_monthly_sales_momentum`. معماری L1/L2/DB با Mutex توزیع‌شده روی `stock:{isin}:lock` (`docs/stock-enterprise-architecture.md`).

### ۴-۲. نمادها و جستجو

| متد | مسیر | فایل |
|---|---|---|
| POST | `/api/v1/instruments` | `endpoints/symbols.py` |
| GET | `/api/v1/instruments` | `endpoints/symbols.py` |
| GET | `/api/v1/instruments/search` | `endpoints/symbols.py` |
| GET | `/api/v1/instruments/{symbol}` | `endpoints/symbols.py` |
| GET | `/api/v1/instruments/{symbol}/detail` | `endpoints/symbols.py` |
| GET | `/api/v1/symbols`، `/api/v1/symbols/search`، `/api/v1/symbols/{symbol}`، `/api/v1/symbols/dashboard` | `endpoints/symbol_search.py`، `endpoints/precompute.py` (`symbols_router`) |

### ۴-۳. قیمت / معاملات / عمق بازار

| متد | مسیر | فایل |
|---|---|---|
| GET | `/api/v1/quotes` (شامل `?symbol=`) | `endpoints/quotes.py` |
| GET | `/api/v1/quotes/test/{instrument_id}` | `endpoints/quotes.py` |
| GET | `/api/v1/trades/{symbol}` | `endpoints/trades.py` |
| GET | `/api/v1/trades/{symbol}/recent` | `endpoints/trades.py` |
| GET | `/api/v1/orderbooks/{symbol}` | `endpoints/orderbooks.py` ← **عمق بازار (تب ۴)** |
| GET | `/api/v1/orderbooks/{symbol}/history` | `endpoints/orderbooks.py` |
| GET | `/api/v1/market-watch` | `endpoints/market_watch.py` ← **دیده‌بان فعلی سند (حفظ شود)** |
| GET | `/api/v1/market-dashboard/*` | `endpoints/market_dashboard.py` |
| GET | `/api/v1/market/overview` · `/indices` · `/gainers` · `/losers` · `/active` · `/watch` · `/bourse` · `/energy-commodity` · `/heatmap` · `/enriched-heatmap` | `endpoints/market.py` |
| WS | `/api/v1/ws/market` | `endpoints/websocket.py` |
| WS | `/api/v1/ws/precompute` | `endpoints/precompute_ws.py` |

### ۴-۴. اندیکاتور

| متد | مسیر | فایل |
|---|---|---|
| POST | `/api/v1/indicators/{instrument_id}/{name}` | `endpoints/indicators.py` |
| GET | `/api/v1/indicators/{instrument_id}/{name}` | `endpoints/indicators.py` |
| GET | `/api/v1/stocks/v2/{symbol}/indicators` | `stocks_v2.py:62` ← مسیر واقعی مصرف‌شده توسط فرانت |

### ۴-۵. بنیادی

| متد | مسیر | فایل |
|---|---|---|
| GET | `/api/v1/fundamental/ratios/{symbol}` | `endpoints/fundamental.py` |
| GET | `/api/v1/fundamental/dcf/{symbol}` | `endpoints/fundamental.py` |
| GET | `/api/v1/fundamental/score/{symbol}` | `endpoints/fundamental.py` |
| GET | `/api/v1/fundamental/compare` | `endpoints/fundamental.py` |
| GET | `/api/v1/fundamental/industry/{industry}` | `endpoints/fundamental.py` |
| GET | `/api/v1/stocks/v2/{symbol}/dossier` | `stocks_v2.py` ← شناسنامه |
### ۴-۶. کدال / رویدادهای شرکتی

| متد | مسیر | فایل |
|---|---|---|
| GET | `/api/v1/codal/*` (شامل `major_holders` در `:414`) | `endpoints/codal.py` |
| GET | `/api/v1/codal-accounting/*` | `endpoints/codal_accounting.py` |
| GET | `/api/v1/codal-audit/*` | `endpoints/codal_audit.py` |
| GET | `/api/v1/codal-professional/*` | `endpoints/codal_professional.py` |
| GET | `/api/v1/brsapi/*` (شامل `sync-all-shareholders-status` در `:2113`) | `endpoints/brsapi.py` |
| GET | `/api/v1/stocks/v2/{symbol}/codal` | `stocks_v2.py` |

❓ `GET /api/v1/stocks/:symbol/corporate-actions` (سند): **یافت نشد**

### ۴-۷. اخبار (تب ۷ — بازاستفاده)

| متد | مسیر | فایل |
|---|---|---|
| GET | `/api/v1/news` | `endpoints/news.py` |
| GET | `/api/v1/news/search` | `endpoints/news.py` |
| GET | `/api/v1/news/symbol/{symbol}` | `endpoints/news.py` ← **دقیقاً فیلتر تگ نماد سند** ✅ |
| GET | `/api/v1/news/category/{category}` | `endpoints/news.py` |
| GET | `/api/v1/news/trending` | `endpoints/news.py` |
| POST | `/api/v1/news/refresh` | `endpoints/news.py` |
| GET | `/api/v1/news/refresh/status` | `endpoints/news.py` |
| GET | `/api/v1/stocks/v2/{symbol}/news` | `stocks_v2.py` |
| POST | `/api/v1/sentiment/*` | `endpoints/sentiment.py` |

❓ `GET /api/v1/stocks/:symbol/news` دقیقاً به شکل سند موجود نیست — شکل واقعی `/stocks/v2/{symbol}/news` است (🔴 تصمیم تیم).

### ۴-۸. اسکرینر

| متد | مسیر | فایل |
|---|---|---|
| GET/POST | `/api/v1/screener/*` | `endpoints/screener.py` |
| GET | `/api/v1/screener/v2/*` (شامل `/compare`) | `endpoints/screener_v2.py` |
| GET | `/api/v1/screener110/monitor` | `endpoints/screener110.py` |
| POST/GET | `/api/v1/scanner/scan`، `/scan/status`، `/scan/results`، `/scan/extract-relations` | `endpoints/scanner.py` |
| GET/POST | `/api/v1/saved-filters/*` | `endpoints/saved_filters.py` |

❓ `GET /api/v1/stocks/screener?peMax=&sector=` (شکل سند): **یافت نشد** — معادل واقعی `/screener*` است.

### ۴-۹. بک‌تست (تب ۸)

| متد | مسیر | فایل |
|---|---|---|
| POST | `/api/v1/backtests/run` | `endpoints/backtests.py` |
| GET | `/api/v1/backtests/runs` · `/runs/{run_id}` · `/runs/{run_id}/result` | `endpoints/backtests.py` |
| GET | `/api/v1/backtests/strategies` | `endpoints/backtests.py` |
| POST/GET | `/backtests/compare/save` · `/compare/history` · `/compare/history/{compare_id}` | `endpoints/backtests.py` |
| POST/GET | `/backtests/generate` · `/generate/status` · `/generate/results` · `/generate/history` · `/generate/export` · `/generate/save` · `/generate/saved` | `endpoints/backtests.py` |
| POST/GET | `/backtests/scan-indicators` · `/scan-indicators/status` · `/scan-indicators/results` | `endpoints/backtests.py` |
| GET | `/backtests/data/stats` · `/data/symbols` | `endpoints/backtests.py` |
| POST | `/backtests/walk-forward` · `/monte-carlo` · `/portfolio-run` | `endpoints/backtests.py` |
| POST/GET | `/backtests/cascade/run` · `/cascade/status` · `/cascade/results` · `/cascade/combinations` | `endpoints/backtests.py` |
| POST/GET | `/backtests/adaptive/init` · `/decide` · `/coevolve` · `/regime` | `endpoints/backtests.py` |

❓ `POST /api/v1/stocks/:symbol/backtest` (شکل سند): **یافت نشد** — معادل واقعی `/backtests/*` (عمومی، per-symbol با `symbols: [...]`) است.

### ۴-۱۰. ML (تب ۹)

| متد | مسیر | فایل |
|---|---|---|
| GET | `/api/v1/ml/models` | `endpoints/ml.py` |
| GET | `/api/v1/ml/runs` · `/runs/{run_id}` | `endpoints/ml.py` |
| POST | `/api/v1/ml/predict/{model_id}` | `endpoints/ml.py` |
| POST | `/api/v1/ml/train` | `endpoints/ml.py` |
| GET/POST | `/api/v1/forecast/*` · `/forecast-engine/*` | `endpoints/forecast.py`, `endpoints/forecast_engine.py` |

❓ `GET /api/v1/stocks/:symbol/ml-prediction` (شکل سند): **یافت نشد** (🔴 تصمیم تیم).

### ۴-۱۱. واچ‌لیست (حفظ شود)

| متد | مسیر | فایل |
|---|---|---|
| GET | `/api/v1/watchlist/` | `endpoints/watchlist.py` |
| POST | `/api/v1/watchlist/` | `endpoints/watchlist.py` |
| GET | `/api/v1/watchlist/search` | `endpoints/watchlist.py` |
| DELETE | `/api/v1/watchlist/{symbol}` | `endpoints/watchlist.py` |

### ۴-۱۲. سایر مرتبط

`/api/v1/alerts/*` (`endpoints/alerts.py`) · `/api/v1/market-insights/*` · `/api/v1/queue-analysis/*` · `/api/v1/signals/*` · `/api/v1/recommendations/*` · `/api/v1/anomalies/*` · `/api/v1/smart-money/*` · `/api/v1/paper-trading/*` · `/api/v1/portfolios/*` · `/api/v1/risk/*` · `/api/v1/alpha/*` · `/api/v1/analysis/*` · `/api/v1/multi-market-signals/*` · `/api/v1/assistant/*` · `/api/v1/stock-assistant/*` (`endpoints/stock_assistant.py`) · `/api/v1/jobs/*` · `/api/v1/precompute/*` · `/api/v1/tables/*`.

📸 **نمونه واقعی ثبت router** (`apps/api/router.py:272-312`): همه با `dependencies=_optional_auth` **بجز** `signals_router` که `_require_user` است (`:296-300`) — یعنی `user`, `analyst`, `admin`؛ `viewer` نه.
---

## ۵️⃣ نمونه داده واقعی

📸 **فایل‌های fixture موجود در `tests/fixtures/`:** `sample_backtests.py`, `sample_codal.py`, `sample_instruments.py`, `sample_macro.py`, `sample_ml_runs.py`, `sample_news.py`, `sample_orderbooks.py`, `sample_quotes.py`, `sample_recommendations.py`, `sample_signals.py`, `sample_trades.py`.

### ۵-۱. نمونه یک سهم (عیناً از کد)

`tests/fixtures/sample_instruments.py:7-27`:
```python
Instrument(
    id="inst_test_001", symbol="فولاد", name="فولاد مبارکه اصفهان",
    isin="IRO1FOLD0001",
    market_type=MarketType.BOURS, asset_class=AssetClass.EQUITY,
    status=InstrumentStatus.ACTIVE,
    sector_code="27",          # فلزات اساسی
    group_code="01",
    tick_size=1.0, lot_size=1000, par_value=1000,
    eps=1500, shares_count=10_000_000_000, base_volume=5_000_000,
    exchange_code="TSETMC", board_code="main",
    tags=["sharia", "blue_chip"],
)
```

### ۵-۲. نمونه یک رکورد قیمت

`tests/fixtures/sample_quotes.py:13-39` (نماد `فولاد`, `date="2024-01-15"`, `data_source="tsetmc"`):
`price_close=15000`, `price_open=14900`, `price_high=15100`, `price_low=14850`, `price_last=15050`, `price_change=100`, `price_change_pct=0.67`, `volume=5_000_000`, `value=75_000_000_000`, `trade_count=1200`, `price_yesterday=14900`, `price_first=14900`, `price_max=15100`, `price_min=14850`, `ask_price=15060`, `ask_volume=10000`, `bid_price=15040`, `bid_volume=15000`, `timeframe="1d"`.

### ۵-۳. نمونه عمق بازار (۳ سطح — نه ۵)

`tests/fixtures/sample_orderbooks.py:15-31`:
```
bids = [(15040, 15000, 5), (15030, 22000, 8), (15020, 18000, 3)]
asks = [(15060, 10000, 4), (15070, 25000, 7), (15080, 12000, 2)]
```
⚠️ fixture فقط ۳ سطح دارد؛ منبع واقعی ۵ سطح می‌دهد (سند ۵ سطح میخواهد).

### ۵-۴. نمونه داده کدال

`tests/fixtures/sample_codal.py:7-31` — `CodalDisclosure` واقعی:
```python
CodalDisclosure(
    id="cod_*", instrument_id="inst_test_001", symbol="فولاد",
    title="فولاد مبارکه اصفهان",
    disclosure_type="yearly_financial",
    fiscal_year="1402", period="12_months", category="audited",
    publish_date=None,
    url="https://codal.ir/Reports/12345.pdf",
    summary={
        "total_revenue": 250_000_000_000_000,
        "net_profit":    45_000_000_000_000,
        "eps":           1500,
        "book_value":    8000,
    },
    is_important=False, data_source="codal",
)
```
⚠️ `publish_date=None` در fixture — یعنی داده زمان‌دار رویداد در fixture خالی است.

### ۵-۵. نمونه واقعی یک اجرای بکتست (از README)

📸 `README.md:2931` — رکورد واقعی جدول بک‌تست:
```
bt_9acbb4afda27405ca19890af | Test Backtest | moving_average_cross | ["فولاد"]
| completed | 2024-01-01 | 2024-12-31 | 1000000000.0 | 999998821.3673556
| -0.0001 | 0.0035 | 10.0
```
→ یعنی: `strategy_type="moving_average_cross"`، `symbols` به‌صورت آرایه JSON، `status="completed"`، `initial_capital=1e9` ریال، `commission_pct=0.0035`، `slippage_bps=10.0`.

❓ نمونه داده seed برای `stock_corporate_actions`, `stock_ohlcv_daily`, `stock_fundamentals`, `stock_ml_predictions` — **یافت نشد** (چون خود جدول‌ها وجود ندارند).

---

## ۶️⃣ احراز هویت و نقش‌ها

📸 **مکانیزم: JWT** (`pyjwt>=2.8`) — `apps/api/auth.py`، `apps/api/dependencies.py`.

- توابع وابستگی موجود: `get_current_user`, `get_optional_user`, `require_roles(...)` (`apps/api/router.py:5-7`)
- ⚠️ **در `apps/api/auth.py` هر دو `verify_api_key` و `verify_token` فقط وقتی `settings.is_production` سخت‌گیری میکنند — در dev توکن اختیاری است.**

📸 **سیستم نقش/دسترسی (RBAC) از قبل وجود دارد:** `core/enums/rbac.py`

```python
class Role(StrEnum):
    ADMIN   = "admin"     # دسترسی کامل: مدیریت کاربران، ورود داده، تنظیمات
    ANALYST = "analyst"   # خواندن/نوشتن: سیگنال، بک‌تست، آموزش ML، پرتفوی
    USER    = "user"      # خواندن: داده بازار، اخبار، واچ‌لیست
    VIEWER  = "viewer"    # فقط خواندن پایه (پیش‌فرض)

ROLE_HIERARCHY = [Role.ADMIN, Role.ANALYST, Role.USER, Role.VIEWER]
```
توابع: `has_role(user_roles, required_role)` · `has_any_role(user_roles, roles)` — admin همیشه bypass (`:38-39`).

 **نقشها کجا ذخیره میشوند:** `users.roles VARCHAR(255) NOT NULL DEFAULT 'viewer'` — **رشته CSV**، نه جدول رابطه‌ای (`models/user.py:21`). پارس: `user_roles.split(",")` (`core/enums/rbac.py:35`).

📸 **نگاشت نقش در router** (`apps/api/router.py:16-18`):
```python
_require_analyst = [Depends(require_any_role("analyst", "admin"))]
_require_admin   = [Depends(require_any_role("admin"))]
_require_user    = [Depends(require_any_role("user", "analyst", "admin"))]
```

📸 **نقش‌های واقعی در ماژولهای موازی:**
- `apps/funds/auth.py:34` → `ROLE_ADMIN = "admin"` + جدول دسترسی مسیرها (`funds:profile`, `funds:compare`, `screener`, `backtest:report`, `alerts:read`, ...)
- `core/security/permissions.py` → کلاس `Role(name, permissions)` دیزاین‌شده بر پایه `Permission`
- `core/security/ime_rbac.py` → RBAC اختصاصی IME (`user_has_permission(roles, "model:write")`)

🔴 **تصمیم تیم — نقش `ML Engineer`:** سند بخش ۱۲ چهار نقش می‌خواهد: `Viewer / Analyst / Admin / ML Engineer`.
 نام دقیق نقش سوم در کد `user` است، نه `member` (سازگار).
 **`ml_engineer` در `core/enums/rbac.py` یافت نشد.** اگر لازم است، باید به `Role` + `ROLE_HIERARCHY` + `_ENDPOINTS` افزوده شود (افزودنی، بدون شکستن).

📸 **فرانت:** JWT در cookie + `frontend/src/middleware.ts` با `PUBLIC_ROUTES` و redirect به `/auth/login?redirect=...` · `frontend/src/lib/auth-context.tsx:279-282` → `hasRole(role)` با admin bypass.

❓ OAuth / Session-based auth: **یافت نشد** (فقط JWT + MFA/TOTP).
❓ نقش `ml_engineer`: **یافت نشد**.
❓ جدول `roles`/`permissions` جداگانه در DB: **یافت نشد** (`users.roles` CSV است).
---

## ۷️⃣ زیرساخت Job / Scheduler

📸 **موجود و فعال — سه لایه:**

1. **APScheduler** (`apps/scheduler/app.py`) — کلاس‌های `BaseJob` در `jobs/definitions/` با متد `execute(context) -> JobResult`، ثبت با `job_registry.register_module(job_definitions)` (`app.py:61`)
2. **registry اختصاصی BrsApi** (`brsapi/jobs/registry.py`) — `BrsApiSyncJob` + `BrsApiJobRegistry` با cronهای `_EVERY_1_MIN/_EVERY_2_MIN/_EVERY_5_MIN/_EVERY_1_HOUR`، فلگ `market_hours_only` و `enabled=False` برای endpointهای per-symbol (`app.py:63-70`)
3. **صف Redis اختیاری** — `jobs/queue_publisher.py` → `LPUSH job:queue`؛ consumer در `apps/worker/`؛ فعال با `JOB_QUEUE_ENABLED`. در حالت queue: «APScheduler فقط trigger می‌کند؛ workerها اجرا می‌کنند» (`app.py:67-70`)
4. **قفل توزیع‌شده:** `JobLocking` روی Redis با fallback in-memory (`app.py:224-234`)

### 📸 جدول واقعی jobهای مرتبط با ماژول سهام (استخراج از `apps/scheduler/app.py:73-219`)

| Job class | Trigger واقعی | خط | نقش |
|---|---|---|---|
| `SyncQuotesJob` | `interval minutes=2` | `:74` | **قیمت لحظه‌ای سهام** |
| `SyncSnapshotsToQuotesJob` | `interval minutes=2` | `:75` | snapshot → quotes |
| `SyncInstrumentsJob` | `interval hours=24` | `:73` | فهرست نمادها |
| `SyncCodalJob` | `interval hours=6` | `:76` | کدال |
| `CodalAttachmentDownloadJob` | `interval minutes=15` | `:77-83` | دانلود پیوست کدال |
| **`IndicatorPrecomputeJob`** | `cron hour="18,21" minute=30` | `:104-111` | **اندیکاتورهای شبانه سهام** (batch ۴۰۰ نماد/run؛ کامنت: «کل بازار در دو شبانه‌روز») |
| **`MonthlySalesFillJob`** | `cron hour=3 minute=30` | `:116-123` | فروش ماهانه کدال |
| **`BackfillHistoricalDataJob`** | `cron hour=2 minute=0` (`max_instances=1`) | `:130-137` | **Backfill تاریخی** |
| `EvaluateAlertsJob` | `interval minutes=2` | `:127` | هشدارها |
| `FundsSyncJob` | `cron hour=17 minute=30` | `:140-147` | صندوق‌ها (تب ۶) |
| `FundDiscoveryJob` | `cron hour="8,14,20" minute=15` | `:152-159` | کشف صندوق |
| `FundNavReconciliationJob` | `cron hour=18 minute=30` | `:163-170` | تطبیق NAV |
| `SyncNavAllJob` | `cron hour="9,18" minute=0` | `:88` | NAV |
| `NewsIngestionJob` | `interval minutes=10` | `:89` | اخبار (تب ۷) |
| `NewsSentimentJob` | `interval minutes=10` | `:93-99` | سنتیمنت اخبار |
| `FeatureStoreBuildJob` | `cron hour=23 minute=30` | `:186-193` | feature store (ورودی ML) |
| `ScreenerDailyScoresJob` | `cron hour=23 minute=45` | `:198-205` | نمرات اسکرینر |
| `PaperTradingJob` | `cron hour=21 minute=0` | `:173-180` | معاملات کاغذی |
| `BrsApiReadyCheckJob` | `interval hours=1` | `:213-219` | پایش مسدودی کلید BrsApi (کامنت: «1 request/hour ≈ 24/day») |

📸 **سایر jobهای موجود (ثبت‌شده در registry؛ trigger در این کاوش تأیید نشد ❓):**
`QuoteIngestionJob`, `HistoricalDataJob`, `RealtimeQuoteJob`, `SignalGenerationJob`, `SignalEvaluationJob`, `BacktestExecutionJob`, `BacktestOptimizationJob`, `AnalyticsComputationJob`, `IndicatorCalculationJob`, `Screener110RunCycleJob`, `RecommendationGenerationJob`, `RecommendationEvaluationJob`, `InstrumentSyncJob`, `AliasResolutionJob`, `CodalIngestionJob`, `MacroDataJob`, `GoldPriceJob`, `MetalsPriceJob`, `ModelTrainingJob`, `BatchInferenceJob`, `ModelEvaluationJob`, `MlArtifactLifecycleJob`, `DataRetentionJob`, `CacheWarmupJob`, `HealthCheckJob`.

 بر اساس `jobs/definitions/*.py`: **هیچ job جداگانه‌ای برای sync رویدادهای شرکتی از کدال** یافت نشد — در حالی که سند بخش ۱۹ می‌خواهد «Scheduler جداگانه برای sync رویدادهای شرکتی از کدال (روزانه یک‌بار کافی است)». نزدیک‌ترین معادل موجود: `SyncCodalJob` (هر ۶ ساعت) و `MonthlySalesFillJob` (۳:۳۰).

 **Audit log مشترک:** جدول `job_runs` (`models/job_run.py`) با `job_type`, `status`, `progress_pct`, `started_at`, `completed_at`, `duration_seconds`, `error_message`, `result`.
سند بخش ۱۹ می‌گوید «جدول Audit مشابه `ingestion_run_logs` بازاستفاده شود» → **`ingestion_run_logs` یافت نشد**؛ معادل واقعی `job_runs` است. تصمیم پیشنهادی: استفاده از `job_runs` با `job_type='stock_ohlcv_sync'` (بدون جدول جدید) — 🔴 تصمیم تیم.
---

## ۸️⃣ ابزار Logging / Monitoring / Testing / CI

| لایه | وضعیت واقعی | منبع |
|---|---|---|
| **Logging** | پکیج سفارشی `core/logging/` (setup, formatters, correlation-id, request_logging, filters, audit_logging) — `get_logger(__name__)` در کل کد. `structlog` در `pyproject.toml:36` اعلام شده ولی **در کد استفاده نمی‌شود** ❓ · loguru ❓ یافت نشد | `core/logging/` |
| **Metrics** | `prometheus-client>=0.19` — endpoint `/metrics` از `apps/api/metrics.py` → `get_prometheus_exporter().export_text()` (`apps/api/app.py:974-981`) · مسیر از `settings.metrics_path` | `apps/api/app.py:974-981` |
| **Tracing** | OpenTelemetry SDK + `opentelemetry-exporter-otlp>=1.22` (متغیر `OTLP_ENDPOINT`) | `requirements.txt:17-18,24` |
| **Error tracking** | Sentry دوطرفه: بک‌اند `sentry-sdk[fastapi]>=2.0` (`core/observability_sentry.py`، متغیر `SENTRY_DSN`) + فرانت `@sentry/nextjs` (`frontend/instrumentation-client.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`) | — |
| **Health** | `/api/v1/health` (`endpoints/health.py`) + جداول `provider_health` / `provider_health_history` (`models/provider_health.py`) + `GET /api/v1/stocks/v2/monitoring` + صفحه فرانت `/data-health` | — |
| **مانیتورینگ منبع داده** | `providers/health/{health_checker, provider_health_manager, provider_health_score, provider_incidents, provider_sla, provider_status_history}.py` — SLA/incident/score برای هر provider | `providers/health/` |
| **تست بک‌اند** | **pytest + pytest-asyncio + pytest-cov** — ۳۵۸ فایل تست · ساختار: `unit/`, `integration/`, `e2e/`, `performance/`, `comprehensive/`, `legacy/`, `load/`, `fixtures/` · تنظیمات: `pyproject.toml:125-136` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`, markers: `performance`, `e2e`, `integration`, `slow`, `needs_db`) | `pyproject.toml` |
| **تست فرانت** | **Vitest + @testing-library/react + jsdom** — ۲۳ فایل تست در `frontend/src/__tests__/` | `frontend/vitest.config.ts` |
| **CI/CD** | ۶ workflow: `ci.yml`, `ci-pr.yml`, `decision-engine.yml`, `fund-service.yml`, `release.yml`, `secrets-scan.yml` · `ci.yml`: push/PR روی `main`/`develop`؛ jobهای lint+typecheck، تست بک‌اند با سرویس‌های PostgreSQL+Redis، build/push Docker روی `main`، scan آسیب‌پذیری · `NODE_VERSION=20`, `PYTHON_VERSION=3.11`, registry `ghcr.io` | `.github/workflows/ci.yml:1-60` |
| **Lint/Type (بک‌اند)** | `ruff` با select `["E","F","I","N","W","UP","B","SIM","ARG","C4"]` · `mypy` با excludeهای گسترده برای legacy · `line-length=120` | `pyproject.toml:59-123` |
| **Dependabot** | `.github/dependabot.yml` | — |

### 📸 تست‌های موجود مرتبط با سهام (پایه‌ای که سند می‌تواند روی آن بسازد)

| فایل | دامنه |
|---|---|
| `tests/unit/services/test_stock_tape_engine.py` | فرمول‌های بومی تابلو تهران — بدون دیتابیس |
| `tests/unit/services/test_stock_technical_signal_engines.py` | موتور تکنیکال + سیگنال (Ichimoku insufficient-data، Kelly cap، R/R filter، no-look-ahead) |
| `tests/unit/services/test_stock_news_sentiment_engine.py` | سنتیمنت، کلیدواژه‌های رگولاتوری، نرمال‌سازی |
| `tests/e2e/test_ml_registry_api.py:278+` | `GET /ml/predictions` |
| `tests/unit/api/test_news_category.py` | دسته‌بندی اخبار (تب ۷) |
| `tests/unit/services/test_symbol_catalog.py` | کاتالوگ نماد |

📸 **تست موتور تعدیل قیمت:** ❓ **یافت نشد** — نه برای `backtesting/corporate_actions.py` و نه برای `domain/market_data/corporate_action.py`. سند بخش ۱۷ «Unit: موتور تعدیل قیمت (۳+ سناریو)» می‌خواهد و **این تست کاملاً از صفر باید نوشته شود**.

📸 **تست موتور بک‌تست:** ✅ موجود و فراوان — `tests/`, `backtesting/`, `docs/BACKTESTING_README.md` (۶۵KB) + لیست «اصلاحات انجام‌شده» در `docs/BACKTESTING_README.md:1323-1327` (یکسان‌سازی مسیر شبیه‌سازی، Look-Ahead Bias، قوانین بازار تاریخی، اجرای Deterministic).

📸 **تست E2E فرانت برای ۹ تب سهم:** ❓ یافت نشد — `frontend/src/__tests__/` شامل تست‌های `fund-analysis`, `compareReport`, `BacktestComponents` است، نه سهم.

### 📸 وضعیت اندیکاتور — دو پیاده‌سازی موازی (⚠️ نکته مهم برای سند بخش ۴)

سند بخش ۴ می‌گوید «اگر کتابخانه استاندارد در اکوسیستم وجود دارد، از بازنویسی پرهیز شود؛ فقط wrapper تست‌شده». 📸 واقعیت:

| مسیر | محتوا |
|---|---|
| `services/stock_technical_engine.py` | موتور اصلی: RSI(14) Wilder + واگرایی `RD+/RD-/HD+/HD-`, MACD(12,26,9), EMA 20/50/100/200 + Golden/Death, Ichimoku کامل, BB(20,2)+Keltner→Squeeze, ATR(14), MFI(14), VWAP, Pivots (Classic/Camarilla/Fibonacci), MTF alignment (`docs/stock-enterprise-architecture.md:59-64`) |
| `src/indicators/` (پکیج خالص) | `general.py` (`calculate_atr`, `calculate_bollinger_bandwidth`, `calculate_zscore`, `calculate_relative_volume`, ...), `stocks.py` (۱۹ تابع تابلوخوانی تهران: `calculate_buyer_power_ratio`, `calculate_ownership_hhi`, `calculate_supply_dryness`, ...), `scoring.py` (`calculate_stock_market_score`), `specs.py` (`ALL_SPECS`, `IndicatorSpec`), `trend_momentum.py`, `advanced.py` |
| `core/indicators.py` | توابع اندیکاتور عمومی |
| `backtesting/composer/indicator_registry.py` | رجیستری اندیکاتور موتور بک‌تست |
| `services/stock_assistant_service.py:26` | `class TechnicalIndicators` (پیاده‌سازی سوم SMA/... ) |
| `brsapi/pipelines/indicators.py` | pipeline اندیکاتور لایه BrsApi |
| `build_symbol_reports.py:356` | EMA محلی (`series.ewm(span=n)`) |

⚠️ **حداقل ۶ پیاده‌سازی موازی اندیکاتور** در کدبیس وجود دارد. سند بخش ۴ باید مشخص کند کدام «موتور واحد» است؛ در غیر این صورت خطر واگرایی نتایج بین تب نمودار، بک‌تست و اسکرینر وجود دارد. (🔴 تصمیم تیم)

 `SMA` به‌عنوان نام تابع مستقل: ❓ یافت نشد — SMA از طریق `core/config/indicators.py:sma_span=20` و پیاده‌سازی‌های محلی/`pandas.rolling` تأمین می‌شود.
---

## ۹️⃣ بدهی فنی و نکات هشدار

### ۹-۱. باگ‌های واقعی در کد فعلی ماژول سهام (تأییدشده در این کاوش)

| # | مورد | شواهد | اثر |
|---|---|---|---|
| **B1** | **`JOIN symbols s ON s.code = t.symbol`** — ستون `code` در جدول `symbols` وجود ندارد | `apps/api/endpoints/stocks_v2.py:478` · اسکیمای `symbols` در `migrations/versions/0001_initial_schema.py:20-39` فقط `symbol` دارد | 🔴 **`GET /api/v1/stocks/v2/market-pulse` احتمالاً دائماً خطا می‌دهد** — تب ۹ فرانت شکسته است. باید روی DB زنده تأیید شود (ممکن است ستون خارج از Alembic اضافه شده باشد) |
| **B2** | **`SELECT name, close_value FROM indices`** — ستون `close_value` در هیچ migration یافت نشد | `apps/api/endpoints/stocks_v2.py:466` · فقط `value` تعریف شده (`0001:203`) و `close_value` در هیچ‌کدام از ۵۵ migration نیست | 🔴 همان endpoint (`market-pulse`) — خطای دوم |
| **B3** | تناقض عرض ستون بین migration و ORM | `symbols.symbol` → migration `VARCHAR(20)` (`0001:23`) ولی ORM `String(50)` (`models/market_data.py:26`) · `symbols.industry` → migration `VARCHAR(200)` (`0001:28`) ولی ORM `String(100)` (`models/market_data.py:31`) | ⚠️ بی‌خطر تا وقتی نام‌ها بلندتر نشوند؛ ولی `create_all` در non-prod می‌تواند schema متفاوت بسازد |
| **B4** | `ADD COLUMN isin` تکراری در migration `0052` | `isin` در `0001:25` (`VARCHAR(50)`) وجود داشت؛ `0052:28` دوباره `VARCHAR(20)` اضافه می‌کند | ⚠️ در محیط تازه ممکن است خطا یا کاهش عرض ستون رخ دهد — نیاز به بررسی دستی |
| **B5** | تعریف دوگانه PK و UniqueConstraint در یک جدول | `stock_indicators_snapshot`: `symbol`+`trade_date` هم `primary_key=True` (`models/stock_enterprise.py:99-100`) و هم `UniqueConstraint("symbol","trade_date")` (`:95`) | ⚠️ index تکراری/اضافی در DB |

### ۹-۲. بدهی ساختاری (تأییدشده در این کاوش)

| # | مورد | شواهد |
|---|---|---|
| **D1** | **`stock_codal_filings` ادعاشده در مستندات وجود ندارد** — `docs/stock-enterprise-architecture.md:11` آن را بخشی از جریان Overnight Engine معرفی می‌کند | grep روی `models/` و `migrations/` → صفر نتیجه |
| **D2** | **`watchlist` بدون migration** — ساخت در runtime با `_ensure_table` | `services/watchlist_service.py` · سند بخش ۰ می‌گوید واچ‌لیست‌ها نباید حذف شوند → انتقال به Alembic پیش‌نیاز است |
| **D3** | **دوگانگی schema:** `create_all` در non-production کنار Alembic | `core/database.py:128-131` |
| **D4** | **۶ پیاده‌سازی موازی اندیکاتور** | `services/stock_technical_engine.py`, `src/indicators/`, `core/indicators.py`, `backtesting/composer/indicator_registry.py`, `services/stock_assistant_service.py`, `brsapi/pipelines/indicators.py` |
| **D5** | **۴ لایه موازی OHLCV** با کلیدها و نام‌گذاری متفاوت (`symbol_id` عددی vs `symbol` رشته vs `isin`) | `daily_history`, `candlesticks`, `brsapi_candlesticks`, `brsapi_historical_daily` |
| **D6** | **۴ مسیر موازی عمق بازار** | `brsapi_symbol_snapshots`, `stock_live_tape` JSON, `stock_order_book_l2`, legacy `orderbooks`/`orderbook_snapshots` |
| **D7** | **تاریخ جلالی به‌صورت رشته در کلید/فیلتر** | `brsapi_historical_daily.date VARCHAR(20)` (`tsetmc.py:418`), `brsapi_candlesticks.date VARCHAR(20)` (`:494`), `brsapi_codal_announcements.date_publish VARCHAR(20)` (`codal.py:37`) — هر فیلتر بازه زمانی = string-compare |
| **D8** | **چندگانگی هویت نماد:** `symbols.symbol`, `brsapi_symbol_snapshots.{symbol,ins_id,isin}`, `brsapi_symbol_details`, `symbols.isin` (دو عرض متفاوت) | بدون resolver مرکزی، تطبیق نماد↔ISIN در چند جا تکرار می‌شود (`fund_holdings` **هم** `instrument_symbol` **هم** `instrument_isin` ذخیره می‌کند) |
| **D9** | **جدول‌های legacy بدون نویسنده فعال** | `orderbooks`, `orderbook_snapshots`, `candlesticks` (migration `0001`) — سند بخش ۰ می‌گوید حفظ شوند ولی مصرف‌کننده‌شان روشن نیست |
| **D10** | **Celery در `requirements.txt:14`** (`celery[redis]>=5.3,<6`) ولی هیچ Celery app/worker فعالی یافت نشد | dead dependency |
| **D11** | **`structlog>=24.1` در `pyproject.toml:36`** ولی `core/logging/` سفارشی است و structlog در کد استفاده نمی‌شود | ❓ dead dependency |
| **D12** | **`package.json` ریشه پروژه** فقط `framer-motion` + `lucide-react`، بدون script | گمراه‌کننده هنگام جستجوی فریم‌ورک فرانت |
| **D13** | **`_FRONTEND_BACKEND_COPY/`** نسخه کهنه فایل‌ها را در ریپو نگه می‌دارد | منبع سردرگمی در grep |
| **D14** | **`ml/datasets/loaders.py:37`** مستقیم به `cdn.tsetmc.com` می‌زند — خارج از کلاینت مرکزی و rate-limiter BrsApi | نقض سیاست سهمیه؛ می‌تواند کلید را بلاک کند |
| **D15** | **۴۱۳ بلاک `except Exception` در `services/`** (طبق کاوش ۲۰۲۶-۰۹-۱۶) | خرابی منبع داده می‌تواند بی‌صدا گم شود — در pipeline سهام خطرناک است |
| **D16** | **عدم تأیید سیاست نگهداشت برای snapshotها** — `brsapi_symbol_snapshots` UQ `(symbol, fetched_at)` دارد و هر چرخه ۲ دقیقه‌ای ردیف جدید می‌سازد | `jobs/definitions/housekeeping_jobs.py:DataRetentionJob` وجود دارد ولی پوشش این جداول ❓ تأیید نشد |
| **D17** | **`stock_quant_signals` عملاً جدول تصمیم است، نه `stock_ml_predictions`** | `models/stock_enterprise.py:132-165` — سند جدول جداگانه با `confidence_interval_low/high` و `actual_close` می‌خواهد |
| **D18** | **هیچ جدولی ستون `actual_close` ندارد** — سند برای سنجش دقت ML لازم دارد | ❓ یافت نشد |
### ۹-۳. ابهام‌ها و موارد نیازمند تصمیم تیم (طبق «قانون طلایی» پرامپت)

| # | ابهام | گزینه‌ها |
|---|---|---|
| **۱** | **تعارض نقشه ۹ تب:** سند = `نمای کلی/نمودار/بنیادی/عمق بازار/رویدادهای شرکتی/صندوق‌های دارنده/اخبار/بک‌تست/ML` · کد = `تابلو/تکنیکال/همگروه/شناسنامه/کدال/اخبار/تاریخچه/پروفایل حجم/نبض بازار` (پیاده‌شده در `StockIntelligencePanel.tsx:6` و `/stocks/v2`) | (الف) حفظ نقشه کد و به‌روزرسانی سند · (ب) ساخت تب‌های جدید افزودنی کنار تب‌های فعلی · (ج) بازطراحی کامل (نقض اصل «فقط افزودن») |
| **۲** | **`stock_ohlcv_daily` جدید vs موجود** | (الف) جدول جدید + sync یک‌طرفه از `brsapi_candlesticks`/`daily_history` · (ب) استفاده مستقیم از `brsapi_candlesticks` (فقط `adjusted_close` اضافه شود) · (ج) نمای (VIEW) یکپارچه‌ساز |
| **۳** | **منبع واحد عمق بازار** (۴ گزینه، بخش ۲-۳) | `stock_order_book_l2` / `stock_live_tape` JSON / `brsapi_symbol_snapshots` / legacy |
| **۴** | **ذخیره ضریب تعدیل رویداد شرکتی** | (الف) جدول `stock_corporate_actions` سند + وصل کردن `CorporateActionAdjuster` موجود (کمترین بازنویسی) · (ب) ساخت موتور مستقل · (ج) استفاده از `candle_type=3` از BrsApi و حذف نیاز به ضریب محلی |
| **۵** | **`ingestion_run_logs` / `ingestion_quarantine_stocks`** | (الف) بازاستفاده از `job_runs` + ساخت فقط quarantine · (ب) ساخت هر دو مطابق سند · (ج) بازاستفاده از `fund_ingestion_quarantine` با ستون `asset_class` |
| **۶** | **نقش `ml_engineer`** | (الف) افزودن به `Role` + `ROLE_HIERARCHY` · (ب) نگاشت ML Engineer → `analyst` · (ج) مکانیزم `Permission` (`core/security/permissions.py`) به‌جای نقش جدید |
| **۷** | **شکل مسیر API** | (الف) نگه‌داشتن `/api/v1/stocks/v2/{symbol}/...` و اصلاح سند · (ب) افزودن alias افزودنی `/api/v1/stocks/{symbol}/...` که به همان سرویس وصل شود · (ج) بازنویسی (نقض اصل) |
| **۸** | **`stock_ml_predictions` جدید vs `ml_*` عمومی** | (الف) جدول جدید مطابق سند · (ب) افزودن `confidence_interval_low/high` + `actual_close` به `ml_predictions` · (ج) استفاده از `ml_symbol_results` |
| **۹** | **Real-time و throttle ۲۵۰-۵۰۰ms** | (الف) پذیرش دانه‌بندی ۲ دقیقه · (ب) پلن BrsApi بالاتر · (ج) منبع WS جدید |
| **۱۰** | **کتابخانه اندیکاتور فرانت** | (الف) محاسبه سمت بک‌اند و ارسال آرایه (بدون وابستگی جدید) · (ب) افزودن وابستگی npm جدید |
| **۱۱** | **`free_float_percentage` سند** | نام کد: `free_float_pct` (`symbols`) یا `free_float_shares` (`screener_profiles`) — کدام مبنا؟ |
| **۱۲** | **موتور واحد اندیکاتور** (D4) | کدام از ۶ پیاده‌سازی مبنا شود؟ |
| **۱۳** | **نگهداشت داده‌های snapshot** (D16) | TTL چند روز برای `brsapi_symbol_snapshots` و `stock_order_book_l2`؟ |
| **۱۴** | **`market-pulse` شکسته (B1/B2)** | فوری رفع شود یا تا بازطراحی تب ۹ معطل بماند؟ |
| **۱۵** | **سهمیه ۴۰۰۰/روز BrsApi** | دامنه backfill (چند نماد، چند سال) با این عدد قابل انجام نیست مگر با برنامه‌ریزی چند ماهه — نیاز به عدد واقعی پلن |
---

## ضمیمه الف — نگاشت «endpointهای گفت‌شده حفظ شوند» → واقعیت دقیق

طبق پرامپت (بخش ۴): «این‌ها همان endpointهایی هستند که در اسناد گفته شده حفظ شوند؛ باید دقیقاً بدانیم چه چیزی الان وجود دارد تا چیزی نشکند.»

| در سند گفته شده | متد + مسیر واقعی | فایل | وضعیت |
|---|---|---|---|
| دیده‌بان بازار (صفحه فعلی) | `GET /api/v1/market-watch` | `endpoints/market_watch.py` | ✅ حفظ شود |
| — | `GET /api/v1/market/overview`, `/indices`, `/gainers`, `/losers`, `/active`, `/watch`, `/bourse`, `/heatmap`, `/enriched-heatmap`, `/treemap`, `/energy-commodity` | `endpoints/market.py` | ✅ حفظ شود |
| — | `GET /api/v1/market-dashboard/*` | `endpoints/market_dashboard.py` | ✅ حفظ شود |
| واچ‌لیست کاربر | `GET/POST /api/v1/watchlist/`, `GET /watchlist/search`, `DELETE /watchlist/{symbol}` | `endpoints/watchlist.py` | ✅ حفظ شود |
| — | `GET /api/v1/instruments`, `/instruments/search`, `/instruments/{symbol}`, `/instruments/{symbol}/detail`, `POST /instruments` | `endpoints/symbols.py` | ✅ حفظ شود |
| — | `GET /api/v1/symbols`, `/symbols/search`, `/symbols/{symbol}` | `endpoints/symbol_search.py` | ✅ حفظ شود |
| — | `GET /api/v1/quotes?symbol=`, `/quotes/test/{instrument_id}` | `endpoints/quotes.py` | ✅ حفظ شود |
| — | `GET /api/v1/trades/{symbol}`, `/trades/{symbol}/recent` | `endpoints/trades.py` | ✅ حفظ شود |
| — | `GET /api/v1/orderbooks/{symbol}`, `/orderbooks/{symbol}/history` | `endpoints/orderbooks.py` | ✅ حفظ شود |
| — | `GET/POST /api/v1/indicators/{instrument_id}/{name}` | `endpoints/indicators.py` | ✅ حفظ شود |
| — | `GET /api/v1/fundamental/ratios`, `/dcf`, `/score/{symbol}`, `/compare`, `/industry/{industry}` | `endpoints/fundamental.py` | ✅ حفظ شود |
| — | `GET /api/v1/codal/*`, `/codal-accounting/*`, `/codal-audit/*`, `/codal-professional/*` | `endpoints/codal*.py` | ✅ حفظ شود |
| — | `GET /api/v1/news`, `/news/search`, `/news/symbol/{symbol}`, `/news/category/{category}`, `/news/trending`, `POST /news/refresh`, `GET /news/refresh/status` | `endpoints/news.py` | ✅ حفظ شود |
| — | `GET/POST /api/v1/screener/*`, `/screener/v2/*`, `/screener110/monitor`, `/scanner/*`, `/saved-filters/*` | `endpoints/screener*.py`, `scanner.py`, `saved_filters.py` | ✅ حفظ شود |
| — | `POST /api/v1/backtests/run` + ۳۰ route دیگر | `endpoints/backtests.py` | ✅ حفظ شود |
| — | `GET/POST /api/v1/ml/*`, `/forecast/*`, `/forecast-engine/*` | `endpoints/ml.py`, `forecast*.py` | ✅ حفظ شود |
| — | `GET/POST /api/v1/funds/*`, `/funds/v2/*` | `endpoints/funds.py`, `funds_v2.py` | ✅ حفظ شود |
| — | `WS /api/v1/ws/market`, `WS /api/v1/ws/precompute` | `endpoints/websocket.py`, `precompute_ws.py` | ✅ حفظ شود |
| — | `GET /api/v1/health`, `/metrics` | `endpoints/health.py`, `apps/api/app.py:974` | ✅ حفظ شود |
| **سند سهام** (طبیعت جدید) | `GET /api/v1/stocks/v2/*` (۱۲ route) | `endpoints/stocks_v2.py` | ✅ **موجود — تازه است؛ حفظ شود** |

**هیچکدام از اینها نباید حذف یا breaking شوند.** مسیر `stocks_v2.py` حتی محافظه‌کارتر است — docstring آن صریح می‌گوید: «نسخه‌بندی مستقل زیر `/stocks/v2` — endpointهای فعلی دست‌نخورده» (`stocks_v2.py:3`).

### 📸 نگاشت دقیق صندوق‌ها (تب ۶ سند) — تنها چیزی که باید اضافه شود

| نیاز سند | واقعیت موجود | کار لازم |
|---|---|---|
| `GET /api/stocks/:symbol/fund-holders` | ❓ یافت نشد · فقط `GET /api/v1/funds/v2/{fund_id}/holdings` (`funds_v2.py:206`) | **یک query جدید روی `fund_holdings.instrument_symbol` / `instrument_isin`** — نه جدول جدید. ستونهای لازم همه موجودند: `quantity`, `book_value`, `market_value`, `weight_pct`, `period_end_date`, `holding_type`. «۳ صندوق برتر» = `ORDER BY weight_pct DESC LIMIT 3` |

---

## ضمیمه ب — آمار کاوش

- **۵۵** migration · **۴۱** فایل ORM در `models/` · **۱۰** فایل ORM در `brsapi/models/` · **۷۲** فایل endpoint · **۵۱۵** route decorator · **۱۳۵** سرویس · **۳۵۸** فایل تست بک‌اند · **۲۳** فایل تست فرانت · **۶** workflow CI · **۳۹** فید خبری · **۲۰+** endpoint BrsApi
- **۶ جدول سند که باید ساخته شوند:** `stock_ohlcv_daily`, `stock_fundamentals`, `stock_corporate_actions`, `stock_ml_predictions`, `stock_backtest_runs`, `ingestion_quarantine_stocks` (+ `ingestion_run_logs`)
- **۵ باگ/تناقض تأییدشده** (B1-B5) · **۱۸ بدهی ساختاری** (D1-D18) · **۱۵ ابهام نیازمند تصمیم تیم**
- جستجوها: schema migrations، ORM models، router registration، endpoint decoratorها، providers، scheduler jobs، fixtures، auth/RBAC، CI، rate limiter، corporate actions، indicators، env vars

> پایان گزارش کاوش. برای پر کردن جاهای `[پر کن]` سند، از `docs/STOCKS_SPEC_FILLED_2026-09-18.md` استفاده کنید.
