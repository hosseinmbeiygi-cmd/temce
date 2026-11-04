"""Single source of truth for the router-auth gate and its unit test.

The allowlist used to be duplicated in scripts/check_router_auth.py and
tests/unit/api/test_router_auth_coverage.py; a route added to one list silently
drifted from the other. Paths here are relative to ``settings.api_prefix``.
"""
from __future__ import annotations

AUTH_DEP_ATTR = "__auth_guard__"

# Named functions only. Closures (require_roles, api_key_auth) are detected by
# AUTH_DEP_ATTR, never by their generic ``_check`` name.
AUTH_NAMES = frozenset(
    {"get_current_user", "get_current_active_user", "require_role"}
)
# Enforces auth on mutating methods only; legal only under PUBLIC_READ_PREFIXES.
WRITE_ONLY_AUTH_NAMES = frozenset({"require_user_for_writes"})

# Tokens the source-text scan of apps/api/app.py accepts. That scan cannot see
# the dependency graph, so it also accepts factory names.
AUTH_SOURCE_TOKENS = AUTH_NAMES | frozenset(
    {"require_roles", "require_any_role", "api_key_auth"}
)

PUBLIC_PREFIXES = frozenset({"", "/health", "/auth"})

PUBLIC_EXACT_PATHS = frozenset(
    {
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/gold/health",
        "/gold/assistant-rules",
        "/gold/analytics/summary",
        "/gold/analytics/macro/calendar",
        "/gold/analytics/macro/iran-events",
        "/gold/analytics/feed-health",
    }
)

PUBLIC_READ_PREFIXES = frozenset(
    {
        "/market",
        "/market-dashboard",
        "/market-watch",
        "/market-info",
        "/instruments",
        "/symbols",
        "/quotes",
        "/orderbooks",
        "/trades",
        "/indicators",
        "/macro",
        "/news",
        "/codal",
        "/codal-accounting",
        "/codal-audit",
        "/codal-professional",
        "/options",
        "/funds",
        "/api/options",
        "/pre-buy",
    }
)

APP_LEVEL_PUBLIC_PATHS = frozenset({"/", "/metrics"})

# A WebSocket is authenticated by verify_websocket_token() in its handler.
# Anything else must be named here explicitly.
WS_PUBLIC_ALLOWLIST: frozenset[str] = frozenset()

# FastAPI 0.128 wraps every include_router() in one private _IncludedRouter.
# If that shape changes, the gate must fail loudly instead of auditing 8 routes.
MIN_OPERATIONS = 500
