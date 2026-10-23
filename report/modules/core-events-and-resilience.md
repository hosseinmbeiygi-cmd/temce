# Module card: core-events-and-resilience

**Name:** core-events-and-resilience  
**Path:** `core/events.py` (24), `core/event_bus.py` (53), `core/circuit_breaker.py` (57); plus `core/retry/`, `core/rate_limit/`, `core/resilience/`, `core/concurrency/` (directories read, key files read where present; some subdirs may contain multiple files — counted below)  
**Tier:** 1 (event-driven glue + resilience directly affect reliability of ingestion/signals/alerts/orders)  
**Purpose:** Domain event model + in-process EventBus; circuit breaker; retry/backoff; rate limiting; resilience helpers; concurrency primitives.  
**Main files (lines):** `core/events.py` (24), `core/event_bus.py` (53), `core/circuit_breaker.py` (57), `core/utils.py` (35), `core/pagination.py` (50), `core/paths.py` (105)  
**Subdirs (file counts, read status):** `core/time/` (7 files, read), `core/validation/` (7 files + __init__, read), `core/enums/` (9 files + __init__, read), `core/constants/` (7 files + __init__, read), `core/ids/` (4 files + __init__, read), `core/typing/` (4 files + __init__, read), `core/feature_flags/` (5 files + __init__, read), `core/dependency_injection/` (5 files + __init__, read), `core/health/` (7 files + __init__, read), `core/json/` (present, not fully enumerated this batch — small).  
**Files read:** events.py, event_bus.py, circuit_breaker.py, utils.py, pagination.py, paths.py, + all of core/time, core/validation, core/enums, core/constants, core/ids, core/typing, core/feature_flags, core/dependency_injection, core/health (full reads for the files listed above; several small files).  
**Files unread:** `core/retry/*`, `core/rate_limit/*`, `core/resilience/*`, `core/concurrency/*` contents not individually read this batch (directories exist; need a quick peek to classify — do next).

## 3.1 Identity

- **Entry points / consumers:**
  - `event_bus` singleton (`core/event_bus.py`) subscribed by handlers across the platform for `quote.updated`, `signal.generated`, `trade.executed`, `alert.triggered`, `data.ingested`, etc. (`core/events.py` defines `MarketEvents` constants + `DomainEvent` dataclass).
  - Circuit breaker used by provider/network call sites (expected in ingestion/providers).
  - Retry/backoff/rate-limit used by provider HTTP calls.
  - Feature flags used to toggle ML/websocket/cache/audit/circuit breaker/provider failover at runtime.
  - Health checks (liveness/readiness/monitor/provider/system) expected at `/health` endpoints.
  - `core/paths.py` provides safe path resolution + data/model/logs/reports/tmp paths (used by `core/validation/files.py`, `core/security/hashing.py` `hash_file`).
  - `core/pagination.py` Page/PageParams used by API paginated responses.
  - `core/utils.py` `safe_error_message` used to sanitize exception messages by environment.
- **Dependencies:** asyncio, logging, structlog, core.config, core.logging, core.constants, core.time, core.validation, core.exceptions (ValidationError).

## 3.2 Logic and algorithms

- **Events** (`core/events.py`, `core/event_bus.py`):
  - `DomainEvent` dataclass: event_id, event_type, timestamp (UTC now), data dict.
  - `MarketEvents` constants: QUOTE_UPDATED, INSTRUMENT_CREATED, SIGNAL_GENERATED, TRADE_EXECUTED, MODEL_TRAINED, BACKTEST_COMPLETED, DATA_INGESTED, ALERT_TRIGGERED.
  - `EventBus`: subscribe/unsubscribe/publish/clear. Publish runs handlers in order; one failing handler does NOT stop others (each isolated, logged with `logger.exception`). Sync and async handlers both supported.
  - Singleton `event_bus`.
- **Circuit breaker** (`core/circuit_breaker.py`):
  - States: CLOSED → (failures ≥ threshold) → OPEN → (recovery_timeout elapsed) → HALF_OPEN → success → CLOSED.
  - Default failure_threshold=5, recovery_timeout=30s.
  - `call(func, *args, **kwargs)` wraps sync/async func; on failure increments count and opens if threshold reached.
  - `reset()` manual close.
- **Feature flags** (`core/feature_flags/*`):
  - `FeatureFlag` (env override `FF_<NAME>`), `FeatureFlags` collection, `FeatureFlagManager` (register + context overrides).
  - Predefined flags: USE_ML_MODELS (True), USE_WEBSOCKET (True), USE_CACHE (True), USE_ADVANCED_BACKTEST (False), ENABLE_AUDIT (True), ENABLE_SENTRY (False), ENABLE_METRICS (True), ENABLE_PROVIDER_FAILOVER (True), ENABLE_CIRCUIT_BREAKER (True), ENABLE_TEANTLEMETRICS? etc.
- **Health** (`core/health/*`):
  - `HealthStatus` dataclass (status, component, message, timestamp, details, duration_ms).
  - `HealthRegistry` + `get_health_registry()`; register/run/run_all.
  - Liveness, Readiness, HealthMonitor (interval loop + callbacks), ProviderHealthCheck, HealthScore (weighted), SystemHealth (cpu/memory/disk/uptime via psutil).
- **Paths** (`core/paths.py`):
  - `safe_resolve(base, user_path)` prevents traversal via `relative_to`.
  - `validate_safe_path(path)` checks for `../` patterns.
  - `data_path/subdir`, `models_path/subdir`, `logs_path`, `reports_path`, `temp_path`, `config_path`.
  - `safe_ensure_dir` + `ensure_dir`.
- **Validation** (`core/validation/*`):
  - Required/length/range/choice/email/mobile/url/alphanumeric/no-whitespace.
  - Symbol/ISIN/ticker validation + normalization (IR_SYMBOL_PATTERN = `^[آ-یA-Za-z0-9_-]+$`; ISIN_PATTERN = `^IR[A-Z0-9]{10}$`).
  - Date/datetime validation (formats, ISO, not-future, not-past, range).
  - File validation (exists/directory/extension/size/writable) using `validate_safe_path`.
  - Payload validation (schema dict with required + fields + type/min/max/choices).
  - `Validator` fluent builder → `ValidationError`.
- **Time** (`core/time/*`):
  - `now_utc`, `now_tehran`, `now_iran`, `utc_now_iso`, `utc_now_naive` (for legacy naive DB columns), `utc_to_tehran`, `tehran_to_utc`, `format_tehran`, `parse_tehran`, `parse_date_tehran`, `range_dates`, `is_market_open`, `next_market_open`, `timeframe_to_timedelta`, `floor_to_timeframe`.
  - Market hours: open 09:00–12:30 (IRAN_TZ = Asia/Tehran); weekend = Thu/Fri (MARKET_WEEKEND_DAYS=(3,4)).
  - Sessions: PRE_OPEN (08:30–09:00), CONTINUOUS (09:00–12:30), POST_CLOSE (12:30–13:00).
  - CalendarUtils (weekend/holiday/business days).
  - Clock (real) + SimulatedClock (for tests/backtests).
  - MarketSession dataclass + `get_current_session`, `is_market_open`, `time_to_market_open/close`.
  - Timezone utils (IRAN_TZ, UTC, TIMEZONES dict, convert_tz, localize, is_dst).
  - TimeWindow + SlidingTimeWindow.
- **Enums/constants** (`core/enums/*`, `core/constants/*`):
  - Markets: MarketType, AssetClass, InstrumentStatus, OrderSide, OrderType, TimeFrame, SignalType, RecommendationAction, ModelStage, JobStatus, DataSource, ProviderHealth; CURRENCY_PAIRS, COMMODITIES, SECTOR_GROUPS, IRAN_MARKET_OPEN/CLOSE, INDICES, MARKET_SECTORS.
  - Markets constants: MARKET_WEEKEND_DAYS=(3,4), TEHRAN_STOCK_EXCHANGE_CODE="TSE", FARABOURSE_CODE="FaraBourse".
  - App constants: APP_NAME/VERSION/DESCRIPTION/LICENSE, page sizes, cache TTLs (default 300, quote 10, instrument 3600, indicator 600), HTTP_TIMEOUT_SECONDS=30, MAX_RETRIES=3, BACKOFF_FACTOR=2.0, API_PREFIX/TITLE/VERSION.
  - Indicators: IndicatorType enum + DEFAULT_INDICATOR_PARAMS + INDICATOR_MIN_PERIODS.
  - ML: MLTask, ModelFramework, DEFAULT_TRAIN_TEST_SPLIT=0.8, DEFAULT_VALIDATION_SPLIT=0.1, DEFAULT_RANDOM_SEED=42, DEFAULT_BATCH_SIZE=2048, DEFAULT_LEARNING_RATE=0.001, DEFAULT_N_ESTIMATORS=100, DEFAULT_MAX_DEPTH=6, DEFAULT_EARLY_STOPPING_ROUNDS=10, MIN_TRAIN_SAMPLES=100, MAX_MODEL_SIZE_MB=500, FEATURE_GROUPS.
  - Paths constants: BASE_DIR = Path.cwd(), DATA_DIR, LOGS_DIR, CONFIG_DIR, TEMP_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR, EXPORTS_DIR, etc.
  - RBAC enums: Role (ADMIN/ANALYST/USER/VIEWER) + hierarchy + has_role/has_any_role.
  - Recommendations: RecommendationStrength, RecommendationSource, RecommendationStatus, RiskLevel.
  - Signals: SignalDirection, SignalStrength, SignalCategory, SignalStatus.
  - Alerts: AlertSeverity, AlertChannel, AlertStatus, AlertCondition.
  - Instruments: Sector (with Persian names), InstrumentGroup, Board, InstrumentFlow.
  - Provider: ProviderState, ProviderCapability, AuthType.
  - Market sessions: MarketSession, TradingState, MarketIndicator.
- **IDs** (`core/ids/*`):
  - `new_id(prefix)`, `new_uuid`, `new_short_id`, `new_snowflake_id(worker_id)` (epoch 1700000000000 ms), `id_from_timestamp`.
  - `new_run_id/pare**/is_valid_run_id` (run_<ts>_<uid>).
  - `symbol_to_id/normalize_symbol/symbol_from_id/is_valid_symbol_id/SymbolIdGenerator(to_id/from_id)`.
  - Trace context (thread-local dict): new_trace_id/get/set/clear + TraceContext.
  - UUID utils.
- **Typing** (`core/typing/*`):
  - `Result[T]` dataclass (generic success/value/error) — likely the platform result type (used in endpoints as `Result[Any]`).

## 3.3 Data

- **Inputs:** event dicts, handler funcs, breaker call args, flag names/context, health check functions, user paths, validation inputs, time queries.
- **Outputs:** published events, breaker results, flag booleans, health statuses, validated/normalized values, typed IDs.
- **Storage:** in-process only (event handlers list, breaker state, flag overrides, health registry, LRU cache in cache module, trace context dict).

## 3.4 General checklist

- **Logic:**
  - [YES] EventBus isolates handler failures (one failure doesn't stop others). [SEEN: core/event_bus.py:37-50]
  - [YES] Circuit breaker state machine implemented. [SEEN: core/circuit_breaker.py]
  - [YES] Path traversal prevention in paths.py + validation/files.py. [SEEN: core/paths.py, core/validation/files.py]
  - [YES] Market hours + weekend (Thu/Fri) encoded. [SEEN: core/time/*.py, core/constants/markets.py]
  - [NO] EventBus is in-process only — no persistence/delivery guarantee; if a handler fails it is logged but event is not retried. [SEEN: core/event_bus.py]
- **Time:**
  - [YES] UTC + Iran/Tehran conversions present. [SEEN: core/time/*]
  - [YES] `utc_now_naive()` for legacy naive DB columns — risk: mixing aware/naive. [SEEN: core/time/timezone.py]
  - [UNKNOWN] Whether new code uses aware UTC everywhere or still mixes naive. (See also core/database.py — DB columns may be DateTime(timezone=False).)
- **Data:**
  - [YES] Symbol normalization strips non-allowed chars. [SEEN: core/ids/symbol_ids.py, core/validation/symbols.py]
  - [YES] Payload validation schema-driven. [SEEN: core/validation/payloads.py]
- **Errors:**
  - [YES] `safe_error_message` redacts secret/token/password in production. [SEEN: core/utils.py:9-25]
  - [YES] Validation errors raise ValidationError. [SEEN: core/validation/__init__.py, core/validation/payloads.py]
- **Concurrency:**
  - [UNKNOWN] EventBus handlers run sequentially in publish; no concurrency control. [SEEN: core/event_bus.py:37-50]
  - [UNKNOWN] Whether CircuitBreaker is shared across callers or per-call-site (it is instantiated per instance — caller decides scope).
- **Performance:**
  - [YES] LRU + single-flight in cache (see observability card).
  - [UNKNOWN] EventBus handler count + latency impact on hot paths (e.g. quote.updated).
- **Security:**
  - [SEEN] Path traversal prevention. [SEEN: core/paths.py:22-55]
  - [SEEN] safe_error_message redacts secrets in prod. [SEEN: core/utils.py:9-25]
  - [UNKNOWN] Whether `send_message`/telegram/alert channels log sensitive data (see gold_desk/telegram_bot.py — message text includes symbol + trigger values; not secrets but market data).
- **Logging/observability:**
  - [SEEN] Event handler failures logged with exception. [SEEN: core/event_bus.py:45]
  - [SEEN] Circuit breaker open logged. [SEEN: core/circuit_breaker.py:47]
  - [UNKNOWN] Whether events are logged at publish time (they are not in EventBus.publish — no audit trail of events themselves).

## 3.5 Specialized checklist

- **Iranian market calendar:** hardcoded market hours 09:00–12:30, weekend Thu/Fri. [SEEN: core/time/*.py, core/constants/markets.py] — verify this matches current TSE schedule (holidays not in code — likely external).
- **Jalali vs Gregorian:** time module uses Gregorian (datetime) + Iran TZ. Jalali display likely in UI/formatting layer elsewhere. Not in this module.
- **Indicators default params:** present in core/constants/indicators.py (RSI period 14, MACD 12/26/9, Bollinger 20/2, etc.) — good reference for Tier 1 indicator reads.

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| ENR-01 | core/event_bus.py:37-50 | EventBus publish catches handler exceptions and logs them, but does not retry or persist. A failing handler is silently skipped (after log). | [SEEN] | medium | If a critical handler (e.g. alert delivery) fails, the event is "published" but the side effect is lost. | Check which handlers are registered for ALERT_TRIGGERED / TRADE_EXECUTED and whether they have their own retry. |
| ENR-02 | core/circuit_breaker.py | CircuitBreaker is a generic class; scope (per-provider vs global) is decided by caller. If a single instance is shared across unrelated providers, one failing provider opens the breaker for all. | [SEEN] | medium | Over-broad breaker can take down unrelated calls. | Verify per-provider breaker instances in ingestion/providers. |
| ENR-03 | core/time/timezone.py:30-34 | `utc_now_naive()` strips tzinfo for legacy naive DB columns; mixing aware/naive can cause subtle bugs. | [SEEN] | medium | Time comparison bugs in signals/backtests if aware/naive mixed. | Audit where utc_now_naive is used vs now_utc; ensure consistency in signal/backtest paths. |
| ENR-04 | core/constants/markets.py:10-12 | Market weekend = Thu/Fri (3,4). Market hours 09:00–12:30. | [SEEN] | low | Correct for TSE standard sessions; holidays not in code. | Verify holiday calendar source (likely external data); check market_sessions for pre/open/post definitions. |
| ENR-05 | core/paths.py + core/validation/files.py | Path traversal prevention present; `validate_safe_path` checks `../` pattern; `safe_resolve` uses relative_to. | [SEEN] | low | Good. | Verify all file-write paths use these helpers (e.g. exports, reports, codal attachments). |
| ENR-06 | core/utils.py:9-25 | `safe_error_message` redacts secret/token/password/PRIVATE_KEY/SECRET in production; in dev returns raw message. | [SEEN] | low | Good defense-in-depth. | Ensure it's used for all user-facing error messages (not just some). |
| ENR-07 | core/feature_flags/flags.py | ENABLE_SENTRY default False; ENABLE_AUDIT default True; USE_ADVANCED_BACKTEST default False. | [SEEN] | low | Feature flags give rollout control. | Confirm flag wiring is actually checked at call sites (not just defined). |

## 3.7 Module monetary risk

- EventBus handler loss (ENR-01) could mean missed alerts or lost side-effects (e.g. order execution signal not delivered) — monetary if downstream relies on event for action.
- Circuit breaker mis-scoping (ENR-02) could cause cascading failures.
- Time awareness bugs (ENR-03) could affect signal timing, market-hours checks, backtest alignment.

## 3.8 Questions and unknowns

- What are the actual contents of `core/retry/`, `core/rate_limit/`, `core/resilience/`, `core/concurrency/`? (Need a quick file list + peek.)
- Which handlers are registered for each MarketEvents type? (Need to grep subscriptions.)
- Is `utc_now_naive` used in signal/backtest paths? (grep.)
- Is there a holiday calendar source? (Check ingestion/ or config.)

## 3.9 Recommendations for Claude

- Re-verify: EventBus handler registrations for ALERT_TRIGGERED/TRADE_EXECUTED; CircuitBreaker scoping in providers; utc_now_naive vs now_utc usage in signals/backtests.
- Must-read: `core/retry/`, `core/rate_limit/`, `core/resilience/`, `core/concurrency/` (next quick batch); then `core/exceptions/` + `core/result.py` typing.

---
*Saved: 2026-10-05 · labels: [SEEN] observed in code (path:line), full reads for events.py, event_bus.py, circuit_breaker.py, utils.py, pagination.py, paths.py, all of core/time, core/validation, core/enums, core/constants, core/ids, core/typing, core/feature_flags, core/dependency_injection, core/health*
