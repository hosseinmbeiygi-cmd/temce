from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImpairmentResult:
    asset_description: str = ""
    carrying_amount: float = 0
    recoverable_amount: float = 0
    impairment_loss: float = 0
    value_in_use: float = 0
    fair_value_less_costs: float = 0
    is_impaired: bool = False
    cash_generating_unit: str = ""
    reasoning: list[str] = field(default_factory=list)


@dataclass
class TaxReconciliationResult:
    accounting_profit: float = 0
    taxable_profit: float = 0
    current_tax: float = 0
    deferred_tax: float = 0
    total_tax_expense: float = 0
    effective_tax_rate: float = 0
    statutory_rate: float = 0
    permanent_differences: list[dict[str, Any]] = field(default_factory=list)
    temporary_differences: list[dict[str, Any]] = field(default_factory=list)
    reconciliation_items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ConsolidationWorksheet:
    parent_company: str = ""
    subsidiaries: list[str] = field(default_factory=list)
    intercompany_transactions: list[dict[str, Any]] = field(default_factory=list)
    minority_interest: float = 0
    consolidated_revenue: float = 0
    consolidated_net_profit: float = 0
    elimination_entries: list[dict[str, Any]] = field(default_factory=list)


class ProfessionalJudgmentSimulator:
    """
    IAS 36: Impairment Testing
    IAS 12: Tax Reconciliation
    IFRS 10: Consolidation
    """

    def __init__(self, discount_rate: float = 0.18, tax_rate: float = 0.25):
        self.discount_rate = discount_rate
        self.tax_rate = tax_rate

    # ── IAS 36: Impairment Testing ─────────────────────────────────────

    def impairment_testing(
        self,
        carrying_amount: float,
        projected_cashflows: list[float],
        fair_value_less_costs: float | None = None,
        growth_rate: float = 0.02,
        cgu_name: str = "Main CGU",
        asset_description: str = "Fixed Assets",
    ) -> ImpairmentResult:
        reasoning = []

        value_in_use = self._dcf_valuation(projected_cashflows, self.discount_rate, growth_rate)

        fvlc = fair_value_less_costs or (carrying_amount * 0.9)
        recoverable_amount = max(value_in_use, fvlc)

        reasoning.append(f"Carrying amount: {carrying_amount:,.0f}")
        reasoning.append(f"Value in use (DCF@{self.discount_rate:.0%}): {value_in_use:,.0f}")
        if fair_value_less_costs:
            reasoning.append(f"Fair value less costs to sell: {fvlc:,.0f}")
        reasoning.append(f"Recoverable amount (higher of Viu and FV): {recoverable_amount:,.0f}")

        is_impaired = carrying_amount > recoverable_amount
        impairment_loss = max(0, carrying_amount - recoverable_amount)

        if is_impaired:
            reasoning.append(f"IMPAIRED: Carrying amount exceeds recoverable amount by {impairment_loss:,.0f} (IAS 36.59)")
        else:
            reasoning.append("NOT IMPAIRED: Recoverable amount exceeds carrying amount (IAS 36.59)")

        return ImpairmentResult(
            asset_description=asset_description,
            carrying_amount=carrying_amount,
            recoverable_amount=round(recoverable_amount),
            impairment_loss=round(impairment_loss),
            value_in_use=round(value_in_use),
            fair_value_less_costs=round(fvlc),
            is_impaired=is_impaired,
            cash_generating_unit=cgu_name,
            reasoning=reasoning,
        )

    # ── IAS 12: Tax Reconciliation ──────────────────────────────────────

    def tax_reconciliation(
        self,
        accounting_profit: float,
        permanent_additions: list[tuple[str, float]] | None = None,
        permanent_deductions: list[tuple[str, float]] | None = None,
        temporary_differences: list[tuple[str, float, str]] | None = None,
    ) -> TaxReconciliationResult:
        statutory = self.tax_rate
        permanent_add = permanent_additions or []
        permanent_ded = permanent_deductions or []
        temp_diffs = temporary_differences or []

        total_permanent_add = sum(v for _, v in permanent_add)
        total_permanent_ded = sum(v for _, v in permanent_ded)
        taxable_profit = accounting_profit + total_permanent_add - total_permanent_ded

        current_tax = taxable_profit * statutory if taxable_profit > 0 else 0

        deferred_tax_liability = 0
        deferred_tax_asset = 0
        for _desc, amount, kind in temp_diffs:
            if kind == "taxable":
                deferred_tax_liability += amount * statutory
            elif kind == "deductible":
                deferred_tax_asset += amount * statutory

        deferred_tax = deferred_tax_liability - deferred_tax_asset
        total_tax = current_tax + deferred_tax
        effective_rate = total_tax / accounting_profit if accounting_profit else 0

        reconciliation_items = [
            {"description": "Accounting profit", "amount": accounting_profit, "type": "base"},
            {"description": "Statutory tax rate", "amount": statutory, "type": "rate"},
            {"description": f"Expected tax expense at {statutory:.0%}", "amount": accounting_profit * statutory, "type": "expected"},
        ]

        for desc, val in permanent_add:
            reconciliation_items.append({"description": f"Permanent addition: {desc}", "amount": val, "type": "permanent_add"})
        for desc, val in permanent_ded:
            reconciliation_items.append({"description": f"Permanent deduction: {desc}", "amount": -val, "type": "permanent_ded"})

        return TaxReconciliationResult(
            accounting_profit=accounting_profit,
            taxable_profit=round(taxable_profit),
            current_tax=round(current_tax),
            deferred_tax=round(deferred_tax),
            total_tax_expense=round(total_tax),
            effective_tax_rate=round(effective_rate, 4),
            statutory_rate=statutory,
            permanent_differences=[{"description": d, "amount": a} for d, a in permanent_add + permanent_ded],
            temporary_differences=[{"description": d, "amount": a, "type": t} for d, a, t in temp_diffs],
            reconciliation_items=reconciliation_items,
        )

    # ── IFRS 10: Consolidation Worksheet ───────────────────────────────

    def consolidation_worksheet(
        self,
        parent_revenue: float,
        parent_net_profit: float,
        parent_investment: float,
        subsidiaries: list[dict[str, Any]],
        intercompany_transactions: list[dict[str, Any]] | None = None,
        ownership_percentages: list[float] | None = None,
    ) -> ConsolidationWorksheet:
        ws = ConsolidationWorksheet()
        total_subsidiary_revenue = 0
        total_subsidiary_profit = 0
        total_subsidiary_equity = 0
        eliminations_revenue = 0
        eliminations_profit = 0

        for i, sub in enumerate(subsidiaries):
            ws.subsidiaries.append(sub.get("name", f"Sub_{i}"))
            total_subsidiary_revenue += sub.get("revenue", 0)
            total_subsidiary_profit += sub.get("net_profit", 0)
            total_subsidiary_equity += sub.get("equity", 0)
            ownership = (ownership_percentages or [1.0] * len(subsidiaries))[i] if i < len(ownership_percentages or []) else 1.0
            minority = 1.0 - ownership
            ws.minority_interest += sub.get("equity", 0) * minority

        interco = intercompany_transactions or []
        for t in interco:
            interco_entry = {"description": t.get("description", ""), "amount": t.get("amount", 0), "type": t.get("type", "revenue")}
            ws.intercompany_transactions.append(interco_entry)
            if t.get("type") == "revenue":
                eliminations_revenue += t.get("amount", 0)
                ws.elimination_entries.append({"account": "Revenue", "debit": t.get("amount", 0), "credit": 0, "description": f"Eliminate intercompany revenue: {t.get('description', '')}"})
            elif t.get("type") == "profit":
                eliminations_profit += t.get("amount", 0)
                ws.elimination_entries.append({"account": "Net Profit", "debit": t.get("amount", 0), "credit": 0, "description": f"Eliminate intercompany profit: {t.get('description', '')}"})

        ws.consolidated_revenue = parent_revenue + total_subsidiary_revenue - eliminations_revenue
        ws.consolidated_net_profit = parent_net_profit + total_subsidiary_profit - eliminations_profit

        ws.elimination_entries.append({"account": "Investment in Subsidiaries", "debit": 0, "credit": parent_investment, "description": "Eliminate parent investment against subsidiary equity"})

        return ws

    def _dcf_valuation(self, cashflows: list[float], discount_rate: float, terminal_growth: float = 0.02) -> float:
        pv = sum(cf / (1 + discount_rate) ** (i + 1) for i, cf in enumerate(cashflows))
        if cashflows:
            terminal = cashflows[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
            pv += terminal / (1 + discount_rate) ** len(cashflows)
        return pv
