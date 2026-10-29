"""Alerts are per-user data: list/update/delete/history must honour the owner.

Audit SEC-05. ``AlertService`` accepted ``user_id`` on create/update/delete but
threw it away, and ``list_alerts``/``get_alert_history`` had no owner parameter
at all — any account could read, disable or delete every alert.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.alert import AlertHistoryModel, AlertModel
from services.alert_service import AlertService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AlertModel.__table__.create)
        await conn.run_sync(AlertHistoryModel.__table__.create)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _create(svc: AlertService, user_id: str, symbol: str) -> str:
    result = await svc.create_alert(
        user_id=user_id,
        instrument_id="",
        symbol=symbol,
        alert_type="price",
        condition={"field": "price", "operator": "gte", "threshold": 100},
        channels=["console"],
        description="",
    )
    assert result.success, result.error
    return result.value["id"]


async def test_create_records_the_owner(session: AsyncSession) -> None:
    svc = AlertService(session)
    alert_id = await _create(svc, "user-1", "AAA")

    row = await session.get(AlertModel, alert_id)
    assert row is not None
    assert row.user_id == "user-1"


async def test_list_is_scoped_to_the_caller(session: AsyncSession) -> None:
    svc = AlertService(session)
    await _create(svc, "user-1", "AAA")
    await _create(svc, "user-2", "BBB")

    mine = await svc.list_alerts(user_id="user-1")
    assert mine.success
    assert [a["symbol"] for a in mine.value["items"]] == ["AAA"]
    assert mine.value["total"] == 1

    everyone = await svc.list_alerts(user_id=None)  # admin / no filter
    assert everyone.value["total"] == 2


async def test_other_user_cannot_update_an_alert(session: AsyncSession) -> None:
    svc = AlertService(session)
    alert_id = await _create(svc, "user-1", "AAA")

    denied = await svc.update_alert(alert_id, "user-2", enabled=False)
    assert not denied.success

    row = await session.get(AlertModel, alert_id)
    assert row is not None and row.enabled is True


async def test_other_user_cannot_delete_an_alert(session: AsyncSession) -> None:
    svc = AlertService(session)
    alert_id = await _create(svc, "user-1", "AAA")

    denied = await svc.delete_alert(alert_id, "user-2")
    assert not denied.success
    assert await session.get(AlertModel, alert_id) is not None

    allowed = await svc.delete_alert(alert_id, "user-1")
    assert allowed.success


async def test_other_user_cannot_read_alert_history(session: AsyncSession) -> None:
    svc = AlertService(session)
    alert_id = await _create(svc, "user-1", "AAA")
    session.add(
        AlertHistoryModel(
            id="hist-1",
            alert_id=alert_id,
            trigger_value=101.0,
            message="AAA price reached 101",
            delivered=True,
        )
    )
    await session.flush()

    denied = await svc.get_alert_history(alert_id, user_id="user-2")
    assert not denied.success

    allowed = await svc.get_alert_history(alert_id, user_id="user-1")
    assert allowed.success
    assert allowed.value["total"] == 1
