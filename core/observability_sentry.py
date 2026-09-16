"""Sentry error tracking — optional, activated by settings.sentry_dsn.

Called from the API lifespan (apps/api/app.py) before any other init so
errors raised during startup are captured too. A missing/empty SENTRY_DSN
keeps the app 100% Sentry-free (no SDK import, no network calls), which is
the default for local development and offline environments.
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_initialized = False


def init_sentry(settings: Any) -> bool:
    """Initialize the Sentry SDK if a DSN is configured. Returns success."""
    global _initialized

    dsn = getattr(settings, "sentry_dsn", None)
    if not dsn:
        logger.debug("SENTRY_DSN not set — Sentry disabled")
        return False

    if _initialized:
        return True

    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed — run: pip install 'sentry-sdk[fastapi]>=2.0'")
        return False

    environment = "production" if getattr(settings, "is_production", False) else "development"

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        # Configurable sampling; default keeps 100% of errors and 10% traces.
        traces_sample_rate=float(getattr(settings, "sentry_traces_sample_rate", 0.1) or 0.1),
        attach_stacktrace=True,
        send_default_pii=False,
        # Never log request bodies — they can carry credentials/tokens.
        before_send=_scrub_breadcrumbs,
        integrations=[
            AsyncioIntegration(),
            FastApiIntegration(),
            RedisIntegration(),
            SqlalchemyIntegration(),
        ],
    )
    _initialized = True
    logger.info("Sentry initialized (env=%s)", environment)
    return True


def _scrub_breadcrumbs(event: dict, _hint: dict) -> dict:
    """Drop events carrying authorization headers; keep everything else."""
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    sensitive = {"Authorization", "Cookie", "X-API-Key", "Proxy-Authorization"}
    if any(k in headers for k in sensitive):
        request.pop("headers", None)
    return event
