from __future__ import annotations

import logging
import re


class SensitiveDataFilter(logging.Filter):
    SENSITIVE_PATTERNS: list[tuple[str, str]] = [
        (r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+", r"\1=***"),
        (r"(?i)(secret|secret_key|api_key|apikey)\s*[:=]\s*\S+", r"\1=***"),
        (r"(?i)(token|auth_token|access_token|refresh_token)\s*[:=]\s*\S+", r"\1=***"),
        (r"(?i)(authorization|bearer)\s+\S+", r"\1 ***"),
        (r"\b\d{16}\b", "****"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "msg") and isinstance(record.msg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg)
        return True


class ModuleFilter(logging.Filter):
    def __init__(self, allowed_modules: list[str] | None = None, denied_modules: list[str] | None = None) -> None:
        super().__init__()
        self.allowed_modules = set(allowed_modules or [])
        self.denied_modules = set(denied_modules or [])

    def filter(self, record: logging.LogRecord) -> bool:
        if self.denied_modules and record.name in self.denied_modules:
            return False
        return not (self.allowed_modules and record.name not in self.allowed_modules)


class LevelFilter(logging.Filter):
    def __init__(self, min_level: int = logging.DEBUG, max_level: int = logging.CRITICAL) -> None:
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return self.min_level <= record.levelno <= self.max_level
