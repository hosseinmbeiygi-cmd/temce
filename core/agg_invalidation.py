"""Cross-process invalidation token for the market aggregate cache.

The sync worker used to import ``apps.api.endpoints.market`` only to call
``invalidate_agg_cache`` — a services -> api inversion (AUD-ARCH-01). Publishing
the generation token is the layer-neutral part: every API process drops its
local entries as soon as it observes a new token, so the worker does not need to
import the API at all.
"""

from __future__ import annotations

import uuid

AGG_TOKEN_KEY = "agg:cache_token"
AGG_TOKEN_TTL = 86_400  # seconds


def new_agg_token() -> str:
    return uuid.uuid4().hex


async def publish_agg_token(token: str) -> None:
    """Write the generation token to L2; callers handle/log failures."""
    from core.cache_manager import get_cache_manager

    await get_cache_manager().set(AGG_TOKEN_KEY, token, ttl=AGG_TOKEN_TTL)
