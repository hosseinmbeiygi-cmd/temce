"""Trusted-proxy-aware client IP extraction (audit SEC-06 / CFG-11).

The direct peer address is authoritative unless the peer is a configured
trusted proxy, in which case the leftmost ``X-Forwarded-For`` value is used.
Trusting the header unconditionally lets any client spoof its IP bucket.
"""
from __future__ import annotations

import contextlib
import ipaddress

from fastapi import Request

from core.config import settings


def _peer_host(request: Request) -> str | None:
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or None


def _is_trusted_proxy(peer: str | None) -> bool:
    if not peer:
        return False
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for entry in getattr(settings, "trusted_proxies", []) or []:
        try:
            if "/" in entry:
                if peer_ip in ipaddress.ip_network(entry, strict=False):
                    return True
            elif peer_ip == ipaddress.ip_address(entry):
                return True
        except ValueError:
            pass
    return False


def get_client_ip(request: Request) -> str:
    """Return the real client IP, honouring TRUSTED_PROXIES (SEC-06)."""
    peer = _peer_host(request)
    with contextlib.suppress(Exception):
        xff: str | None = request.headers.get("x-forwarded-for")
        if xff and _is_trusted_proxy(peer):
            first = xff.split(",")[0].strip()
            if first:
                return first
    return peer or "unknown"
