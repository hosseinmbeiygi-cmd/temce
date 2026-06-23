from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    url: str = Field(default="sqlite:///data/market.db", alias="DATABASE_URL")
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    connect_timeout: int = 10
    statement_timeout: int = 30
    migration_dir: str = "./migrations"
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_default_ttl: int = 300
    redis_max_connections: int = 20

    @property
    def async_url(self) -> str:
        if self.url.startswith("sqlite"):
            return self.url.replace("sqlite:///", "sqlite+aiosqlite:///")
        if "postgres" in self.url:
            if "+" in self.url.split("://", 1)[0]:
                return self.url
            return self.url.replace("://", "+asyncpg://", 1)
        return self.url
