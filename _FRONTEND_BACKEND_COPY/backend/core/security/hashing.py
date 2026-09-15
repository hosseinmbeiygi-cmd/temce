from __future__ import annotations

import hashlib
import hmac
import secrets

from core.paths import validate_safe_path

# Default PBKDF2 iteration count used when no rounds are embedded in the hash.
_DEFAULT_ROUNDS = 100_000

# Hash format: ``{rounds}${salt}${hash}``. Older hashes (pre-rounds format)
# are ``{salt}${hash}`` and are verified with _DEFAULT_ROUNDS.


def hash_password(password: str, rounds: int = _DEFAULT_ROUNDS) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds)
    return f"{rounds}${salt}${pwd_hash.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        parts = hashed.split("$")
        if len(parts) == 3:
            rounds, salt, pwd_hash = parts
            rounds = int(rounds)
        else:
            # Legacy format: ``{salt}${hash}`` — verify with the default rounds.
            salt, pwd_hash = parts
            rounds = _DEFAULT_ROUNDS
        return hmac.compare_digest(
            hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds).hex(),
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
