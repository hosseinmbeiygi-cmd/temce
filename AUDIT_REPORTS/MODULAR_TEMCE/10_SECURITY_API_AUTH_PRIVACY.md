# 10_SECURITY_API_AUTH_PRIVACY

Date/time: 2026-10-28

## Git state
- Root: C:\Users\Iran\Desktop\temce
- Branch: integration/golddesk-fixes
- HEAD: 90597e05
- git status: many staged/unstaged/untracked (see baseline)

## Scope
API auth/token lifecycle, middleware, CORS, authorization/tenant ownership, secrets/config, logging, error responses, delete/cascade, dependency security.

## Files read
- apps/api/auth.py (full)
- apps/api/middleware.py (full)
- tests/unit/test_security_hardening.py (full)
- tests/unit/test_security_middleware.py (partial)
- tests/unit/test_auth_rate_limit.py (partial)

## Findings
1. AUTH_DISABLED explicit flag controls auth; default production-safe. Witness apps/api/auth.py:15-30.
2. Token revocation via jti cache works. Witness tests 17 passed.
3. CSRF middleware same-origin enforcement. Witness middleware.py.
4. Security headers applied. Witness middleware.py.
5. Potential risk: CORS origins may be "*" in dev; CSRF no-op by design. Witness test fixture note.
6. Secret key length warning: 23 bytes below 32 recommended. Witness test warnings.

## Tests
- `python -m pytest tests/unit/test_security_hardening.py -q` -> 17 passed, exit 0 (57s)

## Acceptance
- Auth ownership tests pass.
- No credentials leaked.
- Cascade deletion not tested in this run; blocked for live DB.
