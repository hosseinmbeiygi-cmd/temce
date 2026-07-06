"""
Codal announcement parser.

Maps the ``/Codal/Announcement.php`` JSON response to structured
announcement records suitable for the existing ``CodalReportModel``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


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
        """
        result: dict[str, Any] = {
            "count_announcement": 0,
            "count_page": 0,
            "announcements": [],
        }

        if isinstance(data, dict):
            result["count_announcement"] = int(data.get("count_announcement", 0))
            result["count_page"] = int(data.get("count_page", 0))

            raw_announcements = data.get("announcement") or data.get("announcements") or data.get("data") or data.get("items", [])
            if isinstance(raw_announcements, list):
                result["announcements"] = [cls._parse_item(a) for a in raw_announcements if isinstance(a, dict)]

        elif isinstance(data, list):
            result["count_announcement"] = len(data)
            result["announcements"] = [cls._parse_item(a) for a in data if isinstance(a, dict)]

        else:
            logger.warning("Codal: unexpected data type %s", type(data).__name__)

        return result

    @classmethod
    def parse_announcements_only(cls, data: Any) -> list[dict[str, Any]]:
        """Convenience: return just the list of parsed announcements."""
        parsed = cls.parse(data)
        return parsed["announcements"]

    @classmethod
    def _parse_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()[:30]
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
            "fetched_at": now,
            "raw_json": json.dumps(item, ensure_ascii=False),
        }
