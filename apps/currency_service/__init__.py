"""Standalone currency & USD/USDT market service.

Lightweight FastAPI app on port 8002. Mock/fixture data today; real collectors
later (Tgju/Nobitex/Bonbast). Manual positions persisted in the shared
PostgreSQL via ``core.database.engine``.
"""

__version__ = "0.1.0"
