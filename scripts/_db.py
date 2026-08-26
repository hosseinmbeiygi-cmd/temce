"""Shared DB connection helpers for ad-hoc scripts.

All connection details come from ``core.settings`` (``DATABASE_URL`` in
``.env``) — scripts must NOT hardcode credentials. When running
``python scripts/foo.py`` the scripts directory is on ``sys.path`` so
``import _db`` resolves this module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy.engine import make_url  # noqa: E402

from core.config import settings  # noqa: E402


def database_url_async() -> str:
    """Return the async SQLAlchemy database URL from settings."""
    return settings.database_url_async


def psycopg2_connect(**overrides):
    """Open a psycopg2 connection using settings, with optional overrides."""
    import psycopg2

    url = make_url(settings.database_url_async)
    kwargs = {
        "host": url.host,
        "port": url.port or 5432,
        "dbname": url.database,
        "user": url.username,
        "password": url.password,
    }
    kwargs.update(overrides)
    return psycopg2.connect(**kwargs)
