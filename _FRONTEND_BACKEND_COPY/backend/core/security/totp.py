"""TOTP (RFC 6238) — Time-based One-Time Passwords.

Zero-dependency implementation built on :mod:`hmac`, :mod:`base64` and
:mod:`struct` so MFA works without requiring ``pyotp`` or other packages.

Typical flow::

    secret = generate_totp_secret()          # store per user (base32)
    uri    = build_totp_uri(secret, "user")  # feed to authenticator app QR
    ok     = verify_totp(secret, code)       # check the 6-digit code
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

# Default: 6 digits, 30s period, SHA-1 — the de-facto authenticator-app default.
_DEFAULT_DIGITS = 6
_DEFAULT_PERIOD = 30
_DEFAULT_ALGORITHM = "sha1"

# RFC 6238 only defines HMAC-SHA1/SHA256/SHA512.
_ALLOWED_ALGORITHMS = ("sha1", "sha256", "sha512")

# Tolerate ±1 time step of clock drift by default.
_DEFAULT_WINDOW = 1

_ISSUER = "Iran Market Platform"


def generate_totp_secret(length: int = 20) -> str:
    """Return a random base32 secret (20 bytes = 160-bit, standard for TOTP)."""
    return base64.b32encode(secrets.token_bytes(length)).decode().rstrip("=")


def _int_to_bytestring(value: int) -> bytes:
    """8-byte big-endian representation of a counter value."""
    return struct.pack(">Q", value)


def _hmac_digest(secret_b32: str, counter: int, algorithm: str = _DEFAULT_ALGORITHM) -> bytes:
    if algorithm not in _ALLOWED_ALGORITHMS:
        raise ValueError(f"Unsupported TOTP algorithm: {algorithm!r}")
    key = base64.b32decode(secret_b32.upper() + "=" * ((8 - len(secret_b32) % 8) % 8))
    msg = _int_to_bytestring(counter)
    digest = hmac.new(key, msg, getattr(hashlib, algorithm)).digest()
    return digest


def generate_totp(
    secret: str,
    *,
    digits: int = _DEFAULT_DIGITS,
    period: int = _DEFAULT_PERIOD,
    algorithm: str = _DEFAULT_ALGORITHM,
    timestamp: float | None = None,
) -> str:
    """Compute the current TOTP code for ``secret`` (RFC 4226 HOTP + 6238 TOTP).

    ``timestamp`` overrides ``time.time()`` (useful for deterministic tests).
    """
    if not secret:
        raise ValueError("TOTP secret must not be empty")
    t = time.time() if timestamp is None else timestamp
    counter = int(t // period)
    digest = _hmac_digest(secret, counter, algorithm)
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = binary % (10**digits)
    return str(code).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    *,
    digits: int = _DEFAULT_DIGITS,
    period: int = _DEFAULT_PERIOD,
    algorithm: str = _DEFAULT_ALGORITHM,
    window: int = _DEFAULT_WINDOW,
    timestamp: float | None = None,
) -> bool:
    """Verify a TOTP code allowing ±``window`` time steps of clock drift."""
    if not code or not code.isdigit() or len(code) != digits:
        return False
    if not secret:
        return False
    t = time.time() if timestamp is None else timestamp
    counter = int(t // period)
    for delta in range(-window, window + 1):
        expected = generate_totp(
            secret,
            digits=digits,
            period=period,
            algorithm=algorithm,
            timestamp=(counter + delta) * period,
        )
        if hmac.compare_digest(expected, code):
            return True
    return False


def build_totp_uri(
    secret: str,
    account_name: str,
    issuer: str = _ISSUER,
    *,
    digits: int = _DEFAULT_DIGITS,
    period: int = _DEFAULT_PERIOD,
    algorithm: str = _DEFAULT_ALGORITHM,
) -> str:
    """Build an ``otpauth://`` provisioning URI for QR codes.

    Works with Google Authenticator, Aegis, 2FAS, Authy, etc.
    """
    label = quote(f"{issuer}:{account_name}", safe="")
    params = {
        "secret": secret,
        "issuer": issuer,
        "algorithm": algorithm.upper(),
        "digits": str(digits),
        "period": str(period),
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"otpauth://totp/{label}?{query}"


def parse_totp_uri(uri: str) -> dict[str, str]:
    """Parse an ``otpauth://`` URI back into its parts (round-trip helper)."""
    from urllib.parse import parse_qs, unquote, urlparse

    parsed = urlparse(uri)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    secret = params.get("secret", "")
    # The label is percent-encoded (e.g. ``issuer%3Aaccount``), so decode first.
    label = unquote(parsed.path.lstrip("/"))
    account = label.split(":", 1)[-1]
    return {
        "secret": secret,
        "account": account,
        "issuer": params.get("issuer", ""),
        "algorithm": params.get("algorithm", _DEFAULT_ALGORITHM.lower()),
        "digits": params.get("digits", str(_DEFAULT_DIGITS)),
        "period": params.get("period", str(_DEFAULT_PERIOD)),
    }
