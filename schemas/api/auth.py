from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, SecretStr


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., max_length=255)
    # SCH-006: a plain ``str`` password lands in every traceback, log line and
    # ``repr()`` of the request object. ``SecretStr`` keeps the value out of
    # all of them; callers unwrap explicitly with ``get_secret_value()``.
    password: SecretStr = Field(..., min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=20)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: SecretStr = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for /auth/refresh.

    The refresh token is carried by the httpOnly cookie — the JSON body is
    kept only for API-contract compatibility and ignored by the endpoint.
    """

    refresh_token: str = Field(default="", description="Deprecated: token is read from the httpOnly cookie")


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str = ""
    phone: str = ""
    roles: list[str] = Field(default_factory=lambda: ["viewer"])
    is_active: bool = True
    is_verified: bool = False
    last_login: datetime | None = None
    created_at: datetime | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    full_name: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=20)
    email: str | None = None


class MFASetupRequest(BaseModel):
    """Start MFA enrollment for the current user.

    ``method`` selects how one-time codes are produced:
    - ``totp`` (default): secret + otpauth URI for an authenticator app
    - ``email``: a 6-digit code generated with ``generate_otp`` is emailed
    - ``telegram``: the code is sent to the user's Telegram chat

    ``telegram_chat_id`` (optional) is stored per-user when present and used
    for Telegram delivery; when empty, ``settings.telegram_chat_id`` is used.
    """

    password: str = Field(..., min_length=1, description="Current password (re-auth before MFA setup)")
    method: str = Field(default="totp", pattern=r"^(totp|email|telegram)$")
    telegram_chat_id: str = Field(
        default="",
        max_length=64,
        pattern=r"^\d*$",
        description="Per-user Telegram chat ID (used when method=telegram)",
    )


class MFAVerifyRequest(BaseModel):
    """Confirm MFA setup with a valid TOTP code — enables MFA for the user."""

    code: str = Field(..., min_length=6, max_length=8, pattern=r"^\d+$")


class MFADisableRequest(BaseModel):
    """Disable MFA.

    ``send_code=true`` (first call, OTP methods only) delivers a fresh
    verification code; the subsequent call with that ``code`` disables MFA.
    """

    password: str = Field(..., min_length=1)
    code: str = Field(default="", min_length=6, max_length=8, pattern=r"^\d+$")
    send_code: bool = Field(default=False, description="Request a fresh code for OTP-delivery methods")


class MFALoginRequest(BaseModel):
    """Second step of a two-factor login: username + pending MFA token + code."""

    mfa_token: str = Field(..., min_length=8)
    code: str = Field(..., min_length=6, max_length=8, pattern=r"^\d+$")


class MFARecoveryRequest(BaseModel):
    """Second step of a two-factor login using a one-time recovery code."""

    mfa_token: str = Field(..., min_length=8)
    code: str = Field(..., min_length=8, max_length=32, pattern=r"^[A-Za-z0-9 -]+$")


class MFAEnrollStartRequest(BaseModel):
    """Begin MFA enrollment for an account that is required to use MFA."""

    mfa_token: str = Field(..., min_length=8)
    password: str = Field(..., min_length=1)


class MFAEnrollFinishRequest(BaseModel):
    """Finish enforced MFA enrollment: proves possession of the new secret."""

    mfa_token: str = Field(..., min_length=8)
    code: str = Field(..., min_length=6, max_length=8, pattern=r"^\d+$")


class MFARegenerateRecoveryRequest(BaseModel):
    """Replace the recovery-code set (requires the current password)."""

    password: str = Field(..., min_length=1)


class MFAStatusResponse(BaseModel):
    """MFA state for the current user.

    SCH-009: the shared TOTP secret (and its otpauth URI) may only ever leave
    the API while an enrollment is still *pending* — i.e. exactly once, in the
    response that also shows the QR code. Everything else is scrubbed in
    :meth:`model_dump`, so a caller that flips ``pending`` back to ``False``
    (or the plain status endpoint) cannot leak the secret by accident.
    """

    enabled: bool = False
    pending: bool = False
    method: str | None = None
    secret: str | None = None
    uri: str | None = None
    telegram_chat_id: str | None = None
    recovery_codes_remaining: int = 0

    @classmethod
    def for_status(
        cls,
        *,
        enabled: bool,
        method: str | None = None,
        telegram_chat_id: str | None = None,
        recovery_codes_remaining: int = 0,
    ) -> MFAStatusResponse:
        """Status view — never carries secret material."""
        return cls(
            enabled=enabled,
            pending=False,
            method=method,
            secret=None,
            uri=None,
            telegram_chat_id=telegram_chat_id,
            recovery_codes_remaining=recovery_codes_remaining,
        )

    @classmethod
    def for_enrollment(
        cls,
        *,
        method: str,
        secret: str | None = None,
        uri: str | None = None,
        telegram_chat_id: str | None = None,
    ) -> MFAStatusResponse:
        """Enrollment view — the one response allowed to carry the secret."""
        return cls(
            enabled=False,
            pending=True,
            method=method,
            secret=secret,
            uri=uri,
            telegram_chat_id=telegram_chat_id,
        )

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(**kwargs)
        if not self.pending:
            data.pop("secret", None)
            data.pop("uri", None)
        return data


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset code via email/phone (overseas phone supported)."""

    account: str = Field(..., min_length=3, max_length=255, description="Username, email or phone")


class ResetPasswordRequest(BaseModel):
    account: str = Field(..., min_length=3, max_length=255)
    code: str = Field(..., min_length=6, max_length=8, pattern=r"^\d+$")
    new_password: str = Field(..., min_length=8, max_length=128)
