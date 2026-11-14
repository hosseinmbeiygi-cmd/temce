from __future__ import annotations

import uvicorn

from core.config import settings


def main() -> None:
    kwargs: dict = {
        "host": settings.server_host,
        "port": settings.server_port,
        "log_level": settings.log_level.lower(),
    }
    if settings.is_development:
        kwargs["reload"] = True
    else:
        kwargs["workers"] = settings.workers
    uvicorn.run("apps.api.app:app", **kwargs)


if __name__ == "__main__":
    main()
