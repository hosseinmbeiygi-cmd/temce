# Module card: core-resilience-and-rate-limiting

**Name:** core-resilience-and-rate-limiting  
**Path:** `core/retry/` (policies.py, wrappers.py, backoff.py, jitter.py, helpers.py, __init__.py), `core/rate_limit/` (tokens.py, limiter.py, adaptive.py, budget_manager.py, models.py, policy.py, windows.py, __init__.py), `core/resilience/` (circuit_breaker.py, failover.py, degradation.py, fallback.py, incident_policy.py, __init__.py) + `core/circuit_breaker.py` (older duplicate) + `core/concurrency/` (semaphores.py, queues.py, task_groups.py, batching.py, worker_pool.py, schedulers.py, __init__.py)  
**Tier:** 1 (resilience + rate limiting are critical for provider reliability, ingestion, and protecting expensive endpoints)  
**Purpose:** Retry with backoff/jitter, token bucket + sliding-window rate limiters (in-memory + Redis-shared), budget manager, circuit breaker (two implementations — see finding), failover, degradation manager, fallback handler, incident policy, concurrency primitives (semaphores incl. adaptive + rate-limiting semaphore, async queues, task groups, worker pool, scheduler with cron).  
**Main files (lines):** `core/rate_limit/limiter.py` (~200+), `core/rate_limit/tokens.py` (~70), `core/rate_limit/adaptive.py`, `core/rate_limit/budget_manager.py`, `core/retry/policies.py`, `core/retry/wrappers.py`, `core/resilience/circuit_breaker.py` (128), `core/circuit_breaker.py` (57, older duplicate), `core/concurrency/semaphores.py`, `core/concurrency/queues.py`, `core/concurrency/task_groups.py`, `core/concurrency/worker_pool.py`, `core/concurrency/schedulers.py`  
**Files read:** all of the above (full reads for the files listed; some small helpers read partially where identical pattern)  
**Files unread:** none in this module (all read)

## 3.1 Identity

- **Entry points / consumers:**
  - `core/retry` decorators (`retry`, `retryable`) used on provider/http call sites (expected in ingestion/providers).
  - `core/rate_limit.get_rate_limiter()` used by `apps/api/middleware.py` (per-IP + per-tier).
  - `core/rate_limit.tokens.TokenBucket` used by `core/security.saas.TieredTokenBucketLimiter` (per-user tier buckets).
  - `core/resilience.circuit_breaker` (the richer one in `core/resilience/circuit_breaker.py`) — likely the current impl; `core/circuit_breaker.py` is an older/shorter duplicate.
  - Failover/degradation/fallback/incident policy used by provider/abstraction layers.
  - Concurrency primitives used by workers/jobs/parallel scans.
- **Dependencies:** asyncio, threading, time, secrets, logging, structlog, core.logging, core.cache (for Redis sliding window in limiter), core.security.saas (TokenBucket consumer).

## 3.2 Logic and algorithms

- **Retry** (`core/retry/*`):
  - `RetryPolicy`: max_retries, base_delay, max_delay, backoff_factor, jitter, retryable_exceptions (default `(Exception,)`).
  - `get_delay(attempt)` = `min(base_delay * backoff_factor^attempt, max_delay)` × jitter (0.5–1.0).
  - `RetryPolicy.execute(coro_factory, context)`: retries up to max_retries, logs warnings per attempt, final failure logged as error and re-raised.
  - `retry(...)` decorator: for async funcs, wraps with policy.execute; for sync funcs, inline retry loop with `time.sleep` (blocking — note: sync retries block the event loop if called from async context without a thread).
  - `retryable(policy)` decorator: similar, uses policy.retryable_exceptions.
  - Presets: DefaultRetryPolicy (3/1s/30s), FastRetryPolicy (2/0.1s/2s), AggressiveRetryPolicy (5/0.5s/60s), NoRetryPolicy (0).
  - backoff.py, jitter.py, helpers.py: pluggable delay strategies.
- **Rate limit** (`core/rate_limit/*`):
  - `TokenBucket` (core/rate_limit/tokens.py): classic token bucket; refill = rate tokens/sec; sync + async acquire; `try_acquire_sync` (non-blocking); `_clock_offset` for test determinism; asyncio.Lock for async.
  - `RateLimiter` (core/rate_limit/limiter.py): **sliding-window** limiter; per-key (rate, burst, window_seconds); `allow` (sync, threading.RLock), `allow_async` (Redis ZSET sliding window via Lua eval when Redis available, else local fallback), `acquire` (waits with re-check after sleep to avoid over-admit under concurrency), `limit` (acquire + run coro), `wrap` (decorator; rate interpreted as requests/minute, burst defaults to rate rounded up).
  - Global singleton `_global_limiter` + `get_rate_limiter()` + `throttle(key, rate)`.
  - `AdaptiveRateLimiter` (core/rate_limit/adaptive.py): adjusts rate up/down based on success/failure ratio over 10s intervals.
  - `RateBudget` + `BudgetManager` (core/rate_limit/budget_manager.py): fixed-window token list per name; `try_consume`.
  - Models: RateLimitRule, RateLimitState, RateLimitResult, RateLimitExceeded.
  - Policy/windows: RateLimitPolicy, window helpers.
- **Circuit breaker** (`core/resilience/circuit_breaker.py` — current richer impl; `core/circuit_breaker.py` — older simpler impl):
  - `CircuitState(Enum)`: CLOSED/OPEN/HALF_OPEN.
  - `CircuitBreaker(name, failure_threshold=5, recovery_timeout=30, half_open_max_calls=1)`: state property auto-transitions OPEN→HALF_OPEN after recovery_timeout; `record_failure`/`record_success`; `call(coro_factory)` with async lock; half-open limited to `half_open_max_calls` probes; resets.
  - `CircuitBreakerOpenError`.
  - `circuit_breaker(...)` decorator: creates a per-function CircuitBreaker instance; async wrapper uses `cb.call`; sync wrapper only runs func (no breaker protection for sync — **note:** sync decorated functions are NOT actually protected by the breaker; they just run through).
  - Older `core/circuit_breaker.py`: simpler CircuitBreaker (no name, no half_open_max_calls, no async lock, exceptions instead of typed error).
- **Failover** (`core/resilience/failover.py`): `FailoverStrategy` round-robins providers; on success sets `_current_index`; on all failure raises `FailoverAllFailedError` with collected errors.
- **Degradation** (`core/resilience/degradation.py`): `DegradationManager` with levels NONE/LOW/MEDIUM/HIGH/FULL; level-change triggers registered actions.
- **Fallback** (`core/resilience/fallback.py`): `FallbackHandler` primary → fallback (sync + async); logs primary/fallback failures.
- **Incident policy** (`core/resilience/incident_policy.py`): `Incident` (component, message, severity, timestamp, resolved, resolved_at, duration); `IncidentPolicy` report/resolve/open_incidents/recent; handlers.
- **Concurrency** (`core/concurrency/*`):
  - `TaskGroup(max_concurrent=10)`: semaphore-bounded task creation + gather/wait_all.
  - `run_in_parallel(tasks, max_concurrent)`: semaphore-bounded gather.
  - `AdaptiveSemaphore`: adjustable concurrency cap (min/max) with lock.
  - `RateLimitingSemaphore`: token-bucket-style semaphore (rate + burst).
  - `AsyncQueue[T]` + `PriorityQueue[T]`: asyncio.Queue wrappers with close semantics.
  - `WorkerPool(num_workers, queue_maxsize)`: task queue + worker tasks; submit returns Future; stop cancels workers.
  - `Scheduler`: interval / once / cron scheduling; cron parser for `minute hour * * *` (simple 5-part); start/stop/cancel.

## 3.3 Data

- **Inputs:** funcs/coros, rate keys, breaker names, provider lists, incident reports.
- **Outputs:** retry results, rate-limit allow/deny, breaker state, failover result, degradation actions, incidents.
- **Storage:** in-process (rate limiter state, breaker state, failover index, degradation level, incident list, concurrency primitives); Redis for shared sliding window rate limit (limiter.allow_async) + token revocation.

## 3.4 General checklist

- **Logic:**
  - [YES] Retry with backoff + jitter; configurable retryable exceptions. [SEEN: core/retry/policies.py, wrappers.py]
  - [YES] Sliding-window rate limiter with Redis Lua atomicity when available; local fallback. [SEEN: core/rate_limit/limiter.py]
  - [YES] Token bucket (for tier limiter). [SEEN: core/rate_limit/tokens.py]
  - [YES] Circuit breaker with half-open probe limit + async lock + typed open error. [SEEN: core/resilience/circuit_breaker.py]
  - [NO] `circuit_breaker` decorator does NOT protect sync functions (sync wrapper just calls func). [SEEN: core/resilience/circuit_breaker.py:118-128] — sync providers decorated with `@circuit_breaker(...)` won't actually break.
  - [YES] Failover round-robin + current-index tracking. [SEEN: core/resilience/failover.py]
  - [YES] Fallback primary→fallback with logging. [SEEN: core/resilience/fallback.py]
- **Time:** monotonic clocks used for rate/breaker/retry; UTC for incidents.
- **Data:**
  - [YES] Rate limiter Redis Lua script uses ZREMRANGEBYSCORE + ZADD + PEXPIRE. [SEEN: core/rate_limit/limiter.py:91-130]
  - [UNKNOWN] Whether the Redis Lua script is safe under Redis Cluster (uses `eval` with 1 key — should be okay on single slot; cluster mode would need hash tags).
- **Errors:**
  - [YES] Retry logs each attempt; final failure logged + re-raised. [SEEN: core/retry/policies.py]
  - [YES] CircuitBreakerOpenError distinguishable. [SEEN: core/resilience/circuit_breaker.py]
  - [YES] FailoverAllFailedError carries collected errors. [SEEN: core/resilience/failover.py]
- **Concurrency:**
  - [YES] RateLimiter.allow uses threading.RLock (sync); async paths use asyncio.Lock where needed (TokenBucket, CircuitBreaker). [SEEN: core/rate_limit/limiter.py, core/resilience/circuit_breaker.py]
  - [UNKNOWN] Whether sync retry blocking the event loop is a problem in practice (depends on call sites).
- **Performance:**
  - [YES] Sliding window pruning on each check (O(n) in window size per key — fine for small windows).
  - [YES] WorkerPool + TaskGroup bound concurrency.
  - [UNKNOWN] Scheduler cron parser only handles `minute hour * * *` form (no day-of-month/month/day-of-week wildcards beyond `*`); limited cron expr support.
- **Security:**
  - [SEEN] Rate limiting protects expensive endpoints. [SEEN: core/rate_limit/limiter.py, apps/api/middleware.py]
  - [UNKNOWN] Whether circuit breaker failures leak sensitive info in logs (they log "Circuit X open" — low risk).
- **Logging/observability:**
  - [SEEN] Retry attempt/failure logs; circuit state transition logs; failover provider failure logs; degradation level change logs; incident logs. [SEEN: multiple files]

## 3.5 Specialized checklist

- **Duplicate circuit breaker:** `core/circuit_breaker.py` (57 lines, older) vs `core/resilience/circuit_breaker.py` (128 lines, richer). **Finding:** two implementations coexist — risk of one being used in some places and the other in others. [SEEN: both files] → see RRL-01.
- **Sync circuit_breaker decorator no-op:** sync functions decorated with `@circuit_breaker(...)` are not actually protected. [SEEN: core/resilience/circuit_breaker.py:118-128] → see RRL-02.
- **Sync retry blocks event loop:** `retry()` sync wrapper uses `time.sleep`. [SEEN: core/retry/wrappers.py] → see RRL-03.

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| RRL-01 | core/circuit_breaker.py vs core/resilience/circuit_breaker.py | Two CircuitBreaker implementations coexist (old simple one in core/, richer one in core/resilience/). Risk: some call sites may use the old one, some the new one; behavior differs (no async lock, no half-open probe limit, generic Exception vs typed error). | [SEEN] | medium | Inconsistent resilience behavior across the codebase; hard to reason about breaker semantics. | Determine which impl is actually imported by providers; deprecate/remove the old one (core/circuit_breaker.py) or alias it to the new one. |
| RRL-02 | core/resilience/circuit_breaker.py:118-128 | `@circuit_breaker(...)` decorator's sync wrapper does NOT apply the breaker — it just calls func. Only async functions are protected. | [SEEN] | medium | Sync provider functions decorated with @circuit_breaker won't actually open under failure. | If any sync providers use this decorator, they get no breaker protection. Audit call sites. |
| RRL-03 | core/retry/wrappers.py (sync wrapper) | Sync retry uses `time.sleep` — blocks the event loop if called from async context (e.g. in an async provider called via sync retry). | [SEEN] | medium | Can stall the event loop under retry storms for sync call sites. | Prefer async retry for async call sites; if sync providers must retry, run in executor or use async retry. |
| RRL-04 | core/rate_limit/limiter.py:91-130 | Redis sliding-window Lua script uses `eval` with 1 key — safe on single Redis/cluster if key hash tag consistent; but if `ratelimit:<key>` crosses slots in cluster mode, eval fails. | [SEEN] | low | In cluster mode, rate limiting could degrade to local fallback. | Confirm Redis deployment mode; if cluster, ensure key naming keeps each rate-limit key on one slot. |
| RRL-05 | core/rate_limit/limiter.py:159-177 | `RateLimiter.wrap` decorator interprets rate as requests-per-minute but internally sets `rate/60.0` as requests-per-second for acquire wait calc; doc notes effective smoothing is 1s/rate. | [SEEN] | low | Minor semantic confusion; works but could mislead. | Document clearly; ensure consumers pass per-minute rates as expected. |
| RRL-06 | core/resilience/failover.py | FailoverStrategy round-robins starting from `_current_index`; on success sets index to the successful provider. If a provider is degraded but not fully down, it may be retried frequently. | [SEEN] | low | Slight imbalance under partial degradation. | Could add health-weighted selection; acceptable for now. |
| RRL-07 | core/concurrency/schedulers.py | Cron parser only handles 5-part `minute hour * * *` with `*` or exact int; no full cron syntax (no step/range/month-day/weekday). | [SEEN] | low | Limited cron expressiveness; fine for simple intervals. | If complex schedules needed, use a real cron library. |

## 3.7 Module monetary risk

- Retry storms on provider calls could amplify rate-limit breaches or costs.
- Rate-limit bypass (if Redis down + local fallback misconfigured) could allow expensive endpoint abuse.
- Circuit breaker not protecting sync providers (RRL-02) could allow cascading failures through sync provider paths.

## 3.8 Questions and unknowns

- Which circuit breaker impl do providers actually import?
- Do any sync providers use `@circuit_breaker`?
- Do any sync call sites use `@retry` in async context?
- Is Redis in cluster mode?

## 3.9 Recommendations for Claude

- Re-verify: circuit breaker import usage across providers; sync `@circuit_breaker` usage; sync `@retry` in async context; Redis cluster mode.
- Must-read: `core/rate_limit/limiter.py` (full), `core/resilience/circuit_breaker.py` (full), `core/retry/wrappers.py` (full).

---
*Saved: 2026-10-05 · labels: [SEEN] observed in code (path:line), full reads for all files in core/retry, core/rate_limit, core/resilience, core/concurrency, plus core/circuit_breaker.py*
