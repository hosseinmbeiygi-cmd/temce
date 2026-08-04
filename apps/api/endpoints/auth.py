from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, require_roles
from core.database import get_session
from core.logging import get_logger
from core.rate_limit import get_rate_limiter
from schemas.api.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MFADisableRequest,
    MFALoginRequest,
    MFASetupRequest,
    MFAStatusResponse,
    MFAVerifyRequest,
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


# Strict rate limits for auth endpoints to prevent brute-force attacks.
# Limits are registered per-IP-key lazily (first request for each IP) so the
# sliding window actually applies — the limiter's allow() returns True for
# unregistered keys, so registering only the bare "auth:login" key would
# have made the check a no-op (the key checked below always includes the IP).
_AUTH_LIMITS: dict[str, tuple[float, int]] = {
    "login": (5 / 60.0, 5),            # 5 attempts per 60s per IP
    "register": (3 / 60.0, 3),         # 3 attempts per 60s per IP
    "change_password": (3 / 60.0, 3),  # 3 attempts per 60s per IP
    # TOTP codes are 6 digits — a strict cap prevents brute-force within
    # the 5-minute validity window of the mfa_token.
    "mfa_login": (5 / 300.0, 10),      # 10 attempts per 5min per IP
    # Delivering a code costs an email/Telegram message — cap to prevent
    # channel flooding by a credentialed attacker.
    "mfa_setup": (3 / 300.0, 3),       # 3 setups per 5min per IP
}

_limiter = get_rate_limiter()


def _rate_limit_auth(request: Request, endpoint: str) -> None:
    """FastAPI dependency: rate-limit an auth endpoint by client IP."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"auth:{endpoint}:{client_ip}"
    rate, burst = _AUTH_LIMITS[endpoint]
    if not _limiter.has_limit(key):
        _limiter.set_limit(key, rate=rate, burst=burst)
    if not _limiter.allow(key):
        logger.warning("Auth rate limit hit: %s from %s", endpoint, client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": "60"},
        )


def login_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "login")


def mfa_login_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "mfa_login")


def mfa_setup_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "mfa_setup")


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
    data = result.value
    # MFA-protected account → return mfa_required + short-lived mfa_token
    if data.get("mfa_required"):
        return ApiResponse(
            success=True,
            data={
                "mfa_required": True,
                "mfa_token": data["mfa_token"],
                "user": data["user"],
            },
        )
    return ApiResponse(
        success=True,
        data={
            "user": _build_user_response(data["user"]),
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
        },
    )


@router.post("/mfa/login")
async def mfa_login(
    req: MFALoginRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(mfa_login_rate_limit),
) -> ApiResponse:
    """Complete a two-factor login: verify the TOTP code and issue tokens."""
    svc = UserService(session)
    result = await svc.login_with_mfa(req.mfa_token, req.code)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    data = result.value
    return ApiResponse(
        success=True,
        data={
            "user": _build_user_response(data["user"]),
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
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


@router.get("/login-history")
async def login_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    """Return recent login history for the current user.

    Requires a login_history table. Falls back to returning last_login from the user record.
    """
    svc = UserService(session)
    result = await svc.get_login_history(current_user["sub"], limit=limit)
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
    authorization: str = Header(""),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    """Log out the current user.

    Revokes the access token (jti blacklist in Redis) and clears the
    server-side refresh token so it can no longer be used to mint new tokens.
    """
    from sqlalchemy import select

    from models.user import UserModel

    # Blacklist the current access token until its natural expiry.
    token = authorization.split(" ")[1] if authorization.startswith("Bearer ") else ""
    if token:
        try:
            from core.security.tokens import revoke_access_token
            await revoke_access_token(token)
        except Exception:
            logger.debug("Access token revocation failed during logout", exc_info=True)

    result = await session.execute(select(UserModel).where(UserModel.id == current_user["sub"]))
    user = result.scalar_one_or_none()
    if user:
        user.refresh_token = None
        await session.flush()
    return ApiResponse(success=True, message="Logged out successfully")


# ── MFA / TOTP endpoints ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

@router.get("/mfa/status")
async def mfa_status(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    """Return whether MFA is enabled for the current user."""
    svc = UserService(session)
    result = await svc.mfa_status(current_user["sub"])
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    status = MFAStatusResponse(**result.value)
    return ApiResponse(success=True, data=status.model_dump())


@router.post("/mfa/setup")
async def mfa_setup(
    req: MFASetupRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(mfa_setup_rate_limit),
) -> ApiResponse:
    """Start MFA enrollment for the current user.

    - ``method=totp`` (default): returns ``{secret, uri}`` once — the client
      shows the QR code and then calls ``/mfa/confirm`` with a code from the
      authenticator app.
    - ``method=email`` / ``method=telegram``: a 6-digit code is generated and
      delivered to the channel; ``/mfa/confirm`` verifies it.
    """
    svc = UserService(session)
    result = await svc.setup_mfa(current_user["sub"], req.password, method=req.method)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.post("/mfa/confirm")
async def mfa_confirm(
    req: MFAVerifyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    """Enable MFA once the user proves possession of the secret via a code."""
    svc = UserService(session)
    result = await svc.confirm_mfa(current_user["sub"], req.code)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.post("/mfa/disable")
async def mfa_disable(
    req: MFADisableRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    """Disable MFA.

    - TOTP: requires password + a valid authenticator code.
    - email/Telegram: first call with ``send_code=true`` delivers a fresh
      code; the second call submits that code to complete the disable.
    """
    svc = UserService(session)
    result = await svc.disable_mfa(
        current_user["sub"], req.password, req.code, send_new_code=req.send_code
    )
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


# ── Admin endpoints ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = 1,
    page_size: int = 50,
    _: dict = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.list_users(page=page, page_size=page_size)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str = Query(..., description="New role: admin, analyst, user, viewer"),
    current_user: dict = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    # Prevent admin from changing their own role
    if current_user["sub"] == user_id:
        return ApiResponse(success=False, error={"message": "Cannot change your own role"})
    svc = UserService(session)
    result = await svc.update_user_role(user_id, role)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.put("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: str,
    current_user: dict = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    # Prevent admin from disabling their own account
    if current_user["sub"] == user_id:
        return ApiResponse(success=False, error={"message": "Cannot disable your own account"})
    svc = UserService(session)
    result = await svc.toggle_user_status(user_id)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)
