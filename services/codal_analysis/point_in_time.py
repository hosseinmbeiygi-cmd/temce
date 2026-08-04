from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PointInTimeSnapshot:
    as_of_date: str
    symbol: str
    values: dict[str, float] = field(default_factory=dict)
    source_versions: dict[str, str] = field(default_factory=dict)
    document_ids: list[str] = field(default_factory=list)


@dataclass
class RestatementChain:
    symbol: str
    fiscal_period: str
    versions: list[dict[str, Any]] = field(default_factory=list)
    latest_version: dict[str, Any] | None = None


class PointInTimeEngine:
    """
    SCD Type 2 Point-in-Time Query Engine.
    Answers: "What was the reported net profit for symbol X at date Y?"
    """

    def __init__(self):
        self._versions: dict[str, list[dict[str, Any]]] = {}

    def register_version(
        self,
        symbol: str,
        fiscal_period: str,
        account_code: str,
        amount: float,
        version: int,
        valid_from: str,
        valid_to: str | None = None,
        document_id: str = "",
    ) -> None:
        key = f"{symbol}:{fiscal_period}:{account_code}"
        if key not in self._versions:
            self._versions[key] = []
        self._versions[key].append({
            "amount": amount,
            "version": version,
            "valid_from": valid_from,
            "valid_to": valid_to or "9999-12-31",
            "document_id": document_id,
        })
        self._versions[key].sort(key=lambda x: x["version"], reverse=True)

    def get_value_at(self, symbol: str, fiscal_period: str, account_code: str, as_of_date: str) -> dict[str, Any] | None:
        key = f"{symbol}:{fiscal_period}:{account_code}"
        versions = self._versions.get(key, [])
        for v in versions:
            if v["valid_from"] <= as_of_date <= v["valid_to"]:
                return v
        return None

    def get_latest(self, symbol: str, fiscal_period: str, account_code: str) -> dict[str, Any] | None:
        key = f"{symbol}:{fiscal_period}:{account_code}"
        versions = self._versions.get(key, [])
        if versions:
            return versions[0]
        return None

    def get_all_versions(self, symbol: str, fiscal_period: str, account_code: str) -> list[dict[str, Any]]:
        key = f"{symbol}:{fiscal_period}:{account_code}"
        return self._versions.get(key, [])

    def get_restatement_chain(self, symbol: str, fiscal_period: str, account_codes: list[str] | None = None) -> RestatementChain:
        chain = RestatementChain(symbol=symbol, fiscal_period=fiscal_period)
        seen: dict[int, dict[str, Any]] = {}
        codes = account_codes or []
        for code in codes:
            for v in self.get_all_versions(symbol, fiscal_period, code):
                ver = v["version"]
                if ver not in seen:
                    seen[ver] = {"version": ver, "accounts": {}, "document_id": "", "valid_from": v["valid_from"]}
                seen[ver]["accounts"][code] = v["amount"]
                if v["document_id"]:
                    seen[ver]["document_id"] = v["document_id"]

        chain.versions = sorted(seen.values(), key=lambda x: x["version"], reverse=True)
        if chain.versions:
            chain.latest_version = chain.versions[0]
        return chain

    def build_snapshot_at(self, symbol: str, fiscal_period: str, as_of_date: str, account_codes: list[str]) -> PointInTimeSnapshot:
        snap = PointInTimeSnapshot(as_of_date=as_of_date, symbol=symbol)
        for code in account_codes:
            v = self.get_value_at(symbol, fiscal_period, code, as_of_date)
            if v:
                snap.values[code] = v["amount"]
                snap.source_versions[code] = f"v{v['version']}"
                if v["document_id"] and v["document_id"] not in snap.document_ids:
                    snap.document_ids.append(v["document_id"])
        return snap


class MaterializedViewBuilder:
    """Creates and manages pivoted materialized views for performance"""

    def build_pivoted_snapshot_sql(self, schema: str = "public") -> str:
        return f"""
        CREATE MATERIALIZED VIEW {schema}.mv_financial_snapshot AS
        SELECT
            f.company_id,
            f.date_id,
            d.jalali_date,
            MAX(CASE WHEN a.canonical_code = 'REVENUE' THEN f.amount END) AS revenue,
            MAX(CASE WHEN a.canonical_code = 'COGS' THEN f.amount END) AS cost_of_goods_sold,
            MAX(CASE WHEN a.canonical_code = 'GROSS_PROFIT' THEN f.amount END) AS gross_profit,
            MAX(CASE WHEN a.canonical_code = 'OP_PROFIT' THEN f.amount END) AS operating_profit,
            MAX(CASE WHEN a.canonical_code = 'NET_PROFIT' THEN f.amount END) AS net_profit,
            MAX(CASE WHEN a.canonical_code = 'TOT_ASSETS' THEN f.amount END) AS total_assets,
            MAX(CASE WHEN a.canonical_code = 'TOT_LIAB' THEN f.amount END) AS total_liabilities,
            MAX(CASE WHEN a.canonical_code = 'TOT_EQUITY' THEN f.amount END) AS total_equity,
            MAX(CASE WHEN a.canonical_code = 'CUR_ASSETS' THEN f.amount END) AS current_assets,
            MAX(CASE WHEN a.canonical_code = 'CUR_LIAB' THEN f.amount END) AS current_liabilities,
            MAX(CASE WHEN a.canonical_code = 'CFO' THEN f.amount END) AS operating_cash_flow,
            MAX(CASE WHEN a.canonical_code = 'CASH' THEN f.amount END) AS cash,
            MAX(CASE WHEN a.canonical_code = 'INVENTORY' THEN f.amount END) AS inventory,
            MAX(CASE WHEN a.canonical_code = 'AR' THEN f.amount END) AS accounts_receivable
        FROM fact_financials f
        JOIN dim_account a ON f.account_id = a.account_id
        JOIN dim_date d ON f.date_id = d.date_id
        WHERE f.is_current = TRUE
        GROUP BY f.company_id, f.date_id, d.jalali_date
        ORDER BY f.company_id, f.date_id;
        """
