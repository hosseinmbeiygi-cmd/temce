from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from core.security import hash_password, verify_password
from core.security.tokens import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token
from models.user import UserModel

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, username: str, email: str, password: str, full_name: str = "", phone: str = "") -> Result[dict[str, Any]]:
        try:
            existing = await self.session.execute(
                select(UserModel).where((UserModel.username == username) | (UserModel.email == email))
            )
            if existing.scalar_one_or_none():
                return Result.fail("Username or email already exists")

            user = UserModel(
                id=new_id("usr"),
                username=username,
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                phone=phone,
                roles="viewer",
                is_active=True,
                is_verified=False,
            )
            self.session.add(user)
            await self.session.flush()

            access_token = create_access_token({"sub": user.id, "username": user.username, "roles": ["viewer"]})
            refresh_token = create_refresh_token({"sub": user.id})

            user.refresh_token = refresh_token
            await self.session.flush()

            return Result.ok({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name or "",
                    "phone": user.phone or "",
                    "roles": ["viewer"],
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                },
            })
        except Exception as e:
            logger.error("Registration failed: %s", e)
            return Result.fail(str(e))

    async def login(self, username: str, password: str) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("Invalid username or password")
            if not user.is_active:
                return Result.fail("Account is disabled")

            if not verify_password(password, user.hashed_password):
                return Result.fail("Invalid username or password")

            roles_list = user.roles.split(",") if user.roles else ["viewer"]
            access_token = create_access_token({"sub": user.id, "username": user.username, "roles": roles_list})
            refresh_token = create_refresh_token({"sub": user.id})

            user.last_login = datetime.now(UTC).replace(tzinfo=None)
            user.refresh_token = refresh_token
            await self.session.flush()

            return Result.ok({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name or "",
                    "phone": user.phone or "",
                    "roles": roles_list,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "last_login": user.last_login,
                },
            })
        except Exception:
            logger.error("Login failed", exc_info=True)
            return Result.fail("An unexpected error occurred during login")

    async def refresh_token(self, refresh_token: str) -> Result[dict[str, Any]]:
        try:
            payload = decode_refresh_token(refresh_token)
            user_id = payload.get("sub")
            if not user_id:
                return Result.fail("Invalid token")

            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.is_active:
                return Result.fail("User not found or inactive")
            if user.refresh_token != refresh_token:
                return Result.fail("Token has been revoked")

            roles_list = user.roles.split(",") if user.roles else ["viewer"]
            new_access = create_access_token({"sub": user.id, "username": user.username, "roles": roles_list})
            new_refresh = create_refresh_token({"sub": user.id})
            user.refresh_token = new_refresh
            await self.session.flush()

            return Result.ok({"access_token": new_access, "refresh_token": new_refresh})
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            return Result.fail(str(e))

    async def get_profile(self, user_id: str) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            return Result.ok({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name or "",
                "phone": user.phone or "",
                "roles": user.roles.split(",") if user.roles else ["viewer"],
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "last_login": user.last_login,
                "created_at": user.created_at,
            })
        except Exception as e:
            logger.error("Get profile failed: %s", e)
            return Result.fail(str(e))

    async def update_profile(self, user_id: str, full_name: str = "", phone: str = "", email: str | None = None) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")

            if full_name:
                user.full_name = full_name
            if phone:
                user.phone = phone
            if email is not None:
                existing = await self.session.execute(
                    select(UserModel).where(UserModel.email == email, UserModel.id != user_id)
                )
                if existing.scalar_one_or_none():
                    return Result.fail("Email already in use")
                user.email = email
            await self.session.flush()
            return Result.ok({"id": user.id, "username": user.username, "email": user.email, "full_name": user.full_name or "", "phone": user.phone or ""})
        except Exception as e:
            logger.error("Update profile failed: %s", e)
            return Result.fail(str(e))

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> Result[None]:
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            if not verify_password(current_password, user.hashed_password):
                return Result.fail("Current password is incorrect")
            user.hashed_password = hash_password(new_password)
            user.refresh_token = None
            await self.session.flush()
            return Result.ok(None)
        except Exception as e:
            logger.error("Change password failed: %s", e)
            return Result.fail(str(e))

    async def list_users(self, page: int = 1, page_size: int = 50) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(
                select(UserModel).offset((page - 1) * page_size).limit(page_size)
            )
            users = result.scalars().all()
            total_result = await self.session.execute(select(UserModel))
            total = len(total_result.scalars().all())
            return Result.ok({
                "items": [
                    {
                        "id": u.id,
                        "username": u.username,
                        "email": u.email,
                        "full_name": u.full_name or "",
                        "roles": u.roles.split(",") if u.roles else ["viewer"],
                        "is_active": u.is_active,
                        "is_verified": u.is_verified,
                        "last_login": u.last_login,
                        "created_at": u.created_at,
                    }
                    for u in users
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            })
        except Exception as e:
            logger.error("List users failed: %s", e)
            return Result.fail(str(e))

    async def toggle_user_status(self, user_id: str) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            user.is_active = not user.is_active
            await self.session.flush()
            return Result.ok({"id": user.id, "is_active": user.is_active})
        except Exception as e:
            logger.error("Toggle user status failed: %s", e)
            return Result.fail(str(e))
