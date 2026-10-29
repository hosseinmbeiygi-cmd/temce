"""Reference-data writes need an admin role, not just a valid token.

Audit API-06. ``/news`` create + refresh, ``/symbols`` create + import,
``/codal/import-bulk`` and ``/funds/sync-all`` were mounted on ``_public_read``
(authentication only), so any self-registered account could inject market-wide
news, overwrite instruments, bulk-import disclosures, or trigger costly external
syncs.
"""

from __future__ import annotations

import pytest

# A bearer header keeps SecurityMiddleware out of the way; the role itself is
# resolved by the mocked ``get_current_user`` from the fixtures.
AUTH = {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("POST", "/api/v1/news"),
        ("POST", "/api/v1/news/refresh"),
        ("POST", "/api/v1/instruments"),
        ("POST", "/api/v1/funds/sync-all"),
    ],
)
async def test_regular_user_cannot_write_reference_data(user_client, method: str, url: str) -> None:
    response = await user_client.request(method, url, json={}, headers=AUTH)

    assert response.status_code == 403, f"{method} {url} -> {response.status_code} {response.text}"


async def test_admin_passes_the_role_gate(admin_client, app) -> None:
    """Guard against "locked down" being implemented as "broken for admins"."""
    from apps.api.dependencies import get_symbol_service
    from core.result import Result

    class _FakeSymbolService:
        async def create(self, **kwargs):
            return Result.ok({"id": "sym-1", "symbol": kwargs.get("symbol", "")})

    app.dependency_overrides[get_symbol_service] = lambda: _FakeSymbolService()
    response = await admin_client.post("/api/v1/instruments", json={"symbol": "TEST"}, headers=AUTH)

    assert response.status_code != 403, response.text
