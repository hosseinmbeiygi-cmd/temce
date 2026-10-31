"""Test-only ASGI server for manual UI/API testing.

This intentionally does NOT run the production lifespan: the real startup
builds snapshots, starts the BrsApi scheduler, fetches news and seeds data.
For UI testing we only need the routers, PostgreSQL and Redis.

Environment (read from repo .env, then overridden):
  DATABASE_URL -> postgresql://<DB_USER>:<DEV_POSTGRES_PASSWORD>@127.0.0.1:15432/tse_quant_verify
  REDIS_URL    -> redis://127.0.0.1:16379/0
  ENV=test, AUTH_DISABLED=false
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for path in (ROOT / ".env",):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _redis_url() -> str:
    """Use the test Redis on 16379; read its requirepass from the container
    config without printing it. 16379 is the only Redis allowed by the project
    rules for test work."""
    try:
        import json
        import subprocess

        raw = subprocess.check_output(
            ["docker", "inspect", "tse_redis", "--format", "{{json .Config}}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        cmd = (json.loads(raw).get("Cmd") or [])
        for i, arg in enumerate(cmd):
            if arg == "--requirepass" and i + 1 < len(cmd):
                return f"redis://:{cmd[i + 1]}@127.0.0.1:16379/0"
    except Exception:
        pass
    return "redis://127.0.0.1:16379/0"


def main() -> None:
    env = _load_env()
    user = env.get("DB_USER", "quant_dev")
    password = env.get("DEV_POSTGRES_PASSWORD") or env.get("DB_PASSWORD") or ""
    if not password:
        raise SystemExit("DEV_POSTGRES_PASSWORD is missing in .env")

    test_db = "tse_quant_verify"
    dsn = f"postgresql://{user}:{password}@127.0.0.1:15432/{test_db}"
    os.environ.update(
        {
            "DATABASE_URL": dsn,
            "DATABASE_URL_ASYNC": dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
            "REDIS_URL": _redis_url(),
            "ENV": "test",
            "AUTH_DISABLED": "false",
            "AUTH_COOKIE_SECURE": "false",
            "AUTH_COOKIE_SAMESITE": "lax",
            "SECRET_KEY": env.get("SECRET_KEY") or "ui-test-only-secret-not-for-production",
            "GOLD_API_TOKEN_SALT": env.get("GOLD_API_TOKEN_SALT") or "ui-test-only-salt",
            "SENTRY_DSN": "",
            "OTLP_ENDPOINT": "",
        }
    )

    @asynccontextmanager
    async def lifespan(_app):
        from core.cache import get_cache
        from core.database import init_database

        await init_database()
        try:
            await get_cache().initialize()
        except Exception:
            # Auth works without Redis; rate limiting degrades to null cache.
            pass
        yield

    from fastapi import FastAPI

    from apps.api.error_handlers import register_error_handlers
    from apps.api.router import Router
    from core.config import settings

    app = FastAPI(title="UI test harness", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(Router().setup(), prefix=settings.api_prefix)

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
