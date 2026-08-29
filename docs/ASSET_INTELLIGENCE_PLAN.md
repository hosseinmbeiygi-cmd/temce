# پلن پیاده‌سازی Asset Integrity & Portfolio Intelligence

> تاریخ: ۲۰۲۶-۰۸-۳۰  
> وضعیت: **فاز صفر — فقط پلن، بدون کد**  
> پروژه جدید: `C:\Users\Iran\Desktop\asset-intelligence\` (مستقل از temce)

---

## ۱. گزارش بررسی Spec

### ۱.۱ چیست

سامانه Python/FastAPI برای مدیریت و تحلیل چندبازاری:
- **بازارها:** بورس ایران، طلا، دلار/ارز، کریپتو، وجه نقد/سپرده
- **خروجی:** تحلیل اطلاعاتی (نه توصیه خرید/فروش)
- **محورها:** ثبت → موجودی → PnL → ریسک → سناریو → هشدار

### ۱.۲ نقاط قوت Spec

| جنبه | کیفیت |
|---|---|
| تفکیک بازار با `MarketType` + `InstrumentType` | عالی — چندبازاری واقعی |
| جدایی `Instrument` از `Asset` | درست — نماد در DB، نه hardcode |
| `TransactionType` ۱۱ نوع (BUY/SELL/TRANSFER/DIVIDEND/...) | جامع |
| `Provider` پشت Interface + Mock اول | صحیح — قابل توسعه بدون وابستگی |
| Decimal + UTC + Type Hint | الزامی — درست |
| عدم حذف فیزیکی تراکنش، Reverse/Adjustment | حسابداری صحیح |
| ریال/تومان صریح | اهمیت بالا — ایران |
| حباب سکه، چند نرخ دلار، واحد طلا | دقت لازم |
| ۸ امتیاز ریسک + Risk Profile هر بازار | بالغ |
| `ScoringProfile` قابل تنظیم | درست — وزن‌ها hardcode نباشند |

### ۱.۳ ریسک‌ها / ابهامات

| مورد | نکته |
|---|---|
| **PostgreSQL + Redis لازم** | در دسترس بودن سرویس‌ها قبل از شروع باید تأیید شود |
| **حجم کد** | MVP + ۷ فاز ≈ ۷۰ فایل، ~۸۰۰۰ خط، ۶–۱۰ ساعت |
| **Volatility/Annualization** | spec می‌گوید "قابل تنظیم" ولی فرمول نمی‌دهد — تصمیم لازم |
| **Correlation Matrix** | نیاز به تاریخچه قیمت ≥ ۳۰ روز — وابسته به Provider |
| **Reverse تراکنش** | تراکنش معکوس فقط برای برخی انواع معنا دارد (BUY/SELL نه FEE) |
| **Concurrency** | چند کاربر همزمان روی یک Portfolio — `SELECT ... FOR UPDATE` یا optimistic lock |
| **Currency Conversion** | سبد چندارزی نیاز به graph از FX rates (مثلاً IRR→USD→USDT) |

### ۱.۴ تخمین واقع‌بینانه

| فاز | توضیح | تخمین زمان |
|---|---|---|
| ۰ | زیرساخت (همین پلن) | ۱ ساعت (فعلی) |
| ۱ | Infrastructure (Docker, pyproject, FastAPI skeleton, config) | ۱ ساعت |
| ۲ | Domain (enums, VOs, entities, calculations) | ۲ ساعت |
| ۳ | Database (models, repos, UoW, Alembic) | ۲ ساعت |
| ۴ | Transactions & Holdings (API + محاسبات) | ۲ ساعت |
| ۵ | Risk Engine (Scoring, allocations, snapshots) | ۱.۵ ساعت |
| ۶ | Market Data Providers (Interface, Mock, Manual) | ۱.۵ ساعت |
| ۷ | Scenarios & Alerts | ۱.۵ ساعت |
| ۸ | Production (auth, metrics, health, CI, docs) | ۱.۵ ساعت |
| **جمع** | | **~۱۴ ساعت** |

---

## ۲. معماری پیشنهادی (لایه‌ای)

```
API Layer (FastAPI routes)
    ↓ فقط request/response + validation
Application Layer (Services / Use Cases)
    ↓ orchestrates
Domain Layer (Pure Python, no FastAPI/SQLAlchemy)
    ↓ entities, VOs, calculations, risk engine
Infrastructure Layer
    ├── PostgreSQL (SQLAlchemy 2.x async + Alembic)
    ├── Redis (cache, rate-limit, idempotency)
    ├── Market Data Providers (Protocol-based)
    ├── Celery Workers (price refresh, snapshot jobs)
    └── Notifications (alert dispatch)
```

**قواعد سخت‌گیرانه:**
- Routes فقط validation + فراخوانی service (بدون منطق PnL).
- Domain مستقل از FastAPI و SQLAlchemy — قابل import در worker یا CLI.
- Providerها پشت `MarketDataProvider` Protocol؛ Domain فقط Interface می‌شناسد.
- همه تحلیل‌ها `formula_version` + `calculated_at` دارند.
- هیچ hardcode برای وزن، نرخ، نماد، آستانه.

---

## ۳. ساختار پروژه

```
asset-intelligence/
├── app/
│   ├── main.py                    # FastAPI app factory
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── router.py
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── assets.py          # legacy alias for instruments
│   │       ├── instruments.py
│   │       ├── accounts.py
│   │       ├── transactions.py
│   │       ├── portfolios.py
│   │       ├── analyses.py
│   │       ├── scenarios.py
│   │       ├── alerts.py
│   │       └── market_data.py
│   │
│   ├── core/
│   │   ├── config.py              # Pydantic Settings
│   │   ├── database.py            # async engine + session
│   │   ├── security.py            # JWT, password hashing
│   │   ├── logging.py
│   │   ├── exceptions.py
│   │   └── middleware.py
│   │
│   ├── domain/
│   │   ├── enums.py               # MarketType, InstrumentType, TransactionType
│   │   ├── entities.py            # Instrument, Account, Portfolio, Transaction
│   │   ├── value_objects.py       # Money, Currency, Score, Quantity
│   │   ├── calculations.py        # holdings, PnL (avg-cost)
│   │   ├── risk_policies.py       # ScoringProfile, formula constants
│   │   └── errors.py
│   │
│   ├── application/
│   │   ├── instruments/
│   │   ├── accounts/
│   │   ├── transactions/
│   │   ├── portfolios/
│   │   ├── pricing/
│   │   ├── analytics/
│   │   ├── scenarios/
│   │   └── alerts/
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── models.py          # SQLAlchemy ORM
│   │   │   ├── repositories/      # per-entity repos
│   │   │   └── unit_of_work.py
│   │   ├── market_data/
│   │   │   ├── base.py            # Protocol + DTOs
│   │   │   ├── mock_provider.py
│   │   │   ├── manual_provider.py
│   │   │   ├── tsetmc_provider.py
│   │   │   ├── gold_provider.py
│   │   │   ├── forex_provider.py
│   │   │   └── crypto_provider.py
│   │   ├── cache/                 # Redis wrapper
│   │   └── tasks/                 # Celery jobs
│   │
│   └── schemas/                   # Pydantic v2 request/response
│       ├── instruments.py
│       ├── accounts.py
│       ├── transactions.py
│       ├── portfolios.py
│       ├── analyses.py
│       ├── scenarios.py
│       └── alerts.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── Dockerfile
├── docker-compose.yml             # api + postgres + redis + celery + beat
├── pyproject.toml
├── .env.example
├── alembic.ini
└── README.md
```

---

## ۴. مدل داده (DDL چکیده)

```sql
-- Core
instruments        (id, market_type, instrument_type, symbol, display_name,
                    base_currency, quote_currency, exchange_name, issuer_name,
                    counterparty_name, is_physical, is_debt_based, is_active,
                    metadata_json, created_at, updated_at)

accounts           (id, user_id, name, account_type, institution_name,
                    market_type, currency, external_account_reference,
                    is_active, created_at, updated_at)

portfolios         (id, user_id, name, base_currency, description,
                    is_active, created_at, updated_at, deleted_at)

transactions       (id, user_id, portfolio_id, account_id, instrument_id,
                    transaction_type, trade_time, quantity, unit_price,
                    gross_value, fee, tax, net_value, currency, quote_currency,
                    exchange_rate, external_reference, notes,
                    reverses_transaction_id, created_at)

-- Market data
price_observations (id, instrument_id, price, currency, source,
                    observed_at, received_at, is_valid, metadata_json)

fx_rates           (id, base_currency, quote_currency, rate, source,
                    observed_at, received_at)

-- Risk & analytics
scoring_profiles   (id, name, weights_json, is_active, created_at)

risk_profiles      (id, instrument_id, market_type, profile_json, updated_at)

portfolio_snapshots(id, portfolio_id, base_currency, total_value, total_cost,
                    realized_pnl, unrealized_pnl, portfolio_health, risk_level,
                    debt_exposure_ratio, physical_asset_ratio,
                    market_allocation_json, currency_allocation_json,
                    counterparty_allocation_json, asset_breakdown_json,
                    volatility, max_drawdown, correlation_matrix_json,
                    top_risks_json, formula_version, calculated_at)

-- Scenarios
scenarios          (id, name, description, parameters_json, created_by, created_at)

scenario_results   (id, scenario_id, portfolio_id, current_value, projected_value,
                    nominal_pnl, real_pnl, change_in_health,
                    most_affected_markets_json, most_resilient_markets_json,
                    formula_version, calculated_at)

-- Alerts
alerts             (id, user_id, portfolio_id, code, severity, message,
                    triggered_at, acknowledged_at, is_active)

-- Audit
analysis_history   (id, portfolio_id, snapshot_id, calculated_at, formula_version)
```

**Indexها:** `(user_id)`, `(portfolio_id, instrument_id)`, `(instrument_id, observed_at)`, `(trade_time desc)`.

---

## ۵. فرمول‌ها (خلاصه)

### ۵.۱ Holdings (avg-cost)

```
remaining_qty = Σ(BUY/TRANSFER_IN) - Σ(SELL/TRANSFER_OUT)
total_cost    = Σ(BUY) unit_price × qty + Σ fees
avg_cost      = total_cost / remaining_qty   (when remaining_qty > 0)

realized_pnl  = Σ(SELL) (sell_price - avg_cost_at_sale) × qty - sell_fees
unrealized_pnl= remaining_qty × (current_price - avg_cost)   (per instrument)
```

### ۵.۲ Portfolio Health (weighted)

```
Asset Safety Score =
    TrustScore          × 0.25
  + LiquidityScore     × 0.15
  + InflationHedge     × 0.20
  + (1 - Debt)         × 0.15
  + (1 - Volatility)   × 0.15
  + (1 - Counterparty) × 0.10

Portfolio Health = Σ(item_value_i × safety_i) / total_value
```

### ۵.۳ تبدیل چندارزی

```
value_in_base = quantity × price(quote→base currency) × fx_rate(base→portfolio_base)
```
Fallback: BFS در graph FX rates؛ اگر مسیر مستقیم نبود، ۲-hop.

### ۵.۴ Volatility (روزانه، سالانه با ضریب √252)

```
returns_d = Δprice_d / price_{d-1}
vol_annual = std(returns_d) × √252
```

### ۵.۵ Max Drawdown

```
peak = max(history_values)
drawdown = (current - peak) / peak
max_dd = min(drawdown)
```

---

## ۶. API Surface (خلاصه)

| Resource | Method/Path | Auth | Rate-limit |
|---|---|---|---|
| Instruments | POST/GET/GET-by-id/PATCH | user | 30/min |
| Accounts | POST/GET | user | 30/min |
| Transactions | POST/GET/GET-by-id/POST-reverse | user | 60/min |
| Portfolios | POST/GET/GET/PATCH/DELETE | user | 30/min |
| Holdings | GET portfolio + optional instrument | user | 60/min |
| Analysis | POST analyze / GET latest/history / performance / risk | user | 10/min (expensive) |
| Market Data | POST prices / GET latest / history / fx-rates | user (POST) / open (GET) | 30/min |
| Scenarios | POST /simulate / GET result | user | 10/min |

---

## ۷. ۸ فاز — ترتیب اجرا

### فاز ۰ — پلن (همین سند) ✅
- گزارش بررسی spec + معماری + DDL + API surface.

### فاز ۱ — Infrastructure (۱ ساعت)
- `pyproject.toml` (FastAPI, Pydantic v2, SQLAlchemy 2.x async, alembic, redis, celery, httpx, pandas, numpy, pytest, ruff, mypy).
- `app/main.py` با lifespan (db, redis).
- `core/config.py` (Pydantic Settings + .env).
- `core/logging.py` (JSON formatter، حذف اطلاعات حساس).
- `core/exceptions.py` (DomainError، NotFound، Conflict، Validation).
- `core/middleware.py` (request-id, rate-limit per-user, security headers).
- `Dockerfile` + `docker-compose.yml` (api, postgres, redis, celery, beat).
- `.env.example`، `.gitignore`.
- `tests/conftest.py` + اولین smoke test.

### فاز ۲ — Domain (۲ ساعت)
- `enums.py` (MarketType, InstrumentType, TransactionType, AccountType, AlertSeverity).
- `value_objects.py` (Money با currency, Score بین ۰–۱, Quantity با واحد).
- `entities.py` (dataclass Instrument, Account, Portfolio, Transaction).
- `calculations.py`:
  - `apply_transaction(state, txn)` — pure function
  - `compute_holdings(transactions, prices)`
  - `compute_realized_pnl(transactions)`
  - `compute_unrealized_pnl(holdings, current_prices)`
- `risk_policies.py` (ScoringProfile dataclass + default weights).
- `tests/unit/domain/` — محاسبات مالی با Decimal.

### فاز ۳ — Database (۲ ساعت)
- `infrastructure/database/models.py` (SQLAlchemy 2.x async).
- `repositories/instrument.py`, `account.py`, `portfolio.py`, `transaction.py`.
- `unit_of_work.py` (transaction context).
- Alembic init + اولین migration (tables + indexes).
- `tests/integration/test_repos.py` (DB لازم).

### فاز ۴ — Transactions & Holdings (۲ ساعت)
- API: ثبت معامله + گرفتن + معکوس‌سازی.
- Application service: اعتبارسنجی + اجرای calculation + ذخیره.
- محاسبه خودکار `remaining_qty`، `avg_cost`، `realized_pnl` پس از هر تراکنش.
- Snapshot portfolio پس از هر N تراکنش (config).
- تست‌های: خرید ساده، چند خرید، فروش جزئی، انتقال، PnL تحقق‌یافته، ریال/تومان، دلار/تتر.

### فاز ۵ — Risk Engine (۱.۵ ساعت)
- `application/analytics/risk_engine.py`:
  - محاسبه `market_allocation`, `currency_allocation`, `counterparty_allocation`.
  - `physical_asset_ratio`, `debt_exposure_ratio`.
  - `volatility` (از تاریخچه قیمت).
  - `correlation_matrix` (N×N از daily returns).
  - `top_risks` (sorted by severity).
  - `recommendations` (rule-based، no advice).
- ذخیره `portfolio_snapshot`.
- API: `POST /analyze`, `GET /analysis/latest`, `GET /analysis/history`, `GET /performance`, `GET /risk`.

### فاز ۶ — Market Data Providers (۱.۵ ساعت)
- `infrastructure/market_data/base.py`:
  - `Protocol MarketDataProvider` با `get_latest_price`, `get_historical_prices`.
  - `PriceObservation` dataclass.
  - `StaleDataError`, `MissingDataError`.
- `MockMarketDataProvider` (synthetic random walk).
- `ManualMarketDataProvider` (admin inserts via API).
- `tsetmc_provider.py`, `gold_provider.py`, `forex_provider.py`, `crypto_provider.py` — **stubs** با raise NotImplementedError + مستندسازی.
- Cache در Redis با TTL.
- Validation: `price > 0`, `observed_at <= now()`, `is_valid` flag.

### فاز ۷ — Scenarios & Alerts (۱.۵ ساعت)
- `application/scenarios/`:
  - `apply_shocks(holdings, scenario)` — pure function.
  - `simulate_inflation`, `simulate_currency_devaluation`, `simulate_market_crash`.
  - نتیجه: `{current_value, projected_value, nominal_pnl, real_pnl, change_in_health, most_affected_markets, most_resilient_markets}`.
- `application/alerts/`:
  - `evaluate_alerts(snapshot)` — `STALE_PRICE_DATA`, `HIGH_CRYPTO_VOLATILITY`, `CONCENTRATION_RISK`, `MISSING_FX_RATE`.
  - Celery beat job: هر ۱۵ دقیقه ارزیابی.
- API: `POST /scenarios`, `POST /scenarios/{id}/simulate`, `GET /scenarios/{id}/result`, `GET /alerts`.

### فاز ۸ — Production (۱.۵ ساعت)
- `core/security.py` (JWT, password hashing با bcrypt, refresh tokens).
- API `/auth/register`, `/auth/login`, `/auth/refresh`.
- Middleware: `request_id`, `user_context`, `rate_limit_per_user`.
- `GET /health` (DB ping + Redis ping + Provider availability).
- `GET /metrics` (Prometheus format).
- Celery worker + beat (price refresh، alert evaluation).
- `tests/integration/test_auth.py`, `test_security.py`.
- `tests/load/` با `locust` (اختیاری).
- `README.md` (نصب، env vars، migration، اجرا، API).
- `pyproject.toml` با `ruff` + `mypy` strict.
- CI: GitHub Actions (lint + test + migrate).
- `Dockerfile` multi-stage.

---

## ۸. وابستگی‌های حیاتی (قبل از شروع)

| پیش‌نیاز | دلیل | چک |
|---|---|---|
| PostgreSQL 15+ | DB اصلی | `psql --version` + اتصال به localhost:5432 |
| Redis 7+ | Cache + rate-limit + Celery broker | `redis-cli ping` |
| Python 3.12+ | الزام spec | `python --version` |
| Docker (اختیاری) | محیط یکپارچه | `docker --version` |

**اگر PostgreSQL/Redis در دسترس نباشند:** فاز ۳ (DB) و ۵+ (که به تاریخچه قیمت نیاز دارند) block می‌شوند. قبل از شروع فاز ۱، تأیید کنید.

---

## ۹. استراتژی اجرا

1. **هر فاز = ۱ PR.** در پایان هر فاز: تست‌ها سبز + commit + گزارش مختصر.
2. **Test-first برای Domain** (محاسبات مالی قبل از API).
3. **Integration test فقط وقتی DB/Redis بالا باشند.** در غیر این صورت skip با pytest.mark.
4. **Mock Provider پیش‌فرض** تا اتصال واقعی اختیاری بماند.
5. **Reverse transaction:** پیاده‌سازی در فاز ۴ (نه بعد).
6. **Concurrency:** `SELECT ... FOR UPDATE` در transaction registration.

---

## ۱۰. معیار پذیرش MVP (پایان فاز ۴)

- [ ] ثبت Instrument برای ۵ بازار (نمونه‌های spec)
- [ ] ثبت Account در ۳ کارگزاری/صرافی نمونه
- [ ] ثبت Portfolio با base_currency=IRR
- [ ] ثبت حداقل ۱۰ تراکنش (خرید/فروش/انتقال) در ۴ بازار
- [ ] محاسبه صحیح avg-cost، realized/unrealized PnL
- [ ] تست integration: ۴ بازار → allocations صحیح
- [ ] تست security: کاربر A به Portfolio کاربر B دسترسی ندارد
- [ ] Migration اجرا می‌شود
- [ ] Swagger `/docs` باز می‌شود

---

## ۱۱. ریسک‌های اجرا

| ریسک | احتمال | راهکار |
|---|---|---|
| تأخیر در تأمین PostgreSQL/Redis | بالا | فاز ۱-۲ بدون DB شروع شود |
| پیچیدگی Decimal در pandas | متوسط | استفاده از `Decimal` تا مرحله تحلیل، سپس `float` برای std |
| تست‌های financial با اعداد بزرگ flaky | متوسط | استفاده از `Decimal` + `quantize` |
| Cache miss در سناریوهای همزمان | پایین | Idempotency-Key در POST transactions |
| Provider خارجی بلاک شدن | متوسط | Circuit breaker + fallback به Manual |

---

## ۱۲. شروع

برای شروع، تأیید کنید:

1. PostgreSQL + Redis در دسترس (آدرس + پورت + creds).
2. مسیر پروژه: `C:\Users\Iran\Desktop\asset-intelligence\` تأیید است.
3. کد temce دست‌نخورده می‌ماند.
4. Spec نهایی است (اگر تغییری لازم بود، الان بفرستید).

پس از تأیید، فاز ۱ (Infrastructure) شروع می‌شود.
