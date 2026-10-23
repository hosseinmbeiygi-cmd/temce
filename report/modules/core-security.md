# Module card: platform-security

**Name:** platform-security  
**Path:** `core/security/`  
**Tier:** 1 (auth, secrets, RBAC — blast radius high; also gates every other module)  
**Purpose:** Authentication (JWT + refresh), scoped API keys (GoldDesk SaaS), RBAC + segregation of duties, password/TOTP hashing, input sanitizers, secrets management.  
**Main files (lines):** `tokens.py` (117), `saas.py` (358), `permissions.py` (~70), `auth_context.py` (42), `ime_rbac.py` (143), `hashing.py` (54), `sanitizers.py` (65), `secrets.py` (52), `totp.py` (151), `__init__.py` (94)  
**Files read:** all of the above (full file reads)  
**Files unread:** none in this module

## 3.1 Identity

- **Entry points / consumers:**
  - `apps/api/app.py`, `apps/api/middleware.py`, `apps/api/endpoints/*` depend on `core.security` for JWT + scoped-key auth.
  - `core.security.saas.api_key_auth` is used by GoldDesk endpoints (`apps/api/endpoints/golddesk.py`, `src/gold_desk/api.py`) for scoped token enforcement.
  - `core.security.tokens` used by `core.security.saas.tier_subject_from_request`, tokens revocation flow.
  - `core.security.ime_rbac` referenced by kill-switch revival workflow (`services/kill_switch.py`) and system endpoints (`apps/api/endpoints/system.py`) per its docstring.
  - `core.security.secrets.SecretsManager` is the env-based secret reader; `core.security.tokens` and `core.security.saas` both read `settings.secret_key` (from `core.config`) as the signing key.
- **Dependencies (this module calls):** `core.config.settings`, `core.logging`, `core.cache` (for token revocation/Redis), `core.exceptions.AuthenticationError`, `pyjwt`, `hmac`, `hashlib`, `secrets`, `base64`, `struct`, `time`, `html`, `re`, `os`, `uuid`.

## 3.2 Logic and algorithms

- **JWT access/refresh tokens** (`tokens.py`):
  - Access token carries a unique `jti` (UUID hex) so individual tokens can be revoked via Redis blacklist.
  - Expiry: access = `settings.access_token_expire_minutes` (default 60), refresh = `settings.refresh_token_expire_days` (default 30).
  - Sign/verify with `settings.secret_key` + `settings.jwt_algorithm` (default HS256).
  - Revocation is best-effort: if Redis unavailable, `is_token_revoked()` returns False (safe default — token not revoked). Same for `revoke_token()` — logged warning, no-op.
- **Scoped API keys (GoldDesk)** (`saas.py`):
  - Format: `gdesk_<base64url payload>_<hmac-sha256 signature>`.
  - Payload: tier, sorted scopes, owner, token_id, exp.
  - Signing secret derived from `settings.secret_key` via SHA-256.
  - Scopes catalog: `market:read`, `market:read_extended`, `options:read`, `options:analyze`, `portfolio:read`, `portfolio:write`, `signals:read`, `signals:generate`, `gold:read`, `gold:analyze`, `admin:write`.
  - Tiers: free (10 rpm/burst 10/daily 1000), pro (120/120/50000), institutional (600/600/unlimited).
  - Per-token bucket limiter (`TieredTokenBucketLimiter`) is in-process, keyed by `gdesk:<token_id>`. 버킷은 전역 싱글톤 (`_global_tier_limiter`).
  - `api_key_auth(*required_scopes)` FastAPI dependency: reads `X-API-Key` header, verifies scoped token, enforces per-token bucket, enforces required scopes.
- **RBAC / roles** (`permissions.py`, `ime_rbac.py`):
  - Generic `Permission`/`Role` model in `permissions.py` with pre-defined roles: admin, analyst, ml_engineer, viewer.
  - IME-specific roles in `ime_rbac.py`: VIEWER, TRADER, QUANT, ADMIN (from سند §14.2).
  - Segregation of duties matrix: no single role may hold both `model:write` + `risk:write`, `policy:write` + `trade_card:approve`, `kill_switch:revive` + `model:write`.
  - Dual approval required for: `kill_switch:revive`, `risk:write`, `policy:write` (≥2 distinct approvers, no segregation violation).
- **Password hashing** (`hashing.py`):
  - PBKDF2-SHA256, default 100,000 rounds, format `{rounds}${salt}${hash}`; legacy `{salt}${hash}` verified with default rounds.
  - `hash_file` uses `core.paths.validate_safe_path` (경로 검증) before opening.
- **TOTP** (`totp.py`): RFC 6238 implementation, zero deps (hmac/base64/struct/time). Default 6 digits / 30s / SHA-1 / ±1 window. Issuer = "Iran Market Platform".
- **Secrets management** (`secrets.py`):
  - `SecretsManager` reads `SECRET_<KEY>` env vars. `get_required` raises ValueError if missing.
  - No secure storage of its own — only reads env. `rotate` writes new secret back to env (process-only, not persisted).
- **Input sanitizers** (`sanitizers.py`):
  - `sanitize_sql`: replaces `'` → `''` and removes `;`. **Note:** this is a denial-of-help, not real SQL injection defense — should rely on parameterized queries (verify callers do).
  - `sanitize_command`: strips shell metacharacters.
  - `sanitize_html`, `strip_html`, `sanitize_filename`, `sanitize_path_component`, `sanitize_log_output`, `sanitize_json_key`, plus `Sanitizer` helper class (string/int/float/bool coercion).

## 3.3 Data

- **Inputs:**
  - env vars for secrets (`SECRET_*`, `SECRET_KEY`, `GOLD_TELEGRAM_BOT_TOKEN`, etc.).
  - HTTP `Authorization: Bearer <jwt>` and `X-API-Key: <scoped key>` headers.
  - Redis for token revocation and (optionally) log aggregation.
- **Outputs:** decoded JWT payloads, scoped token objects, auth context, boolean allow/deny.
- **Storage:** no persistent storage in this module. Token revocation list lives in Redis (volatile). Secrets come from env (not stored here).
- **Data contract:** callers get either a decoded payload (`dict`), a `ScopedToken` dataclass, an `AuthContext`, or an HTTP 401/403. Consistent.

## 3.4 General checklist

- **Logic:**
  - [YES] JWT expiry enforced in `create_*_token`. [SEEN: tokens.py:30-46]
  - [YES] Token revocation uses Redis; missing Redis = not revoked (safe default). [SEEN: tokens.py:74-97]
  - [YES] Scoped token signature verified with HMAC compare. [SEEN: saas.py:215-222]
  - [NO] `sanitize_sql` is weak — only escapes single-quote and removes semicolon; does not cover all injection vectors. Rely on parameterized queries. [SEEN: sanitizers.py:9-10]
  - [UNKNOWN] Whether `sanitize_sql` is actually used anywhere — need to grep callers.
- **Time:**
  - [YES] JWT uses `datetime.now(UTC)` (UTC). [SEEN: tokens.py:26,33]
  - [YES] TOTP uses `time.time()` with ±window drift. [SEEN: totp.py:68-95]
  - [UNKNOWN] Jalali/Gregorian handling not in this module — likely in `core/time/`.
- **Data:**
  - [YES] `secrets.py` uses env only. [SEEN: secrets.py:27-46]
  - [YES] Scoped token body is base64url + HMAC; unknown tier/scope rejected. [SEEN: saas.py:224-240]
- **Errors:**
  - [YES] JWT errors raise `AuthenticationError`. [SEEN: tokens.py:48-58]
  - [YES] Scoped token errors raise `ScopedTokenError` → HTTP 401. [SEEN: saas.py:266-270]
  - [YES] Revocation failures logged and return safe default. [SEEN: tokens.py:74-97]
- **Concurrency:**
  - [YES] `TieredTokenBucketLimiter` is process-wide singleton; in-process buckets. [SEEN: saas.py:107-176]
  - [UNKNOWN] Thread/async safety of bucket counters under concurrent requests — need to check `TokenBucket` impl in `core/rate_limit/tokens.py`.
- **Performance:**
  - [YES] In-memory buckets — fast.
  - [UNKNOWN] `TieredTokenBucketLimiter` unbounded growth if many subjects; eviction policy exists (`_evict_full_buckets`, max 100k subjects). [SEEN: saas.py:133-150]
- **Security:**
  - [SEEN] `secret_key` default = `"change-me-in-production"` (core/config/__init__.py:63). **Finding:** default secret is a well-known string — must be overridden in .env for any real deployment. [SEEN: core/config/__init__.py:63,322-323]
  - [SEEN] Production validation (`validate_production`) enforces secret_key change, CORS restriction, no SQLite, cookie secure, OTLP endpoint. [SEEN: core/config/__init__.py:318-333]
  - [SEEN] `enable_input_sanitization=True` by default; middleware strips markup/control chars from request bodies. [SEEN: core/config/__init__.py:81]
  - [SEEN] `telegram_bot_token` is an empty-string default in config (core/config/__init__.py:274); actual token read from `GOLD_TELEGRAM_BOT_TOKEN` env in `telegram_bot.py`. [SEEN: core/config/__init__.py:274, src/gold_desk/telegram_bot.py:29]
  - [SEEN] No secrets printed to logs; `secrets.py` only logs "Required secret not found" without value. [SEEN: secrets.py:35-37]
  - [UNKNOWN] Whether `sanitize_log_output` is consistently applied to user-supplied values before logging — need spot-check in signal/alert paths.
- **Logging/observability:**
  - [SEEN] structlog via `get_logger`. Revocation failures and Redis-unavailable warnings logged. [SEEN: tokens.py, saas.py]
  - [UNKNOWN] Decision traceability for auth failures (who/when) — likely in middleware; not in this module.

## 3.5 Specialized checklist

- **➡ 参照先:** 金銭計算・指標・検証は他モジュール（T1-3 〜 T1-8）にて個別に評価。
- **Segregation of duties:** implemented in `ime_rbac.py` and documented as سند §14.2 / §19.3. [SEEN: ime_rbac.py:1-95]
- **Auth disabled flag:** `auth_disabled` setting exists (default False); per docstring, only way to opt out, intended for throwaway sandboxes. [SEEN: core/config/__init__.py:25, docstring]

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| SEC-01 | core/config/__init__.py:63, 322-323 | Default `SECRET_KEY` = `"change-me-in-production"`; production validator rejects it, but any env without `SECRET_KEY` set (or set to the default) uses a well-known signing key. | [SEEN] | high | JWT + scoped API keys can be forged if deployed with default secret. | Confirm .env / production env sets a real secret. If public release planned, add startup hard-fail in non-sandbox envs when secret == default. |
| SEC-02 | sanitizers.py:9-10 | `sanitize_sql` only escapes `'` and removes `;`. Not a complete SQLi defense. | [SEEN] | medium | If any caller builds SQL with string concat and relies on this, injection possible. | Find all usages of `sanitize_sql`; confirm the codebase uses parameterized queries everywhere instead. |
| SEC-03 | tokens.py:74-97, saas.py:74-97 | Token revocation / scoped-token bucket fail open when Redis unavailable (return False / allow). Safe for revocation (token not wrongly blocked), but rate limiting on scoped keys degrades to "allow" when Redis down. | [SEEN] | medium | Under Redis outage, scoped API key rate limits stop enforcing. | Decide if that is acceptable for the release; consider local fallback bucket or fail-closed for admin scopes. |
| SEC-04 | saas.py:107-176 | `TieredTokenBucketLimiter` is a process-wide in-memory singleton with max 100k subjects; eviction policy exists but under extreme churn could briefly exceed limit or evict active subjects. | [SEEN] | low | Local limit drift / spurious 429 under heavy subject churn. | Low risk for single-worker; relevant if many workers each keep own limiter (they do — in-process per worker). |
| SEC-05 | core/config/__init__.py:25, tokens.py:48-58 | `auth_disabled` flag can disable auth; documented as sandbox-only. | [SEEN] | low | If accidentally enabled in production, endpoints become open. | Ensure `validate_production` also rejects `auth_disabled=True` (currently not checked). |

## 3.7 Module monetary risk

- **If this module fails / is misconfigured:**
  - Wrong/weak secret → attacker can forge JWTs and scoped API keys → read/write access to market data, signals, portfolio, gold analysis, possibly orders via downstream modules.
  - Auth bypassed (`auth_disabled=True` or sandbox mode left on) → unauthenticated access to everything.
  - RBAC/segregation bypassed → quant + risk caps in one role (policy violation; monetary risk if risk caps can be raised by the same role that changes models).
- **Safety net:**
  - Production config validation (`validate_production`) catches default secret, open CORS, SQLite, insecure cookie.
  - Kill switch is a separate module (`services/kill_switch.py`) with dual-approval + segregation — not in this module, but connected.
  - Paper broker only (see broker card) — no live brokerage in this module.

## 3.8 Questions and unknowns

- Is `sanitize_sql` actually used anywhere, or is it dead code? (grep callers)
- Does `core/rate_limit/tokens.py` `TokenBucket` use atomic operations / locks for async concurrency?
- Is `auth_disabled=True` blocked by `validate_production`? (Currently not — see SEC-05.)
- How is refresh-token storage/replay protection handled beyond JWT expiry? (This module only does JWT + Redis revocation for access tokens.)
- Are scoped tokens revocable? (Current design: no revocation for `gdesk_*` keys — they are valid until expiry. Only JWT access tokens are revoked.)

## 3.9 Recommendations for Claude

- **Re-verify:**
  1. `core/config/__init__.py:63,322-323` — default secret + production validation.
  2. `sanitizers.py:9-10` + all callers of `sanitize_sql` — is it relied on?
  3. `core/security/saas.py:107-176` — TokenBucket concurrency + eviction.
  4. `core/security/tokens.py:74-97` — revocation fail-open behavior.
- **Must-read for Claude:**
  - `core/config/__init__.py` (full) — env → settings → production validation.
  - `apps/api/middleware.py` — where auth + per-IP rate limit + input sanitization middleware is wired.
  - `services/kill_switch.py` — how the kill switch uses `ime_rbac` dual approval.
  - Any endpoint that accepts recommendation/order input (`apps/api/endpoints/trades.py`, `recommendations.py`, `compose.py`, `src/gold_desk/api.py`) for authz + input validation.

---
*Saved: 2026-10-05 · labels: [SEEN] observed in code (path:line), full file reads for core/security/*.py*
