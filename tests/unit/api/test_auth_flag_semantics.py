"""Regression: ``AUTH_DISABLED`` must only bypass auth when it is enabled.

Audit SEC-01. ``apps/api/dependencies.get_current_user`` treated the *falsy*
values (``0/false/no/off/""``) as "auth disabled" and returned an anonymous
principal, so the documented ``AUTH_DISABLED=false`` skipped token validation
entirely. ``apps/api/auth._auth_required`` already had the correct polarity;
the two gates disagreed.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException


@pytest.mark.parametrize("value", ["false", "0", "no", "off", ""])
async def test_falsy_flag_requires_a_token(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    from apps.api.dependencies import get_current_user

    monkeypatch.setenv("AUTH_DISABLED", value)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="")

    assert exc.value.status_code == 401


async def test_unset_flag_requires_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api.dependencies import get_current_user
    from core.config import settings

    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.setattr(settings, "auth_disabled", False, raising=False)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="")

    assert exc.value.status_code == 401


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
async def test_enabled_flag_returns_anonymous(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    from apps.api.dependencies import get_current_user

    monkeypatch.setenv("AUTH_DISABLED", value)

    user = await get_current_user(authorization="")

    assert user == {"anonymous": True, "roles": []}
