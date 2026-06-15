from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SECURITY_", env_file=".env", extra="ignore")

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    api_key_header: str = "X-API-Key"
    allowed_hosts: list[str] = ["*"]
    bcrypt_rounds: int = 12
    jwt_algorithm: str = "HS256"
    rate_limit_per_minute: int = 60
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    session_timeout_minutes: int = 30
    enable_csrf: bool = True
    enable_https_redirect: bool = False
    content_security_policy: str | None = None
