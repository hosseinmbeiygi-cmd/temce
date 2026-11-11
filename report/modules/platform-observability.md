# Module card: platform-observability

**Name:** platform-observability  
**Path:** `core/logging/__init__.py` (228), `core/cache.py` (168), `core/cache_manager.py` (351), `core/observability_sentry.py` (71)  
**Tier:** 1 (logging + caching are cross-cutting; cache correctness affects pricing/signals; sentry touches error reporting)  
**Purpose:** Structured logging (structlog), Redis-backed caching (2 implementations: simple CacheService + 3-layer CacheManager), optional Sentry error tracking.  
**Main files (lines):** `core/logging/__init__.py` (228), `core/cache.py` (168), `core/cache_manager.py` (351), `core/observability_sentry.py` (71)  
**Files read:** all fully  
**Files unread:** none in this module

## 3.1 Identity

- **Entry points / consumers:**
  - `get_logger()` used by virtually every module.
  - `setup_logging()` called from app lifespans (e.g. `apps/api/app.py`, `apps/decision_engine/app.py`).
  - `get_cache()` (simple CacheService singleton) and `get_cache_manager()` (3-layer singleton) are both exported and used by downstream services (token revocation uses `get_cache()`; CacheManager is the richer one).
  - `init_sentry(settings)` called from API lifespan before other init.
- **Dependencies:** structlog, logging, json, asyncio, orjson, redis.asyncio, sentry_sdk (optional), pytz, core.config, core.logging.

## 3.2 Logic and algorithms

- **Logging** (`core/logging/__init__.py`):
  - `setup_logging()` configures structlog + stdlib handlers from `settings.log_format` (json/text) and `settings.log_level`.
  - `SafeStreamHandler` degrades on encoding errors (Persian text on Windows cp1252 consoles).
  - JSON vs text processors; file handler if `settings.log_file` set.
  - Optional Redis Streams log aggregation (`log_aggregation_enabled`).
  - Third-party loggers (httpx, httpcore, asyncio, urllib3) quieted to WARNING.
  - `get_logger(name)` returns a per-name cached structlog BoundLogger.
  - `bind_context()` / `unbind_context()` / `clear_context()` wrap structlog.contextvars.
- **Simple cache** (`core/cache.py`):
  - `NullCache` (no-op), `CacheService` (Redis async via `redis.asyncio`).
  - Lazy init: `initialize()` only connects once; after `close()` reconnects on next op.
  - `is_connected` property; `ping()`; JSON serialize/deserialize.
  - `get/set/delete/pop/remember`; `set_persistent` (no TTL).
  - Graceful degradation to null cache when Redis unavailable.
  - Singleton via `get_cache()`.
- **3-layer cache** (`core/cache_manager.py`):
  - L1 = in-memory LRU (OrderedDict, maxsize configurable, default 100), L2 = Redis, L3 = compute (user func).
  - `get_or_compute(key, ttl, func)`: L1 → L2 → L3. On compute, promotes to L1 + L2.
  - **Single-flight** for concurrent L3 misses: Redis `SET NX EX` lock (_LOCK_TTL_SECONDS=30); losers poll L2 up to 5s (_LOCK_WAIT_ATTEMPTS=50 × 0.1s); on timeout they fall through and compute themselves (fail-open, not fail-closed).
  - Lock release in `finally`; if lock acquisition failed, compute anyway.
  - `invalidate(key)` clears L1 + L2; `clear_all()` clears L1 + all keys this manager wrote.
  - Serialization: **orjson, NOT pickle** (deliberate choice to avoid RCE from attacker-reachable Redis keyspace). [SEEN: core/cache_manager.py:319-326]
  - None payloads treated as misses in L1 (sentinel caveat noted).
  - Singleton via `get_cache_manager()`; `set_cache_manager()` for tests/teardown.
- **Sentry** (`core/observability_sentry.py`):
  - `init_sentry(settings)`: no-op if no `SENTRY_DSN`; else initializes sentry_sdk with Asyncio/FastAPI/Redis/SQLAlchemy integrations.
  - `send_default_pii=False`; `before_send` scrubs requests carrying Authorization/Cookie/X-API-Key/Proxy-Authorization headers.
  - Environment = "production" if `settings.is_production` else "development".
  - Traces sample rate default 0.1 (10%).

## 3.3 Data

- **Inputs:** log records, cache keys/values, Sentry events.
- **Outputs:** structured log lines, cached values, Sentry reports.
- **Storage:** Redis (cache + optional log aggregation); L1 in-memory.
- **Data contract:** async `get/set/delete` + `get_or_compute`. JSON (orjson) for L2 payloads.

## 3.4 General checklist

- **Logic:**
  - [YES] 3-layer cache with single-flight. [SEEN: core/cache_manager.py]
  - [YES] pickle avoided for L2 (orjson). [SEEN: core/cache_manager.py:319-326]
  - [YES] Redis unavailable → graceful degradation (null cache / L1-only). [SEEN: core/cache.py, core/cache_manager.py]
  - [YES] Sentry scrubs auth headers before send. [SEEN: core/observability_sentry.py:66-73]
  - [NO] L1 treats None as miss — if None is a valid cached value, it is recomputed every time. [SEEN: core/cache_manager.py:155-157] (documented caveat)
- **Time:**
  - [YES] Log timestamps ISO. [SEEN: core/logging/__init__.py]
  - [YES] Cache TTLs in seconds. [SEEN: core/cache.py, core/cache_manager.py]
- **Data:**
  - [YES] JSON serialization for L2. [SEEN: core/cache_manager.py:319-326]
  - [UNKNOWN] Whether cache keys can collide across namespaces (CacheManager uses `_namespace` prefix; simple CacheService does not namespace by default — keys are raw).
- **Errors:**
  - [YES] L2 read/write failures logged + degrade. [SEEN: core/cache_manager.py]
  - [YES] Sentry init failures logged + non-fatal. [SEEN: core/observability_sentry.py]
- **Concurrency:**
  - [YES] L1 is single-event-loop safe (OrderedDict; project uses asyncio). [SEEN: core/cache_manager.py:31-53]
  - [YES] Single-flight lock uses Redis SET NX. [SEEN: core/cache_manager.py:184-213]
  - [UNKNOWN] Whether two separate processes/ workers share L1 (they do not — L1 is per-process; L2 is shared). This is by design.
- **Performance:**
  - [YES] LRU L1 O(1). [SEEN: core/cache_manager.py:31-53]
  - [YES] Single-flight prevents DB stampede on cold keys. [SEEN: core/cache_manager.py:184-213]
  - [UNKNOWN] L1 maxsize default = 100 — small; may be too small for high-cardinality quote caches. Check usage.
- **Security:**
  - [SEEN] orjson not pickle (RCE avoidance). [SEEN: core/cache_manager.py:319-326]
  - [SEEN] Sentry scrubs auth headers. [SEEN: core/observability_sentry.py:66-73]
  - [UNKNOWN] Whether sensitive data (prices/positions) is cached in Redis in a way that is attacker-reachable if Redis auth is weak. Redis auth is via URL (settings.redis_url) — check .env (NOT reading it).
  - [UNKNOWN] Whether log aggregation includes sensitive fields.
- **Logging/observability:**
  - [SEEN] structlog JSON in production. [SEEN: core/logging/__init__.py]
  - [SEEN] Redis-cache failures logged at WARNING. [SEEN: core/cache_manager.py]
  - [UNKNOWN] Whether cache hits/misses are logged (they are not, by default — no observability into cache efficiency).

## 3.5 Specialized checklist

- **Cache correctness for financial data:** important — stale quotes/signals can cause wrong decisions. CacheManager TTL per-call; default TTL from settings (redis_default_ttl=300). Quote TTL constant is 10s (core/constants/app.py: CACHE_TTL_QUOTE=10) — but that constant is in core/constants, not necessarily wired into CacheManager usage. **Action for Claude:** verify which TTLs are actually used per data type.

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| OBS-01 | core/cache_manager.py:155-157 | L1 treats cached None as miss → recomputes every call if a value is None. | [SEEN] | low | Wasted compute on None-valued keys. | If any financial value can be None (e.g. missing price), this causes repeated L3 compute. Check usage. |
| OBS-02 | core/cache_manager.py:31-53 | L1 default maxsize=100 (passed from get_cache_manager default). | [SEEN] | low | Too-small LRU for high-cardinality data (e.g. per-symbol quotes). | Confirm L1 size is tuned for actual key cardinality; otherwise L1 never hits and single-flight benefit is reduced. |
| OBS-03 | core/cache.py vs core/cache_manager.py | Two cache abstractions exist (CacheService + CacheManager) — potential dual source of truth for "the cache". | [SEEN] | medium | Inconsistent TTL/key conventions; token revocation uses get_cache() (simple), other code may use get_cache_manager(). | Map which consumers use which; consolidate if possible. |
| OBS-04 | core/observability_sentry.py:45-58 | Sentry init uses `getattr(settings, "is_production", False)` — but Settings class has property `is_production` (core/config/__init__.py:311). If sentry init receives a different object, environment may mis-label. | [SEEN] | low | Sentry env label could be wrong if called with non-Settings object. | Verify call site passes real settings. |
| OBS-05 | core/logging/__init__.py:105-115 | Optional Redis Streams log aggregation — if enabled, log lines (possibly with context) go to Redis. | [SEEN] | low | Log aggregation could carry sensitive context if bound. | Check what context is bound in auth/signal paths before enabling aggregation. |

## 3.7 Module monetary risk

- Stale or missing cache for quotes/signals → wrong decisions.
- CacheManager single-flight reduces DB stampede but if L2 is down, every process computes — potential DB overload on cache misses during Redis outage.
- pickle avoidance is good security practice; no issue here.

## 3.8 Questions and unknowns

- Which cache abstraction does each consumer use?
- Are quote TTLs actually 10s end-to-end, or only in a constant that is not wired?
- Is log aggregation enabled in prod (.env not read)?
- Is `settings.redis_url` authenticated (Redis auth)?

## 3.9 Recommendations for Claude

- Re-verify: `core/cache_manager.py` single-flight + L1 None handling; `core/cache.py` vs `core/cache_manager.py` consumer mapping; Sentry call site.
- Must-read: `core/constants/app.py` (TTL constants) + the consumers of get_cache/get_cache_manager in services.

---
*Saved: 2026-10-05 · labels: [SEEN] observed in code (path:line), full file reads for core/logging/__init__.py, core/cache.py, core/cache_manager.py, core/observability_sentry.py*
