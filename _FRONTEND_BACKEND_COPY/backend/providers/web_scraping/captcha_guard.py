from __future__ import annotations

import asyncio
import random

from core.logging import get_logger

logger = get_logger(__name__)


class CaptchaGuard:
    def __init__(self) -> None:
        self._captcha_detected: bool = False
        self._cooldown_until: float = 0.0

    def detect_captcha(self, html: str) -> bool:
        indicators = [
            "captcha",
            "recaptcha",
            "g-recaptcha",
            "h-captcha",
            "cf-turnstile",
            "are you a human",
            "verify your identity",
            "challenge",
            "security check",
            "403 forbidden",
        ]
        html_lower = html.lower()
        for indicator in indicators:
            if indicator in html_lower:
                self._captcha_detected = True
                logger.warning("Captcha detected: %s", indicator)
                return True
        return False

    def is_blocked(self, status_code: int) -> bool:
        if status_code in (403, 429):
            self._captcha_detected = True
            return True
        return False

    async def wait_if_needed(self) -> None:
        if self._captcha_detected:
            import time

            now = time.monotonic()
            if now < self._cooldown_until:
                wait = self._cooldown_until - now
                logger.info("Waiting %.1fs for captcha cooldown", wait)
                await asyncio.sleep(wait)
            else:
                cooldown = random.uniform(30, 120)
                self._cooldown_until = now + cooldown
                logger.info("Captcha cooldown for %.1fs", cooldown)
                await asyncio.sleep(cooldown)
            self._captcha_detected = False

    def reset(self) -> None:
        self._captcha_detected = False
        self._cooldown_until = 0.0
