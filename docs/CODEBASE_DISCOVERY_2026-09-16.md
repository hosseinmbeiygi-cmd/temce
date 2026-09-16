# گزارش کاوش خودکار کدبیس (Codebase Discovery)

> تاریخ: ۱۶ سپتامبر ۲۰۲۶ · branch: `main`
> هدف: پاسخ به تمام جاهای `[پر کن]` اسناد مشخصات فنی ۶ ماژول (صندوق‌ها، سهام، طلا/دلار/نقره، اخبار، بازار کالا، آپشن) بر اساس کد واقعی — بدون حدس.
> هر موردی که در کد یافت نشد، صریحاً «**یافت نشد**» علامت خورده است.

---

## ۱️⃣ معماری کلی

### Backend
| مورد | مقدار واقعی | منبع |
|------|-------------|------|
| زبان | Python `>=3.11` | `pyproject.toml:10` |
| فریمورک | FastAPI `>=0.109` + uvicorn[standard] | `requirements.txt` |
| اعتبارسنجی داده | pydantic `>=2.5` + pydantic-settings `>=2.1` | `requirements.txt` |
| ORM | SQLAlchemy `>=2.0` (async، درایور asyncpg) | `requirements.txt` |
| Migration | Alembic `>=1.13` — **۵۵ فایل migration** در `migrations/versions/` | `ls migrations/versions/` |
| Scheduler | APScheduler `>=3.10` | `apps/scheduler/app.py` |
| Queue | Redis LPUSH (`job:queue`) + consumer سفارشی در `apps/worker/`؛ **Celery در requirements اعلام شده ولی هیچ Celery-app فعالی یافت نشد** | `jobs/queue_publisher.py:40` |
| Auth | pyjwt `>=2.8` | `apps/api/auth.py` |
| Observability | sentry-sdk[fastapi]>=2.0، OpenTelemetry SDK + OTLP exporter، prometheus-client | `requirements.txt` |
| کتابخانه‌های بازار ایران | finpy-tse, tsetmc, tehran-stocks, tse-utils | `requirements.txt` |
| ML (اختیاری) | scikit-learn/xgboost/lightgbm/catboost — کامنت‌شده، نصب با `.[ml]` | `requirements.txt:35-39` |

### Frontend
| مورد | مقدار واقعی | منبع |
|------|-------------|------|
| فریمورک | Next.js `16.2.9` (App Router) + React `19.2.4` | `frontend/package.json` |
| زبان | TypeScript `^5` | `frontend/package.json` |
| استایل | **Tailwind CSS 4** (`@tailwindcss/postcss`) — CSS Modules/Styled Components/Emotion: **یافت نشد** | `frontend/package.json` |
| State management | **TanStack React Query `^5.101.0`** برای state سرور (۱۲۲ فایل tsx از useQuery/useMutation استفاده می‌کنند) + ۲ React Context (auth، theme) — Redux/Zustand/Vuex: **یافت نشد** | `git grep` |
| نمودار | **recharts `^3.8.1`** (۲۵ فایل) برای نمودارهای آماری + **lightweight-charts `^5.2.0`** برای کندل/چارت معاملاتی | `frontend/src/components/charts/` |
| تست | Vitest `^4.1.9` + @testing-library/react + jsdom — ۲۳ فایل تست | `frontend/src/__tests__/` |
| Sentry فرانت | @sentry/nextjs `^10.74.0` | `frontend/instrumentation-client.ts` |
| آیکون/انیمیشن | lucide-react، framer-motion، sonner (toast) | `frontend/package.json` |

### ساختار پوشه‌بندی (نمای درختی کلیدی)
```
temce/
├── apps/                  ← اپ‌های مستقل FastAPI
│   ├── api/               ← API اصلی (app.py + router.py + endpoints/ با ۷۲ فایل endpoint)
│   ├── scheduler/         ← APScheduler (ثبت jobها)
│   ├── worker/            ← consumer صف Redis
│   ├── currency_service/  ← سرویس مستقل ارز/طلا
│   ├── admin/  gateway/  decision_engine/  ml_worker/  ingestion_worker/
│   └── analytics_worker/  backtest_worker/  strategy_worker/  cli/
├── core/                  ← زیرساخت مشترک (config, database, logging, cache, security, enums, rate_limit)
├── services/              ← ۱۳۵ سرویس بیزینسی (fund_*, news_*, gold/*, options_*, ...)
├── models/                ← ORM models (SQLAlchemy) — ~۶۰ جدول
├── domain/                ← entities/logic دامنه (از جمله domain/news/*)
├── providers/             ← آداپتور منابع داده خارجی
│   ├── news/  tsetmc/  funds/  codal/  macro/{fx,gold,commodities,energy,metals}
│   ├── realtime/  historical/  reference/  web_scraping/  base/
├── brsapi/                ← یکپارچه‌سازی BrsApi (client, config, jobs/, migrations, models)
├── jobs/                  ← چارچوب job (base_job, registry, dispatcher, queue_*, definitions/)
├── migrations/versions/   ← ۵۵ فایل Alembic
├── schemas/               ← pydantic schemas API
├── repositories/          ← لایه دسترسی داده (news_repository و...)
├── scripts/               ← ابزارهای CLI (seed, export, load test)
├── tests/                 ← ۳۵۸ فایل تست pytest
└── frontend/              ← Next.js (src/app با ~۷۰ روت، src/components، src/lib)
```

### دیتابیس
- **PostgreSQL با افزونه TimescaleDB** — image واقعی: `timescale/timescaledb:latest-pg15` (`docker-compose.yml:5`)
- **Redis 7.0-alpine** برای cache/queue/rate-limit (`docker-compose.yml:25`)
- اتصال: `DATABASE_URL` + pool `DB_POOL_MIN_SIZE=5` / `DB_POOL_MAX_SIZE=20` (`.env.example:19-30`)
- نکته مهم: `core/database.py:128-131` — **در production فقط Alembic؛ در non-production علاوه بر Alembic، `Base.metadata.create_all` هم اجرا می‌شود** (منبع دوگانگی schema).

---

## ۲️⃣ مدل داده فعلی

### جدول‌های مرتبط با ۶ ماژول (از migrations + ORM models)

**صندوق‌ها:**
| جدول | منبع | فیلدهای کلیدی |
|------|------|----------------|
| `funds` | migration `0015` + `models/fund.py` | `id` String(50) PK، `symbol` String(20) unique، `name`، `isin` unique، `fund_type` (سهامی/درآمد ثابت/اهرمی/مختلط/بخشی/اختصاصی)، `nav`، `nav_change`، `nav_change_pct`، `price_last/close/yesterday/max/min`، `trade_volume` BigInteger، `trade_value` |
| `fund_categories` | migration `0015`/`0045` (دوسطحی) | — |
| `fund_nav_history` | `models/fund_enterprise.py:60` (migration `0051`) | تاریخچه NAV با gap-fill |
| `fund_portfolio_reports` / `fund_holdings` / `fund_portfolio_diffs` | `models/fund_enterprise.py:83/108/136` | ریز دارایی + تغییرات وزنی |
| `fund_market_quotes_cache` / `fund_scores_history` / `fund_ingestion_quarantine` / `fund_symbol_aliases` / `fund_ingestion_runs` | `models/fund_enterprise.py:160-257` | cache/KPI/قرنطینه/alias |
| `etf_nav` | migration `0001` | NAV صندوق‌های ETF |
| `gold_fund_nav` | migration `0041` | NAV صندوق‌های طلا |

**سهام:**
| جدول | منبع | فیلدهای کلیدی |
|------|------|----------------|
| `symbols` | migration `0001` + `models/market_data.py:23` | `id` BigInteger PK، `symbol` String(50) unique، `name`، `isin`، `market_type`، `asset_class`، `industry`، `total_shares`، `base_volume`، `eps`، `pe`، `tick_size`، `lot_size`، `is_active` |
| `daily_history` | `models/market_data.py:48` | PK ترکیبی (`symbol_id`, `trade_date`) |
| `candlesticks` | migration `0001` | OHLCV با `candle_type` |
| `quotes` | `models/quote.py:8` | `instrument_id` String(50) indexed، `symbol`، `price_open/high/low/close/last`، `price_change(_pct)` |
| `intraday_trades` / `orderbooks` / `trades` / `shareholders` / `indices` / `daily_real_legal` / `market_ticks` / `symbol_snapshots` / `orderbook_snapshots` | migration `0001` | داده معاملاتی خام |
| `stock_live_tape` / `stock_order_book_l2` / `stock_indicators_snapshot` / `stock_quant_signals` / `stock_news_sentiment` / `stock_monthly_sales_production` / `market_macro_indicators` | `models/stock_enterprise.py` (migration `0052_tse_stocks_enterprise`) | لایه Enterprise سهام |

**قیمت‌ها:** `quotes` + `daily_history` + `candlesticks` (بالا) + `market_snapshots` + snapshotهای BrsApi (`brsapi_*`).
- ⚠️ ادعای unique constraint روی `(instrument_id, date)` در جدول قیمت‌ها: در migrations **تأیید نشد** — indexهای یکتای موجود در `0040_unique_constraints_and_indexes.py` بر `url` اخبار و بقیه‌اند. (نیاز به بررسی دستی روی DB زنده)

**کاربران:**
| جدول | منبع | فیلدها |
|------|------|--------|
| `users` | `models/user.py:13` | `id` String(50) PK، `username` unique، `email` unique، `hashed_password`، `full_name`، `phone`، `roles` String(255) default `'viewer'`، `is_active`، `is_verified`، `last_login`، `refresh_token`، `metadata`، `totp_secret`، `totp_enabled`، `totp_confirmed_at`، `mfa_method`، `telegram_chat_id` (migrationهای 0022-0024) |

**واچ‌لیست:**
- ⚠️ **یافت نشد در migrations و models** — جدول `watchlist` در `services/watchlist_service.py:36-51` با `CREATE TABLE IF NOT EXISTS` در runtime ساخته می‌شود (`_ensure_table`). این یعنی schema واچ‌لیست خارج از کنترل Alembic است.

**اخبار (وضعیت فعلی، قبل از ماژول جدید):**
| جدول | منبع | فیلدها |
|------|------|--------|
| `news_articles` | `models/news.py:8` | `id` String(50) PK، `title` String(500)، `summary`، `content` Text، `source` String(100) indexed، `url` Text، `category` String(50) indexed، `symbols` **Text** (تگ‌ها به‌صورت رشته)، `published_at` **String(40)** ⚠️ (مهاجرت عرض در `0021`)، `sentiment` default 'neutral'، `sentiment_score` Float، `data_source` default 'rss'، `created_at`/`updated_at` |
| `stock_news_sentiment` | `models/stock_enterprise.py:171` | `symbol`، `isin`، `industry`، `title`، `body`، `source`، `published_at` DateTime، `sentiment`، `sentiment_score`، `impact_tag` + Index `ix_news_symbol_pub` |

- `news_items` / `news_tags` / `news_ingestion_sources` (پیشنهاد سند مشخصات): **یافت نشد** — باید ساخته شوند.
- ⚠️ CREATE TABLE اصلی `news_articles` در هیچ migrationی یافت نشد (فقط alterها در 0006/0021/0040) → احتمالاً توسط `create_all` در دوره‌ای قبل از پیوستن Alembic ساخته شده. **نامشخص - نیاز به بررسی دستی روی DB زنده.**

**طلا/ارز:** `gold_snapshots`، `gold_currency_prices`، `gold_trades`، `gold_holdings`، `gold_alert_rules`، `gold_alert_events`، `gold_dca_plans`، `gold_score_history`، `gold_futures_positions`، `gold_kill_switch_events`، `gold_portfolio_holdings` (migrations 0001/0041/0042 + `models/gold.py`)

**بازار کالا:** `commodity_prices`، `commodity_futures`، `commodity_options`، `commodity_certificates`، `commodity_trades`، `commodity_funds` (migration 0001 + `models/market_data.py:120-197`)

**آپشن:** `options` (0001)، `option_contracts`، `option_snapshots`، `option_trades`، `open_interest_history`، `volatility_surface`، `corporate_actions` (`models/option.py`)

---

## ۳️⃣ منابع داده خارجی

### ✅ BrsApi — منبع اصلی بازار (REST)
- **دامنه:** `https://Api.BrsApi.ir` (`BRSAPI_BASE_URL` در `.env.example:139`)
- **کلید:** متغیر env `BRSAPI_API_KEY` (فقط نام؛ مقدار در env) — به‌عنوان پارامتر `key` به endpointها پاس داده می‌شود (`required_params=("key",)` در `brsapi/config.py`)
- **کلاینت:** `brsapi/client.py` با rate-limit توکن-باکتی per-endpoint-category، retry، cache TTL
- **endpointها (واقعی از `brsapi/config.py`):**

| Endpoint | مسیر | فاصله sync (registry) |
|----------|------|----------------------|
| ALL_SYMBOLS | `/Tsetmc/AllSymbols.php` | هر ۲ دقیقه (فقط ساعات بازار) |
| SYMBOL_DETAIL | `/Tsetmc/Symbol.php` | on-demand |
| INDEX | `/Tsetmc/Index.php` | هر ۲ دقیقه (type=1 بورس، type=2 فرابورس) |
| NAV | `/Tsetmc/Nav.php` | on-demand per-symbol (`sync_nav`) |
| OPTION | `/Tsetmc/Option.php` | هر ۵ دقیقه |
| TRANSACTION | `/Tsetmc/Transaction.php` | — |
| HISTORY_PRICE / HISTORY_REALLEGAL | `/Tsetmc/History.php` | on-demand per-symbol |
| CANDLESTICK | `/Tsetmc/Candlestick.php` | on-demand |
| SHAREHOLDER | `/Tsetmc/Shareholder.php` | on-demand |
| CODAL_ANNOUNCEMENT | `/Codal/Announcement.php` | per config |
| IME_FUTURES / OPTION / CERTIFICATE / FUND / PHYSICAL | `/IME/*.php` | هر ۵ دقیقه |
| COMMODITY | `/Market/Commodity.php` | هر ۵ دقیقه |
| CRYPTOCURRENCY | `/Market/Cryptocurrency.php` | هر ۵ دقیقه |
| GOLD_COIN | `/Market/Coin.php` | ❌ غیرفعال (404 می‌دهد) |
| GOLD_CURRENCY + PRO | `/Market/Gold_Currency.php` / `_Pro.php` | هر ۵ دقیقه / هر ۵ دقیقه |

- نمادهای نمونه در کد: `brsapi/constants.py` — لیست `BRSAPI_ETF_SYMBOLS` با ~۲۰۰ نماد صندوق واقعی (اهرم، توان، شتاب، آگاس، ...).

### ✅ RSS خبرگزاری‌ها — منبع اخبار (REST/XML، بدون کلید)
`providers/news/domestic/rss_domestic_provider.py` — **۳۹ فید**:
- `fardaye_*` (۲۳ فید: latest/homepage/popular/macro/bourse/gold/crypto/industry/energy/housing/auto/tech/companies + prog_*)
- `boursepress_*` (۴)، `ecoiran_latest`، `tejarat_*` (۴)، `eghtesadonline_*` (۳)
- `isna_*` (۴): `https://www.isna.ir/rss/tp/68` (اقتصادی)، `/tp/7` (انرژی)، `/tp/11` (صنعت)، `/tp/57` (بازار سرمایه)

### ✅ Codal
- `CODAL_BASE_URL=https://codal.ir` (`.env.example:60`) + مسیر BrsApi `/Codal/Announcement.php` — هم‌اکنون فعال (SyncCodalJob هر ۶ ساعت، CodalAttachmentDownloadJob هر ۱۵ دقیقه)

### ✅ TSETMC
- `TSETMC_BASE_URL=http://tsetmc.com` (`.env.example:59`) + `providers/tsetmc/` + `providers/realtime/tsetmc/`

### ✅ Tabdeal (رمزارز)
- کلاینت `tabdeal/client.py` — CRUD سفارش/ترید/حساب/بازار (`apps/api/endpoints/tabdeal.py`)

### ⚠️ FX/طلا/نقره — **نکته مهم**
- `providers/macro/fx/domestic_fx_provider.py` و `providers/macro/gold/*` با آدرس **placeholder** `https://api.example.com/fx/domestic` و `https://api.example.com/gold/domestic` ساخته شده‌اند — **stub هستند**.
- منبع واقعی قیمت دلار/طلا/سکه در عمل: **BrsApi `/Market/Gold_Currency.php` و `_Pro.php`** (سرویس `services/gold/live_service.py` مستقیماً `BrsApiQueryService` را wrap می‌کند).

### ⚠️ NAV صندوق‌ها — دو مسیر
1. **واقعی:** BrsApi `/Tsetmc/Nav.php` per-symbol (`SyncNavAllJob` cron 9,18)
2. **stub:** `providers/funds/client.py` با `base_url=http://localhost:8500/api/funds` و fallback داده **MOCK** (`MOCK_NAV_HISTORY`, `MOCK_HOLDINGS`) — فقط وقتی سرویس fund محلی پاسخ ندهد.

### ❌ Elasticsearch / Kafka / سرویس جستجو
- **هیچ اتصالی پیدا نشد** — این منابع باید از صفر طراحی شوند (ادعای گزارش‌های قبلی، رد شده).

### WebSocket
- `apps/api/endpoints/websocket.py` → `@router.websocket("/market")` + SSE در `GET /funds/intraday/stream`؛ فرانت: `frontend/src/hooks/useWebSocket.ts`

---

## ۴️⃣ Endpointهای API فعلی بک‌اند

پیش‌فرض همه: `settings.api_prefix = "/api/v1"` (`core/config/__init__.py:42`). ثبت: `apps/api/router.py` (خطوط ۲۴۲-۶۱۵). کنترلرها در `apps/api/endpoints/`.

### اخبار (`/api/v1/news` — `endpoints/news.py`)
| متد | مسیر | توضیح |
|-----|------|-------|
| GET | `/news` | فهرست صفحه‌بندی‌شده (`page`, `page_size`)؛ فیلترهای query: symbol، category |
| POST | `/news` | ایجاد خبر (سازگاری فرانت) |
| GET | `/news/search` | جستجوی متنی |
| GET | `/news/symbol/{symbol}` | اخبار یک نماد |
| GET | `/news/category/{category}` | دسته‌بندی: `market, company, economic, political, international` ⚠️ (مقدار `company` ولی سند جدید `stock_market` می‌خواهد) |
| GET | `/news/trending` | اخبار داغ (sentiment-based) |
| POST | `/news/refresh` | ingest دستی RSS (state global در-memory) |
| GET | `/news/refresh/status` | وضعیت آخرین refresh |

### صندوق‌ها
- `/api/v1/funds` (`endpoints/funds.py`, ۱۳ روت): `GET ""`، `GET /types`، `GET /top`، `GET /overview`، `GET /nav-history` (گروهی)، `GET /intraday`، `GET /intraday/candles`، `GET /intraday/stream` (SSE)، `GET /{symbol}/nav`، `GET /{symbol}`، `POST /sync-all`، `POST /{symbol}/update`، `GET /{symbol}/analysis`
- `/api/v1/funds/v2` (`endpoints/funds_v2.py`, ۱۵ روت): `GET /universe`، `GET /{fund_id}/nav-history`، `/holdings` (JIT کدال)، `/valuation`، `/score`، `/backtest`، `GET /rankings`، `/portfolio-diffs`، `/monitoring`، `/coverage`، `/aliases/{fund_id}`، `/quarantine`، `POST /discover`، `POST /quarantine/{qid}/review`

### سهام
- `/api/v1/stocks/v2` (`endpoints/stocks_v2.py`): `/{symbol}/tape`، `/indicators`، `/signal`، `/peers`، `/dossier`، `/codal`، `/news`، `/history`، `/history/export.csv`، `/volume-profile`، `GET /market-pulse`، `GET /monitoring`
- `/api/v1/market` (`endpoints/market.py`): `/overview`، `/indices`، `/gainers`، `/losers`، `/active`، `/watch`، `/bourse`، `/energy-commodity`، `/heatmap`، `/enriched-heatmap`، `/treemap`
- سایر prefixهای مرتبط: `/symbols`، `/quotes`، `/orderbooks`، `/trades`، `/instruments`، `/market-dashboard`، `/market-watch`، `/intraday` (migration سطح API)، `/screener`، `/screener-v2`، `/screener110`، `/fundamental`، `/forecast`، `/forecast-engine`

### طلا/ارز
- `/api/v1/gold` (`endpoints/gold.py`, ۱۳+ روت): `GET /live-prices` (+POST سازگاری)، alertها، DCA، portfolio و... (سرویس: `services/gold/live_service.py` روی BrsApi)
- سرویس مستقل `apps/currency_service/`: `/health`، `/overview`، `POST /positions`، `GET /positions`، `/signals`

### کالا
- `/api/v1/ime` (`endpoints/ime.py`): ۵ روت GET برای futures/options/certificates/funds/physical از داده IME (BrsApi)
- macro: `/api/v1/macro` → `GET /`، `/{indicator}`، `/{indicator}/history`

### آپشن
- `/api/v1/options` (`endpoints/options.py`): `GET /strategies`، `POST /analyze`، `POST /recommend`، `GET /greeks`، `GET /pricing`، `GET /reference/*` (selection-guide، mistakes، glossary، references، examples، syllabus، iran-rules)
- داده خام آپشن: BrsApi `/Tsetmc/Option.php` (sync هر ۵ دقیقه) + جدول‌های `option_*`

### احراز هویت
- `/api/v1/auth` (`endpoints/auth.py`): `POST /register`، `/login`، `/mfa/login`، `/refresh`، `/forgot-password`، `/reset-password`، `/change-password`، `/logout`، `GET /me`، `/login-history`، `/mfa/status`، `PUT /profile`

### سایر (مربوط به اسناد دیگر)
`/alerts`، `/signals`، `/recommendations`، `/indicators`، `/chat`، `/codal` + `/codal-accounting` + `/codal-audit` + `/codal-professional`، `/data-import`، `/economic-calendar`، `/jobs` (admin)، `/ml`، `/backtests`، `/reports`، `/smart-money`، `/risk`، `/saved-filters`، `/portfolios`، `/paper-trading`، `/watchlist`، `/decision-engine`، `/queue-analysis`، `/ws`، `/ingestion`، `/precompute`، `/brsapi`، `/tabdeal`، `/tables`، `/compose`، `/market-info`، `/market-insights`، `/signal-insights`، `/assistant`، `/stock-assistant`، `/tests`، `/health`

---

## ۵️⃣ نمونه داده واقعی

### Fixture خبر واقعی (`tests/fixtures/sample_news.py`)
```python
NewsItem(
    id=new_id("news"),
    title="افزایش قیمت جهانی فولاد",
    summary="قیمت جهانی فولاد در بازارهای بین‌المللی با رشد همراه شد",
    content="بهای هر تن فولاد در بازارهای جهانی با افزایش ...",
    source="rss",
    url="https://example.com/news/123",
    category="market",
    symbols=["فولاد"],
    publish_date=datetime.fromisoformat("2024-01-15T10:30:00"),
    sentiment=0.85,
    sentiment_label="positive",
    data_source="rss",
)
```
نمادهای استفاده‌شده در fixtureها: `فولاد، فملی، وبانک، کگل، خودرو` (`sample_news_list`).

### سایر فیکسچرها
`tests/fixtures/`: `sample_backtests.py`، `sample_codal.py`، `sample_instruments.py`، `sample_macro.py`، `sample_ml_runs.py`، `sample_orderbooks.py`
اسکریپت‌های seed: `scripts/seed_funds.py` (پرکردن از BrsApi با `--limit/--symbols/--dry-run/--db-url`)، `seed_architecture.py`، `seed_decisions.py`
داده mock در کد: `providers/funds/client.py` → `MOCK_NAV_HISTORY`, `MOCK_HOLDINGS`

---

## ۶️⃣ احراز هویت و نقش‌ها

- **مکانیزم:** JWT (pyjwt) با HTTPBearer + refresh token + **revocation** (بررسی `jti` در Redis — `core/security/tokens.py`, `is_token_revoked`) + **MFA/TOTP** (به‌ازای کاربر: `totp_secret`, `mfa_method`) + reset/forget password
- **نکته مهم:** در `apps/api/auth.py` هر دو `verify_api_key` و `verify_token` فقط وقتی `settings.is_production` سخت‌گیری می‌کنند — در dev توکن اختیاری است.
- **RBAC موجود است:** `core/enums/rbac.py` → نقش‌ها: **`admin`, `analyst`, `user`, `viewer`** با سلسله‌مراتب (`ROLE_HIERARCHY`)، توابع `has_role`/`has_any_role`، admin همیشه bypass. نقش روی `users.roles` (comma-separated string) ذخیره می‌شود.
- این با الگوی سند مشخصات (Viewer/Analyst/Admin) سازگار است؛ فقط نام دقیق نقش سوم `user` است نه `member`.
- فرانت: JWT در cookie + middleware (`frontend/src/middleware.ts`) با `PUBLIC_ROUTES` و redirect به `/auth/login?redirect=...`

---

## ۷️⃣ زیرساخت Job/Scheduler

**موجود و فعال** — دو لایه:

1. **APScheduler** (`apps/scheduler/app.py`): کلاس‌های `BaseJob` در `jobs/definitions/` (هر کدام `execute(context) -> JobResult`) با ثبت از طریق `job_registry.register_module(job_definitions)`.
2. **registry اختصاصی BrsApi** (`brsapi/jobs/registry.py` — ۱۷۶۰+ خط): `BrsApiSyncJob` + `BrsApiJobRegistry` با cronهای `_EVERY_1_MIN/_EVERY_2_MIN/_EVERY_5_MIN/_EVERY_1_HOUR` و فلگ `market_hours_only` و `enabled=False` برای endpointهای per-symbol.
3. **صف Redis اختیاری:** `jobs/queue_publisher.py` → `LPUSH job:queue`؛ consumer در `apps/worker/`؛ فعال با `JOB_QUEUE_ENABLED` (بدون آن، scheduler مستقیم اجرا می‌کند).

**جدول‌بندی jobهای فعلی (نمونه‌های مرتبط با ۶ ماژول):**
| Job | Trigger | ماژول |
|-----|---------|-------|
| `SyncQuotesJob` + `SyncSnapshotsToQuotesJob` | هر ۲ دقیقه | سهام |
| `SyncInstrumentsJob` | ۲۴ ساعت | سهام |
| `SyncNavAllJob` | cron 9:00, 18:00 | صندوق‌ها (NAV) |
| `FundsSyncJob` | cron 17:30 | صندوق‌ها |
| `FundDiscoveryJob` | cron 8:15, 14:15, 20:15 | صندوق‌ها (Zero-Config) |
| `SyncCodalJob` / `CodalAttachmentDownloadJob` | ۶ ساعت / ۱۵ دقیقه | کدال |
| `NewsIngestionJob` | هر ۱۰ دقیقه | **اخبار (معادل پیشنهاد ۵-۱۵ دقیقه سند — هم‌اکنون ۱۰ دقیقه است)** |
| `NewsSentimentJob` | هر ۱۰ دقیقه، بعد از ingestion | اخبار |
| `brsapi_gold_currency` + `_pro` | هر ۵ دقیقه | طلا/دلار |
| `brsapi_commodity` / `_crypto` | هر ۵ دقیقه | کالا |
| `brsapi_options` / `ime_*` | هر ۵ دقیقه | آپشن/IME |
| `IndicatorPrecomputeJob` | cron 18:30, 21:30 | سهام Enterprise |
| `MonthlySalesFillJob` | cron 3:30 | سهام Enterprise |
| `EvaluateAlertsJob` | هر ۲ دقیقه | هشدارها |
| `PaperTradingJob` / `BackfillHistoricalDataJob` | cron 21:00 / 02:00 | معاملات کاغذی/تاریخچه |

**Audit log مشترک:** جدول `job_runs` (`models/job_run.py`: job_type, status, progress_pct, started_at, completed_at, duration_seconds, error_message, result). جدول `ingestion_run_logs` پیشنهادی سند: **یافت نشد** — معادل موجود همان `job_runs` است (`job_type='...'`).

---

## ۸️⃣ Logging / Monitoring / Testing / CI

| لایه | وضعیت |
|------|-------|
| **Logging** | پکیج سفارشی `core/logging/` (setup, formatters, correlation-id, request_logging, filters, audit_logging) — `get_logger(__name__)` در کل کد. structlog/loguru: **یافت نشد** |
| **Metrics** | prometheus-client — `/metrics` از `apps/api/metrics.py` (`get_prometheus_exporter`) |
| **Tracing** | OpenTelemetry SDK + exporter OTLP (requirements) |
| **Error tracking** | Sentry دوطرفه (backend `sentry-sdk[fastapi]`، frontend `@sentry/nextjs`) — env-guarded با `SENTRY_DSN` |
| **تست backend** | pytest + pytest-asyncio + pytest-cov — **۳۵۸ فایل تست** در `tests/` (شامل ۲۴ تست خدمات fund/news جدید) |
| **تست frontend** | Vitest + Testing Library — **۲۳ فایل تست** |
| **CI/CD** | `.github/workflows/`: `ci.yml`، `ci-pr.yml`، `decision-engine.yml`، `fund-service.yml`، `release.yml`، `secrets-scan.yml` |
| **Health** | `/api/v1/health` + جدول‌های `provider_health`/`provider_health_history` + صفحه `/data-health` فرانت |

---

## ۹️⃣ بدهی فنی و نکات هشدار (مرتبط با ارتقای ۶ ماژول)

1. **`published_at` اخبار به‌صورت `String(40)` ذخیره می‌شود** نه TIMESTAMP (`models/news.py:19`؛ migration `0021` فقط عرض را زیاد کرده). هر فیلتری روی بازه زمانی فعلاً string-compare است — سند مشخصات TIMESTAMP می‌خواهد؛ تبدیل = migration با cast داده (تصمیم تیم).
2. **Tagging فعلی بسیار ابتدایی است:** `providers/news/parser.py:72-79` — لیست hardcoded شش نماد `{"فولاد", "فملی", "وبانک", "کگل", "خودرو", "شپنا"}` و ذخیره در ستون `symbols` (TEXT) از `news_articles`. جدول `news_tags` با confidence: **یافت نشد**.
3. **Dedup فعلی فقط in-memory:** `services/news_dedup.py` (`NewsDeduplicator` با TTL 86400s و hash عنوان نرمال‌شده) — بدون `dedup_hash` پایدار در DB (unique index فعلی روی `url` است — `0040`). ری‌استارت worker = از دست رفتن حافظه dedup.
4. **`watchlist` بدون migration:** ساخته‌شدن در runtime توسط `_ensure_table` (`services/watchlist_service.py`) — خارج از کنترل Alembic؛ قبل از هر توسعه‌ای باید به migration منتقل شود.
5. **`news_articles` CREATE TABLE در migrations یافت نشد** (فقط alterها) — احتمالاً با `create_all` قدیمی ساخته شده؛ اسکیما روی DB زنده باید دستی تأیید شود.
6. **providerهای stub:** `providers/macro/fx|gold` با `api.example.com`؛ `providers/funds/client.py` با MOCK fallback — هر ارتقایی باید مسیر واقعی (BrsApi) را مبنا بگیرد، نه این آداپتورها.
7. **۴۱۳ بلاک `except Exception` در `services/`** (۲۴ مورد silent `pass`) — error handling ضخیم؛ در ارتقای pipeline اخبار، خرابی منبع نباید در این الگوها گم شود.
8. **refresh دستی اخبار با state global در-memory** (`_refresh_status` در `endpoints/news.py:27`) — با uvicorn multi-worker بین workerها share نمی‌شود؛ برای وضعیت باید `job_runs`/Redis مبنا شود.
9. **دو لایه مفهومی موازی:** `models/` (ORM) و `domain/` (entities مثل `domain/news/news_item.py`) — هنگام افزودن `news_items` جدید باید تکلیف این دو لایه روشن شود.
10. **Celery در requirements اعلام شده ولی هیچ Celery app فعالی یافت نشد** — یا حذف شود یا مستند که عمداً برای آینده است.
11. **`_FRONTEND_BACKEND_COPY/` هنوز در ریپو است** و نسخه کهنه `models/news.py` و endpointهای news را دارد — منبع درگیری/سردرگمی هنگام جستجوی کد.
12. **dual-write احساسات:** امتیاز sentiment هم روی `news_articles.sentiment(_score)` ذخیره می‌شود و هم جدول جدا `stock_news_sentiment` دارد — سیاست منبع واحد حقیقت باید روشن شود.
13. **دسته‌بندی اخبار فعلی:** `{market, company, economic, political, international}` (`news.py:22`) — سند جدید `stock_market` پیشنهاد می‌دهد؛ نگاشت لازم است.

### ابهام‌های نیازمند تصمیم تیم (طبق قانون طلایی پرامپت)
| # | ابهام | گزینه‌ها |
|---|-------|----------|
| ۱ | `published_at` VARCHAR(40) موجود vs TIMESTAMP سند | مهاجرت با cast، یا ستون جدید + backfill، یا حفظ string |
| ۲ | بسط `news_articles` فعلی vs ساخت `news_items` جدید سند | اصل «فقط افزودن» سند هر دو را ممکن می‌کند؛ مبنا چه باشد؟ |
| ۳ | دسته‌بندی: `company` فعلی vs `stock_market` سند | نگاشت در لایه نرمال‌سازی، یا تغییر ثابت‌ها |

---

## ضمیمه: آمار کاوش
- ۵۵ migration، ~۶۰ جدول ORM، ۷۲ فایل endpoint، ۱۳۵ سرویس، ۳۵۸ تست backend، ۲۳ تست frontend، ۶ workflow CI، ۳۹ فید RSS، ۲۰+ endpoint BrsApi
- جستجوها: schema migrations، ORM models، router registration، providers، scheduler jobs، CI، fixtures، auth/RBAC
