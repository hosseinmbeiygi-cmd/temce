"""Unit tests for ``core/security/hashing.py``.

Covers the rounds-format password hash (``{rounds}${salt}${hash}``),
backward compatibility with the legacy ``{salt}${hash}`` format, and
malformed-input safety.
"""

from __future__ import annotations

import hashlib
import secrets

from core.security.hashing import (
    _DEFAULT_ROUNDS,
    generate_salt,
    hash_data,
    hash_file,
    hash_password,
    verify_password,
)

# ── Password hashing (rounds format) ───────────────────────────────


def test_hash_password_embeds_rounds_and_salt():
    hashed = hash_password("my-secret")
    parts = hashed.split("$")
    assert len(parts) == 3
    rounds, salt, digest = parts
    assert rounds == str(_DEFAULT_ROUNDS)
    assert len(salt) == 32  # 16 bytes token_hex
    assert len(digest) == 64  # sha256 hex
    # digest is reproducible from salt + rounds
    expected = hashlib.pbkdf2_hmac(
        "sha256", b"my-secret", salt.encode(), _DEFAULT_ROUNDS
    ).hex()
    assert digest == expected


def test_verify_password_roundtrip():
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hash_password_custom_rounds_embedded():
    hashed = hash_password("pw", rounds=5_000)
    assert hashed.split("$")[0] == "5000"
    assert verify_password("pw", hashed) is True


def test_verify_password_uses_embedded_rounds():
    # A low-rounds hash verifies quickly and proves the embedded rounds value
    # is used (not the default).
    hashed = hash_password("pw", rounds=1_000)
    assert hashed.split("$")[0] == "1000"
    assert verify_password("pw", hashed) is True


def test_verify_password_legacy_format_compat():
    """Pre-rounds hashes (``{salt}${hash}``) verify with the default rounds."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", b"legacy-pw", salt.encode(), _DEFAULT_ROUNDS
    ).hex()
    legacy = f"{salt}${digest}"
    assert verify_password("legacy-pw", legacy) is True
    assert verify_password("nope", legacy) is False


def test_verify_password_handles_malformed_input():
    assert verify_password("x", "") is False
    assert verify_password("x", "not-a-hash") is False
    assert verify_password("x", "$nope") is False
    assert verify_password("x", "abc$def$ghi$extra") is False
    assert verify_password("x", "notint$salt$digest") is False
    assert verify_password("x", None) is False  # type: ignore[arg-type]


def test_verify_password_distinct_hashes_same_password():
    # Salted hashes must differ even for identical passwords.
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1) is True
    assert verify_password("same", h2) is True


# ── hash_data / hash_file ──────────────────────────────────────────


def test_hash_data_is_sha256():
    assert hash_data("hello") == hashlib.sha256(b"hello").hexdigest()
    assert hash_data("hello") == hash_data("hello")
    assert hash_data("hello") != hash_data("world")


def test_hash_file(tmp_path):
    f = tmp_path / "data.txt"
    f.write_bytes(b"file contents")
    expected = hashlib.sha256(b"file contents").hexdigest()
    assert hash_file(str(f)) == expected
    assert hash_file(str(f), algorithm="md5") == hashlib.md5(b"file contents").hexdigest()


# ── salt helper ────────────────────────────────────────────────────


def test_generate_salt_length_and_uniqueness():
    s1 = generate_salt()
    s2 = generate_salt()
    assert len(s1) == 32
    assert s1 != s2
    assert len(generate_salt(length=8)) == 16
