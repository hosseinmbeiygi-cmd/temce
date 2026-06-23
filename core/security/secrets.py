from __future__ import annotations

import os
import secrets

from core.logging import get_logger

logger = get_logger(__name__)


def generate_secret(length: int = 32) -> str:
    return secrets.token_hex(length)


def generate_api_key() -> str:
    return f"imk_{secrets.token_hex(32)}"


def generate_token() -> str:
    return secrets.token_hex(32)


def generate_otp(length: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def generate_password(length: int = 16) -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return "".join(secrets.choice(chars) for _ in range(length))


class SecretsManager:
    def __init__(self, env_prefix: str = "SECRET_") -> None:
        self.env_prefix = env_prefix

    def get(self, key: str, default: str | None = None) -> str | None:
        return os.environ.get(f"{self.env_prefix}{key.upper()}", default)

    def get_required(self, key: str) -> str:
        value = self.get(key)
        if value is None:
            logger.debug("Required secret not found: %s%s", self.env_prefix, key.upper())
            raise ValueError("Required secret not found")
        return value

    def set(self, key: str, value: str) -> None:
        os.environ[f"{self.env_prefix}{key.upper()}"] = value

    def rotate(self, key: str) -> str:
        new_value = generate_secret()
        self.set(key, new_value)
        return new_value
