"""API Token — احراز هویت ساده برای استفاده خارجی.

Token = hash(token_string + salt). ذخیره در Redis.

Scopes:
- read: GET endpoints
- write: POST/PUT/DELETE (DCA, alerts)
- admin: همه چیز

این ساده‌ترین مکانیزم برای استفاده شخصی است. برای production باید
از JWT + rotation + rate limiting استفاده شود.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

logger = logging.getLogger(__name__)

SALT = os.getenv("GOLD_API_TOKEN_SALT", "temce-golddesk-default-salt")
STORAGE_KEY = "golddesk:api_tokens"

Scope = Literal["read", "write", "admin"]


@dataclass(frozen=True)
class TokenInfo:
    token_id: str  # 8 chars (preview)
    name: str
    scopes: list[Scope]
    created_at: datetime
    last_used_at: datetime | None
    enabled: bool


def _hash(token: str) -> str:
    return hashlib.sha256((token + SALT).encode()).hexdigest()


def generate_token(name: str, scopes: list[Scope]) -> tuple[str, TokenInfo]:
    """ساخت token جدید. فقط یک‌بار plain token برمی‌گرداند."""
    plain = secrets.token_urlsafe(32)
    token_id = plain[:8]
    info = TokenInfo(
        token_id=token_id,
        name=name,
        scopes=list(scopes),
        created_at=datetime.utcnow(),
        last_used_at=None,
        enabled=True,
    )
    return plain, info


async def save_token(plain: str, info: TokenInfo) -> None:
    """ذخیره hash + metadata در Redis."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        token_hash = _hash(plain)
        await cache.set(
            f"{STORAGE_KEY}:hash:{token_hash}",
            info_to_dict(info),
            ttl=None,  # persistent
        )
        await cache.set(
            f"{STORAGE_KEY}:meta:{info.token_id}",
            info_to_dict(info),
            ttl=None,
        )
    except Exception as exc:
        logger.warning("save_token failed: %s", exc)


async def verify_token(token: str) -> TokenInfo | None:
    """بررسی token. None = نامعتبر."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        token_hash = _hash(token)
        data = await cache.get(f"{STORAGE_KEY}:hash:{token_hash}")
        if not data:
            return None
        info = dict_to_info(data)
        if not info.enabled:
            return None
        # update last_used (best effort)
        info_dict = info_to_dict(info)
        info_dict["last_used_at"] = datetime.utcnow().isoformat()
        await cache.set(f"{STORAGE_KEY}:hash:{token_hash}", info_dict, ttl=None)
        return info
    except Exception as exc:
        logger.warning("verify_token failed: %s", exc)
        return None


async def revoke_token(token_id: str) -> bool:
    """حذف token."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        meta = await cache.get(f"{STORAGE_KEY}:meta:{token_id}")
        if not meta:
            return False
        # حذف hash entry (نمی‌تونیم plain token رو از hash برگردونیم)
        # فقط revoke با ID ممکنه
        meta_dict = info_to_dict(dict_to_info(meta))
        meta_dict["enabled"] = False
        await cache.set(f"{STORAGE_KEY}:meta:{token_id}", meta_dict, ttl=None)
        return True
    except Exception as exc:
        logger.warning("revoke_token failed: %s", exc)
        return False


async def list_tokens() -> list[TokenInfo]:
    """لیست tokenها (فقط metadata)."""
    # پیاده‌سازی ساده: یک index set در Redis
    try:
        from core.cache import get_cache

        cache = get_cache()
        ids = await cache.get(f"{STORAGE_KEY}:index") or []
        out: list[TokenInfo] = []
        for tid in ids:
            meta = await cache.get(f"{STORAGE_KEY}:meta:{tid}")
            if meta:
                out.append(dict_to_info(meta))
        return out
    except Exception as exc:
        logger.warning("list_tokens failed: %s", exc)
        return []


# ── Serialization helpers ─────────────────────────────────────


def info_to_dict(info: TokenInfo) -> dict:
    return {
        "token_id": info.token_id,
        "name": info.name,
        "scopes": info.scopes,
        "created_at": info.created_at.isoformat() if info.created_at else None,
        "last_used_at": info.last_used_at.isoformat() if info.last_used_at else None,
        "enabled": info.enabled,
    }


def dict_to_info(d: dict) -> TokenInfo:
    return TokenInfo(
        token_id=d.get("token_id", ""),
        name=d.get("name", ""),
        scopes=list(d.get("scopes", ["read"])),
        created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.utcnow(),
        last_used_at=datetime.fromisoformat(d["last_used_at"]) if d.get("last_used_at") else None,
        enabled=bool(d.get("enabled", True)),
    )
