"""Security helpers — single facade over the canonical submodules.

This module **re-exports** the canonical implementations defined in
``core.security.hashing``, ``core.security.tokens`` and
``core.security.secrets`` so that both import styles work:

    from core.security import hash_password          # facade
    from core.security.hashing import hash_password  # direct

Historically this file duplicated the implementations, which let the two
copies drift apart (e.g. ``verify_password`` without error handling).
Today it is a thin facade only.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

from core.config import settings
from core.security.hashing import hash_data, hash_file, hash_password, verify_password
from core.security.secrets import (
    SecretsManager,
    generate_api_key,
    generate_otp,
    generate_password,
    generate_secret,
    generate_token,
)
from core.security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)

__all__ = [
    # hashing
    "hash_password",
    "verify_password",
    "hash_data",
    "hash_file",
    # tokens
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    # secrets
    "generate_api_key",
    "generate_secret",
    "generate_token",
    "generate_otp",
    "generate_password",
    "SecretsManager",
    # api-key helpers (defined here)
    "hash_api_key",
    "verify_api_key",
    "generate_id",
    # encryption (defined here)
    "encrypt_data",
    "decrypt_data",
]


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str, hashed: str) -> bool:
    import hmac

    return hmac.compare_digest(hash_api_key(key), hashed)


def generate_id(prefix: str = "") -> str:
    uid = secrets.token_hex(16)
    return f"{prefix}_{uid}" if prefix else uid


def encrypt_data(data: str) -> str:
    from cryptography.fernet import Fernet

    key = hashlib.sha256(settings.secret_key.encode()).digest()
    f = Fernet(base64.urlsafe_b64encode(key))
    return f.encrypt(data.encode()).decode()


def decrypt_data(encrypted: str) -> str:
    from cryptography.fernet import Fernet

    key = hashlib.sha256(settings.secret_key.encode()).digest()
    f = Fernet(base64.urlsafe_b64encode(key))
    return f.decrypt(encrypted.encode()).decode()
