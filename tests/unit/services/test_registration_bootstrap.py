"""SEC-08: first-user admin bootstrap is serialized and operator-gated.

Two simultaneous registrations used to read ``count(users) == 0`` and both
create an admin. Registration now takes a PostgreSQL advisory lock for the
transaction (no schema change needed) and the bootstrap role is behind
``BOOTSTRAP_FIRST_ADMIN`` so it can be provisioned out-of-band.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.config import settings
from services.user_service import UserService


class _Result:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _Session:
    def __init__(self, total_users: int) -> None:
        self.total_users = total_users
        self.statements: list[str] = []
        self.added: list[Any] = []
        self.flushes = 0

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        self.statements.append(" ".join(str(statement).split()))
        return _Result(None)

    async def scalar(self, _statement: Any) -> int:
        return self.total_users

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1


async def _register(total_users: int) -> tuple[Any, dict[str, Any]]:
    session = _Session(total_users)
    service = UserService(session)
    result = await service.register("owner", "owner@example.invalid", "S3cret-pass")
    assert result.success, result.error
    return session, result.value["user"]


async def test_empty_table_bootstraps_an_admin() -> None:
    session, user = await _register(0)

    assert user["roles"] == ["admin"]
    assert any("pg_advisory_xact_lock" in stmt for stmt in session.statements), (
        "the bootstrap decision must be serialized"
    )


async def test_second_user_is_not_an_admin() -> None:
    _, user = await _register(1)

    assert user["roles"] == ["user"]


async def test_operator_dial_disables_the_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "bootstrap_first_admin", False, raising=False)

    _, user = await _register(0)

    assert user["roles"] == ["user"]
