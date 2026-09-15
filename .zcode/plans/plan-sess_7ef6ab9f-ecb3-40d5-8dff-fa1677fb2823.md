## برنامه ارتقای API به 100% (v6 Hardening + Performance)

### 1. اصول راهنما
- **Backward compat**: قرارداد endpoint، URL، response shape حفظ می‌شود. فقط داخل بهتر.
- **Writeها Pydantic، GETها دست نخورده** (مگر درد واضح).
- **`str(exc)` ممنوع** در production. error_handlers استاندارد، trace_id در dev فقط.
- **هر slice یک PR منطقی** با تست.

### 2. Slices (به ترتیب اجرا)

#### Slice A — Core Hardening (`apps/api/`)
فایل‌ها: `app.py`, `middleware.py`, `error_handlers.py`, `dependencies.py`, `auth.py`, `router.py`, `metrics.py`, `pagination.py`.

تغییرات:
1. **error_handlers.py** — اضافه `trace_id` (uuid4) به هر error response، در prod فقط `code+message`، در dev اضافه `trace_id`. یک helper `error_response(err, status, code)` که همه handlerها ازش استفاده کنن.
2. **middleware.py** — یک `RequestContextMiddleware` که قبل از بقیه `trace_id` ست کنه و در `request.state.trace_id` بگذاره. LoggingMiddleware از این استفاده کنه. MetricsMiddleware با `trace_id` label.
3. **dependencies.py** — فاکتوری واحد `get_service(ServiceCls)` با `Depends(get_db_session)` بجای 30 تا فاکتوری تکراری (lazy import حفظ). audit script `scripts/check_router_auth.py` که CI اجرا کنه: هر `include_router` بدون `dependencies=` غیر از `health/auth` فیل بشه.
4. **app.py** — `Settings` v2 فقط (Config class → model_config)، یکی‌سازی `model_config = SettingsConfigDict(env_file=..., extra='ignore')`. تبدیل هر `class Config:` (اگر مونده) به v2.
5. **router.py** — `dependencies=_protect_default` بجای `_optional_auth` پیش‌فرض، یعنی اگه فراموش شد hard-fail در dev، در prod log warn. چون الان همه routerها include میشن با auth، فقط safety net اضافه می‌کنیم.
6. **pagination.py** — `@computed_field` بمونه، فقط type hints tighten: `Page[T].items: list[T]` با validator که `page_size <= max_page_size`.

تست‌ها:
- `tests/unit/test_error_handlers_trace_id.py` — هر error code، trace_id در body، در prod نیست.
- `tests/unit/test_request_context_middleware.py` — همان `trace_id` در log و response header `X-Trace-Id`.
- `tests/integration/test_router_auth_audit.py` — script خروجی را تست می‌کنه.
- `tests/unit/test_pagination_limits.py` — page_size>max → 422.

#### Slice B — Hot Endpoints Refactor

##### B1. `endpoints/brsapi.py` (3,242 LOC)
- **تقسیم**: استخراج `brsapi_admin.py` (raw DB، ETL، import)، `brsapi_public.py` (query، lookup) در همون router اما `_ADMIN_PREFIXES` route-level. چون backward compat لازم، URLها ثابت می‌مونن ولی handlerها از `services/brsapi_*` صدا زده می‌شن.
- **str(exc)** → حذف. هر `except Exception as exc: ... error={"message": str(exc)}` → `raise AppError("BRSAPI_QUERY_FAILED", "internal error", 500)` در dev فقط str(exc) در extra.
- **CSV streaming**: `csv.DictWriter` در حافظه → `StreamingResponse` با `aiofiles`.
- **Blocking `open().json.load()`** → `aiofiles.open` + `orjson.loads`.
- **تست**: contract test برای 5 endpoint پرکاربرد (symbols search, latest price, etf list).

##### B2. `endpoints/funds.py` (1,615 LOC)
- **4 query تکراری** → یک helper `latest_per_symbol(table: str)` در `repositories/fund_repository.py`.
- **`_CACHE_TTL_SECONDS=120`** → `settings.fund_cache_ttl_seconds`.
- **SSE**: session-scoped روی `funds.py:1314` → context manager با try/finally تضمینی.
- **تست**: `test_funds_api.py` expand، NAV contract حفظ، `test_funds_sse_disconnect.py` (clean close).

##### B3. `endpoints/decision_engine.py` (927 LOC)
- **13 مورد `str(exc)`** → `AppError`.
- **22 `session.execute()`** → repository pattern. `DecisionResultRepository` در `repositories/` با متدهای `list_paginated`, `by_symbol`, `distinct_symbols`, `count_estimate`.
- **`count_stmt = ... .limit(10000)`** → `EXPLAIN`-based count یا `EXISTS` (سریع‌تر روی 10K+).
- **تست**: `test_decision_engine_endpoints.py` (404, 422, 500 contract).

##### B4. `endpoints/backtests.py` (1,302 LOC)
- **5 تا `body: dict`** → 5 Pydantic model: `BacktestRunRequest`, `BacktestGenerateRequest`, `CompareStrategiesRequest`, `AdaptiveRequest`, `CascadeRequest`.
- **N+1 `compare_strategies`**: `asyncio.gather` با semaphore.
- **`list_backtests` fake pagination** → واقعی با `count()` + `limit/offset`.
- **تست**: e2e `test_backtest_api.py` expand برای هر 5 endpoint.

##### B5. `endpoints/screener_v2.py` (623 LOC)
- **4-layer rate limit + LRU + dedupe** → یکپارچه در `core/rate_limit.py` با Redis-backed token bucket. در-process LRU فقط برای warm.
- **Magic numbers** → settings.
- **تست**: `test_screener_endpoint.py` + concurrency test.

##### B6. (اختیاری) `codal_professional.py` (759 LOC)
- **49 `body: dict`** → 49 Pydantic model (اگر زمان بود). بزرگ‌ترین تغییر مکانیکی.

#### Slice D — Observability
- `metrics.py`: اضافه `http_request_in_flight` gauge.
- یک `core/observability/tracing.py` با OTEL hooks (در env اختیاری).
- LoggingMiddleware: structured log با `trace_id`, `user_id`, `path`, `latency_ms`.

#### Slice E — Cleanup
- `scripts/check_router_auth.py` در CI.
- حذف هر `await asyncio.sleep(...)` بی‌معنا (احتمالاً نیست).
- PR description با checklist: breaking? perf gain? test?

### 3. تست استراتژی
- **Contract tests** با `httpx.ASGITransport(app=app)` برای هر slice.
- **CI**: `pytest tests/unit -q` (~5min) در PR، `pytest tests/e2e` شبانه.
- **Coverage gate**: `apps/api/` >= 70% (الان نامشخص).
- **MyPy**: همین الان strict روی signal chain، extend به `apps/api/endpoints/`.

### 4. ریسک و مهار
- **خطر بزرگ**: brsapi.py و backtests.py backtest شدنی‌اند ولی تغییرات زیاد. راه‌حل: شاخه جدا برای هر slice، rebase تدریجی.
- **Performance regression**: benchmark `bench_rate_limits.py` و custom latency check قبل/بعد.
- **Breaking API**: forbidden (`extra="ignore"` در Pydantic، URL‌ها ثابت).

### 5. اسکوپ نهایی (این plan)
انتخاب: **Slice A + Slice B (B1-B5) + Slice D + Slice E**. بدون B6 (49 model خیلی بزرگ، اسکوپ بعدی). بدون تغییر در admin/decision_engine microservice/workers.

### 6. تخمین
- Slice A: 4 ساعت (فایل‌ها کوچک، refactor ایمن).
- Slice B: 12 ساعت (5 فایل بزرگ).
- Slice D+E: 2 ساعت.
- **جمع: ~18 ساعت**، در 4-5 PR.

### 7. خارج از اسکوپ (صریح)
- تغییر frontend.
- migration DB جدید (فقط استفاده از schema فعلی).
- OpenAPI commit.
- معماری v7 domain-driven (الان core+service کافی).
- ML model retraining.

اگر تأیید کنی، شروع می‌کنم با Slice A.