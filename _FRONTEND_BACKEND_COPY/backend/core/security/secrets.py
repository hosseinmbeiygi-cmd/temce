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


class VaultBackend:
    """Abstract Vault/KMS backend — plug HashiCorp Vault, AWS SM, or Azure KV.

    The default implementation falls back to env vars so existing deployments
    keep working. Override `fetch` in a subclass and pass it to SecretsManager.
    """

    def fetch(self, key: str) -> str | None:
        return None


class EnvVaultBackend(VaultBackend):
    def __init__(self, env_prefix: str = "SECRET_") -> None:
        self.env_prefix = env_prefix

    def fetch(self, key: str) -> str | None:
        return os.environ.get(f"{self.env_prefix}{key.upper()}")


class SecretsManager:
    def __init__(
        self, env_prefix: str = "SECRET_", backend: VaultBackend | None = None
    ) -> None:
        self.env_prefix = env_prefix
        self._backend: VaultBackend = backend or EnvVaultBackend(env_prefix)
        # Optional HashiCorp Vault via hvac if VAULT_ADDR/VAULT_TOKEN are set
        self._vault_client = None
        vault_addr = os.environ.get("VAULT_ADDR")
        vault_token = os.environ.get("VAULT_TOKEN")
        if vault_addr and vault_token:
            try:
                import hvac  # type: ignore

                self._vault_client = hvac.Client(url=vault_addr, token=vault_token)
                logger.info("Vault backend enabled at %s", vault_addr)
            except Exception as exc:
                logger.warning("Vault init failed, falling back to env: %s", exc)

    def get(self, key: str, default: str | None = None) -> str | None:
        # 1) Try Vault KV v2 at secret/<key>
        if self._vault_client is not None:
            try:
                # hvac KV v2 path: secret/data/<key>
                resp = self._vault_client.secrets.kv.v2.read_secret_version(path=key.lower())
                val = resp.get("data", {}).get("data", {}).get("value")
                if val:
                    return str(val)
            except Exception:
                pass
        # 2) Try env / backend
        val = self._backend.fetch(key)
        if val is not None:
            return val
        # 3) Direct env without prefix (DATABASE_URL, SECRET_KEY, etc.)
        direct = os.environ.get(key) or os.environ.get(key.upper())
        if direct is not None:
            return direct
        return default

    def get_required(self, key: str) -> str:
        value = self.get(key)
        if value is None:
            logger.debug("Required secret not found: %s%s", self.env_prefix, key.upper())
            raise ValueError(f"Required secret not found: {key}")
        return value

    def set(self, key: str, value: str) -> None:
        os.environ[f"{self.env_prefix}{key.upper()}"] = value
        # Also write to Vault if connected
        if self._vault_client is not None:
            try:
                self._vault_client.secrets.kv.v2.create_or_update_secret(
                    path=key.lower(), secret={"value": value}
                )
            except Exception as exc:
                logger.warning("Vault write failed for %s: %s", key, exc)

    def rotate(self, key: str) -> str:
        new_value = generate_secret()
        self.set(key, new_value)
        return new_value
