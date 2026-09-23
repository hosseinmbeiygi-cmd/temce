# گزارش کاوش خودکار کدبیس — تمرکز: ماژول آپشن بورس (اختیار معامله)

> تاریخ کاوش: ۱۶ سپتامبر ۲۰۲۶ · branch: `main` · مخزن: `C:\Users\Iran\Desktop\temce`
> هدف: پاسخ به تمام جاهای `[پر کن]` و سوالات باز سند «مشخصات فنی کامل و نهایی — ماژول آپشن بورس».
> روش: خواندن کد + **بررسی زنده DB** (`localhost:5432` → `my_first_db`) و **API در حال اجرا** (`127.0.0.1:8000`) در همان تاریخ. هیچ فرضی زده نشده؛ هر موردی که در کد پیدا نشد، صریحاً «**یافت نشد**» علامت خورده است.

---

## ۱. شناسایی معماری کلی

### بک‌اند
| مورد | مقدار واقعی | منبع |
|---|---|---|
| زبان | Python `>=3.11` | `pyproject.toml` |
| فریمورک | FastAPI `>=0.109` (نصب‌شده در venv: `0.128.8`) + `uvicorn[standard]` | `requirements.txt` |
| اعتبارسنجی | Pydantic `>=2.5` + pydantic-settings | `requirements.txt` |
| ORM | SQLAlchemy `>=2.0` **async** + `asyncpg 0.31` | `core/database.py` |
| Migration | Alembic `>=1.13` — **۵۴ فایل** در `migrations/versions/` (جدیدترین: `0053_fund_universe_aliases.py`، ۲۰۲۶-۰۹-۱۶) | شمارش پوشه |
| Scheduler | APScheduler `>=3.10` (نصب‌شده `3.11.2`) | `apps/scheduler/app.py` |
| Queue | Redis LPUSH (`job:queue`) + consumer سفارشی `apps/worker/`؛ Celery `5.6.3` فقط در `precompute/workers/celery_tasks.py` (lazy، بدون Beat) | `jobs/queue_publisher.py` |
| Auth | JWT (`pyjwt 2.13`) + Refresh Cookie + MFA/TOTP | `core/security/tokens.py` |
| Observability | structlog، Sentry، prometheus-client، OpenTelemetry (exporter تعریف‌شده ولی به startup وصل نشده — نامشخص) | `core/logging/`, `core/observability_sentry.py`, `integrations/observability/` |

- نقطه ورود: `main.py` → `uvicorn.run("apps.api.app:app")`؛ اپ در `apps/api/app.py` (`create_app`) و روتر اصلی در `apps/api/router.py` با prefix پیش‌فرض `settings.api_prefix = "/api/v1"` (`core/config/__init__.py`).
- پوشه `backend/` **خالی** است؛ بک‌اند اصلی `apps/api` است.

### فرانت‌اند
| مورد | مقدار واقعی | منبع |
|---|---|---|
| فریمورک | **Next.js `16.2.9` (App Router)** + React `19.2.4` + TypeScript `^5` | `frontend/package.json` |
| State Management | **TanStack React Query `^5.101.0`** برای state سرور (۱۲۲+ فایل `tsx`) + ۲ React Context دستی: `auth-context.tsx` و `ThemeProvider` (gold) — **Redux / Zustand / MobX / SWR: یافت نشد** | grep |
| کتابخانه نمودار | **recharts `^3.8.1`** (نمودارهای آماری) + **lightweight-charts `^5.2.0`** (کندل) | `frontend/package.json` |
| استایل | **Tailwind CSS 4** (`@tailwindcss/postcss`) — CSS Modules / Styled Components / Emotion: **یافت نشد** | grep |
| HTTP Client | `fetch` بومی داخل wrapperهای `frontend/src/lib/*.ts` (`axios`: یافت نشد)؛ Base: `process.env.NEXT_PUBLIC_API_URL || '/api/v1'` | `frontend/src/lib/api.ts` |
| تست | Vitest `4.1.9` + Testing Library + jsdom — **۲۵ فایل** test/spec | شمارش `frontend/src` |
| Sentry | `@sentry/nextjs ^10.74.0` | `frontend/instrumentation-client.ts` |

### دیتابیس
- **PostgreSQL 15 + TimescaleDB** (ایمیج `timescale/timescaledb:latest-pg15` در `docker-compose.yml`)؛ SQLite در `core/database.py` صریحاً رد می‌شود.
- Redis 7 برای cache/queue/rate-limit/revocation.
- Hypertableهای مرتبط: `etf_nav`، `gold_currency_prices`، `commodity_prices`، ... (`migrations/versions/0001_initial_schema.py`).

### ساختار پوشه‌بندی (نمای درختی کلیدی)
```
temce/
├── apps/api/            ← API اصلی (app.py, router.py, endpoints/ با ۷۲ فایل)
├── apps/scheduler/      ← APScheduler
├── apps/worker/         ← consumer صف Redis
├── core/                ← config, database, logging, security, enums, ...
├── services/            ← ~۱۴۰ سرویس؛ شامل options_service.py, options_analytics.py, options_reference.py
├── domain/options/      ← ۱۴ ماژول pricing/greeks/...  + domain/decision_engine_v5/
├── models/              ← ORM؛ شامل option.py
├── brsapi/              ← یکپارچه‌سازی BrsApi (client, config, parsers, models, jobs, services)
├── jobs/definitions/    ← تعریف jobها
├── migrations/versions/ ← ۵۴ فایل Alembic
├── ingestion/           ← منابع ingestion (شامل sources/derivatives.py)
├── tests/unit/options/  ← ۱۱ فایل تست آپشن
└── frontend/src/app/options/ ← UI آپشن (۷ تب + ۹ کامپوننت)
```

### وضعیت فعلی ماژول آپشن در معماری (خلاصه واقعیت)
| بخش | وضعیت |
|---|---|
| API آپشن (`apps/api/endpoints/options.py`، ۲۶ روت) | **وجود دارد ولی در `apps/api/router.py` mount نشده** → در API زنده همه ۴۰۴ |
| موتور استراتژی (`services/options_service.py`) | پیاده‌سازی واقعی (~۱۱۵۵ خط، ۳۰ استراتژی، `OptionsStrategyEngine`) |
| تحلیل‌ها (`services/options_analytics.py`) | پیاده‌سازی واقعی (Put-Call Parity، IV، Greeks پورتفوی، Max Pain) |
| مرجع آموزشی (`services/options_reference.py`) | داده ثابت واقعی |
| پکیج دامنه (`domain/options/`) | ۱۴ ماژول واقعی: Black-Scholes، Greeks، Black-76، Heston، درخت دو جمله‌ای، مونت‌کارلو، VaR، Margin |
| مدل داده آپشن (`models/option.py`) | ۶ جدول تعریف‌شده ولی **خالی (۰ ردیف) و بدون migration** |
| داده واقعی زنجیره | `brsapi_option_snapshots` (+ `brsapi_ime_options`) با ingestion فعال هر ۵ دقیقه |
| UI آپشن (`frontend/src/app/options/`) | ۷ تب واقعی که همه فراخوانی‌هایش به router mount نشده می‌خورد → الان عملاً بی‌داده |
| پیش‌بینی (`frontend/.../ForecastPanel`) | از `GET /api/v1/forecast` کار می‌کند (مربوط به آپشن نیست) |
| بک‌تست آپشن (`backtesting/strategies/options/`) | ۶ فایل اسکلت/placeholder (مثلاً Covered Call فقط سهم می‌خرد و هرگز call نمی‌فروشد) |

---

## ۲. مدل داده فعلی

### جدول‌های واقعی و پرشده (بررسی زنده DB — ۲۰۲۶-۰۹-۱۶)
**`brsapi_option_snapshots`** (مدل: `brsapi/models/tsetmc.py` → `OptionSnapshotModel`) — منبع: BrsApi `/Tsetmc/Option.php`
- تعداد ردیف: **۸۴۱٬۹۸۸** · بازه: `2026-07-15 07:53` تا `2026-09-16 08:50` · **۲٬۴۵۷** نماد متمایز · **۲۵** دارایی پایه متمایز
- یک ردیف = یک قرارداد در یک سیکل sync (~۵ دقیقه در ساعات بازار)
- ۶۰+ ستون؛ گروه‌های اصلی: `ins_id, symbol, name, isin, underlying_symbol/id, option_type, contract_size, strike_price, open_interest, date_begin, date_end, days_remaining, sector, underlying_price_* (۵ ستون), price_* (min/max/yesterday/first/last/close + change), trade_count/volume/value, notional_value, buy/sell_real/legal_* (۸ ستون), bid_count/volume/price_1..5 و ask_*_1..5 (۳۰ ستون), time, fetched_at, raw_json`
- **Greeks و IV در این جدول ذخیره نمی‌شوند.**

**`brsapi_ime_options`** (مدل: `brsapi/models/ime.py` → `ImeOptionModel`) — منبع: BrsApi `/IME/Option.php`
- تعداد ردیف: **۹۴٬۱۸۵** · همان بازه زمانی · ساختار «یک ردیف به ازای هر Strike» با جفت call/put: `strike_price, level_strike, call_contract_code, call_contract_size, call_date_end, call_days_remaining, call_margin_initial/required, call_open_interest, call_price_*, call_bid/ask_*_1..3` و همان مجموعه برای `put_*`.

**نمونه داده واقعی (عیناً از DB زنده):**
```json
{"symbol": "ضسپا6047", "underlying_symbol": "خساپا", "option_type": "call", "contract_size": "1000",
 "strike_price": "750.0", "price_last": "1.0", "price_close": "3.0", "trade_volume": "11196298",
 "open_interest": "5546365", "days_remaining": "0", "date_end": "1405-06-25",
 "underlying_price_last": "755.0", "fetched_at": "2026-09-16 08:50:58"}

{"symbol": "ضخود7138", "underlying_symbol": "خودرو", "option_type": "call", "contract_size": "1000",
 "strike_price": "900.0", "price_last": "10.0", "price_close": "10.0", "trade_volume": "9429529",
 "open_interest": "20516098", "days_remaining": "14", "date_end": "1405-07-08",
 "underlying_price_last": "737.0", "fetched_at": "2026-09-16 08:50:58"}

{"symbol": "ضسپا6046", "underlying_symbol": "خساپا", "option_type": "call", "contract_size": "1000",
 "strike_price": "700.0", "price_last": "40.0", "price_close": "31.0", "trade_volume": "6502834",
 "open_interest": "2494033", "days_remaining": "0", "date_end": "1405-06-25",
 "underlying_price_last": "755.0", "fetched_at": "2026-09-16 08:50:58"}
```
```json
// IME (brsapi_ime_options)
{"contract_category_commodity": "LG ETC", "strike_price": "700000.0",
 "call_contract_code": "TLDY05C70", "call_price_last": "726603.0", "call_open_interest": "488615",
 "put_contract_code": "TLDY05P70", "put_price_last": "0.0", "put_open_interest": "0",
 "call_date_end": "1405-10-27"}
{"contract_category_commodity": "SilverBar", "strike_price": "2400000.0",
 "call_contract_code": "SLAZ05C240", "call_price_last": "2022099.0", "call_open_interest": "508803",
 "put_contract_code": "SLAZ05P240", "put_price_last": "0.0", "put_open_interest": "0",
 "call_date_end": "1405-09-28"}
```

### جدول‌های ORM آپشن — `models/option.py` (همه خالی، ۰ ردیف)
| مدل | جدول | فیلدهای کلیدی | وضعیت |
|---|---|---|---|
| `OptionContractModel` | `option_contracts` | `id PK, symbol unique, underlying_symbol, underlying_isin, option_type, strike_price, expiry_date, contract_size, currency, style, settlement_mode, asset_class, is_active, isin, market` | ۰ ردیف — **بدون migration Alembic** |
| `OptionSnapshotModel` | `option_snapshots` | `contract_id FK, date, OHLC, settlement/last, volume, open_interest, bid/ask, implied_volatility, delta, gamma, theta, vega, rho, underlying_price, block_volume, meta JSONB` | ۰ ردیف — بدون migration |
| `OptionTradeModel` | `option_trades` | `contract_id FK, date, time, side, quantity, price, value, is_block_trade, meta` | ۰ ردیف — بدون migration |
| `OpenInterestHistoryModel` | `open_interest_history` | `contract_id FK, date, open_interest, change_oi, change_pct` | ۰ ردیف — بدون migration |
| `VolatilitySurfaceModel` | `volatility_surface` | `underlying_symbol, date, strike, expiry_date, days_to_expiry, moneyness, implied_volatility, option_type` | ۰ ردیف — بدون migration |
| `CorporateActionModel` | `corporate_actions` | `symbol, action_type, ex_date, record_date, params JSONB, applied, source, raw_text` | ۰ ردیف — بدون migration |

> این ۶ جدول توسط `scripts/fix_schema_gap.py` به‌صورت idempotent (`table.create`) ساخته شده‌اند، نه Alembic. `scripts/generate_db_readme.py` آن‌ها را «نسخه قدیمی» برچسب می‌زند و می‌گوید داده واقعی آپشن در `brsapi_option_snapshots` است.

### جدول‌های Legacy
| جدول | منبع DDL | ردیف زنده | نویسنده فعلی |
|---|---|---|---|
| `options` (`StockOptionModel`, `models/market_data.py`) | migration `0001_initial_schema.py` | **۳٬۲۲۵** | **یافت نشد** (فقط خوانده/گزارش می‌شود) |
| `commodity_options` (`CommodityOptionModel`) | migration `0001` | **۴۷۶** | **یافت نشد** |

### جدول‌های پیشنهادی سند مشخصات vs واقعیت
| جدول سند | واقعیت کدبیس |
|---|---|
| `option_contracts` | **جدول هم‌نام وجود دارد ولی خالی است** و schema آن با سند یکی نیست (سند: `BIGSERIAL, contract_symbol UNIQUE, option_type VARCHAR(4), strike_price NUMERIC, expiry_date DATE, contract_size INT DEFAULT 1`). هیچ `contract_symbol` و `underlying_price` در آن نیست. |
| `option_market_data` | **یافت نشد** (نه جدول، نه مدل، نه migration) |
| `option_strategy_templates` | **یافت نشد** — استراتژی‌های آماده فعلاً hardcoded در `services/options_service.py` هستند، نه جدول |
| `saved_payoff_scenarios` | **یافت نشد** |

### سایر جدول‌های مرتبط با سند (برای مرجع)
- کاربران: `users` (`models/user.py`) — `roles` به‌صورت string comma-separated، `totp_*` برای MFA.
- واچ‌لیست: **بدون migration** — در runtime با `CREATE TABLE IF NOT EXISTS` در `services/watchlist_service.py` ساخته می‌شود.
- دارایی پایه/قیمت: `symbols`, `quotes`, `daily_history`, `candlesticks` (migration `0001`).
- صندوق/کالا/اخبار: طبق `docs/CODEBASE_DISCOVERY_2026-09-16.md`.

---

## ۳. منابع داده خارجی (APIها)

### آپشن — منابع موجود
| منبع | پروتکل | جزئیات | فایل |
|---|---|---|---|
| **BrsApi `/Tsetmc/Option.php`** (منبع اصلی زنجیره بورس) | REST GET | `https://api.brsapi.ir` + پارامتر `key` (`BRSAPI_API_KEY`)؛ rate رسمی `3/10s` (18/min) | `brsapi/config.py:115` (`OPTION = EndpointConfig(...)`)، `brsapi/client.py` |
| **BrsApi `/IME/Option.php`** (آپشن کالا) | REST GET | همان دامنه؛ rate `2/10s` (12/min) | `brsapi/config.py:209`، `brsapi/parsers/ime.py:parse_options` |
| **TSETMC CDN مستقیم** (جایگزین) | REST GET | `https://cdn.tsetmc.com/api/Option/GetOption/{ins_id}` — ثبت‌شده در ingestion ولی **شواهد اجرا/داده ذخیره‌شده یافت نشد** | `ingestion/sources/derivatives.py:14-49`، `ingestion/main.py` (`tsetmc_options`) |

- **نمونه درخواست واقعی:** `GET https://api.brsapi.ir/Tsetmc/Option.php?key=<BRSAPI_API_KEY>` — پارسر خام را در `brsapi/parsers/tsetmc.py:parse_options` به فیلدهای داخلی map می‌کند (`l18→symbol`, `base_l18→underlying_symbol`, `price_strike→strike_price`, `interest_open→open_interest`, `date_end`, `day_remain`, `tvol/tval`, سطوح `zd/qd/pd` و `zo/qo/po` → سفارش‌ها).
- **نمونه JSON فیکسچر ذخیره‌شده: یافت نشد** (`tests/fixtures/brsapi/option_sample.json` که در `docs/phase0/0-5_BrsApiMapping.md` وعده داده شده وجود ندارد). نزدیک‌ترین نمونه واقعی، ستون `raw_json` در جدول `brsapi_option_snapshots` است.
- **Greeks از منبع:** **در payload برساپی وجود ندارد** (ستون‌های d/g/t/v نه در parser و نه در جدول) → باید داخلی محاسبه شود (پیاده‌سازی موجود است، بخش ۹).
- **API Key:** فقط نام `BRSAPI_API_KEY` (مقدار در `.env` — گزارش نمی‌شود).

### سایر منابع (خلاصه کاوش)
| نیاز | منبع واقعی | وضعیت |
|---|---|---|
| قیمت سهام | BrsApi (`/Tsetmc/AllSymbols.php`, `/Symbol.php`, `/Index.php`, ...) + TSETMC CDN (`services/tsetmc_client.py`, `ingestion/sources/tsetmc.py`) | فعال |
| NAV صندوق | BrsApi `/Tsetmc/Nav.php` + Fipiran (`fund.fipiran.ir/api/v1/funds`) | فعال |
| کدال | BrsApi `/Codal/Announcement.php` + `search.codal.ir/api/search/v2/q` | فعال |
| دلار/طلا | BrsApi `/Market/Gold_Currency(_Pro).php` + گزینه TGJU (scrape، `src/gold_desk/secondary_source.py`) + Nobitex | فعال |
| **نقره** | منبع اختصاصی: **یافت نشد** (فقط `XAGUSD` در catalog و آپشن کالای IME با دسته `SilverBar` در `brsapi_ime_options`) | نامشخص |
| اخبار | ۳۹ فید RSS داخلی (`providers/news/domestic/rss_domestic_provider.py`) + BrsApi `/Market/News.php` | فعال |
| بازار کالا / IME | BrsApi `/IME/Futures|Option|Certificate|Fund|Physical.php` + `/Market/Commodity.php` | فعال |
| رمزارز | BrsApi `/Market/Cryptocurrency.php` + Nobitex/Wallex/Ramzinex + Tabdeal | فعال |
| WebSocket خارجی | **یافت نشد** (فقط WS داخلی `apps/api/endpoints/websocket.py`) | — |
| GraphQL | **یافت نشد** | — |

- منابع stub (نباید مبنای کار باشند): `providers/macro/fx|gold|commodities|metals/*` روی `api.example.com`، `providers/news/foreign/*`، `providers/funds/client.py` با fallback داده MOCK.
- کلیدهای env موجود (فقط نام): `BRSAPI_API_KEY`, `SECRET_KEY`, `ENCRYPTION_KEY`, `SENTRY_DSN`, `SMTP_*`, `FIPIRAN_API_KEY` (تعریف‌شده در Settings ولی غایب در `.env`ها), `CODAL_API_KEY` (خالی), `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` (تعریف‌شده، بدون مقدار در env). برای Tabdeal هیچ نام env معتبری bind نشده (کد با `getattr(settings, "tabdeal_api_key", "")` می‌خواند) → **یافت نشد**.

---

## ۴. Endpointهای API فعلی

### ۴.۱. روتر آپشن — موجود ولی غیرفعال (مهم‌ترین یافته)
`apps/api/endpoints/options.py` — `router = APIRouter()` بدون prefix، **۲۶ روت** (کاملاً تأییدشده با شمارش):

| # | متد | مسیر (نسبی) | منبع داده |
|---|---|---|---|
| ۱ | GET | `/strategies` | ۳۰ استراتژی hardcoded در `services/options_service.py` |
| ۲ | POST | `/analyze` | محاسبه خالص (۱۶ استراتژی از ۳۰ پشتیبانی کامل) |
| ۳ | POST | `/recommend` | محاسبه خالص |
| ۴ | GET | `/greeks` | `domain/options/pricing.py` (Black-Scholes خالص) |
| ۵ | GET | `/pricing` | همان |
| ۶–۱۴ | GET | `/reference/{selection-guide,mistakes,glossary,references,examples,syllabus,iran-rules,stats,formulas}` | داده ثابت `services/options_reference.py` |
| ۱۵ | GET | `/analytics/arbitrage/parity` | `services/options_analytics.py` (r=0.15 ثابت) |
| ۱۶ | POST | `/analytics/arbitrage/scan` | محاسبه خالص |
| ۱۷ | POST | `/analytics/volatility` | محاسبه خالص (نکته: `stock_price` به‌صورت query اجباری است ولی فرانت در body می‌فرستد → در صورت mount، 422) |
| ۱۸ | POST | `/analytics/portfolio` | محاسبه خالص (همان مشکل query/body) |
| ۱۹–۲۳ | POST | `/professional/{costs,position-sizing,iv-rank,chain-analysis,checklist}` | محاسبه خالص / ثابت |
| ۲۴ | GET | `/live/chain/{underlying}` | **DB واقعی**: raw SQL روی `brsapi_option_snapshots` (top volume، volume/price>0) |
| ۲۵ | GET | `/live/symbols` | **DB واقعی**: aggregate روی `brsapi_option_snapshots` |
| ۲۶ | GET | `/professional/iran-costs` | ثابت‌های بازار ایران |

**وضعیت mount:** در `apps/api/router.py` هیچ import/`include_router` برای `options` وجود ندارد (`grep` روی `options_router|endpoints.options` → هیچ؛ `apps/api/endpoints/__init__.py` هم آن را در `__all__` ندارد).
**تأیید زنده (API در حال اجرا):** `GET /api/v1/options/strategies` → **404**، `/api/v1/options/live/symbols` → **404**، `/api/v1/options/live/chain/خودرو` → **404**.

### ۴.۲. مسیرهای آپشن که واقعاً کار می‌کنند (mount شده)
| Endpoint | وضعیت زنده |
|---|---|
| `GET /api/v1/multi-market-signals?market=option` | **200** — گزارش `option: success, signal_count=3, data_available=true, source=options_pcr_analysis` (موتور `services/multi_market_signal_engine.py:_signals_options` روی `brsapi_option_snapshots`) |
| `POST /api/v1/brsapi/manage/sync/option` و `/sync/ime-options` | mount در `apps/api/endpoints/brsapi.py` — sync واقعی برساپی |
| `GET /api/v1/brsapi/manage/sections` | ۲۰۰ — شامل `option` ("Options") و `ime-options` (البته `record_count:0` تخمین stale است؛ واقعیت ۸۴۱٬۹۸۸) |
| `GET /api/v1/brsapi/manage/download/{section_id}` | mount — خروجی JSON/CSV از DB (`option` در بررسی ما HTTP 500 داد؛ نیاز به بررسی) |
| `GET /api/v1/forecast` | ۲۰۰ — تب «پیش‌بینی» فرانت (اختصاصی آپشن نیست) |

### ۴.۳. فراخوانی‌های فرانت‌اند آپشن (همه به روتر mount نشده می‌خورند)
- `frontend/src/lib/api.ts`: `API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1'`
- `OptionsDashboard` → `GET /options/live/symbols` + `GET /options/strategies` → ۴۰۴
- `StrategyAnalyzer` → `GET /options/strategies` + `POST /options/analyze` → ۴۰۴
- `LiveChainPanel` → `GET /options/live/chain/{underlying}?limit=50` (refetch 15s) → ۴۰۴
- `AnalyticsPanel` → `GET /options/greeks`, `GET /options/analytics/arbitrage/parity`, `POST /options/analytics/volatility|portfolio` → ۴۰۴ (+ باگ body/query)
- `ProfessionalTools` → ۴ روت `POST /options/professional/*` → ۴۰۴
- `LearnPanel` → ۵ روت `/options/reference/*` → ۴۰۴
- دو صفحه `markets/options-market` و `markets/search` از مسیر `GET /api/v1/options/...` استفاده می‌کنند در حالی که base آن‌ها `/api/v1` است → **باگ double-prefix** (`/api/v1/api/v1/options/...`).

### ۴.۴. سایر prefixهای مرتبط (فهرست کوتاه)
`/api/v1/funds` (+`/funds/v2`)، `/stocks/v2`، `/market`، `/market-dashboard`، `/market-watch`، `/brsapi`، `/ime` (روتر IME هم **mount نشده**)، `/gold` (mount نشده)، `/news`، `/codal`، `/screener*`، `/signals` (user+)، `/portfolios` (user+)، `/watchlist`، `/backtests`، `/paper-trading`، `/ws/market` و `/ws/precompute` (WebSocket).
- نکته: `apps/api/endpoints/ime.py` (شامل `/ime/options`) هم مثل options و gold **mount نشده** است.

---

## ۵. نمونه داده واقعی

- **فیکسچر/seed اختصاصی آپشن: یافت نشد.** `tests/fixtures/` شامل `sample_news.py`, `sample_backtests.py`, `sample_codal.py`, `sample_instruments.py`, `sample_macro.py`, `sample_ml_runs.py`, `sample_orderbooks.py` است ولی فیکسچر آپشن ندارد. `tests/fixtures/brsapi/*option*` هم یافت نشد.
- **نمونه واقعی زنجیره:** همان ۳ ردیف `brsapi_option_snapshots` و ۲ ردیف `brsapi_ime_options` در بخش ۲ (مستقیماً از DB زنده).
- `test_options.py` (ریشه، ۳۷۷ خط؛ نسخه قدیمی‌تر ۳۱۱ خطی در `tests/legacy/root/`) اسکریپت smoke تست ۴ provider خارجی است (`algotik-tse`, `pytsetmc-api`, BrsApi History, tsetmc.com) و خروجی‌ها را در `test_results/*.json` می‌نویسد؛ نتایج ذخیره‌شده `algotik` وضعیت `failed` (ImportError) دارند. این فایل توسط pytest اجرا نمی‌شود.
- seed اسکریپت‌های موجود: `scripts/seed_funds.py`, `scripts/seed_architecture.py`, `scripts/seed_decisions.py` — **seed آپشن: یافت نشد**.

---

## ۶. سیستم احراز هویت و نقش‌ها

- **مکانیزم:** JWT (HS256) — access token (پیش‌فرض ۶۰ دقیقه) + refresh token (پیش‌فرض ۳۰ روز، تنها از کوکی httpOnly با نام پیش‌فرض `im_refresh` خوانده می‌شود) + revocation با `jti` در Redis (`core/security/tokens.py`).
- **هش پسورد:** PBKDF2-HMAC-SHA256، ۱۰۰٬۰۰۰ دور (`core/security/hashing.py`)؛ bcrypt در کد **یافت نشد** (فقط در تنظیمات).
- **MFA/TOTP:** پیاده‌سازی‌شده (ستون‌های `totp_secret/enabled/confirmed_at`, `mfa_method` در `users`) + روت‌های `/mfa/*`.
- **نقش‌ها (سه سیستم موازی):**
  - `core/enums/rbac.py` → **`admin`, `analyst`, `user`, `viewer`** با سلسله‌مراتب و `admin` bypass؛ پیش‌فرض کاربر جدید `["viewer"]`.
  - `core/security/ime_rbac.py` → **`viewer`, `trader`, `quant`, `admin`** (نقش‌های عملیاتی IME + جداسازی وظایف).
  - `apps/funds/auth.py` → **`guest`, `user`, `analyst`, `admin`**.
- **اعمال:** `apps/api/dependencies.py` → `require_role` / `require_roles`؛ mountهای `/jobs`، `/tables`، `/data-import`، `/dashboard` (admin)، `/signal-insights` (analyst/admin)، `/signals` و `/portfolios` (user/analyst/admin).
- **ادمین پنل:** اپ مستقل `apps/admin/` روی prefix `/admin` (dashboard, jobs, providers, models, backtests, audit).
- **فرانت:** `frontend/src/middleware.ts` فقط وجود کوکی را چک می‌کند؛ کامپوننت `RoleGate.tsx` وجود دارد ولی **در هیچ صفحه‌ای استفاده نشده**؛ access token در حافظه ماژول (نه localStorage).

---

## ۷. زیرساخت اجرای Job/Scheduler

- **APScheduler** (`AsyncIOScheduler`، timezone پیش‌فرض `Asia/Tehran`) در `apps/scheduler/app.py`؛ ورودی `python -m apps.scheduler`.
- **JobStore:** `jobstores` سفارشی **یافت نشد** → پیش‌فرض **MemoryJobStore** (با ری‌استارت از دست می‌رود). قفل توزیع‌شده `jobs/locking.py` (Redis + fallback in-memory). صف اختیاری Redis با `JOB_QUEUE_ENABLED` (`jobs/queue_publisher.py`, `jobs/queue_consumer.py`, `apps/worker/consumer.py`).
- **جاب‌های مرتبط با آپشن (واقعی و فعال):**
  | Job | نام | Trigger | شرط |
  |---|---|---|---|
  | sync زنجیره بورس | `brsapi_options` | `_EVERY_5_MIN` | `market_hours_only=True` — تأیید مستقیم `brsapi/jobs/registry.py:144` |
  | sync آپشن کالا | `brsapi_ime_options` | هر ۵ دقیقه | بازار |
  | (تکمیلی) سایر syncهای برساپی | all_symbols/index هر ۱۲۰s، codal هر ۹۰۰s، ... | `brsapi/jobs/registry.py` | — |
- جاب‌های ماژولار دیگر: `jobs/definitions/` (fund_jobs, news_jobs, market_data_jobs, ...)؛ جاب‌های داخل lifespan خود API: orchestrator هر ساعت، fund sync هر ۱۵ دقیقه (ساعات بازار).
- **Audit/دانش اجرا:** جدول `job_runs` (`models/job_run.py`) وجود دارد ولی **migration Alembic برای آن یافت نشد** (دسترسی با SQL خام در `apps/api/endpoints/jobs.py`). جدول پیشنهادی سند `ingestion_run_logs` **یافت نشد**؛ معادل واقعی: `job_runs` و `fund_ingestion_runs` (این یکی migration دارد و ساخته می‌شود).
- اجرای عملکردی مرتبط: Celery فقط در `precompute/workers/celery_tasks.py` (lazy, بدون Beat) — **Celery Beat یافت نشد**.

---

## ۸. ابزار Logging / Monitoring / Testing موجود

| لایه | وضعیت واقعی |
|---|---|
| Logging | **structlog** (`core/logging/__init__.py`: JSON در production، متن در dev، `SafeStreamHandler` برای Windows، correlation-id، audit logging) |
| Error tracking | **Sentry** (`core/observability_sentry.py`, env-guarded با `SENTRY_DSN`؛ فرانت `@sentry/nextjs`) |
| Metrics | **Prometheus** — روت `/metrics` (`apps/api/metrics.py`) + `prometheus.yml` ریشه (job مربوط به ingestion)؛ سرویس Prometheus/Grafana در compose **یافت نشد** |
| Tracing | OpenTelemetry SDK + OTLP exporter (`integrations/observability/otel_exporter.py`) — **به startup هیچ اپی وصل نشده (یافت نشد)** |
| تست بک‌اند | pytest + pytest-asyncio — **۳۵۸ فایل** `test_*.py`؛ `tests/unit/options/` با **۱۱ فایل**: `test_greeks.py`, `test_options_comprehensive.py`, `test_phase2_ci.py`, `test_ime_pricing_engine.py`, `test_ime_signal_factory.py`, `test_ime_slippage_simulator.py`, `test_margin_engine.py`, `test_var_calculator.py`, `test_monte_carlo.py`, `test_commodity_pricing_guards.py`, `test_tier2_prediction.py` — **تست اختصاصی موتور Payoff: یافت نشد**؛ **تست برای `apps/api/endpoints/options.py`: یافت نشد** |
| تست فرانت | Vitest + Testing Library + jsdom — **۲۵ فایل** test/spec |
| CI/CD | ۶ workflow: `ci.yml` (ruff/mypy/tsc/hadolint + pytest با Postgres&Redis + build/push/Trivy)، `ci-pr.yml`، `fund-service.yml`، `decision-engine.yml`، `release.yml`، `secrets-scan.yml` (gitleaks) |
| Health | `/api/v1/health` (تأیید زنده: 200) + جداول `provider_health` + صفحه `/data-health` |

---

## ۹. بدهی فنی و نکات هشدار (اولویت‌دار برای ماژول آپشن)

1. **روتر آپشن mount نشده (بزرگ‌ترین ریسک):** ۲۶ روت کامل + UI ۷ تبی فرانت + موتور استراتژی، همه آماده‌اند ولی در `apps/api/router.py` ثبت نشده‌اند. هر برنامه‌ای برای ماژول باید اول این شکاف را ببندد (mount کردن) یا نسخه جدید بسازد؛ مستندات `OPTIONS_MARKET_REPORT.md` و `docs/CODEBASE_DISCOVERY_2026-09-16.md` این ۲۶ روت را «فعال» فرض کرده‌اند که با واقعیت اجرا (۴۰۴) نمی‌خواند.
2. **سه خانواده موازی ذخیره آپشن:** `brsapi_option_snapshots` (واقعی و پرشده) / `option_contracts`+`option_snapshots`+... (ORM، خالی، بدون Alembic) / `options`+`commodity_options` (Legacy migration 0001، بدون نویسنده). سیاست «منبع واحد حقیقت» باید تیم تعیین کند؛ جدول‌های پیشنهادی سند با هیچ‌کدام دقیقاً منطبق نیستند.
3. **`option_contracts` و ۵ جدول هم‌خانواده migration ندارند** — با `scripts/fix_schema_gap.py` و `create_all` ساخته شده‌اند (schema drift). هر migration جدید روی این جدول‌ها باید idempotent/سازگار نوشته شود.
4. **Greeks/IV ذخیره نمی‌شوند:** نه در `brsapi_option_snapshots` می‌آیند و نه جایی محاسبه و persist می‌شوند. پیاده‌سازی‌های محاسبه موجودند (`domain/options/pricing.py`, `greeks.py`, `higher_order_greeks.py`, `commodity_pricing.py`, `domain/decision_engine_v5/pricing_tiered.py`).
5. **نرخ بدون ریسک ثابت و پراکنده:** `0.15` در `services/options_service.py:48` و `services/options_analytics.py` و پیش‌فرض API؛ `0.30` در `src/gold_desk/black76.py:28`؛ `0.23` در `services/fund_quant_engine.py:29`؛ جداول تاریخی در `backtesting/metrics/risk_free_rate.py:70` و `dynamic_risk_free.py`. منبع زنده اخزا وجود ندارد: ستون `market_macro_indicators.akhzar_ytm` (`models/stock_enterprise.py:228`) ساخته شده ولی **جدول خالی است** و فرانت صریحاً گفته اخزا در BrsApi موجود نیست (`frontend/src/app/markets/bonds/page.tsx:153`).
6. **کیفیت داده آپشن و Backfill:** داده تاریخی از ۲۰۲۶-۰۷-۱۵ (حدود ۲ ماه) موجود است؛ ولی «آخرین وضعیت» و «تاریخچه» در یک جدول insert-only جمع شده‌اند و view/جدول خلاصه آخرین وضعیت (مطابق سند بخش ۱۶) **یافت نشد**. مانیتورینگ کیفیت اختصاصی آپشن (OI منفی، Strike غیرمنطقی، هشدار عدم به‌روزرسانی) هم **یافت نشد**؛ فقط زیرساخت عمومی `monitoring/` و `brsapi/raw_validation.py` موجود است.
7. **باگ‌های API موجود حتی در صورت mount:** `POST /analytics/volatility|portfolio` پارامتر `stock_price` را query می‌گیرند ولی فرانت در body می‌فرستد (۴۲۲)؛ کلیدهای پاسخ (`average_iv`/`historical_vol`) با تایپ فرانت (`implied_volatility`/`historical_volatility`) نمی‌خواند؛ دو صفحه markets با double-prefix `/api/v1/api/v1/options` صدا می‌زنند؛ `POST /analyze` برای ۱۴ استراتژی `TypeError` می‌دهد (swallow شده به `success=false`).
8. **بک‌تست آپشن اسکلت است:** ۶ استراتژی در `backtesting/strategies/options/` (مثلاً `covered_call_strategy.py` فقط سهم می‌خرد و call نمی‌فروشد؛ پارامترهای `call_strike/call_premium` بی‌استفاده). داده تاریخی آپشن به این استراتژی‌ها وصل نشده.
9. **payoff سمت فرانت و بک:** `PayoffDiagram` در `frontend/src/app/options/components/helpers.tsx` نقاشی SVG می‌کند و `profit_at_expiry` فقط برای ۹ استراتژی در `services/options_service.py` پر می‌شود؛ یک **تابع خالص مشترک payoff** مطابق سند بخش ۳.۱ با تست مرجع **یافت نشد** (فقط محاسبات پراکنده در domain).
10. **موارد عمومی اثرگذار:** دو migration با شماره `0042`؛ `watchlist` بدون migration؛ `job_runs`/`audit_logs` بدون migration؛ کپی کهنه `_FRONTEND_BACKEND_COPY/` در ریپو؛ ۴۱۳ بلاک `except Exception` در `services/` (۲۴ مورد `pass` خاموش)؛ JobStore حافظه‌ای APScheduler؛ `apps/api/endpoints/ime.py` و `gold.py` هم mount نشده‌اند.

### ابهام‌های نیازمند تصمیم تیم (طبق قانون طلایی)
| # | ابهام | گزینه‌ها |
|---|---|---|
| ۱ | منبع واحد داده آپشن | (الف) `brsapi_option_snapshots` به‌عنوان source of truth + view خلاصه؛ (ب) پر کردن `option_contracts/option_snapshots` از برساپی با یک mapper؛ (ج) جدول‌های جدید سند (`option_market_data`, ...) |
| ۲ | نرخ بدون ریسک | **تصمیم تیم (۲۰۲۶-۰۹-۱۶): ثابت config با پیش‌فرض ۰٫۱۵** (هماهنگ با `services/options_service.py:48`) |
| ۳ | سرنوشت روتر فعلی | **تصمیم تیم (۲۰۲۶-۰۹-۱۶): mount همان روتر در `router.py` + افزودن مسیرهای جدید سند به‌صورت افزودنی** |
| ۴ | Greeks | محاسبه داخلی (Black-Scholes موجود) با IV ضمنی داخلی — تأیید کارشناس مالی تیم |
| ۵ | Payoff محاسبه سمت سرور یا کلاینت | موتور خالص مشترک مطابق سند + endpoint `/payoff-calculator` در برابر تکیه بر `profit_at_expiry` فعلی |

---

## ضمیمه A — پاسخ مستقیم به سوالات باز و جاهای `[پر کن]` سند آپشن

1. **نرخ بدون ریسک (سند بخش ۳.۲، `[پر کن]` خط ۱۲۸):** منبع زنده‌ای در کد وجود ندارد؛ نرخ‌ها ثابت‌اند: `0.15` (`services/options_service.py:48`، `services/options_analytics.py`، پیش‌فرض پارامتر `r` در API)، `0.30` (`src/gold_desk/black76.py:28`)، `0.23` (`services/fund_quant_engine.py:29`)، جداول تاریخی `0.15–0.30` (`backtesting/metrics/risk_free_rate.py`). ستون اخزا (`market_macro_indicators.akhzar_ytm`) خالی است و فرانت گفته داده اخزا در دسترس نیست. **تصمیم تیم لازم است؛ تا آن زمان پیشنهاد: پارامتر قابل تنظیم با پیش‌فرض ۰٫۱۵.**
2. **داده تاریخی قیمت آپشن (سند بخش ۴، `[پر کن]` خط ۱۴۰):** **بله، موجود است** — `brsapi_option_snapshots` با ۸۴۱٬۹۸۸ ردیف از ۲۰۲۶-۰۷-۱۵ تا ۲۰۲۶-۰۹-۱۶ (~۲ ماه، هر ~۵ دقیقه در ساعات بازار) و `brsapi_ime_options` با ۹۴٬۱۸۵ ردیف. Greeks/IV ذخیره نشده‌اند. بک‌تست باید بر پایه اسنپ‌شات‌ها طراحی شود.
3. **Greeks از منبع یا محاسبه داخلی (سوال باز ۱):** در payload برساپی **نیست** → محاسبه داخلی؛ پیاده‌سازی Black-Scholes/Black-76/IV از قبل در `domain/options/` و `domain/decision_engine_v5/` و `src/gold_desk/black76.py` موجود است.
4. **داده تاریخی (سوال باز ۲):** همان مورد ۲ — بله برای ~۲ ماه اخیر؛ دوره‌های قدیمی‌تر باید Backfill شوند.
5. **سرچشمه نرخ بدون ریسک (سوال باز ۳):** همان مورد ۱ — فعلاً ثابت؛ فید اخزا وجود ندارد.
