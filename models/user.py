from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class UserModel(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    roles: Mapped[str] = mapped_column(String(255), nullable=False, server_default=sa.text("'viewer'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sa.text("true"))
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=sa.text("false"))
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[str | None] = mapped_column("metadata", Text)

    # ── MFA / TOTP ──
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, server_default=sa.text("false"))
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Which MFA delivery method is active: "totp" | "email" | "telegram" | None
    # (None → falls back to "totp" for backward compatibility).
    mfa_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Per-user Telegram chat ID for MFA code delivery — enables multi-user
    # Telegram MFA (falls back to the global ``settings.telegram_chat_id``
    # when unset).
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
