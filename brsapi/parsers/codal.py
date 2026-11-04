"""
Codal announcement parser.

Maps the ``/Codal/Announcement.php`` JSON response to structured
announcement records suitable for the existing ``CodalReportModel``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from brsapi.parsers.errors import BrsApiParseError, ensure_payload, is_no_data

# ── Audit status patterns ────────────────────────────
# Detect audit status from Persian announcement titles.

_AUDITED_PATTERN = re.compile(r"\(\s*حسابرسی\s*شده\s*\)")
_UNAUDITED_PATTERN = re.compile(r"\(\s*حسابرسی\s*نشده\s*\)")


def detect_audit_status(title: str) -> str:
    """
    Detect audit status from a Codal announcement title.

    Returns one of:
    - ``"audited"``   — title contains "(حسابرسی شده)"
    - ``"unaudited"`` — title contains "(حسابرسی نشده)"
    - ``""``           — unknown
    """
    if not title:
        return ""
    if _UNAUDITED_PATTERN.search(title):
        return "unaudited"
    if _AUDITED_PATTERN.search(title):
        return "audited"
    return ""


class CodalParser:
    """
    Parses BrsApi Codal announcement responses.

    The API returns a dict with:
    - ``count_announcement``: total announcements in current response
    - ``count_page``: total pages
    - ``announcements``: list of announcement dicts (or directly a list)

    Each announcement has:
    ``l18``, ``l30``, ``title``, ``code``, ``date_title``, ``date_send``,
    ``time_send``, ``date_publish``, ``time_publish``, ``link``,
    ``link_pdf``, ``link_excel``, ``link_attachment``.
    """

    @classmethod
    def parse(cls, data: Any) -> dict[str, Any]:
        """
        Parse the codal announcements response.

        Returns::
            {
                "count_announcement": int,
                "count_page": int,
                "announcements": [ {...}, ... ],
            }

        Raises ``BrsApiParseError`` when the payload cannot be read; a no-data
        answer (``{}`` / ``{"status": "no_data"}``) returns an empty page.
        """
        result: dict[str, Any] = {
            "count_announcement": 0,
            "count_page": 0,
            "announcements": [],
        }

        ensure_payload(data, "Codal")
        if is_no_data(data):
            return result

        if isinstance(data, dict):
            try:
                result["count_announcement"] = int(data.get("count_announcement") or 0)
                result["count_page"] = int(data.get("count_page") or 0)
            except (TypeError, ValueError) as exc:
                raise BrsApiParseError(
                    f"Codal: page counters are not integers ({exc})",
                    code="unexpected_shape",
                ) from exc

            key = next(
                (
                    k
                    for k in ("announcement", "announcements", "data", "items")
                    if k in data
                ),
                None,
            )
            if key is None:
                raise BrsApiParseError(
                    f"Codal: unrecognised envelope keys {sorted(data)[:5]}",
                    code="unrecognised_envelope",
                )
            raw_announcements = data[key]
            if not isinstance(raw_announcements, list):
                raise BrsApiParseError(
                    f"Codal: '{key}' must be a list, got "
                    f"{type(raw_announcements).__name__}",
                    code="unexpected_shape",
                )
            result["announcements"] = [
                cls._parse_item(a) for a in raw_announcements if isinstance(a, dict)
            ]

        elif isinstance(data, list):
            result["count_announcement"] = len(data)
            result["announcements"] = [cls._parse_item(a) for a in data if isinstance(a, dict)]

        else:
            raise BrsApiParseError(
                f"Codal: expected a list or object, got {type(data).__name__}",
                code="unexpected_shape",
            )

        return result

    @classmethod
    def parse_announcements_only(cls, data: Any) -> list[dict[str, Any]]:
        """Convenience: return just the list of parsed announcements."""
        parsed = cls.parse(data)
        return parsed["announcements"]

    @classmethod
    def _content_hash(cls, item: dict[str, Any]) -> str:
        """Stable hash for idempotency across sync runs."""
        payload = "|".join([
            str(item.get("l18", "")),
            str(item.get("code", "")),
            str(item.get("date_publish", "")),
            str(item.get("time_publish", "")),
            str(item.get("title", "")),
            str(item.get("link", "")),
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _parse_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"
        title = item.get("title", "")
        return {
            "symbol": item.get("l18", ""),
            "company_name": item.get("l30", ""),
            "title": title,
            "code": item.get("code", ""),
            "date_title": item.get("date_title", ""),
            "date_send": item.get("date_send", ""),
            "time_send": item.get("time_send", ""),
            "date_publish": item.get("date_publish", ""),
            "time_publish": item.get("time_publish", ""),
            "link": item.get("link", ""),
            "link_pdf": item.get("link_pdf", ""),
            "link_excel": item.get("link_excel", ""),
            "link_attachment": item.get("link_attachment", ""),
            "audit_status": detect_audit_status(title),
            "content_hash": cls._content_hash(item),
            "fetched_at": now,
            "raw_json": json.dumps(item, ensure_ascii=False),
        }
