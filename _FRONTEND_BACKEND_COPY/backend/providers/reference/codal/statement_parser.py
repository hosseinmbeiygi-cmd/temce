from __future__ import annotations

import re
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


FINANCIAL_STATEMENT_TYPES = ["balance_sheet", "income_statement", "cash_flow", "notes"]


class StatementParser:
    def __init__(self) -> None:
        self._patterns: dict[str, re.Pattern] = {
            "total_assets": re.compile(r"مجموع\s*دارایی", re.IGNORECASE),
            "total_liabilities": re.compile(r"مجموع\s*بدهی", re.IGNORECASE),
            "equity": re.compile(r"حقوق\s*صاحبان\s*سهام", re.IGNORECASE),
            "revenue": re.compile(r"درآمد\s*عملیاتی|فروش", re.IGNORECASE),
            "net_income": re.compile(r"سود\s*خالص|خالص\s*سود", re.IGNORECASE),
            "eps": re.compile(r"سود\s*به\s*ازای\s*سهم|EPS", re.IGNORECASE),
        }

    def parse(self, text: str, statement_type: str = "") -> dict[str, Any]:
        if statement_type and statement_type not in FINANCIAL_STATEMENT_TYPES:
            logger.warning("Unknown statement type: %s", statement_type)

        result: dict[str, Any] = {}
        for field, pattern in self._patterns.items():
            match = pattern.search(text)
            if match:
                lines = text[match.start() :].split("\n")
                if len(lines) > 0:
                    value_line = lines[0]
                    numbers = re.findall(r"[\d,]+(?:\.\d+)?", value_line)
                    result[field] = numbers[-1] if numbers else None

        result["statement_type"] = statement_type or "unknown"
        result["raw_length"] = len(text)
        return result

    def parse_table(self, table_text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        lines = [line.strip() for line in table_text.split("\n") if line.strip()]
        for line in lines:
            parts = re.split(r"\s{2,}|\t", line)
            if len(parts) >= 2:
                row: dict[str, Any] = {"label": parts[0]}
                for i, val in enumerate(parts[1:], 1):
                    clean = val.replace(",", "").strip()
                    try:
                        row[f"col_{i}"] = int(clean) if clean.isdigit() else float(clean)
                    except ValueError:
                        row[f"col_{i}"] = val
                rows.append(row)
        return rows
