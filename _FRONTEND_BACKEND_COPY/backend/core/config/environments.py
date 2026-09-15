from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


ENV_FILE_MAP: dict[Environment, str] = {
    Environment.DEVELOPMENT: ".env.development",
    Environment.STAGING: ".env.staging",
    Environment.PRODUCTION: ".env.production",
    Environment.TESTING: ".env.testing",
}


def get_env_file(env: str | None = None) -> str:
    if env is None:
        from core.config import settings

        env = settings.environment
    try:
        return ENV_FILE_MAP[Environment(env)]
    except (ValueError, KeyError):
        return ".env"
