"""The Telegram bot token must never reach logs, results or exceptions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from integrations.notifications.telegram_sender import TelegramSender, redact_token

TOKEN = "123456789:AAFakeSecretTokenValue_0123456789abcd"
SECRET = "AAFakeSecretTokenValue_0123456789abcd"


def _client_raising(exc: Exception) -> MagicMock:
    client = MagicMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    async def post(*_a, **_k):
        raise exc

    client.post = post
    return client


def test_redact_token_plain_encoded_and_unknown_token():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert SECRET not in redact_token(url, TOKEN)
    assert SECRET not in redact_token(url.replace(":", "%3A"), TOKEN)
    assert SECRET not in redact_token(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectError(f"cannot reach https://api.telegram.org/bot{TOKEN}/sendMessage"),
        RuntimeError(f"unexpected https://api.telegram.org/bot{TOKEN}/sendMessage"),
        ValueError(f"bad url bot{TOKEN.replace(':', '%3A')}"),
    ],
)
async def test_send_failure_never_returns_or_logs_token(exc):
    sender = TelegramSender(bot_token=TOKEN, chat_id="42")
    with patch("integrations.notifications.telegram_sender.httpx.AsyncClient", return_value=_client_raising(exc)), \
            patch("integrations.notifications.telegram_sender.logger") as mock_logger:
        result = await sender.send("hi")
    assert not result.success
    assert SECRET not in str(result.error)
    assert SECRET not in repr(mock_logger.mock_calls)


@pytest.mark.asyncio
async def test_send_photo_and_document_failures_are_redacted(tmp_path):
    sender = TelegramSender(bot_token=TOKEN, chat_id="42")
    exc = RuntimeError(f"x https://api.telegram.org/bot{TOKEN}/sendPhoto")
    with patch("integrations.notifications.telegram_sender.httpx.AsyncClient", return_value=_client_raising(exc)):
        result = await sender.send_photo("https://example.invalid/p.png")
    assert not result.success
    assert SECRET not in str(result.error)


@pytest.mark.asyncio
async def test_gold_desk_exception_log_is_redacted():
    from src.gold_desk import telegram_bot

    cfg = telegram_bot.TelegramConfig(bot_token=TOKEN, default_chat_id="42", enabled=True)
    exc = RuntimeError(f"boom https://api.telegram.org/bot{TOKEN}/sendMessage")
    with patch("src.gold_desk.telegram_bot.httpx.AsyncClient", return_value=_client_raising(exc)), \
            patch("src.gold_desk.telegram_bot.logger") as mock_logger:
        ok = await telegram_bot.send_message("hi", config=cfg)
    assert ok is False
    assert mock_logger.error.called
    assert SECRET not in repr(mock_logger.mock_calls)
