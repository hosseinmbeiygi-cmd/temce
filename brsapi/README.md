# BrsApi.ir Integration Module

Complete, production-ready integration with [BrsApi.ir](https://brsapi.ir) — Iran's
comprehensive financial data API provider. Fetches, parses, stores, and serves
realtime and historical data from TSETMC, IME, Codal, global commodities, and
cryptocurrency markets.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Your Application                           │
│  (Backtest, AI, News, Analytics, API endpoints, Dashboards, etc.)  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      BrsApiQueryService                             │
│              Read-optimised access to cached DB data                │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      BrsApiSyncService                              │
│        Orchestrates fetch → parse → store pipeline                  │
└──────┬────────────┬──────────────┬──────────────┬───────────────────┘
       │            │              │              │
       ▼            ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────┐
│ Parser   │ │ Model    │ │ Repository   │ │ SyncLog/Raw  │
│ (raw→dict)│ │ (ORM)    │ │ (bulk insert)│ │ (audit)      │
└──────────┘ └──────────┘ └──────────────┘ └──────────────┘
       ▲                                                  │
       │                                                  ▼
┌──────┴──────────────────────────────────────────────────────────┐
│                      BrsApiClient                               │
│    HTTP client with circuit-breaker, retry, rate limiter, cache │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
                       BrsApi.ir API
                 (https://Api.BrsApi.ir)
```

---

## Directory Structure

```
brsapi/
├── __init__.py              # Package exports
├── config.py                # Endpoint definitions, rate limits, sync intervals
├── client.py                # HTTP client (retry, circuit-breaker, rate-limit)
├── rate_limiter.py          # Token-bucket rate limiter per category
├── parsers/
│   ├── __init__.py
│   ├── tsetmc.py            # TSETMC symbol, index, option, NAV, trade parsers
│   ├── commodity.py         # Global commodity prices (metals, energy)
│   ├── crypto.py            # Cryptocurrency prices
│   ├── ime.py               # IME futures, options, certificates, funds, physical
│   └── codal.py             # Codal announcements
├── models/
│   ├── __init__.py
│   ├── base.py              # BrsApiBase, RawPayloadModel, SyncLogModel
│   ├── tsetmc.py            # 10 ORM models for TSETMC data
│   ├── ime.py               # 5 ORM models for IME data
│   ├── commodity.py         # CommodityPriceModel
│   ├── crypto.py            # CryptoPriceModel
│   └── codal.py             # CodalAnnouncementModel
├── repositories/
│   ├── __init__.py
│   └── base.py              # BulkUpsert, SyncLog, RawPayload repositories
├── services/
│   ├── __init__.py
│   ├── sync_service.py      # Sync orchestration
│   └── query_service.py     # Read-optimised queries
├── jobs/
│   ├── __init__.py
│   └── registry.py          # 13 pre-defined sync jobs for APScheduler
├── migrations/
│   └── 001_create_brsapi_tables.py  # Alembic migration
└── README.md
```

---

## Quick Start

### 1. Get an API Key

1. Go to [https://brsapi.ir](https://brsapi.ir)
2. Request a free API key
3. Add it to your `.env` file:

```env
BRSAPI_API_KEY=your-api-key-here
BRSAPI_BASE_URL=https://Api.BrsApi.ir
BRSAPI_REQUEST_TIMEOUT=30
BRSAPI_MAX_RETRIES=3
BRSAPI_CACHE_ENABLED=true
BRSAPI_ONLY_DURING_MARKET_HOURS=true
```

### 2. Run Database Migration

```bash
alembic upgrade head
```

This creates all 20 BrsApi tables (see model list below).

### 3. Use the Sync Service

```python
import asyncio
from brsapi import BrsApiClient, BrsApiConfig
from brsapi.services import BrsApiSyncService
from core.database import get_session

async def sync_market():
    client = BrsApiClient()
    await client.start()

    async for session in get_session():
        service = BrsApiSyncService(client=client)

        # Sync all TSETMC symbols
        report = await service.sync_all_symbols(session)
        print(f"Symbols: {report.items_count} items in {report.duration_ms:.0f}ms")

        # Sync market indices
        report = await service.sync_index(session, "1")
        print(f"Index: {report.items_count} items")

        # Sync commodity prices
        report = await service.sync_commodities(session)
        print(f"Commodities: {report.items_count} items")

    await client.stop()

asyncio.run(sync_market())
```

### 4. Query the Data

```python
from brsapi.services import BrsApiQueryService
from core.database import get_session

async def query():
    async for session in get_session():
        qs = BrsApiQueryService(session)

        # Top gainers
        gainers = await qs.get_top_gainers(10)
        for g in gainers:
            print(f"{g['symbol']}: {g['price_last_change_pct']:.2f}%")

        # Latest indices
        indices = await qs.get_latest_indices()

        # Commodity prices
        metals = await qs.get_commodity_prices(category="precious_metal")

        # Crypto prices
        crypto = await qs.get_crypto_prices(limit=20)
```

---

## API Endpoints Covered

| Endpoint | Path | Category | Rate Limit | Sync Interval |
|---|---|---|---|---|
| All Symbols | `/Tsetmc/AllSymbols.php` | TSETMC | 30/min | 60s |
| Symbol Detail | `/Tsetmc/Symbol.php` | TSETMC | 30/min | 60s |
| Index | `/Tsetmc/Index.php` | TSETMC | 20/min | 60s |
| NAV | `/Tsetmc/Nav.php` | TSETMC | 20/min | 60s |
| Options | `/Tsetmc/Option.php` | TSETMC | 15/min | 120s |
| Transactions | `/Tsetmc/Transaction.php` | TSETMC | 20/min | 300s |
| History (Price) | `/Tsetmc/History.php?type=0` | TSETMC | 20/min | 3600s |
| History (Real/Legal) | `/Tsetmc/History.php?type=1` | TSETMC | 20/min | 3600s |
| Candlestick | `/Tsetmc/Candlestick.php` | TSETMC | 30/min | 60s |
| Shareholder | `/Tsetmc/Shareholder.php` | TSETMC | 15/min | 3600s |
| IME Futures | `/IME/Futures.php` | IME | 15/min | 60s |
| IME Options | `/IME/Option.php` | IME | 15/min | 60s |
| IME Certificates | `/IME/Certificate.php` | IME | 15/min | 60s |
| IME Funds | `/IME/Fund.php` | IME | 15/min | 60s |
| IME Physical | `/IME/Physical.php` | IME | 10/min | 3600s |
| Commodities | `/Market/Commodity.php` | GLOBAL | 15/min | 60s |
| Crypto | `/Market/Cryptocurrency.php` | GLOBAL | 15/min | 60s |
| Codal | `/Codal/Announcement.php` | CODAL | 20/min | 900s |

---

## Database Tables (20)

| Table | Rows represent | Key columns |
|---|---|---|
| `brsapi_raw_payloads` | Audit trail of raw JSON | endpoint, payload, fetched_at |
| `brsapi_sync_log` | Sync operation history | endpoint, status, items_count, duration_ms |
| `brsapi_symbol_snapshots` | Realtime symbol data | ins_id, symbol, prices, trades, orderbook (5L) |
| `brsapi_symbol_details` | Enriched symbol info | ins_id, fundamentals, sectors, limits |
| `brsapi_index_values` | Market index snapshots | name, value, change, market_value |
| `brsapi_nav_records` | ETF fund NAV | symbol, nav_issue, nav_redemption |
| `brsapi_option_snapshots` | Option contracts | symbol, underlying, strike, greeks |
| `brsapi_intraday_trades` | Trade ticks | symbol, time, volume, price |
| `brsapi_historical_daily` | Daily OHLCV summary | symbol, date, prices, volumes |
| `brsapi_historical_real_legal` | Daily real/legal breakdown | symbol, date, buy/sell real/legal |
| `brsapi_candlesticks` | OHLCV candles | symbol, date, open/high/low/close/volume |
| `brsapi_shareholder_records` | Major shareholders | symbol, name, volume, percent |
| `brsapi_ime_futures` | IME futures contracts | contract_code, prices, open_interest |
| `brsapi_ime_options` | IME option contracts | strike, call/put sides, all fields |
| `brsapi_ime_certificates` | IME depository receipts | contract_code, commodity, prices |
| `brsapi_ime_funds` | IME commodity funds | symbol, prices, trades, real/legal |
| `brsapi_ime_physical_trades` | IME physical trades | symbol, prices, volumes, parties |
| `brsapi_commodity_prices` | Global commodity prices | symbol, price, category, change |
| `brsapi_crypto_prices` | Crypto prices | symbol, price_usd, price_toman, rank |
| `brsapi_codal_announcements` | Codal reports | symbol, title, links, dates |

---

## Rate Limit & Data Management

### How it works

1. **Token-bucket rate limiter**: Each API category (TSETMC, IME, CODAL, commodities, crypto) has its own bucket configured with requests-per-minute limits.

2. **Circuit breaker**: If an endpoint fails 5+ consecutive times, the circuit opens for 30 seconds, preventing any requests until recovery.

3. **Exponential backoff retry**: Failed requests retry with 1.5× backoff, up to 3 retries (configurable).

4. **Dedup via sync log**: Before fetching, the service checks if a recent successful sync exists for the same endpoint. If so, the fetch is skipped (dedup window configurable per endpoint).

5. **Market-hours only** (optional): By default, realtime syncs only run between 08:30 and 15:30 Tehran time — no point polling a closed market.

6. **Raw payload storage** (optional): Raw JSON can be stored for audit with configurable retention (default 30 days auto-purge).

### Configuration

All settings via environment variables with `BRSAPI_` prefix:

```env
# Required
BRSAPI_API_KEY=your-key

# Connection
BRSAPI_BASE_URL=https://Api.BrsApi.ir
BRSAPI_REQUEST_TIMEOUT=30
BRSAPI_MAX_RETRIES=3

# Rate limits (requests per minute, 0 = unlimited)
BRSAPI_RATE_LIMIT_TSETMC=30
BRSAPI_RATE_LIMIT_CODAL=20
BRSAPI_RATE_LIMIT_IME=15
BRSAPI_RATE_LIMIT_COMMODITY=15
BRSAPI_RATE_LIMIT_CRYPTO=15

# Cache
BRSAPI_CACHE_ENABLED=true
BRSAPI_CACHE_TTL_DEFAULT=55

# Market hours
BRSAPI_MARKET_TIMEZONE=Asia/Tehran
BRSAPI_MARKET_OPEN=08:30
BRSAPI_MARKET_CLOSE=15:30
BRSAPI_ONLY_DURING_MARKET_HOURS=true

# Audit
BRSAPI_RAW_PAYLOAD_SINK_ENABLED=false
BRSAPI_MAX_RAW_PAYLOAD_AGE_DAYS=30
```

---

## Integration with Other Systems

### Backtesting

```python
from brsapi.services import BrsApiQueryService

# Get daily price history for backtesting
history = await qs.get_historical_daily(symbol="فملی", limit=365)
# Returns list of dicts with date, open, high, low, close, volume
```

### AI / ML

```python
# Get candlestick data for feature engineering
candles = await qs.get_candlesticks(symbol="فملی", candle_type="3", limit=500)

# Get cross-market features
commodities = await qs.get_commodity_prices()
indices = await qs.get_latest_indices()
crypto = await qs.get_crypto_prices()
```

### News / Analytics

```python
# Get recent codal announcements
announcements = await qs.get_recent_announcements(limit=20)

# Market overview
gainers = await qs.get_top_gainers(10)
losers = await qs.get_top_losers(10)
active = await qs.get_most_active(10)
```

### Pricing Service

```python
# Get realtime price for a symbol
snapshot = await qs.get_symbol_snapshot(symbol="فملی")
# → {symbol, price_last, price_last_change_pct, ...}
```

---

## Adding a New Data Field

The system is designed for extensibility:

1. **New column**: Add a `Mapped` field to the relevant model in `brsapi/models/`.
2. **New parser**: Add parsing logic in the relevant parser class in `brsapi/parsers/`.
3. **Migration**: Create a new Alembic migration with `op.add_column()`.
4. **Query**: Add a method to `BrsApiQueryService` in `brsapi/services/query_service.py`.

No code outside the `brsapi/` package needs to change.

---

## Running Scheduled Jobs

### With APScheduler

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from brsapi.jobs import register_all_brsapi_jobs

scheduler = AsyncIOScheduler()
registry = register_all_brsapi_jobs()
registry.register_with_apscheduler(scheduler)
scheduler.start()
```

### With Celery Beat

```python
# celery_config.py
from celery.schedules import crontab
from brsapi.jobs import BRsAPI_SYNC_JOBS

beat_schedule = {}
for job in BRsAPI_SYNC_JOBS:
    beat_schedule[job.name] = {
        "task": f"brsapi.tasks.sync_{job.name}",
        "schedule": job.cron if isinstance(job.cron, int) else crontab(*job.cron.split()),
    }
```

### Standalone

```python
from brsapi.jobs import register_all_brsapi_jobs

registry = register_all_brsapi_jobs()
report = await registry.run_job("brsapi_all_symbols")
print(f"Synced {report.items_count} symbols")
```
