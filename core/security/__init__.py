from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import settings
from core.exceptions import AuthenticationError


def generate_api_key() -> str:
    return f"imk_{secrets.token_hex(32)}"


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_api_key(key), hashed)


def generate_token() -> str:
    return secrets.token_hex(32)


def generate_id(prefix: str = "") -> str:
    uid = secrets.token_hex(16)
    return f"{prefix}_{uid}" if prefix else uid


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    salt, pwd_hash = hashed.split("$", 1)
    return hmac.compare_digest(
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex(),
        pwd_hash,
    )


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    import jwt

    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    import jwt

    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")


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


import base64
