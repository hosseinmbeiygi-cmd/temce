from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.common.base_entity import BaseEntity
from models.user import UserModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class User(BaseEntity):
    def __init__(
        self,
        id: str,
        username: str,
        email: str,
        hashed_password: str,
        full_name: str = "",
        phone: str = "",
        roles: str = "viewer",
        is_active: bool = True,
        is_verified: bool = False,
        last_login: datetime | None = None,
        refresh_token: str | None = None,
        metadata_: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.phone = phone
        self.roles = roles
        self.is_active = is_active
        self.is_verified = is_verified
        self.last_login = last_login
        self.refresh_token = refresh_token
        self.metadata_ = metadata_


class UserRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem: InMemoryRepository[User] | None = None if session else InMemoryRepository[User]()
        self._db: _UserDbRepo | None = None if not session else _UserDbRepo(session)

    async def get(self, id: str) -> Result[User]:
        if self._db:
            return await self._db.get(id)
        return await self._mem.get(id)

    async def save(self, entity: User) -> Result[User]:
        if self._db:
            return await self._db.save(entity)
        return await self._mem.save(entity)

    async def delete(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete(id)
        return await self._mem.delete(id)

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[User]]:
        if self._db:
            return await self._db.list(page, page_size)
        return await self._mem.list(page, page_size)

    async def get_by_username(self, username: str) -> Result[User]:
        if self._db:
            return await self._db.get_by_username(username)
        for u in self._mem._store.values():
            if u.username == username:
                return Result.ok(u)
        return Result.fail(f"User {username} not found")

    async def get_by_email(self, email: str) -> Result[User]:
        if self._db:
            return await self._db.get_by_email(email)
        for u in self._mem._store.values():
            if u.email == email:
                return Result.ok(u)
        return Result.fail(f"User with email {email} not found")

    async def count(self) -> int:
        if self._db:
            return await self._db.count()
        return len(self._mem._store)


class _UserDbRepo(DbRepository[User, UserModel]):
    model_class = UserModel

    async def get_by_username(self, username: str) -> Result[User]:
        stmt = select(UserModel).where(UserModel.username == username)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"User {username} not found")
        return Result.ok(self._to_domain(row))

    async def get_by_email(self, email: str) -> Result[User]:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"User with email {email} not found")
        return Result.ok(self._to_domain(row))

    async def count(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(UserModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, orm: UserModel) -> User:
        return User(
            id=orm.id,
            username=orm.username,
            email=orm.email,
            hashed_password=orm.hashed_password,
            full_name=orm.full_name or "",
            phone=orm.phone or "",
            roles=orm.roles or "viewer",
            is_active=orm.is_active if orm.is_active is not None else True,
            is_verified=orm.is_verified if orm.is_verified is not None else False,
            last_login=orm.last_login,
            refresh_token=orm.refresh_token,
            metadata_=orm.metadata_,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_orm(self, domain: User) -> UserModel:
        return UserModel(
            id=domain.id,
            username=domain.username,
            email=domain.email,
            hashed_password=domain.hashed_password,
            full_name=domain.full_name or None,
            phone=domain.phone or None,
            roles=domain.roles or "viewer",
            is_active=domain.is_active,
            is_verified=domain.is_verified,
            last_login=domain.last_login,
            refresh_token=domain.refresh_token,
            metadata=domain.metadata_,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
