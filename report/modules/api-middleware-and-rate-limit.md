# Module card: api-middleware-and-rate-limit

**Name:** api-middleware-and-rate-limit  
**Path:** `apps/api/middleware.py` (full read; length ~520+ lines)  
**Tier:** 1 (auth enforcement, rate limiting, input sanitization, security headers — cross-cutting; wrong behavior affects every endpoint)  
**Purpose:** Request context (trace id), timing + logging, security headers, CSRF, input sanitization, per-IP + per-tier rate limiting, defense-in-depth auth on sensitive write endpoints.  
**Main files (lines):** `apps/api/middleware.py` (read fully)  
**Files read:** middleware.py (full)  
**Files unread:** none in this module

## 3.1 Identity

- **Entry points / consumers:** mounted in `apps/api/app.py` (FastAPI lifespan + middleware stack). All HTTP traffic passes through.
- **Dependencies:** starlette BaseHTTPMiddleware, fastapi Request/Response/JSONResponse, core.config.settings, core.logging, core.rate_limit (get_rate_limiter), core.security.saas (TIERS, get_tier_limiter, tier_subject_from_request), core.security.tokens (decode_access_token, is_token_revoked), core.security.sanitizers (strip_html).

## 3.2 Logic and algorithms

- **RequestContextMiddleware** (outermost): sets `request.state.trace_id` (X-Trace-Id header if client supplied, else uuid4); adds `X-Trace-Id` to response.
- **TimingMiddleware**: logs each request/response with elapsed time; adds `X-Response-Time-Ms`.
- **LoggingMiddleware**: DEBUG log of request method/path + response status.
- **SecurityMiddleware** (defense-in-depth):
  - On POST/PUT/DELETE/PATCH, for sensitive write prefixes (`/api/v1/backtests/run`, `/api/v1/backtests/generate`, `/api/v1/backtests/cascade`, `/api/v1/backtests/adaptive`, `/api/v1/ml/train`, `/api/v1/ml/predict`, `/api/v1/portfolios`, `/api/v1/alerts`, `/api/v1/watchlist`, `/api/v1/trades`, `/api/v1/data-import`, `/api/v1/signal-insights`), requires Bearer token; validates signature + revocation (access token type check).
  - Adds security headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Cache-Control no-store, Pragma no-cache (except /docs /openapi.json /health).
- **CSRFMiddleware**: for unsafe methods, if Origin/Referer present, checks origin against `cors_origins`; blocks if not allowed. No-op when `enable_csrf=False`. Safe methods + health/docs pass. Requests without Origin/Referer (curl/S2S) allowed.
- **InputSanitizationMiddleware**:
  - Enabled via `settings.enable_input_sanitization` (default True).
  - For JSON content types: parse body, recursively sanitize.
  - `_SANITIZE_RAW_FIELDS` allow-list (password, current_password, new_password, code, secret, token, refresh_token, access_token, mfa_token, telegram_chat_id, api_key, private_key): these are capped to 100k chars, NUL removed, but otherwise kept intact (opaque fields).
  - Other strings: strip_html + remove CR/LF/NUL + truncate to 100k.
  - Non-string scalars (bool/int/float) pass; any other type in a scalar field → 400 `INVALID_INPUT_TYPE`.
  - Rewrites `request._body` + `request._receive` so downstream sees sanitized body; keeps Content-Length in sync.
  - Recursion depth guard at 20.
- **RateLimitMiddleware**:
  - Per-endpoint limits from `settings.endpoint_rate_limits`; fallback to `provider_rate_limit_per_minute` (300).
  - Key = `api:<client_ip>:<path>`; uses `RateLimiter.allow_async` (Redis sliding window when available, else local bucket).
  - On top: per-user tier bucket via `tier_subject_from_request` → `TieredTokenBucketLimiter.allow` (free/pro/institutional). Anonymous → IP window only.
  - 429 with Retry-After + X-RateLimit-* headers on exceed.
  - Exempt: test env, /docs /openapi.json /health /metrics.

## 3.3 Data

- **Inputs:** HTTP request (headers, body, client IP).
- **Outputs:** sanitized body, rate-limit decisions, security headers, trace id.
- **Storage:** none (in-memory rate limiter + tier limiter; Redis for shared sliding window rate limit + tier revocation).

## 3.4 General checklist

- **Logic:**
  - [YES] Defense-in-depth auth on sensitive write prefixes (middleware-level, in addition to router deps). [SEEN: apps/api/middleware.py:152-180]
  - [YES] CSRF origin check against cors_origins; `*` in cors_origins bypasses (same as CORS semantic). [SEEN: apps/api/middleware.py:195-271]
  - [YES] Input sanitization recurses with depth limit; opaque fields preserved. [SEEN: apps/api/middleware.py:340-405]
  - [YES] Rate limit: per-IP sliding window (Redis if available) + per-tier bucket. [SEEN: apps/api/middleware.py:407-520]
  - [NO] CSRF bypass if `cors_origins` contains `*` — then any origin allowed. [SEEN: apps/api/middleware.py:241,247] (intentional semantic match to CORS; but combined with open CORS it weakens CSRF.)
- **Time:** rate-limit windows in seconds; tier refill in seconds.
- **Data:**
  - [YES] Opaque fields preserved (password etc.) — good for credential verification. [SEEN: apps/api/middleware.py:29-41]
  - [UNKNOWN] Whether sanitization is applied to non-JSON bodies (e.g. multipart/file uploads) — out of scope (middleware only handles JSON content types).
- **Errors:**
  - [YES] Sanitization TypeError → 400. [SEEN: apps/api/middleware.py:360-370]
  - [YES] Auth failures in SecurityMiddleware → 401 with codes. [SEEN: apps/api/middleware.py:160-180]
- **Concurrency:**
  - [YES] RateLimiter.allow_async uses Redis eval (atomic) when available; local fallback uses threading.RLock. [SEEN: core/rate_limit/limiter.py]
  - [YES] Tier limiter is in-process per worker (see core-security card). [SEEN: core/security/saas.py]
- **Performance:**
  - [YES] Rate limiting uses sliding window + Redis Lua when available. [SEEN: core/rate_limit/limiter.py:91-130]
  - [UNKNOWN] Latency impact of JSON reparsing + recursive sanitize on every JSON body (could be notable for large payloads).
- **Security:**
  - [SEEN] Input sanitization on JSON bodies (strip_html, CRLF/NUL removal). [SEEN: apps/api/middleware.py:340-405]
  - [SEEN] Security headers on responses. [SEEN: apps/api/middleware.py:182-193]
  - [SEEN] Auth enforcement on sensitive write prefixes (middleware-level). [SEEN: apps/api/middleware.py:152-180]
  - [SEEN] CSRF origin check. [SEEN: apps/api/middleware.py:195-271]
  - [SEEN] `X-Content-Type-Options: nosniff` etc. [SEEN: apps/api/middleware.py:183-188]
  - [UNKNOWN] Whether file upload endpoints ( multipart) have equivalent sanitization/validation (out of this middleware's scope).
  - [SEEN] `cors_origins` default = `["http://localhost:3000"]`; production validator rejects `["*"]`. [SEEN: core/config/__init__.py:61,324-326] — but if `cors_origins` is `["*"]` in non-production env, CSRF + CORS are effectively open.

## 3.5 Specialized checklist

- **Input sanitization vs SQLi:** sanitization removes markup/control chars but is NOT SQL injection defense — relies on parameterized queries (verify). [SEEN: apps/api/middleware.py + core/security/sanitizers.py]
- **Opaque fields:** passwords/tokens kept intact (good), but note `secret` and `api_key` are in the raw allow-list — if those ever appear in a JSON body, they are not stripped of markup (but they are server-side hashed/compared per docstring).
- **Rate limit dual layer:** per-IP + per-tier — good; but tier limiter is per-process (see core-security SEC-03 / OBS-03).

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| MW-01 | apps/api/middleware.py:29-41 | `_SANITIZE_RAW_FIELDS` includes `secret`, `api_key`, `private_key` — these are preserved as opaque (not stripped of markup). If any of these fields appear in a JSON body, they pass through sanitization unchanged (only NUL removed + length capped). | [SEEN] | low | If combined with a log/render path that renders these without escaping, could be an issue. But they are server-side hashed/compared per docstring. | Confirm how these fields are used downstream (hashed vs stored vs logged). |
| MW-02 | apps/api/middleware.py:152-180 | SecurityMiddleware authenticates sensitive write prefixes at middleware level, but the list is a snapshot — new sensitive endpoints added later may be missed unless added here too. | [SEEN] | medium | New sensitive endpoint could be unprotected at middleware layer (though router deps may still cover it). | Check whether router-level deps also protect writes; ensure the list stays in sync as endpoints are added. |
| MW-03 | apps/api/middleware.py:241,247 | CSRF + CORS: if `cors_origins` contains `*`, both CSRF origin check and CORS are effectively open. | [SEEN] | medium | Open CORS + open CSRF in any non-prod env, or if prod misconfigured. | Production validator rejects `["*"]` (core/config:324-326), but confirm no other wildcard/inclusion logic bypasses. |
| MW-04 | apps/api/middleware.py:340-405 | Input sanitization only applies to JSON content types; multipart/form-data uploads are out of scope. | [SEEN] | low | File upload fields could carry markup/control chars if rendered later. | Check upload endpoints (data-import, codal attachments) for their own validation/render escaping. |
| MW-05 | apps/api/middleware.py:407-520 | Rate limiting: per-IP sliding window Redis-based when available; local fallback on Redis failure. Tier bucket is per-process. | [SEEN] | low | Under Redis outage, per-IP rate limiting degrades to local per-process buckets (workers don't share). | Acceptable for single-worker; multi-worker needs Redis for accurate per-IP limits. |
| MW-06 | apps/api/middleware.py:117,119 | Request/response logging at DEBUG level includes path but not body (good — bodies not logged by this middleware). | [SEEN] | low | Prevents logging sensitive payloads at this layer. | Verify other layers (e.g. endpoint handlers) don't log sensitive bodies. |

## 3.7 Module monetary risk

- Auth bypass on sensitive write endpoints would allow unauthorized backtests/ML/portfolio/alert/trade/data-import actions — monetary + data integrity risk.
- Rate-limit bypass could allow amplification (e.g. expensive backtests/ML calls).
- Input sanitization gap (non-JSON) could allow stored markup if rendered later.

## 3.8 Questions and unknowns

- Are file upload endpoints validated/escaped on render?
- Is the sensitive-write-prefix list kept in sync with actual endpoints?
- Are there other wildcard CORS mechanisms?

## 3.9 Recommendations for Claude

- Re-verify: SecurityMiddleware sensitive prefix list vs actual write endpoints; CSRF/CORS wildcard; input sanitization on upload endpoints; rate-limit Redis fallback behavior.
- Must-read: `apps/api/app.py` (middleware wiring + lifespan + Sentry init order).

---
*Saved: 2026-10-05 · labels: [SEEN] observed in code (path:line), full file read for apps/api/middleware.py*
