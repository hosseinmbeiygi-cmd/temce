from __future__ import annotations

import uvicorn

from core.config import settings


def main() -> None:
    uvicorn.run(
        "apps.api.app:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.is_development,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
