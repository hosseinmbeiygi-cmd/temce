# Module card: brsapi-client-and-budget

**Name:** brsapi-client-and-budget  
**Path:** `brsapi/client.py` (592), `brsapi/config.py` (540), `brsapi/budget.py` (730), `brsapi/rate_limiter.py` (419), `brsapi/readiness.py` (156) + endpoint configs in `brsapi/config.py` (BrsApiEndpoints)  
**Tier:** 1 (external data ingestion — data correctness + provider key safety; budget governor is the key-protection layer)  
**Purpose:** Async HTTP client for BrsApi.ir (TSETMC/IME/Codal/commodity/crypto/gold-currency endpoints), with per-endpoint configs (rate limits + sync intervals + TTLs + critical flag), a 3-layer rate limiter (daily + 5-min + per-category bucket), a persistent cross-process budget governor (Redis/file/memory), circuit breakers per path, and a key-readiness probe that detects when the key is unblocked.  
**Main files (lines):** client.py (592), config.py (540), budget.py (730), rate_limiter.py (419), readiness.py (156)  
**Files read:** all fully  
**Files unread:** none in this module

## 3.1 Identity

- **Entry points / consumers:**
  - `BrsApiClient` (singleton via `get_client()`) is the main ingestion HTTP client. Used by ingestion services, brsapi jobs, and the readiness probe.
  - `BrsApiEndpoints` (in config.py) is the canonical endpoint catalog (rate limits + intervals + TTLs + required/optional params + critical flag).
  - `BrsApiSettings` (env `BRSAPI_*`) drives client behavior: api_key, base_url, enabled master switch, timeouts, retries, cache TTL, market hours, per-category rate limits, global daily/5-min caps, budget governor settings, backfill chunking config.
  - `BrsApiBudgetGovernor` (singleton via `get_budget_governor()`) is the persistent cross-process key-protection layer.
  - `RateLimiter` (singleton via `brsapi.rate_limiter.get_rate_limiter()`) enforces daily + 5-min + per-category buckets.
  - `readiness.check_and_notify()` is the hourly probe that detects key reset and notifies (Telegram or loud log).
- **Dependencies:** httpx, pydantic/pydantic_settings, redis.asyncio (optional), core.cache (`get_cache()` for Redis client reuse), core.logging, `brsapi.rate_limiter`, `brsapi.budget`, `core.config.settings` (for redis_url).

## 3.2 Logic and algorithms

- **Endpoint catalog** (`BrsApiEndpoints` in config.py):
  - Per-endpoint `EndpointConfig`: path, category, rate_limit_per_minute (derived from official BrsApi.ir docs, e.g. AllSymbols 2/100s ≈ 1.2/min → configured 1; Symbol 3/10s → 18/min; History 4/10s → 24/min), sync_interval_seconds, required/optional/default params, ttl_cache_seconds, critical flag.
  - Categories: TSETMC, CODAL, IME, COMMODITY, CRYPTOCURRENCY.
  - Sync intervals: REALTIME_FAST=15, REALTIME=30, REALTIME_SLOW=60, MODERATE=300, HOURLY=3600, DAILY=86400, WEEKLY=604800.
  - Gold/coin/currency endpoints under COMMODITY category (Coin, Gold_Currency, CoinHistory, Currency, CurrencyHistory, Gold_Currency_Pro).
  - Note: `GOLD_24H` and `CURRENCY_24H` removed (HTTP 404 since ~June 2026); data now via `/Market/Gold_Currency.php`.
- **BrsApiSettings** (config.py):
  - `enabled` master switch (default True) — when False, client returns clear error, no live HTTP.
  - `global_daily_limit` default 10,000 (doc says free/basic plan blocks ~5,000/day; default 4,000/day mentioned in docstring but field default is 10,000 — **discrepancy, see finding**).
  - `global_5min_limit` default 1,000 (upgraded plan limit).
  - `fail_fast_on_daily_exhausted` default True.
  - `budget_warn_pct` 85, `budget_soft_reject_pct` 95 — non-critical traffic shed above 95%.
  - `budget_block_cooldown_seconds` 900 (15 min) after HTTP 302 heavy-file redirect.
  - `budget_redis_prefix` default "brsapi:budget"; `budget_state_file` default json/brsapi/budget_state.json.
  - Backfill chunking config: candlestick 1000/day @ 0.2s delay; shareholder 1000/day @ 5s; history_price 500/day @ 5s; history_real_legal 500/day @ 5s; symbol_detail 1000/day @ 4s @ 21:00 nightly.
  - `market_timezone` Asia/Tehran, market_open 08:30, market_close 15:30, `only_during_market_hours` True.
  - `raw_payload_sink_enabled` False; `max_raw_payload_age_days` 30.
  - `verify_ssl` True (default secure).
- **Rate limiter** (`brsapi/rate_limiter.py`):
  - 3 layers enforced for every `acquire()`:
    1. Daily counter (Tehran calendar day; resets at Tehran midnight).
    2. 5-min sliding window (deque of timestamps; pruned with `<=` cutoff to avoid boundary off-by-one).
    3. Per-category token bucket (Bucket: max_tokens, refill_rate = rpm/60).
  - Notifications at 80/90/95/100% daily usage (fire async callback, best-effort).
  - `fail_fast`: when True and daily exhausted, raise `RateLimitExhaustedError` immediately instead of sleeping until midnight.
  - `acquire` re-checks global limits after sleeping for bucket refill (prevents concurrent callers slipping past daily cap).
  - `status()` returns snapshot: global daily/5-min, per-endpoint counts, per-category bucket status, Tehran time.
  - Default daily limit = 10,000 (DEFAULT_GLOBAL_DAILY_LIMIT), 5-min = 1,000.
- **Budget governor** (`brsapi/budget.py`):
  - Makes daily + 5-min counters PERSISTENT and SHARED across processes/restarts (Redis INCRBY + Lua check-and-reserve for daily; Redis ZSET sliding window for 5-min; file fallback `json/brsapi/budget_state.json`; memory fallback).
  - Daily reservation Lua: check `current + requested > limit` → return -1 (no mutate); else INCRBY + EXPIRE. (Atomic check-and-reserve prevents counting rejected requests.)
  - 5-min window: Redis ZSET of `now:timestamp` members; ZREMRANGEBYSCORE prune; ZCARD count; if full and fail_fast → raise; else sleep until oldest expires (max 10s sleep).
  - Block state (HTTP 302 heavy-file redirect = server over-quota signal): arms `blocked_until = now + cooldown` (900s default); every live call rejected fast during cooldown; cleared only after cooldown elapsed AND server answers 200 (`report_ok`).
  - `acquire()` flow: block check → daily hard cap (persisted) → budget tiers (warn @85%, soft-reject non-critical @95%) → 5-min window → in-process limiter → record usage.
  - `report_302(location)` arms cooldown + persists; `report_ok()` clears block after cooldown.
  - Usage recorder (optional) attached for `brsapi_daily_usage` report table.
  - Seeds in-process limiter's daily count from persisted backend on init (so restarted process doesn't get fresh budget).
- **BrsApiClient** (`brsapi/client.py`):
  - `fetch(endpoint, extra, fail_fast, raise_on_empty)`:
    - If `BRSAPI_ENABLED=false` → return fail (DB-only mode).
    - budget governor `check_allowed` pre-check (block + daily cap + tiers).
    - rate limiter `acquire` (category + tokens=1 + endpoint + fail_fast).
    - circuit breaker per path (`_circuit_breaker(path)`) wraps the HTTP call.
    - HTTP GET with params (key + defaults + extra); parse JSON (or raw_text on JSONDecodeError); on 302 → `report_302(location)` + return fail; on 200 → `report_ok()` + return success; on 429 → parse Retry-After, sleep, retry once; on timeout/request error → retry with backoff (base^attempt, max delay).
    - Retries: timeout → retry; RequestError → retry; other → fail.
    - Raw payload sink (optional) stores response bytes.
  - `_redact_sensitive_text`: redacts api_key in error text (replace api_key value with `[REDACTED]`).
  - `probe_ready()`: bypasses `enabled` gate (so it works in DB-only mode); acquires governor with fail_fast=True (never sleeps); hits AllSymbols; returns ready=True only on HTTP 200; 302 → ready=False + detail.
  - `health()`: returns rate limit buckets + budget governor stats + circuit breaker states + reachable/ready.
  - `_configure_rate_limits()`: seeds rate limiter buckets from BrsApiSettings per-category limits.
  - `_circuit_breaker(path)`: per-path CircuitBreaker (failure_threshold=5, recovery_timeout=30) — uses `core.resilience.circuit_breaker.CircuitBreaker`? **Need to verify import; see finding.** [SEEN: client.py:439-445]
  - Singleton `get_client()` (lazy start), `close_client()`.

## 3.3 Data

- **Inputs:** BRSAPI_API_KEY (env), endpoint params, HTTP responses.
- **Outputs:** parsed JSON/data, Result objects (success/error/raw_bytes), health/readiness snapshots.
- **Storage:** Redis (budget governor daily counter + 5-min window + block state), JSON file fallback (budget_state.json, readiness_state.json), in-process state (rate limiter counters, circuit breakers, httpx client).
- **Data contract:** `fetch()` returns a Result (success + data/raw_bytes, or error). `health()`/`probe_ready()` return dicts.

## 3.4 General checklist

- **Logic:**
  - [YES] Master switch `enabled` → DB-only mode when False. [SEEN: client.py:216-219]
  - [YES] Budget governor persistent daily counter (Redis Lua check-and-reserve). [SEEN: budget.py:205-235]
  - [YES] 5-min sliding window shared across processes (Redis ZSET). [SEEN: budget.py:317-345]
  - [YES] 302 heavy-file redirect → block cooldown (900s) + fast rejection. [SEEN: budget.py:374-415, client.py:335]
  - [YES] Non-critical traffic soft-rejected above 95% daily usage; critical endpoints (same-day market record) keep going to 100%. [SEEN: budget.py:195-213, config.py:92-97]
  - [YES] Sensitive text (api_key) redacted in error logs. [SEEN: client.py:54-63]
  - [NO] **Daily limit default discrepancy**: docstring says default 4,000/day (safety margin below ~5,000/day plan cap), but `global_daily_limit` field default is 10,000. [SEEN: config.py:182-188 vs 214-220] → see BUD-01.
  - [UNKNOWN] Whether `fetch()` circuit breaker uses the new `core.resilience.circuit_breaker.CircuitBreaker` or the old `core.circuit_breaker.CircuitBreaker` — import statement needed. [SEEN: client.py:439-445 references `CircuitBreaker` but import line not captured in tail read; need to confirm which impl.]
- **Time:**
  - [YES] Tehran timezone used for daily counter reset + budget dates. [SEEN: budget.py:39, rate_limiter.py:20]
  - [YES] Market hours config (08:30–15:30) + `only_during_market_hours`. [SEEN: config.py:168-172]
  - [UNKNOWN] Whether market-hours gating is actually enforced in the client (config has the flag; need to check where it's applied — likely in sync jobs, not in `fetch()` itself).
- **Data:**
  - [YES] Endpoint configs include required params (e.g. `key`, `l18`) + defaults. [SEEN: config.py]
  - [YES] Response parse falls back to raw_text on JSONDecodeError. [SEEN: client.py:423-428]
- **Errors:**
  - [YES] 302 → report_302 + fail (not retried as success). [SEEN: client.py:335]
  - [YES] 429 → parse Retry-After, sleep, retry once. [SEEN: client.py tail]
  - [YES] Timeout/RequestError → retry with backoff. [SEEN: client.py tail]
  - [YES] Budget blocked → fast rejection (BudgetBlockedError). [SEEN: budget.py:175-185]
- **Concurrency:**
  - [YES] Rate limiter uses asyncio.Lock for daily/5-min/bucket state. [SEEN: rate_limiter.py]
  - [YES] Budget governor uses asyncio.Lock + Redis atomic ops. [SEEN: budget.py]
  - [YES] Client fetch enforces governor → limiter → circuit breaker ordering. [SEEN: client.py]
  - [UNKNOWN] Whether per-path circuit breaker is shared across all clients (it is per-client instance — `_circuit_breakers: dict[path, CircuitBreaker]` on the client instance; singleton client → effectively shared).
- **Performance:**
  - [YES] 5-min window prune + ZCARD; daily Lua check-and-reserve (atomic). [SEEN: budget.py]
  - [YES] Raw payload sink disabled by default (avoids storing full responses). [SEEN: config.py:177-178]
  - [UNKNOWN] Whether `fetch()` reconciliation/parse is expensive for large endpoints.
- **Security:**
  - [SEEN] api_key redacted in error text. [SEEN: client.py:54-63]
  - [SEEN] verify_ssl default True. [SEEN: config.py:175]
  - [SEEN] Master switch `enabled` for emergency kill of live calls. [SEEN: config.py:130-135, client.py:216-219]
  - [SEEN] Budget governor protects the API key from getting blocked (the original incident: key hit 19k requests, got blocked). [SEEN: budget.py:1-28]
  - [UNKNOWN] Whether api_key is ever logged elsewhere (client.py redacts in its own errors; need to verify provider-wide).
  - [UNKNOWN] Whether raw_payload_sink, if enabled, stores api_key in captured response params (it stores response bytes; params are in URL query string — likely captured; but sink is disabled by default).
- **Logging/observability:**
  - [SEEN] Threshold notifications (80/90/95/100%) logged. [SEEN: rate_limiter.py]
  - [SEEN] Budget governor block/cooldown/reset logged. [SEEN: budget.py]
  - [SEEN] Health snapshot includes rate limit buckets + budget governor stats + circuit breaker states. [SEEN: client.py:537-567]
  - [UNKNOWN] Whether `fetch()` logs the endpoint path with api_key redacted (likely; need to verify).

## 3.5 Specialized checklist

- **Iranian market hours + holidays:**
  - Market hours config: 08:30–15:30 ( Tehran) — note this is WIDER than the core/time market session (09:00–12:30 continuous + pre/post). **Discrepancy:** config.py market_open/close (08:30–15:30) vs core/time market sessions (09:00–12:30). Likely different semantics (ingestion window vs trading session), but worth flagging. [SEEN: config.py:168-172 vs core/time/*.py]
  - Holidays: not in code — likely external (Codal/calendar data).
- **Price source:** BrsApi.ir is the primary external provider for TSETMC + IME + Codal + commodity + crypto + gold/currency. [SEEN: config.py endpoint catalog]
- **Critical endpoints:** Symbol detail, Nav, Transaction, History price, History real/legal, Candlestick flagged `critical=True` (keep running past soft budget ceiling for same-day market record). [SEEN: config.py:92-97, endpoint configs]
- **Rate limits from official docs:** documented in BrsApiEndpoints docstring (e.g. TSETMC_AllSymbols 2/100s, TSETMC_Symbol 3/10s, etc.). [SEEN: config.py:56-90]

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| BUD-01 | brsapi/config.py:182-188 vs 214-220 | Daily limit default discrepancy: field default = 10,000, but docstring says "default 4,000/day keeps a safety margin below ~5,000/day plan cap". If the intent is to stay below 5,000, the field default of 10,000 is wrong (and DOC says 4,000). | [SEEN] | high | If deployed with default 10,000/day but the real plan cap is ~5,000/day, the key could get blocked (the exact incident this governor was built to prevent). | Confirm intended default; reconcile docstring vs field default. If free/basic plan cap is ~5,000/day, default should be ≤4,000 (as doc says). |
| BUD-02 | brsapi/client.py:439-445 | `CircuitBreaker` import not confirmed in tail read — need to verify whether it's `core.resilience.circuit_breaker.CircuitBreaker` (new, with async lock + half-open probe limit) or `core.circuit_breaker.CircuitBreaker` (old, simpler). | [SEEN import not captured] | medium | If the old impl is used, breaker semantics differ from the "current" one; if new impl, fine. | Check the import line at top of client.py. |
| BUD-03 | brsapi/config.py:168-172 vs core/time/*.py | Market hours: config.py says 08:30–15:30; core/time market sessions say continuous 09:00–12:30 (+ pre/post). Different semantics likely (ingestion window vs trading session), but could cause confusion if one is used for "is market open" logic. | [SEEN] | low | If any code uses config market_open/close to decide trading-session behavior, it may be wrong vs core/time. | Clarify which is authoritative for "market open" and ensure consistency. |
| BUD-04 | brsapi/budget.py:1-28 | Budget governor is the key-protection layer built after the key got blocked (hit 19k). Good design (persistent + shared + block cooldown + soft reject). | [SEEN] | low (positive) | This is the safety net for the provider key. | Verify it's actually wired into all live call paths (client.fetch + any direct acquirer). |
| BUD-05 | brsapi/config.py:214-220 | `fail_fast_on_daily_exhausted` default True — good (prevents cascade). But if a caller sets fail_fast=False and doesn't handle the sleep-until-midnight case, a job could hang until midnight. | [SEEN] | low | Low risk if defaults kept; risk if overridden. | Check callers that pass fail_fast=False. |
| BUD-06 | brsapi/readiness.py:65-95 | Readiness probe bypasses `enabled` gate intentionally (so it works in DB-only mode) but honors governor fail_fast. Good. | [SEEN] | low (positive) | Allows detecting key reset even when platform is in DB-only mode. | None. |
| BUD-07 | brsapi/client.py:54-63 | `_redact_sensitive_text` redacts api_key in error text. | [SEEN] | low (positive) | Prevents api_key leakage in error logs. | Verify no other path logs the raw key. |

## 3.7 Module monetary risk

- **Provider key blocking:** if budget governor misconfigured (e.g. daily limit default 10,000 vs real cap ~5,000), the key could be blocked → ingestion stops → stale market data → wrong signals/decisions. This is the core monetary risk of this module.
- **Data correctness:** if endpoint configs (rate limits/params/TTLs) are wrong vs BrsApi.ir actual API, ingestion may under/over-fetch, parse wrong, or serve stale data.
- **Critical endpoint shedding:** if `critical` flags are wrong, same-day market record could be shed during budget pressure → missing same-day data.

## 3.8 Questions and unknowns

- Which CircuitBreaker impl does client.py import?
- Is `only_during_market_hours` enforced in the client or only in sync jobs?
- Is the api_key ever logged anywhere besides client.py's redacted errors?
- Are raw_payload_sink captures ever stored with api_key in URL query?
- What is the real BrsApi.ir plan cap for this key (free/basic ~5,000/day)? The config doc says ~5,000/day; field default says 10,000.

## 3.9 Recommendations for Claude

- Re-verify: `brsapi/config.py:182-188` vs `214-220` daily limit default; `brsapi/client.py` CircuitBreaker import line; market hours consistency (config vs core/time); api_key logging across the project.
- Must-read: `brsapi/client.py` (full, already mostly read), `brsapi/budget.py` (full), `brsapi/rate_limiter.py` (full), `brsapi/config.py` (full — endpoint catalog + settings).

---
*Saved: 2026-10-05 · labels: [SEEN] observed in code (path:line), full file reads for brsapi/client.py, brsapi/config.py, brsapi/budget.py, brsapi/rate_limiter.py, brsapi/readiness.py*
