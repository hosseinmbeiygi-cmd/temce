from __future__ import annotations

import html
import re
from typing import Any


def sanitize_html(value: str) -> str:
    return html.escape(value, quote=True)


def sanitize_sql(value: str) -> str:
    return value.replace("'", "''").replace(";", "")


def sanitize_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", value)


def sanitize_path_component(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)


def sanitize_command(value: str) -> str:
    return re.sub(r"[;&|`$(){}[\]!#~<>]", "", value)


def sanitize_log_output(value: str) -> str:
    return re.sub(r"[\r\n]", " ", value)[:1000]


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def sanitize_json_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


class Sanitizer:
    @staticmethod
    def string(value: str, max_length: int = 1000) -> str:
        return str(value).strip()[:max_length]

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on")
        return bool(value)
