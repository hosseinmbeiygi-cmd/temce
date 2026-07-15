from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user
from core.database import get_session
from core.logging import get_logger
from core.rate_limit import get_rate_limiter
from schemas.api.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from schemas.common.responses import ApiResponse
from services.user_service import UserService

logger = get_logger(__name__)
router = APIRouter()


# Strict rate limits for auth endpoints to prevent brute-force attacks
# Limits are set ONCE at module level (NOT per-request) to avoid resetting state
_limiter = get_rate_limiter()
_limiter.set_limit("auth:login", rate=5 / 60.0, burst=5)          # 5 attempts per 60s per IP
_limiter.set_limit("auth:register", rate=3 / 60.0, burst=3)       # 3 attempts per 60s per IP
_limiter.set_limit("auth:change_password", rate=3 / 60.0, burst=3)  # 3 attempts per 60s per IP


def _rate_limit_auth(request: Request, endpoint: str) -> None:
    """FastAPI dependency: rate-limit an auth endpoint by client IP."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"auth:{endpoint}:{client_ip}"
    if not _limiter.allow(key):
        logger.warning("Auth rate limit hit: %s from %s", endpoint, client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": "60"},
        )


def login_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "login")


def register_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "register")


def change_password_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "change_password")


def _build_token_response(data: dict) -> TokenResponse:
    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
    )


def _build_user_response(data: dict) -> UserResponse:
    return UserResponse(
        id=data["id"],
        username=data["username"],
        email=data["email"],
        full_name=data.get("full_name", ""),
        phone=data.get("phone", ""),
        roles=data.get("roles", ["viewer"]),
        is_active=data.get("is_active", True),
        is_verified=data.get("is_verified", False),
        last_login=data.get("last_login"),
        created_at=data.get("created_at"),
    )


@router.post("/register")
async def register(
    req: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(register_rate_limit),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.register(req.username, req.email, req.password, req.full_name, req.phone)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(
        success=True,
        data={
            "user": _build_user_response(result.value["user"]),
            "access_token": result.value["access_token"],
            "refresh_token": result.value["refresh_token"],
        },
    )


@router.post("/login")
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(login_rate_limit),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.login(req.username, req.password)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(
        success=True,
        data={
            "user": _build_user_response(result.value["user"]),
            "access_token": result.value["access_token"],
            "refresh_token": result.value["refresh_token"],
        },
    )


@router.post("/refresh")
async def refresh(req: RefreshRequest, session: AsyncSession = Depends(get_session)) -> ApiResponse:
    svc = UserService(session)
    result = await svc.refresh_token(req.refresh_token)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=_build_token_response(result.value))


@router.get("/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.get_profile(current_user["sub"])
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=_build_user_response(result.value))


@router.put("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.update_profile(current_user["sub"], req.full_name, req.phone, req.email)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(change_password_rate_limit),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.change_password(current_user["sub"], req.current_password, req.new_password)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, message="Password changed successfully. Please login again.")


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    from sqlalchemy import select

    from models.user import UserModel

    result = await session.execute(select(UserModel).where(UserModel.id == current_user["sub"]))
    user = result.scalar_one_or_none()
    if user:
        user.refresh_token = None
        await session.flush()
    return ApiResponse(success=True, message="Logged out successfully")
