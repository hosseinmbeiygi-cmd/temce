"""Uvicorn entrypoint. ``uvicorn apps.currency_service.app:currency_app``."""

from __future__ import annotations

import uvicorn

from apps.currency_service.config import settings


def main() -> None:
    uvicorn.run(
        "apps.currency_service.app:currency_app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
