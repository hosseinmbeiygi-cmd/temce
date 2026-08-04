from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class EmailSender:
    def __init__(
        self,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        default_from: str = "",
    ):
        self._host = host or getattr(settings, "smtp_host", "localhost")
        self._port = port
        self._username = username or getattr(settings, "smtp_username", "")
        self._password = password or getattr(settings, "smtp_password", "")
        self._use_tls = use_tls
        self._from = default_from or getattr(settings, "smtp_from", "noreply@market.local")

    def _send_sync(self, msg: Any, all_recipients: list[str]) -> None:
        """Blocking SMTP delivery — runs inside a worker thread."""
        with smtplib.SMTP(self._host, self._port, timeout=30) as server:
            if self._use_tls:
                server.starttls()
            if self._username:
                server.login(self._username, self._password)
            server.sendmail(self._from, all_recipients, msg.as_string())

    async def send(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> Result[bool]:
        recipients = [to] if isinstance(to, str) else to
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = ", ".join(recipients)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html:
            msg.attach(MIMEText(html, "html", "utf-8"))
        all_recipients = recipients + (cc or []) + (bcc or [])
        try:
            # SMTP is blocking I/O — never run it on the event loop.
            await asyncio.to_thread(self._send_sync, msg, all_recipients)
            logger.info("Email sent to %s: %s", ", ".join(recipients), subject)
            return Result.ok(True)
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed - check credentials")
            return Result.fail("SMTP authentication failed")
        except smtplib.SMTPException as e:
            logger.error("Failed to send email: %s", e)
            return Result.fail(str(e))

    async def send_alert(self, to: str | list[str], alert_type: str, message: str) -> Result[bool]:
        subject = f"[{alert_type.upper()}] Market Alert"
        return await self.send(to, subject, message)

    async def send_report(self, to: str | list[str], report_name: str, summary: str) -> Result[bool]:
        subject = f"Report: {report_name}"
        return await self.send(to, subject, summary)
