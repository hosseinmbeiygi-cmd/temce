from __future__ import annotations

from typing import Any

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)

CODAL_FIELD_MAP = {
    "TracingNo": "tracking_no",
    "Title": "title",
    "SentDateTime": "published_at",
    "InsCode": "instrument_id",
    "Symbol": "symbol",
    "CompanyCode": "company_code",
    "CompanyName": "company_name",
    "IndustryCode": "industry_code",
    "IndustryName": "industry_name",
    "CodalType": "disclosure_type",
    "CodalTitle": "disclosure_title",
    "Url": "url",
    "HasAttachment": "has_attachment",
    "AttachmentUrl": "attachment_url",
}

DISCLOSURE_TYPE_MAP = {
    "گزارش فعالیت ماهانه": "monthly_activity",
    "صورت‌های مالی": "financial_statements",
    "گزارش هیئت مدیره": "board_report",
    "افشاء اطلاعات": "information_disclosure",
    "سایر اطلاعیه‌ها": "other",
    "mitelecture": "general_meeting",
    "مجمع عمومی": "general_meeting",
    "پیشنهاد افزایش سرمایه": "capital_increase",
}


class CodalHarmonizer:
    def harmonize(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {"id": new_id("codal")}
        for raw_key, value in raw.items():
            key = CODAL_FIELD_MAP.get(raw_key, raw_key)
            normalized[key] = value
        raw_type = normalized.get("disclosure_type", "")
        normalized["disclosure_type"] = DISCLOSURE_TYPE_MAP.get(raw_type, raw_type)
        if not normalized.get("published_at"):
            normalized["published_at"] = None
        normalized.setdefault("source", "codal")
        normalized.setdefault("extra", {})
        logger.debug("Harmonized codal disclosure: %s", normalized.get("tracking_no", "?"))
        return normalized

    def harmonize_batch(self, raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.harmonize(raw) for raw in raw_list]
