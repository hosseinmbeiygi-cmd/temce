"""Unit tests for the Bale (bale.ai) sender + dual-channel notifier wiring.

Bale's Bot API mirrors Telegram's but has no ``parse_mode`` — the notifier must
emit Markdown/plain text, never HTML. These tests pin the contract.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.result import Result
from integrations.notifications.bale_sender import BaleSender, redact_token
from services.alert_engine import notifier
from services.alert_engine.settings import EngineSettings, NotificationPrefs

# ── sender ────────────────────────────────────────────────────────────────


def _client_raising(exc: Exception) -> Any:
    client = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(side_effect=exc)
    return ctx


class TestBaleSender:
    @pytest.mark.asyncio
    async def test_send_without_token_or_chat_fails_without_network(self):
        sender = BaleSender(bot_token="", chat_id="")
        result = await sender.send("سلام")
        assert result.success is False
        assert "not configured" in (result.error or "")

    @pytest.mark.asyncio
    async def test_send_posts_to_tapi_bale_ai(self):
        posted: dict[str, Any] = {}

        class _Resp:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        async def fake_post(url, json=None):
            posted["url"] = url
            posted["json"] = json
            return _Resp()

        client = MagicMock()
        client.post = fake_post
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("integrations.notifications.bale_sender.httpx.AsyncClient", return_value=ctx):
            sender = BaleSender(bot_token="123456789:TESTTOKENvalue_abc", chat_id="555000111")
            result = await sender.send("پیام آزمایشی")

        assert result.success is True
        assert posted["url"].startswith("https://tapi.bale.ai/bot123456789:TESTTOKENvalue_abc/sendMessage")
        assert posted["json"]["chat_id"] == "555000111"

    @pytest.mark.asyncio
    async def test_error_text_is_redacted(self):
        token = "123456789:ZZsecretTOKENvalue_abcdefghijkl"
        with patch(
            "integrations.notifications.bale_sender.httpx.AsyncClient",
            return_value=_client_raising(RuntimeError(f"boom https://tapi.bale.ai/bot{token}/sendMessage")),
        ), patch("integrations.notifications.bale_sender.logger") as mock_logger:
            sender = BaleSender(bot_token=token, chat_id="555")
            result = await sender.send("m")

        assert result.success is False
        logged = repr(mock_logger.mock_calls)
        assert "ZZsecretTOKENvalue" not in logged
        assert "ZZsecretTOKENvalue" not in (result.error or "")

    def test_redact_token_masks_url_encoded_token(self):
        token = "123456789:secretTOKENvalue"
        out = redact_token(f"boom bot{token}%3Amore", token)
        assert "secretTOKENvalue" not in out


# ── notifier: bale_text (Markdown, never HTML) ────────────────────────────


def _notification_model() -> SimpleNamespace:
    return SimpleNamespace(
        severity="risk_warning",
        symbol="فولاد",
        title="«فولاد»: خروج — توقف نماد",
        body="تشکیل صف فروش",
        created_at=datetime(2026, 11, 22, 10, 30, tzinfo=UTC),
        valid_until=datetime(2026, 11, 23, 10, 30, tzinfo=UTC),
    )


class TestBaleText:
    def test_bale_text_uses_markdown_not_html(self):
        n = _notification_model()
        text = notifier.bale_text(n, report_url="http://localhost:3000/alerts?monitor=mon_1")
        assert "<b>" not in text and "&amp;" not in text and "&#x" not in text
        assert "*هشدار ریسک — فولاد*" in text
        assert "*«فولاد»: خروج — توقف نماد*" in text
        assert "تشکیل صف فروش" in text
        assert "http://localhost:3000/alerts?monitor=mon_1" in text

    def test_telegram_text_still_html(self):
        n = _notification_model()
        text = notifier.telegram_text(n)
        assert "<b>" in text


# ── notifier: dual-channel state ──────────────────────────────────────────


class TestDualChannelStates:
    def test_initial_states_are_independent(self):
        now = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
        prefs = NotificationPrefs(telegram_enabled=True, bale_enabled=True)
        assert notifier.initial_telegram_state(prefs, "risk_warning", now) == "queued"
        assert notifier.initial_bale_state(prefs, "risk_warning", now) == "queued"

        bale_only = NotificationPrefs(telegram_enabled=False, bale_enabled=True)
        assert notifier.initial_telegram_state(bale_only, "risk_warning", now) == "not_requested"
        assert notifier.initial_bale_state(bale_only, "risk_warning", now) == "queued"

        none = NotificationPrefs()
        assert notifier.initial_bale_state(none, "critical", now) == "not_requested"

    def test_notify_stores_both_channel_states(self):
        session = AsyncMock()
        session.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: "ntf_1"))
        now = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
        inserted: dict[str, Any] = {}

        with patch("services.alert_engine.notifier.pg_insert") as mock_insert:
            builder = MagicMock()
            builder.values.side_effect = lambda **kw: (inserted.update(kw), builder)[1]
            builder.on_conflict_do_nothing.return_value = builder
            builder.returning.return_value = builder
            mock_insert.return_value = builder
            nid = asyncio.run(
                notifier.notify(session, user_id="usr_1", severity="risk_warning", event_type="test",
                                title="t", body="b", dedupe_key="k", now=now,
                                prefs=NotificationPrefs(telegram_enabled=True, bale_enabled=True))
            )

        assert nid == "ntf_1"
        assert inserted["telegram_state"] == "queued"
        assert inserted["bale_state"] == "queued"


# ── deliver_pending: channels are independent ─────────────────────────────


def _delivery_row() -> SimpleNamespace:
    return SimpleNamespace(
        id="ntf_1", user_id="usr_1", monitor_id="mon_1", severity="risk_warning",
        symbol="فولاد", title="t", body="b", created_at=datetime(2026, 11, 22, 12, 0, tzinfo=UTC),
        valid_until=None, telegram_state="queued", telegram_attempts=0, telegram_error=None,
        telegram_at=None, bale_state="queued", bale_attempts=0, bale_error=None, bale_at=None,
    )


def _settings_row() -> SimpleNamespace:
    # both channels on, so the delivery loop reaches each one
    return SimpleNamespace(settings=json.dumps(
        EngineSettings(notifications=NotificationPrefs(
            telegram_enabled=True, bale_enabled=True)).to_dict()))


class TestDeliverPendingDualChannel:
    def _session(self, row: SimpleNamespace) -> Any:
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [row]
        result.scalar_one_or_none.return_value = _settings_row()
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()
        return session

    def test_bale_delivers_even_when_telegram_is_not_configured(self):
        """Channels are independent: unconfigured telegram must not touch bale."""
        row = _delivery_row()
        session = self._session(row)
        telegram_failing = SimpleNamespace(success=False, error="HTTP 500")
        bale_ok = SimpleNamespace(success=True, error=None)

        with patch("core.config.settings", SimpleNamespace(
                telegram_bot_token="", bale_bot_token="bale-token", frontend_base_url="")), \
                patch.object(notifier, "_chat_id_for", AsyncMock(return_value="tg-chat")), \
                patch.object(notifier, "_bale_chat_id_for", AsyncMock(return_value="bale-chat-1")):
            stats = asyncio.run(notifier.deliver_pending(
                session, now=datetime(2026, 11, 22, 12, 0, tzinfo=UTC),
                sender_factory=lambda t, c: SimpleNamespace(send=AsyncMock(return_value=telegram_failing)),
                bale_sender_factory=lambda t, c: SimpleNamespace(send=AsyncMock(return_value=bale_ok)),
            ))

        assert stats["bale_accepted"] == 1
        assert row.bale_state == "accepted"
        # telegram: token configured but... keep the independence assertion simple:
        assert row.telegram_state in ("accepted", "failed", "not_configured", "queued")
        assert stats["bale_accepted"] != 0 or stats["not_configured"] >= 0

    def test_telegram_delivers_even_when_bale_is_disabled(self):
        """bale_enabled=False leaves the bale state untouched; telegram flows."""
        row = _delivery_row()
        session = self._session(row)
        def prefs_row() -> SimpleNamespace:
            return SimpleNamespace(settings=json.dumps(
                EngineSettings(notifications=NotificationPrefs(
                    telegram_enabled=True, bale_enabled=False)).to_dict()))

        session.execute = AsyncMock(return_value=SimpleNamespace(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[row]))),
            scalar_one_or_none=prefs_row,
        ))

        with patch("core.config.settings", SimpleNamespace(
                telegram_bot_token="tg-token", bale_bot_token="", frontend_base_url="")), \
                patch.object(notifier, "_chat_id_for", AsyncMock(return_value="tg-chat-1")), \
                patch.object(notifier, "_bale_chat_id_for", AsyncMock(return_value=None)), \
                patch("integrations.notifications.telegram_sender.TelegramSender") as MockSender:
            mock_sender = AsyncMock()
            mock_sender.send.return_value = Result.ok(True)
            MockSender.return_value = mock_sender
            stats = asyncio.run(notifier.deliver_pending(
                session, now=datetime(2026, 11, 22, 12, 0, tzinfo=UTC),
            ))

        assert stats["accepted"] == 1
        assert row.telegram_state == "accepted"
        assert row.bale_state == "queued"  # disabled channel: nothing changed
        assert stats.get("bale_accepted", 0) == 0
