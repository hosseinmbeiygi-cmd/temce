"""Redaction helpers for values that must never reach logs."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def redact_redis_url(url: str) -> str:
    """Mask the password in a Redis URL before it is logged.

    A URL that cannot be parsed is replaced entirely: echoing the original
    could leak the very credential this helper exists to hide.
    """

    if not isinstance(url, str) or not url:
        return "redis://***"

    try:
        parts = urlsplit(url)
        if parts.scheme not in ("redis", "rediss") or not parts.netloc:
            return "redis://***"

        if "@" not in parts.netloc:
            # ``redis://:secret`` (no host) is a malformed credential URL;
            # never echo it. A normal host:port URL has no secret to mask.
            return "redis://***" if parts.netloc.startswith(":") else url

        userinfo, hostpart = parts.netloc.rsplit("@", 1)
        if not hostpart:
            return "redis://***"
        if ":" not in userinfo:
            # Username without a password: nothing secret to redact.
            return url

        username, _password = userinfo.split(":", 1)
        redacted_netloc = f"{username}:***@{hostpart}" if username else f":***@{hostpart}"
        return urlunsplit(
            (parts.scheme, redacted_netloc, parts.path, parts.query, parts.fragment)
        )
    except Exception:  # noqa: BLE001 — never let redaction echo the input
        return "redis://***"
