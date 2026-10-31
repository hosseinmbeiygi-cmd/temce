"""قرارداد W4-02: چرخهٔ حیات توکن API (ساخت → verify → revoke → list) با Redis جعلی.

نقص genuine: ``save_token`` hash و meta را ذخیره می‌کند ولی ``token_id`` را به
``STORAGE_KEY:index`` نمی‌افزاند، پس ``list_tokens()`` همیشه خالی برمی‌گردد.
"""

from __future__ import annotations

import core.cache as cache_module

import src.gold_desk.api_token as api_token
from src.gold_desk.api_token import (
    generate_token,
    revoke_token,
    save_token,
    verify_token,
    list_tokens,
    STORAGE_KEY,
)


class _FakeCache:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl=None):
        self.data[key] = value


def _install_cache(monkeypatch, cache):
    monkeypatch.setattr(cache_module, "get_cache", lambda: cache)


async def test_token_lifecycle(monkeypatch):
    cache = _FakeCache()
    _install_cache(monkeypatch, cache)

    plain, info = generate_token("dev", ["read", "write"])
    await save_token(plain, info)

    # verify
    v = await verify_token(plain)
    assert v is not None
    assert v.token_id == info.token_id
    assert v.enabled is True

    # list — save_token باید id را به index اضافه کرده باشد
    tokens = await list_tokens()
    assert len(tokens) == 1, (
        f"list_tokens خالی است (index در save_token ثبت نشده): {tokens}"
    )
    assert tokens[0].token_id == info.token_id

    # revoke
    ok = await revoke_token(info.token_id)
    assert ok is True

    # verify after revoke → None
    v2 = await verify_token(plain)
    assert v2 is None
