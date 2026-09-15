from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from core.security import hash_password, verify_password
from core.security.secrets import generate_otp
from core.security.tokens import create_access_token, create_refresh_token, decode_refresh_token
from core.security.totp import build_totp_uri, generate_totp_secret, verify_totp
from models.user import UserModel

logger = get_logger(__name__)

# Redis key prefix for one-time MFA login tokens (short-lived, single use).
_MFA_TOKEN_PREFIX = "auth:mfa:"
_MFA_TOKEN_TTL = 5 * 60  # 5 minutes to enter the code

# Redis key prefix for delivered OTP codes (login + enrollment), keyed by user id.
_MFA_OTP_PREFIX = "auth:mfa:otp:"
_MFA_OTP_TTL = 5 * 60  # codes expire after 5 minutes

# MFA methods that deliver a generated code (via generate_otp) instead of
# requiring a TOTP authenticator app.
_OTP_DELIVERY_METHODS = ("email", "telegram")


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(
        self, username: str, email: str, password: str, full_name: str = "", phone: str = ""
    ) -> Result[dict[str, Any]]:
        try:
            existing = await self.session.execute(
                select(UserModel).where((UserModel.username == username) | (UserModel.email == email))
            )
            if existing.scalar_one_or_none():
                return Result.fail("Username or email already exists")

            # Personal system: first user gets admin role automatically
            total_users = await self.session.scalar(select(func.count(UserModel.id)))
            is_first_user = (total_users or 0) == 0
            initial_role = "admin" if is_first_user else "user"

            user = UserModel(
                id=new_id("usr"),
                username=username,
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                phone=phone,
                roles=initial_role,
                is_active=True,
                is_verified=is_first_user,  # First user is auto-verified
            )
            self.session.add(user)
            await self.session.flush()

            access_token = create_access_token({"sub": user.id, "username": user.username, "roles": [initial_role]})
            refresh_token = create_refresh_token({"sub": user.id})

            user.refresh_token = refresh_token
            await self.session.flush()

            logger.info("New user registered: %s (role: %s)", username, initial_role)

            return Result.ok(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name or "",
                        "phone": user.phone or "",
                        "roles": [initial_role],
                        "is_active": user.is_active,
                        "is_verified": user.is_verified,
                    },
                }
            )
        except Exception as e:
            logger.error("Registration failed: %s", e)
            return Result.fail(str(e))

    async def login(self, username: str, password: str) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.username == username))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("Invalid username or password")
            if not user.is_active:
                return Result.fail("Account is disabled")

            if not verify_password(password, user.hashed_password):
                return Result.fail("Invalid username or password")

            roles_list = user.roles.split(",") if user.roles else ["viewer"]

            # ── MFA enabled → first step of a two-step login ──
            if user.totp_enabled:
                method = user.mfa_method or "totp"
                token = await self._issue_mfa_token(user.id)
                if not token:
                    # Fail closed: without a persisted one-time token the
                    # second step could never succeed.
                    logger.error("MFA login aborted: could not persist MFA token for user %s", user.id)
                    return Result.fail("MFA is temporarily unavailable. Please try again later.")

                # OTP delivery methods: generate + send a code now so the
                # second step only verifies the code the user received.
                if method in _OTP_DELIVERY_METHODS:
                    code = generate_otp()
                    sent = await self._store_and_deliver_otp(user, code)
                    if not sent:
                        return Result.fail("Could not send the verification code. Please try again later.")

                return Result.ok(
                    {
                        "mfa_required": True,
                        "mfa_token": token,
                        "method": method,
                        "user": {
                            "id": user.id,
                            "username": user.username,
                            "roles": roles_list,
                        },
                    }
                )

            return await self._complete_login(user)
        except Exception:
            logger.error("Login failed", exc_info=True)
            return Result.fail("An unexpected error occurred during login")

    # ── MFA / TOTP ────────────────────────────────────────────────────────────

    async def _issue_mfa_token(self, user_id: str) -> str | None:
        """Create a short-lived, single-use token authorizing the second MFA step.

        Returns ``None`` when the token could not be persisted (e.g. Redis is
        unavailable) so callers can fail the login instead of issuing a token
        that can never be redeemed — two-factor auth must fail closed.
        """
        import secrets as _secrets

        token = _secrets.token_urlsafe(32)
        try:
            from core.cache import get_cache

            cache = get_cache()
            if not cache.is_connected:
                logger.warning("MFA token issuance skipped: cache unavailable")
                return None
            await cache.set(_MFA_TOKEN_PREFIX + token, user_id, ttl=_MFA_TOKEN_TTL)
            return token
        except Exception:
            logger.error("MFA token cache write failed", exc_info=True)
            return None

    async def _consume_mfa_token(self, token: str) -> str | None:
        """Validate + consume a pending MFA token. Returns the user id, or None.

        Uses an atomic pop (GETDEL) so two concurrent requests can never both
        redeem the same token — exactly one caller wins.
        """
        try:
            from core.cache import get_cache

            cache = get_cache()
            if not cache.is_connected:
                return None
            user_id = await cache.pop(_MFA_TOKEN_PREFIX + token)
            return str(user_id) if user_id else None
        except Exception:
            logger.debug("MFA token consume failed", exc_info=True)
            return None

    async def login_with_mfa(self, mfa_token: str, code: str) -> Result[dict[str, Any]]:
        """Complete a two-factor login: verify the code and issue tokens.

        Supports both TOTP (authenticator app) and delivered OTP codes
        (email/Telegram). The pending code, when applicable, is stored under
        ``auth:mfa:otp:{user_id}`` by :meth:`_store_and_deliver_otp` during
        the first login step.
        """
        try:
            user_id = await self._consume_mfa_token(mfa_token)
            if not user_id:
                return Result.fail("MFA token expired or already used. Please login again.")

            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.is_active:
                return Result.fail("User not found or inactive")
            if not user.totp_enabled:
                return Result.fail("MFA is not enabled for this account")

            method = user.mfa_method or "totp"
            if method in _OTP_DELIVERY_METHODS:
                stored = await self._pop_stored_otp(user.id)
                if not stored or stored != code:
                    return Result.fail("Invalid authentication code")
            else:
                if not user.totp_secret:
                    return Result.fail("MFA is not enabled for this account")
                if not verify_totp(user.totp_secret, code):
                    return Result.fail("Invalid authentication code")
            return await self._complete_login(user)
        except Exception:
            # Never leak internal error details to the client.
            logger.error("MFA login failed", exc_info=True)
            return Result.fail("MFA login failed. Please try again.")

    # ── OTP delivery (email / Telegram) ──────────────────────────────────────

    async def _store_and_deliver_otp(self, user: UserModel, code: str) -> bool:
        """Persist a generated code for ``user`` and deliver it via the
        configured channel (email or Telegram).

        Returns False when the code could not be persisted or delivered so
        callers can fail closed. Never raises.
        """
        try:
            from core.cache import get_cache

            cache = get_cache()
            if not cache.is_connected:
                logger.warning("OTP not stored: cache unavailable")
                return False
            await cache.set(_MFA_OTP_PREFIX + user.id, code, ttl=_MFA_OTP_TTL)
            return await self._deliver_otp(user, code)
        except Exception:
            logger.error("OTP store/deliver failed", exc_info=True)
            return False

    async def _deliver_otp(self, user: UserModel, code: str) -> bool:
        """Send ``code`` to the user's configured channel. Returns True on success."""
        method = user.mfa_method or "totp"
        try:
            if method == "email":
                from integrations.notifications.email_sender import EmailSender

                res = await EmailSender().send(
                    user.email,
                    subject="Your login verification code",
                    body=(
                        f"Your verification code is: {code}\n"
                        "It expires in 5 minutes. If you did not request this, ignore this email."
                    ),
                )
                return res.success
            if method == "telegram":
                from integrations.notifications.telegram_sender import TelegramSender

                # Per-user chat ID wins; fall back to the global setting so
                # single-user deployments keep working without a new column.
                sender = TelegramSender(chat_id=user.telegram_chat_id or "")
                res = await sender.send(f"🔐 Your verification code is <b>{code}</b>\nIt expires in 5 minutes.")
                return res.success
            logger.warning("Unsupported MFA method for OTP delivery: %s", method)
            return False
        except Exception:
            logger.error("OTP delivery failed", exc_info=True)
            return False

    async def _pop_stored_otp(self, user_id: str) -> str | None:
        """Atomically retrieve + consume the pending code for ``user_id``."""
        try:
            from core.cache import get_cache

            cache = get_cache()
            if not cache.is_connected:
                return None
            val = await cache.pop(_MFA_OTP_PREFIX + user_id)
            return str(val) if val else None
        except Exception:
            logger.debug("OTP consume failed", exc_info=True)
            return None

    async def _complete_login(self, user: UserModel) -> Result[dict[str, Any]]:
        """Issue tokens and record last_login for a fully-authenticated user."""
        roles_list = user.roles.split(",") if user.roles else ["viewer"]
        access_token = create_access_token({"sub": user.id, "username": user.username, "roles": roles_list})
        refresh_token = create_refresh_token({"sub": user.id})

        user.last_login = datetime.now(UTC).replace(tzinfo=None)
        user.refresh_token = refresh_token
        await self.session.flush()

        return Result.ok(
            {
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
            }
        )

    async def setup_mfa(
        self, user_id: str, password: str, method: str = "totp", telegram_chat_id: str = ""
    ) -> Result[dict[str, Any]]:
        """Start MFA enrollment for the current user.

        - ``method="totp"`` (default): persist a fresh TOTP secret and return
          the provisioning URI for an authenticator app.
        - ``method="email"`` / ``method="telegram"``: generate a one-time
          code with ``generate_otp``, persist it and deliver it to the chosen
          channel. ``confirm_mfa`` then verifies the code the user received.

        ``telegram_chat_id`` (required when ``method="telegram"`` in a
        multi-user deployment) is stored per-user so codes reach the right
        chat; it falls back to ``settings.telegram_chat_id`` when empty.
        """
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            if not verify_password(password, user.hashed_password):
                return Result.fail("Current password is incorrect")

            if method in _OTP_DELIVERY_METHODS:
                # Delivered-code enrollment: no secret to scan — just prove
                # the channel works by delivering a code.
                if method == "telegram" and telegram_chat_id.strip():
                    user.telegram_chat_id = telegram_chat_id.strip()
                user.mfa_method = method
                user.totp_secret = None
                user.totp_enabled = False
                user.totp_confirmed_at = None
                await self.session.flush()

                code = generate_otp()
                sent = await self._store_and_deliver_otp(user, code)
                if not sent:
                    return Result.fail("Could not send the verification code. Please try again later.")
                return Result.ok(
                    {
                        "method": method,
                        "pending": True,
                        "delivered_to": "email" if method == "email" else "telegram",
                    }
                )

            secret = generate_totp_secret()
            user.mfa_method = "totp"
            user.totp_secret = secret
            user.totp_enabled = False
            user.totp_confirmed_at = None
            await self.session.flush()

            uri = build_totp_uri(secret, user.username or user.email)
            return Result.ok({"method": "totp", "secret": secret, "uri": uri})
        except Exception as e:
            logger.error("MFA setup failed: %s", e)
            return Result.fail(str(e))

    async def confirm_mfa(self, user_id: str, code: str) -> Result[dict[str, Any]]:
        """Enable MFA once the user proves possession of the secret via a code.

        Works for both TOTP (code from the authenticator app against the
        stored secret) and delivered OTP methods (code received by
        email/Telegram).
        """
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")

            method = user.mfa_method or "totp"
            if method in _OTP_DELIVERY_METHODS:
                stored = await self._pop_stored_otp(user.id)
                if not stored or stored != code:
                    return Result.fail("Invalid authentication code")
            else:
                if not user.totp_secret:
                    return Result.fail("MFA setup has not been started")
                if not verify_totp(user.totp_secret, code):
                    return Result.fail("Invalid authentication code")

            user.totp_enabled = True
            user.totp_confirmed_at = datetime.now(UTC).replace(tzinfo=None)
            await self.session.flush()
            return Result.ok({"enabled": True, "method": method})
        except Exception as e:
            logger.error("MFA confirm failed: %s", e)
            return Result.fail(str(e))

    async def disable_mfa(
        self, user_id: str, password: str, code: str, *, send_new_code: bool = False
    ) -> Result[dict[str, Any]]:
        """Disable MFA — requires password and a valid verification code.

        For TOTP the code is verified against the stored secret. For OTP
        delivery methods (email/Telegram) a fresh code is generated and
        delivered (via ``send_new_code=True`` in the endpoint) so the user can
        prove possession of the channel before disabling.
        """
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            if not verify_password(password, user.hashed_password):
                return Result.fail("Current password is incorrect")

            method = user.mfa_method or "totp"
            if user.totp_enabled and method in _OTP_DELIVERY_METHODS:
                # Fresh code delivered on request — the stored one (if any)
                # belongs to a previous login/setup and may already be stale.
                if send_new_code:
                    fresh = generate_otp()
                    sent = await self._store_and_deliver_otp(user, fresh)
                    if not sent:
                        return Result.fail("Could not send the verification code. Please try again later.")
                    return Result.ok({"requires_code": True, "method": method})
                stored = await self._pop_stored_otp(user.id)
                if not stored or stored != code:
                    return Result.fail("Invalid authentication code")
            elif user.totp_enabled and user.totp_secret and not verify_totp(user.totp_secret, code):
                return Result.fail("Invalid authentication code")

            user.totp_enabled = False
            user.totp_secret = None
            user.totp_confirmed_at = None
            user.mfa_method = None
            await self.session.flush()
            return Result.ok({"enabled": False})
        except Exception as e:
            logger.error("MFA disable failed: %s", e)
            return Result.fail(str(e))

    async def mfa_status(self, user_id: str) -> Result[dict[str, Any]]:
        """Return whether MFA is enabled for the user."""
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            return Result.ok(
                {
                    "enabled": bool(user.totp_enabled),
                    "pending": bool(user.totp_secret and not user.totp_enabled)
                    or bool(user.mfa_method in _OTP_DELIVERY_METHODS and not user.totp_enabled),
                    "method": user.mfa_method or "totp",
                    "telegram_chat_id": user.telegram_chat_id,
                }
            )
        except Exception as e:
            logger.error("MFA status failed: %s", e)
            return Result.fail(str(e))

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

            # Include the user profile so browser clients can restore their
            # session (access token + user) from the httpOnly refresh cookie
            # without a second round-trip.
            return Result.ok(
                {
                    "access_token": new_access,
                    "refresh_token": new_refresh,
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
                }
            )
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            return Result.fail(str(e))

    async def get_profile(self, user_id: str) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            return Result.ok(
                {
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
                }
            )
        except Exception as e:
            logger.error("Get profile failed: %s", e)
            return Result.fail(str(e))

    async def update_profile(
        self, user_id: str, full_name: str = "", phone: str = "", email: str | None = None
    ) -> Result[dict[str, Any]]:
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
            return Result.ok(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name or "",
                    "phone": user.phone or "",
                }
            )
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

    # ── Forgot password (overseas phone supported) ────────────────────────
    _RESET_PREFIX = "auth:reset:"
    _RESET_TTL = 10 * 60  # 10 minutes

    async def request_password_reset(self, account: str) -> Result[dict[str, Any]]:
        try:
            from core.cache import get_cache

            q = account.strip()
            result = await self.session.execute(
                select(UserModel).where((UserModel.username == q) | (UserModel.email == q) | (UserModel.phone == q))
            )
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("Account not found")
            cache = get_cache()
            if not cache.is_connected:
                return Result.fail("Service temporarily unavailable")
            code = generate_otp()
            await cache.set(self._RESET_PREFIX + user.id, code, ttl=self._RESET_TTL)
            # Deliver via available channel: prefer email, fallback to phone/sms
            if user.email:
                try:
                    from integrations.notifications.email_sender import EmailSender

                    await EmailSender().send(
                        user.email, subject="Password reset code", body=f"Your reset code is: {code} (10 min)"
                    )
                except Exception:
                    logger.warning("Reset email failed for %s", user.id, exc_info=True)
            if user.phone:
                try:
                    from integrations.notifications.sms_sender import SmsSender  # type: ignore

                    await SmsSender().send(user.phone, f"Reset code: {code}")  # type: ignore
                except Exception:
                    logger.debug("SMS reset not configured for %s", user.id)
            logger.info("Password reset code issued for %s", user.id)
            return Result.ok(
                {
                    "user_id": user.id,
                    "masked_email": (user.email[:3] + "***" if user.email else ""),
                    "masked_phone": (user.phone[:3] + "***" if user.phone else ""),
                }
            )
        except Exception as e:
            logger.error("request_password_reset failed: %s", e)
            return Result.fail(str(e))

    async def reset_password(self, account: str, code: str, new_password: str) -> Result[None]:
        try:
            from core.cache import get_cache

            q = account.strip()
            result = await self.session.execute(
                select(UserModel).where((UserModel.username == q) | (UserModel.email == q) | (UserModel.phone == q))
            )
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("Account not found")
            cache = get_cache()
            if not cache.is_connected:
                return Result.fail("Service temporarily unavailable")
            stored = await cache.pop(self._RESET_PREFIX + user.id)
            if not stored or str(stored) != str(code):
                return Result.fail("Invalid or expired code")
            user.hashed_password = hash_password(new_password)
            user.refresh_token = None
            await self.session.flush()
            logger.info("Password reset via code for %s", user.id)
            return Result.ok(None)
        except Exception as e:
            logger.error("reset_password failed: %s", e)
            return Result.fail(str(e))

    async def list_users(self, page: int = 1, page_size: int = 50) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(select(UserModel).offset((page - 1) * page_size).limit(page_size))
            users = result.scalars().all()
            total = await self.session.scalar(select(func.count(UserModel.id))) or 0
            return Result.ok(
                {
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
                }
            )
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

    async def get_login_history(self, user_id: str, limit: int = 20) -> Result[dict[str, Any]]:
        """Return login history for the user.

        If a login_history table exists, query it. Otherwise fall back to
        the user's last_login timestamp (returns a single-entry list).
        """
        try:
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")

            # If there's a dedicated login_history table, query it
            try:
                from sqlalchemy import text

                # Check if table exists
                check = await self.session.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'login_history')")
                )
                if check.scalar():
                    from models.login_history import LoginHistoryModel

                    hist_result = await self.session.execute(
                        select(LoginHistoryModel)
                        .where(LoginHistoryModel.user_id == user_id)
                        .order_by(LoginHistoryModel.created_at.desc())
                        .limit(limit)
                    )
                    records = hist_result.scalars().all()
                    return Result.ok(
                        {
                            "items": [
                                {
                                    "ip_address": r.ip_address or "",
                                    "user_agent": r.user_agent or "",
                                    "created_at": r.created_at,
                                }
                                for r in records
                            ],
                            "total": len(records),
                        }
                    )
            except Exception:
                logger.debug("login_history table not available, falling back to last_login")

            # Fallback: return last_login as a single entry
            items = []
            if user.last_login:
                items.append(
                    {
                        "ip_address": "",
                        "user_agent": "",
                        "created_at": user.last_login,
                    }
                )
            return Result.ok({"items": items, "total": len(items)})
        except Exception as e:
            logger.error("Get login history failed: %s", e)
            return Result.fail(str(e))

    async def update_user_role(self, user_id: str, role: str) -> Result[dict[str, Any]]:
        try:
            from core.enums.rbac import Role

            valid_roles = [r.value for r in Role]
            if role not in valid_roles:
                return Result.fail(f"Invalid role: {role}. Must be one of {valid_roles}")
            result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return Result.fail("User not found")
            old_role = user.roles
            user.roles = role
            await self.session.flush()
            logger.info("User role updated: %s %s -> %s", user.username, old_role, role)
            return Result.ok({"id": user.id, "username": user.username, "old_role": old_role, "new_role": role})
        except Exception as e:
            logger.error("Update user role failed: %s", e)
            return Result.fail(str(e))
