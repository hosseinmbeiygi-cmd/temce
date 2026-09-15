from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.codal_financial import CodalFinancialStatementModel
from services.codal_accounting_service import (
    REPORT_TYPE_LABELS,
    _classify_item,
    _extract_last_value,
)

logger = get_logger(__name__)

RATIO_DEFINITIONS: dict[str, dict[str, Any]] = {
    "current_ratio": {
        "label": "نسبت جاری",
        "formula": "دارایی‌های جاری / بدهی‌های جاری",
        "description": "نشان‌دهنده توانایی شرکت در پرداخت بدهی‌های کوتاه‌مدت",
        "good_range": "۱.۵ - ۳",
        "inputs": ["total_current_assets", "total_current_liabilities"],
        "fallback_inputs": ["current_assets", "current_liabilities"],
    },
    "debt_to_equity": {
        "label": "نسبت بدهی به حقوق صاحبان سهام (D/E)",
        "formula": "جمع بدهی‌ها / حقوق صاحبان سهام",
        "description": "میزان اهرم مالی شرکت را نشان می‌دهد",
        "good_range": "< ۱",
        "inputs": ["total_liabilities", "total_equity"],
        "fallback_inputs": ["total_liabilities", "equity"],
    },
    "roe": {
        "label": "بازده حقوق صاحبان سهام (ROE)",
        "formula": "سود خالص / حقوق صاحبان سهام",
        "description": "میزان بازدهی سرمایه صاحبان سهام",
        "good_range": "> ۲۰%",
        "inputs": ["net_profit", "total_equity"],
        "fallback_inputs": ["net_profit", "equity"],
    },
    "roa": {
        "label": "بازده دارایی‌ها (ROA)",
        "formula": "سود خالص / جمع دارایی‌ها",
        "description": "میزان کارایی شرکت در استفاده از دارایی‌ها",
        "good_range": "> ۱۰%",
        "inputs": ["net_profit", "total_assets"],
    },
    "gross_margin": {
        "label": "حاشیه سود ناخالص",
        "formula": "سود ناخالص / فروش",
        "description": "درصد سود پس از کسر بهای تمام شده",
        "good_range": "متغیر بر اساس صنعت",
        "inputs": ["gross_profit", "revenue"],
    },
    "net_margin": {
        "label": "حاشیه سود خالص",
        "formula": "سود خالص / فروش",
        "description": "درصد سود خالص از فروش",
        "good_range": "> ۱۰%",
        "inputs": ["net_profit", "revenue"],
    },
    "operating_margin": {
        "label": "حاشیه سود عملیاتی",
        "formula": "سود عملیاتی / فروش",
        "description": "درصد سود عملیاتی از فروش",
        "good_range": "> ۱۵%",
        "inputs": ["operating_profit", "revenue"],
    },
}


class CodalFinancialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_symbols(self) -> list[dict[str, Any]]:
        stmt = (
            select(
                CodalFinancialStatementModel.symbol,
            )
            .distinct()
            .order_by(CodalFinancialStatementModel.symbol)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        symbols = []
        for (symbol,) in rows:
            cnt = await self._count_reports(symbol)
            symbols.append(
                {
                    "symbol": symbol,
                    "total_reports": cnt,
                    "source": "db",
                }
            )
        return symbols

    async def _count_reports(self, symbol: str) -> int:
        stmt = select(CodalFinancialStatementModel).where(CodalFinancialStatementModel.symbol == symbol)
        result = await self.session.execute(stmt)
        return len(result.all())

    async def list_reports(self, symbol: str, report_type: str | None = None) -> list[dict[str, Any]]:
        stmt = select(CodalFinancialStatementModel).where(CodalFinancialStatementModel.symbol == symbol)
        if report_type:
            stmt = stmt.where(CodalFinancialStatementModel.report_type == report_type)
        stmt = stmt.order_by(CodalFinancialStatementModel.report_date.desc().nullslast())
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        reports: list[dict[str, Any]] = []
        for m in models:
            reports.append(
                {
                    "symbol": m.symbol,
                    "report_type": m.report_type or "",
                    "report_type_label": REPORT_TYPE_LABELS.get(m.report_type or "", m.report_type or ""),
                    "date": m.report_date or "",
                    "filename": m.filename or "",
                    "filepath": m.file_path or "",
                    "source": "db",
                }
            )
        return reports

    async def get_report_data(self, symbol: str, filename: str) -> dict[str, Any] | None:
        stmt = select(CodalFinancialStatementModel).where(
            CodalFinancialStatementModel.symbol == symbol,
            CodalFinancialStatementModel.filename == filename,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model and model.parsed_data:
            data = dict(model.parsed_data)
            data["symbol"] = symbol
            data["filename"] = filename
            data["report_type"] = model.report_type or ""
            data["date"] = model.report_date or ""
            data["source"] = "db"
            return data
        return None

    async def get_financial_summary(self, symbol: str) -> dict[str, Any]:
        reports = await self.list_reports(symbol)
        if not reports:
            return {"symbol": symbol, "error": "No reports found in DB"}

        report_types = {r["report_type"] for r in reports if r["report_type"]}
        result: dict[str, Any] = {
            "symbol": symbol,
            "total_reports": len(reports),
            "source": "db",
            "latest_reports": {},
        }

        for rt in report_types:
            type_reports = [r for r in reports if r["report_type"] == rt]
            if type_reports:
                latest = type_reports[0]
                data = await self.get_report_data(symbol, latest["filename"])
                if data:
                    table_summaries: dict[str, Any] = {}
                    for table in data.get("tables", []):
                        for item in table.get("items", []):
                            label = item["label"]
                            if label in ("جمع", "مجموع"):
                                continue
                            if item["values"]:
                                vals = list(item["values"].values())
                                numeric_vals = [v for v in vals if v != 0]
                                if numeric_vals:
                                    table_summaries[label] = numeric_vals[-1]
                    result["latest_reports"][rt] = {
                        "date": latest["date"],
                        "filename": latest["filename"],
                        "label": REPORT_TYPE_LABELS.get(rt, rt),
                        "items": table_summaries,
                    }

        return result

    async def calculate_ratios(self, symbol: str) -> dict[str, Any]:
        reports = await self.list_reports(symbol)
        if not reports:
            return {"symbol": symbol, "error": "No reports found in DB"}

        classified: dict[str, float] = {}
        seen_labels: set[str] = set()

        for rt in {r["report_type"] for r in reports if r["report_type"]}:
            type_reports = [r for r in reports if r["report_type"] == rt]
            if not type_reports:
                continue
            data = await self.get_report_data(symbol, type_reports[0]["filename"])
            if not data or "error" in data:
                continue

            for table in data.get("tables", []):
                for item in table.get("items", []):
                    label = item["label"]
                    if label in seen_labels:
                        continue
                    category = _classify_item(label)
                    if category:
                        seen_labels.add(label)
                        value = _extract_last_value(item)
                        if value != 0:
                            if category not in classified or abs(value) > abs(classified[category]):
                                classified[category] = value

        ratios: list[dict[str, Any]] = []
        for key, defn in RATIO_DEFINITIONS.items():
            numerator = None
            denominator = None
            for inputs in [defn["inputs"], defn.get("fallback_inputs", [])]:
                if len(inputs) >= 2:
                    a = classified.get(inputs[0])
                    b = classified.get(inputs[1])
                    if a is not None and b is not None and b != 0:
                        numerator = a
                        denominator = b
                        break

            if numerator is not None and denominator is not None:
                ratio_value = numerator / denominator
                ratio_pct = ratio_value * 100
                ratios.append(
                    {
                        "key": key,
                        "label": defn["label"],
                        "formula": defn["formula"],
                        "description": defn["description"],
                        "good_range": defn["good_range"],
                        "value": round(ratio_value, 4),
                        "value_pct": round(ratio_pct, 2),
                        "numerator": round(numerator, 2),
                        "denominator": round(denominator, 2),
                        "numerator_label": defn["inputs"][0] if len(defn["inputs"]) >= 1 else "",
                        "denominator_label": defn["inputs"][1] if len(defn["inputs"]) >= 2 else "",
                    }
                )

        return {
            "symbol": symbol,
            "total_reports": len(reports),
            "source": "db",
            "classified_items": {
                k: round(v, 2) for k, v in sorted(classified.items(), key=lambda x: abs(x[1]), reverse=True)
            },
            "ratios": ratios,
            "ratio_count": len(ratios),
        }

    async def get_all_reports_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """Get all reports with full parsed data for a symbol."""
        stmt = (
            select(CodalFinancialStatementModel)
            .where(CodalFinancialStatementModel.symbol == symbol)
            .order_by(CodalFinancialStatementModel.report_date.desc().nullslast())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        reports: list[dict[str, Any]] = []
        for m in models:
            reports.append(
                {
                    "id": m.id,
                    "symbol": m.symbol,
                    "report_type": m.report_type or "",
                    "report_type_label": REPORT_TYPE_LABELS.get(m.report_type or "", ""),
                    "date": m.report_date or "",
                    "filename": m.filename or "",
                    "title": m.title or "",
                    "table_count": m.table_count or 0,
                    "row_count": m.row_count or 0,
                    "import_batch": m.import_batch or "",
                    "imported_at": str(m.imported_at) if m.imported_at else "",
                }
            )
        return reports
