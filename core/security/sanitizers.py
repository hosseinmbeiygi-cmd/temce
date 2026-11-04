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


# Windows device names cannot be used as a file or directory name.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_path_component(value: str, fallback: str = "unknown", max_length: int = 200) -> str:
    """Reduce *value* to a single traversal-proof path component.

    Separators, control characters and Windows-reserved device names are
    neutralised; ``.`` / ``..`` and leftovers that reduce to dots fall back to
    ``fallback``. Non-ASCII text (Persian/Arabic symbols) is preserved.
    """
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", str(value or ""))
    cleaned = cleaned.strip().strip(" .").strip()
    if not cleaned or cleaned in {".", ".."} or cleaned.split(".")[0].upper() in _WINDOWS_RESERVED:
        return fallback
    return cleaned[:max_length]


_FILENAME_SEPARATORS = re.compile(r"[\\/]")


def symbol_from_filename(filename: str, fallback: str = "") -> str:
    """Derive a symbol from an uploaded filename, dropping any directory part.

    ``../../etc/passwd.csv`` becomes ``passwd`` and
    ``..\\..\\windows\\evil.csv`` becomes ``evil``: separators are removed
    *before* the suffix is stripped, so a client-chosen filename can never turn
    a derived symbol (written to the database and logs) into a path or a
    traversal sequence.
    """
    last = _FILENAME_SEPARATORS.split(filename or "").pop()
    stem = last.rsplit(".", 1)[0] if "." in last else last
    return safe_path_component(stem, fallback=fallback)


def sanitize_command(value: str) -> str:
    return re.sub(r"[;&|`$(){}[\]!#~<>]", "", value)


def sanitize_log_output(value: str) -> str:
    return re.sub(r"[\r\n]", " ", value)[:1000]


def strip_html(value: str) -> str:
    """Remove HTML-like tags.

    A tag must start with a letter, ``/``, ``!`` or ``?`` after ``<``; a bare
    comparison like ``x < y > z`` or ``EPS < 10`` is therefore left intact.
    """
    return re.sub(r"</?[A-Za-z!?][^>]*>", "", value)


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
