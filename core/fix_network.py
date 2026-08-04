"""
Fix Network — Bypass Broken Windows Proxy
==========================================

Windows has ``ProxyEnable=1`` in the registry with ``ProxyServer=127.0.0.1:57630``
(a proxy that is no longer running).  Python's ``requests``, ``httpx``, ``urllib``,
and ``pip`` all read this setting via ``urllib.request.getproxies()`` and then fail
with ``ProxyError`` / ``ConnectionRefused``.

This module patches the proxy-detection functions **at import time** so that
every script that imports it gets clean network access.

Usage
-----
Put this at the **very top** of any script that makes HTTP(S) requests::

    from core.fix_network import fix_network
    fix_network()

Or use the one-liner convenience at the module level::

    import core.fix_network          # ← patches automatically on import
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_PATCHED = False


def fix_network() -> None:
    """Apply all network fixes (idempotent — safe to call multiple times)."""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    # ── 1. Environment variables ──────────────────────────────
    # These are checked by httpx, requests, urllib, pip, etc.
    _set_env("NO_PROXY", "*")
    _set_env("no_proxy", "*")
    # Explicitly clear any proxy env vars that may exist
    _unset_env("HTTP_PROXY")
    _unset_env("HTTPS_PROXY")
    _unset_env("http_proxy")
    _unset_env("https_proxy")
    _unset_env("ALL_PROXY")
    _unset_env("all_proxy")

    # ── 2. Patch urllib.request.getproxies() ──────────────────
    # This is the ROOT CAUSE on Windows — Python's stdlib reads
    # the registry via winreg and returns the stale proxy.
    # We replace it with a function that returns an empty dict.
    try:
        import urllib.request as _ur

        _original_getproxies = _ur.getproxies

        def _patched_getproxies() -> dict[str, str]:
            """Return an empty proxy map (bypass the Windows registry)."""
            return {}

        if _ur.getproxies is not _patched_getproxies:
            _ur.getproxies = _patched_getproxies
            logger.debug(
                "Patched urllib.request.getproxies() — was returning %s",
                _original_getproxies() if callable(_original_getproxies) else "?",
            )
    except Exception as exc:
        logger.warning("Could not patch urllib.request.getproxies: %s", exc)

    logger.info("Network proxy bypass active — all HTTP clients use direct connections.")


def _set_env(key: str, value: str) -> None:
    """Set an environment variable only if it's not already set correctly."""
    if os.environ.get(key, "") != value:
        os.environ[key] = value


def _unset_env(key: str) -> None:
    """Remove an environment variable if present."""
    if key in os.environ:
        del os.environ[key]


# ── Auto-fix on import (convenience) ─────────────────────────────
fix_network()
