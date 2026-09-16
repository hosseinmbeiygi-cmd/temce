from __future__ import annotations

import contextlib

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, require_roles
from core.config import settings
from core.database import get_session
from core.logging import get_logger
from core.rate_limit import get_rate_limiter
from schemas.api.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MFADisableRequest,
    MFALoginRequest,
    MFASetupRequest,
    MFAStatusResponse,
    MFAVerifyRequest,
    RegisterRequest,
    ResetPasswordRequest,
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
    "mfa_confirm": (5 / 300.0, 5),     # 5 attempts per 5min per IP
    "mfa_disable": (5 / 300.0, 5),     # 5 attempts per 5min per IP
}

_limiter = get_rate_limiter()


def _get_client_ip(request: Request) -> str:
    with contextlib.suppress(Exception):
        headers = getattr(request, "headers", None)
        if headers is not None:
            # Starlette Headers or plain dict
            xff = headers.get("x-forwarded-for") if hasattr(headers, "get") else None
            if xff:
                first = xff.split(",")[0].strip()
                if first:
                    return first
    client = getattr(request, "client", None)
    if client and getattr(client, "host", None):
        return client.host
    return "unknown"


def _rate_limit_auth(request: Request, endpoint: str) -> None:
    """FastAPI dependency: rate-limit an auth endpoint by client IP."""
    client_ip = _get_client_ip(request)
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


def mfa_confirm_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "mfa_confirm")


def mfa_disable_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "mfa_disable")


def register_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "register")


def change_password_rate_limit(request: Request) -> None:
    _rate_limit_auth(request, "change_password")


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Persist the refresh token in an httpOnly cookie (XSS-safe).

    The token stays out of JavaScript (HttpOnly), travels only over HTTPS
    in production (Secure), and is scoped to the API's own origin
    (SameSite=Lax) so CSRF against /auth/refresh is not possible from other
    sites. Insecure in dev (http://localhost) by default — flip
    ``AUTH_COOKIE_SECURE=true`` behind TLS.

    Deployment note: because refresh is cookie-only and the cookie is
    SameSite=Lax, the frontend and API must be served from the same site
    (same registrable domain) in production. If they are ever split across
    sites, switch this cookie to ``SameSite=None; Secure`` instead.
    """
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain or None,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Expire the refresh cookie immediately (used on logout)."""
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        domain=settings.auth_cookie_domain or None,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


def _refresh_token_from_cookie(request: Request) -> str:
    """Read the refresh token from the httpOnly cookie (XSS-safe).

    The token is never exposed to JavaScript (not returned in JSON bodies), so
    the cookie is the only transport. Clients that cannot manage cookies must
    use their own credential storage — the JSON body is intentionally ignored.
    """
    return request.cookies.get(settings.auth_cookie_name, "")


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
    response: Response,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(register_rate_limit),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.register(req.username, req.email, req.password, req.full_name, req.phone)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    _set_refresh_cookie(response, result.value["refresh_token"])
    return ApiResponse(
        success=True,
        data={
            "user": _build_user_response(result.value["user"]),
            "access_token": result.value["access_token"],
        },
    )


@router.post("/login")
async def login(
    req: LoginRequest,
    response: Response,
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
    _set_refresh_cookie(response, data["refresh_token"])
    return ApiResponse(
        success=True,
        data={
            "user": _build_user_response(data["user"]),
            "access_token": data["access_token"],
        },
    )


@router.post("/mfa/login")
async def mfa_login(
    req: MFALoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(mfa_login_rate_limit),
) -> ApiResponse:
    """Complete a two-factor login: verify the TOTP code and issue tokens."""
    svc = UserService(session)
    result = await svc.login_with_mfa(req.mfa_token, req.code)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    data = result.value
    _set_refresh_cookie(response, data["refresh_token"])
    return ApiResponse(
        success=True,
        data={
            "user": _build_user_response(data["user"]),
            "access_token": data["access_token"],
        },
    )


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    svc = UserService(session)
    token = _refresh_token_from_cookie(request)
    if not token:
        return JSONResponse(
            status_code=401,
            content=ApiResponse(success=False, error={"message": "No refresh token provided"}).model_dump(mode="json"),
        )  # type: ignore[return-value]
    result = await svc.refresh_token(token)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    _set_refresh_cookie(response, result.value["refresh_token"])
    # Rotate the access token and return the user profile so the frontend can
    # restore the full session from the httpOnly refresh cookie. The refresh
    # token itself stays cookie-only — it is never included in JSON bodies.
    data = {"access_token": result.value["access_token"]}
    if result.value.get("user"):
        data["user"] = _build_user_response(result.value["user"]).model_dump()
    return ApiResponse(success=True, data=data)


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


@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(register_rate_limit),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.request_password_reset(req.account)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value, message="Reset code sent if account exists")


@router.post("/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(register_rate_limit),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.reset_password(req.account, req.code, req.new_password)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, message="Password has been reset. Please login.")


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    authorization: str = Header(""),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(change_password_rate_limit),
) -> ApiResponse:
    svc = UserService(session)
    result = await svc.change_password(current_user["sub"], req.current_password, req.new_password)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    # Revoke the current access token so the old session cannot be reused after password change.
    token = ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]
    if token:
        try:
            from core.security.tokens import revoke_access_token

            await revoke_access_token(token)
        except Exception:
            logger.debug("Failed to revoke token after password change", exc_info=True)
    return ApiResponse(success=True, message="Password changed successfully. Please login again.")


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    authorization: str = Header(""),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    """Log out the current user.

    Revokes the access token (jti blacklist in Redis), clears the refresh
    cookie, and clears the server-side refresh token so it can no longer be
    used to mint new tokens.
    """
    from sqlalchemy import select

    from models.user import UserModel

    # Logout must remain usable when the short-lived access token has expired.
    # In that case the refresh cookie is still enough to identify and revoke
    # the server-side session.
    token = ""
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]

    access_user_id: str | None = None
    if token:
        try:
            from core.security.tokens import decode_access_token, revoke_access_token

            payload = decode_access_token(token)
            access_user_id = str(payload.get("sub") or "") or None
            await revoke_access_token(token)
        except Exception:
            logger.debug("Access token revocation failed during logout", exc_info=True)

    refresh_token = _refresh_token_from_cookie(request)
    refresh_user_id: str | None = None
    if refresh_token:
        try:
            from core.security.tokens import decode_refresh_token

            payload = decode_refresh_token(refresh_token)
            refresh_user_id = str(payload.get("sub") or "") or None
        except Exception:
            logger.debug("Refresh token could not be decoded during logout", exc_info=True)

    user_id = access_user_id or refresh_user_id
    try:
        if session is not None and user_id:
            result = await session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            # Do not revoke a newer login from another browser: only clear the
            # refresh token that was actually presented by this session.
            if user and refresh_token and user.refresh_token == refresh_token:
                user.refresh_token = None
                await session.flush()
    except Exception:
        # Cookie deletion is still useful when the database is temporarily
        # unavailable; the next login/refresh will establish a new session.
        logger.warning("Could not clear server-side refresh token during logout", exc_info=True)
    finally:
        _clear_refresh_cookie(response)
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
    result = await svc.setup_mfa(
        current_user["sub"], req.password, method=req.method, telegram_chat_id=req.telegram_chat_id
    )
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.post("/mfa/confirm")
async def mfa_confirm(
    req: MFAVerifyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(mfa_confirm_rate_limit),
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
    _: None = Depends(mfa_disable_rate_limit),
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
