"""
BrsApi.ir Integration Module
============================

Complete integration layer for BrsApi.ir — Iran's comprehensive financial
data API provider. This module handles:

- TSETMC realtime data (all symbols, indices, options, NAV, trades)
- IME data (futures, options, certificates, commodity funds, physical trades)
- Global commodity prices (metals, energy)
- Cryptocurrency prices
- Codal announcements

Architecture Layers:
    config.BrsApiConfig     →  Endpoints, API keys, rate limits
    client.BrsApiClient     →  HTTP client with retry / circuit-breaker
    rate_limiter            →  Token-bucket rate limiter per endpoint
    parsers                 →  Raw JSON → domain entity mappers
    models                  →  SQLAlchemy ORM models
    repositories            →  Data access layer
    services                →  Sync orchestration & query services
    jobs                    →  APScheduler / Celery Beat job definitions
"""

from brsapi.client import BrsApiClient
from brsapi.config import BrsApiEndpoints, BrsApiSettings, EndpointConfig, SyncInterval, settings
from brsapi.rate_limiter import RateLimiter, get_rate_limiter

__all__ = [
    "BrsApiSettings",
    "BrsApiClient",
    "BrsApiEndpoints",
    "EndpointConfig",
    "SyncInterval",
    "RateLimiter",
    "get_rate_limiter",
    "settings",
]
