from __future__ import annotations

import hashlib
import hmac
import secrets

from core.paths import validate_safe_path


def hash_password(password: str, rounds: int = 100_000) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, pwd_hash = hashed.split("$", 1)
        return hmac.compare_digest(
            hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex(),
            pwd_hash,
        )
    except (ValueError, AttributeError):
        return False


def hash_data(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def hash_file(path: str, algorithm: str = "sha256") -> str:
    safe_path = validate_safe_path(path)
    h = hashlib.new(algorithm)
    with open(safe_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_salt(length: int = 16) -> str:
    return secrets.token_hex(length)
