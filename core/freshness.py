"""Source-timestamp helpers for API envelopes.

The envelope's ``data_as_of`` must describe the rows actually served — the
source fetch time, never the response build time (audit API-04).
"""

from __future__ import annotations

from typing import Any


def newest_fetched_at(rows: Any) -> str | None:
    """Return the newest ``fetched_at`` carried by *rows* as an ISO-8601 string."""
    latest: str | None = None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        value = row.get("fetched_at")
        if value is None:
            continue
        text = value.isoformat() if hasattr(value, "isoformat") else str(value)
        if latest is None or text > latest:
            latest = text
    return latest
