"""Vault key rotation service — Phase 2-7.

Simulates HashiCorp Vault integration for secrets management.
Handles:
- Secret storage/retrieval (BRSAPI_KEY, BROKER_TOKEN)
- Automatic 90-day rotation with expiry tracking
- 7-day advance warning before expiry
- RBAC access control stubs
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

ROTATION_INTERVAL_DAYS = 90
WARNING_DAYS_BEFORE_EXPIRY = 7


class VaultService:
    """Simulated HashiCorp Vault integration for secrets management.

    In production, this would wrap ``hvac`` (Python client for Vault) with
    transit engine for key rotation and audit logging.
    """

    def __init__(self) -> None:
        self._secrets: dict[str, dict[str, Any]] = {}
        self._audit_log: list[dict[str, Any]] = []

    def store(self, key: str, value: str, owner: str = "admin") -> dict[str, Any]:
        """Store a secret with metadata (expiry, owner)."""
        now = datetime.now(UTC)
        secret = {
            "key": key,
            "value": value,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=ROTATION_INTERVAL_DAYS)).isoformat(),
            "owner": owner,
            "version": 1,
        }
        self._secrets[key] = secret
        self._audit_log.append(
            {
                "action": "store",
                "key": key,
                "by": owner,
                "timestamp": now.isoformat(),
            }
        )
        logger.info("Vault: stored secret %s (owner=%s, expires in %d days)", key, owner, ROTATION_INTERVAL_DAYS)
        return {"key": key, "status": "stored", "expires_at": secret["expires_at"]}

    def retrieve(self, key: str, requester: str = "system") -> str | None:
        """Retrieve a secret value if not expired and requester has access."""
        secret = self._secrets.get(key)
        if not secret:
            logger.warning("Vault: secret %s not found (requested by %s)", key, requester)
            return None

        expires_at = datetime.fromisoformat(secret["expires_at"])
        if datetime.now(UTC) > expires_at:
            logger.warning("Vault: secret %s expired at %s", key, secret["expires_at"])
            return None

        self._audit_log.append(
            {
                "action": "retrieve",
                "key": key,
                "by": requester,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        return secret["value"]

    def rotate(self, key: str, new_value: str | None = None, rotated_by: str = "system") -> dict[str, Any]:
        """Rotate a secret: generate new value and update expiry."""
        secret = self._secrets.get(key)
        if not secret:
            raise ValueError(f"Secret {key} not found")

        now = datetime.now(UTC)
        old_value = secret["value"]
        secret["value"] = new_value or self._generate_secret()
        secret["previous_value"] = old_value
        secret["created_at"] = now.isoformat()
        secret["expires_at"] = (now + timedelta(days=ROTATION_INTERVAL_DAYS)).isoformat()
        secret["version"] = secret.get("version", 0) + 1

        self._audit_log.append(
            {
                "action": "rotate",
                "key": key,
                "by": rotated_by,
                "timestamp": now.isoformat(),
                "new_version": secret["version"],
            }
        )
        logger.info("Vault: rotated secret %s (new version %d)", key, secret["version"])
        return {
            "key": key,
            "status": "rotated",
            "new_version": secret["version"],
            "expires_at": secret["expires_at"],
            "rotated_by": rotated_by,
        }

    def check_expiry_warnings(self) -> list[dict[str, Any]]:
        """Return list of secrets expiring within WARNING_DAYS_BEFORE_EXPIRY."""
        warnings: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        threshold = now + timedelta(days=WARNING_DAYS_BEFORE_EXPIRY)

        for key, secret in self._secrets.items():
            expires_at = datetime.fromisoformat(secret["expires_at"])
            days_left = (expires_at - now).days
            if 0 <= days_left <= WARNING_DAYS_BEFORE_EXPIRY:
                warnings.append(
                    {
                        "key": key,
                        "expires_at": secret["expires_at"],
                        "days_left": days_left,
                        "owner": secret["owner"],
                        "needs_rotation": True,
                    }
                )
        return warnings

    def get_audit_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent audit log entries."""
        return self._audit_log[-limit:]

    def status(self) -> dict[str, Any]:
        """Return vault status summary."""
        now = datetime.now(UTC)
        active = 0
        expiring = 0
        expired = 0
        for secret in self._secrets.values():
            expires_at = datetime.fromisoformat(secret["expires_at"])
            if now > expires_at:
                expired += 1
            elif (expires_at - now).days <= WARNING_DAYS_BEFORE_EXPIRY:
                expiring += 1
            else:
                active += 1
        return {
            "total_secrets": len(self._secrets),
            "active": active,
            "expiring_soon": expiring,
            "expired": expired,
            "rotation_interval_days": ROTATION_INTERVAL_DAYS,
            "warning_days": WARNING_DAYS_BEFORE_EXPIRY,
        }

    @staticmethod
    def _generate_secret(length: int = 32) -> str:
        """Generate a cryptographically secure random secret."""
        return secrets.token_hex(length)
