"""Parse-error contract for the ingestion parser layer.

A parser that returns an empty list is saying "the source responded and it has
nothing for us". That return value must never stand for "we could not read the
response": those cases raise :class:`ParseError`, so callers can record a failed
ingest instead of a successful sync with ``items_count=0``.
"""

from __future__ import annotations

from typing import Literal

ParseReason = Literal[
    "invalid_json",  # body is not JSON at all (an empty body counts)
    "html_response",  # provider served an HTML page (e.g. Suspend.php)
    "unexpected_shape",  # JSON parsed, but the top-level value is not an object
    "missing_required_fields",  # object without any recognised envelope field
]


class ParseError(Exception):
    """A payload could not be turned into records.

    ``reason`` is machine-readable (one of :data:`ParseReason`); ``str(exc)``
    keeps the reason and the offending source so logs and sync logs stay
    traceable.
    """

    def __init__(self, reason: ParseReason, detail: str = "", *, source: str = "") -> None:
        self.reason: ParseReason = reason
        self.detail = detail
        self.source = source
        message = f"{reason}: {detail}" if detail else reason
        if source:
            message = f"{source}: {message}"
        super().__init__(message)
