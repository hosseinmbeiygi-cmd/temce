"""Push Notifications — Web Push API با VAPID.

subscribers: subscription objects از frontend → ذخیره در Redis
ارسال: alert fired → push به همه subscribers

نیاز:
- VAPID keys (generate once: py_vapid)
- Service Worker (frontend, قبلاً موجود)
- HTTPS (localhost مجازه)
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)

REDIS_KEY_SUBSCRIBERS = "golddesk:push:subscribers"
REDIS_KEY_VAPID = "golddesk:push:vapid"


@dataclass(frozen=True)
class PushSubscription:
    """Web Push subscription."""

    endpoint: str
    p256dh: str
    auth: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PushMessage:
    """پیام push."""

    title: str
    body: str
    url: str = "/gold"
    icon: str = "/icons/golddesk-192.png"
    tag: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── VAPID keys ─────────────────────────────────────────────


def _generate_vapid_keys() -> tuple[str, str]:
    """تولید کلید VAPID (application server + public)."""
    try:
        import base64

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        # Private key (PEM)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Public key (raw 65 bytes uncompressed)
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )

        private_b64 = base64.urlsafe_b64encode(private_pem).rstrip(b"=").decode()
        public_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode()

        return private_b64, public_b64
    except ImportError:
        # cryptography نصب نیست
        return "", ""


async def get_or_create_vapid_keys() -> tuple[str, str]:
    """از cache یا generate جدید."""
    with contextlib.suppress(Exception):
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_VAPID)
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return data.get("private", ""), data.get("public", "")

    priv, pub = _generate_vapid_keys()
    if priv and pub:
        with contextlib.suppress(Exception):
            from core.cache import get_cache

            cache = get_cache()
            await cache.set(
                REDIS_KEY_VAPID,
                json.dumps({"private": priv, "public": pub}),
                ttl=None,
            )
    return priv, pub


# ── Subscriber management ─────────────────────────────────


async def add_subscriber(sub: PushSubscription) -> int:
    """افزودن subscriber. بازمی‌گرداند total count."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_SUBSCRIBERS) or []
        subs: list[dict] = json.loads(raw) if isinstance(raw, str) else raw

        # dedup by endpoint
        if not any(s.get("endpoint") == sub.endpoint for s in subs):
            subs.append(sub.to_dict())
            await cache.set(REDIS_KEY_SUBSCRIBERS, json.dumps(subs), ttl=None)
        return len(subs)
    except Exception as exc:
        logger.warning("add_subscriber failed: %s", exc)
        return 0


async def remove_subscriber(endpoint: str) -> int:
    """حذف subscriber."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_SUBSCRIBERS) or []
        subs: list[dict] = json.loads(raw) if isinstance(raw, str) else raw
        subs = [s for s in subs if s.get("endpoint") != endpoint]
        await cache.set(REDIS_KEY_SUBSCRIBERS, json.dumps(subs), ttl=None)
        return len(subs)
    except Exception as exc:
        logger.warning("remove_subscriber failed: %s", exc)
        return 0


async def list_subscribers() -> list[PushSubscription]:
    try:
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_SUBSCRIBERS) or []
        subs: list[dict] = json.loads(raw) if isinstance(raw, str) else raw
        return [PushSubscription(**s) for s in subs]
    except Exception:
        return []


# ── Send ───────────────────────────────────────────────────


async def send_push(msg: PushMessage) -> int:
    """ارسال push به همه subscribers. بازمی‌گرداند تعداد موفق."""
    subs = await list_subscribers()
    if not subs:
        return 0

    # تلاش با pywebpush (اگه نصبه)
    try:
        from pywebpush import WebPushException, webpush

        priv, pub = await get_or_create_vapid_keys()
        if not priv:
            logger.warning("VAPID keys not available")
            return 0

        claims = {
            "sub": os.getenv("GOLD_PUSH_SUBJECT", "mailto:admin@temce.local"),
        }

        sent = 0
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=json.dumps(msg.to_dict()),
                    vapid_private_key=priv,
                    vapid_claims=claims,
                )
                sent += 1
            except WebPushException as exc:
                # 404/410 = subscription expired
                if exc.response and exc.response.status_code in (404, 410):
                    await remove_subscriber(sub.endpoint)
                logger.debug("push failed for %s: %s", sub.endpoint[:50], exc)
        return sent
    except ImportError:
        # pywebpush نصب نیست
        logger.debug("pywebpush not installed, push disabled")
        return 0
    except Exception as exc:
        logger.warning("send_push failed: %s", exc)
        return 0
