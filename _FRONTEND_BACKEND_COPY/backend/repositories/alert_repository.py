from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.alerts.entities import Alert
from domain.common.base_entity import BaseEntity
from models.alert import AlertHistoryModel, AlertModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class AlertHistory(BaseEntity):
    def __init__(
        self,
        id: str,
        alert_id: str,
        triggered_at: datetime | None = None,
        trigger_value: float | None = None,
        message: str | None = None,
        delivered: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.alert_id = alert_id
        self.triggered_at = triggered_at
        self.trigger_value = trigger_value
        self.message = message
        self.delivered = delivered


class AlertRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[Alert] | None = None if session else InMemoryRepository[Alert]()
        self._db: _AlertDbRepo | None = None if not session else _AlertDbRepo(session)

    async def get(self, id: str) -> Result[Alert]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: Alert) -> Result[Alert]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[Alert]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_instrument(self, instrument_id: str) -> Result[list[Alert]]:
        if self._db:
            return await self._db.get_by_instrument(instrument_id)
        matches = [a for a in self._mem._store.values() if a.instrument_id == instrument_id]
        return Result.ok(matches)

    async def get_by_symbol(self, symbol: str) -> Result[list[Alert]]:
        if self._db:
            return await self._db.get_by_symbol(symbol)
        matches = [a for a in self._mem._store.values() if a.symbol == symbol]
        return Result.ok(matches)

    async def get_by_type(self, alert_type: str) -> Result[list[Alert]]:
        if self._db:
            return await self._db.get_by_type(alert_type)
        matches = [a for a in self._mem._store.values() if a.alert_type == alert_type]
        return Result.ok(matches)

    async def get_triggered(self) -> Result[list[Alert]]:
        if self._db:
            return await self._db.get_triggered()
        matches = [a for a in self._mem._store.values() if a.is_triggered]
        return Result.ok(matches)

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)

    async def save_history(self, entity: AlertHistory) -> Result[AlertHistory]:
        if self._db:
            return await self._db.save_history(entity)
        return Result.ok(entity)

    async def get_history(self, alert_id: str) -> Result[list[AlertHistory]]:
        if self._db:
            return await self._db.get_history(alert_id)
        return Result.ok([])

    async def list_history(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[AlertHistory]]:
        if self._db:
            return await self._db.list_history(page, page_size)
        return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=0))


class _AlertDbRepo(DbRepository[Alert, AlertModel]):
    model_class = AlertModel

    async def get_by_instrument(self, instrument_id: str) -> Result[list[Alert]]:
        stmt = select(AlertModel).where(AlertModel.instrument_id == instrument_id)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_by_symbol(self, symbol: str) -> Result[list[Alert]]:
        stmt = select(AlertModel).where(AlertModel.symbol == symbol)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_by_type(self, alert_type: str) -> Result[list[Alert]]:
        stmt = select(AlertModel).where(AlertModel.alert_type == alert_type)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def get_triggered(self) -> Result[list[Alert]]:
        stmt = select(AlertModel).where(AlertModel.last_triggered.isnot(None)).order_by(desc(AlertModel.last_triggered))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._to_domain(r) for r in rows])

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(AlertModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def save_history(self, entity: AlertHistory) -> Result[AlertHistory]:
        orm = AlertHistoryModel(
            id=entity.id,
            alert_id=entity.alert_id,
            triggered_at=entity.triggered_at,
            trigger_value=entity.trigger_value,
            message=entity.message,
            delivered=entity.delivered,
        )
        self.session.add(orm)
        await self.session.flush()
        return Result.ok(
            AlertHistory(
                id=orm.id,
                alert_id=orm.alert_id,
                triggered_at=orm.triggered_at,
                trigger_value=orm.trigger_value,
                message=orm.message,
                delivered=bool(orm.delivered) if orm.delivered is not None else False,
            )
        )

    async def get_history(self, alert_id: str) -> Result[list[AlertHistory]]:
        stmt = (
            select(AlertHistoryModel)
            .where(AlertHistoryModel.alert_id == alert_id)
            .order_by(desc(AlertHistoryModel.triggered_at))
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        items = [
            AlertHistory(
                id=r.id,
                alert_id=r.alert_id,
                triggered_at=r.triggered_at,
                trigger_value=r.trigger_value,
                message=r.message,
                delivered=bool(r.delivered) if r.delivered is not None else False,
            )
            for r in rows
        ]
        return Result.ok(items)

    async def list_history(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[AlertHistory]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(AlertHistoryModel)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(AlertHistoryModel)
            .order_by(desc(AlertHistoryModel.triggered_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        items = [
            AlertHistory(
                id=r.id,
                alert_id=r.alert_id,
                triggered_at=r.triggered_at,
                trigger_value=r.trigger_value,
                message=r.message,
                delivered=bool(r.delivered) if r.delivered is not None else False,
            )
            for r in rows
        ]
        return Result.ok(
            PaginatedResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    def _to_domain(self, orm: AlertModel) -> Alert:
        extra: dict[str, Any] = {}
        if orm.condition:
            try:
                extra["condition"] = json.loads(orm.condition)
            except Exception:
                extra["condition"] = orm.condition
        if orm.channels:
            try:
                extra["channels"] = json.loads(orm.channels)
            except Exception:
                extra["channels"] = orm.channels
        return Alert(
            id=orm.id,
            instrument_id=orm.instrument_id or "",
            rule_id="",
            symbol=orm.symbol or "",
            alert_type=orm.alert_type,
            message=orm.description or "",
            severity="info",
            value=0.0,
            threshold=0.0,
            direction="",
            is_read=False,
            is_triggered=orm.last_triggered is not None,
            triggered_at=orm.last_triggered,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            extra=extra,
        )

    def _to_orm(self, domain: Alert) -> AlertModel:
        extra = domain.extra or {}
        condition_json = None
        if extra.get("condition") is not None:
            cond = extra["condition"]
            # Avoid double-encoding when a raw string was stored (JSON parse fallback).
            condition_json = cond if isinstance(cond, str) else json.dumps(cond)
        channels_json = None
        if extra.get("channels") is not None:
            chans = extra["channels"]
            channels_json = chans if isinstance(chans, str) else json.dumps(chans)
        return AlertModel(
            id=domain.id,
            instrument_id=domain.instrument_id or None,
            symbol=domain.symbol or None,
            alert_type=domain.alert_type,
            condition=condition_json,
            channels=channels_json,
            enabled=True,
            triggered_count=1 if domain.is_triggered else 0,
            last_triggered=domain.triggered_at,
            description=domain.message or None,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
