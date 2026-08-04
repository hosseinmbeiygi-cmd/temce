from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ConfirmationRequest:
    entity_name: str = ""
    account_type: str = ""
    balance: float = 0
    method: str = "positive"
    sent_date: str = ""
    response_date: str = ""
    confirmed_balance: float | None = None
    difference: float = 0
    status: str = "pending"
    exception_notes: str = ""


@dataclass
class ConfirmationSummary:
    total_sent: int = 0
    total_positive: int = 0
    total_negative: int = 0
    responses_received: int = 0
    exceptions_found: int = 0
    confirmed_without_exception: int = 0
    alternative_procedures_needed: int = 0
    coverage_pct: float = 0
    conclusion: str = ""


class ConfirmationManager:
    """ISA 505: External Confirmations"""

    @classmethod
    def create_request(
        cls, entity: str, account_type: str, balance: float,
        method: str = "positive",
    ) -> ConfirmationRequest:
        return ConfirmationRequest(
            entity_name=entity,
            account_type=account_type,
            balance=balance,
            method=method if method in ("positive", "negative") else "positive",
        )

    @classmethod
    def record_response(
        cls, request: ConfirmationRequest, confirmed: float, notes: str = "",
    ) -> ConfirmationRequest:
        request.response_date = "recorded"
        request.confirmed_balance = confirmed
        request.difference = round(request.balance - confirmed, 2)
        if abs(request.difference) > 0:
            request.status = "exception"
            request.exception_notes = notes or f"Difference: {request.difference:,.0f}"
        else:
            request.status = "confirmed"
        return request

    @classmethod
    def summarize(cls, requests: list[ConfirmationRequest], total_population: float = 0) -> ConfirmationSummary:
        summary = ConfirmationSummary(
            total_sent=len(requests),
            total_positive=sum(1 for r in requests if r.method == "positive"),
            total_negative=sum(1 for r in requests if r.method == "negative"),
            responses_received=sum(1 for r in requests if r.status != "pending"),
            exceptions_found=sum(1 for r in requests if r.status == "exception"),
            confirmed_without_exception=sum(1 for r in requests if r.status == "confirmed"),
            alternative_procedures_needed=sum(1 for r in requests if r.status == "pending"),
        )
        confirmed_sum = sum(r.balance for r in requests if r.status in ("confirmed", "exception"))
        if total_population > 0:
            summary.coverage_pct = round(confirmed_sum / total_population * 100, 1)
        if summary.exceptions_found > 0:
            summary.conclusion = "Exceptions identified - additional procedures required"
        elif summary.alternative_procedures_needed > 0:
            summary.conclusion = "Non-responses require alternative procedures"
        else:
            summary.conclusion = "All confirmations reconciled without exception"
        return summary


def format_confirmation_for_response(summary: ConfirmationSummary, requests: list[ConfirmationRequest] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "summary": {
            "total_sent": summary.total_sent,
            "responses_received": summary.responses_received,
            "confirmed_without_exception": summary.confirmed_without_exception,
            "exceptions_found": summary.exceptions_found,
            "coverage_pct": summary.coverage_pct,
            "conclusion": summary.conclusion,
        }
    }
    if requests:
        result["requests"] = [
            {
                "entity": r.entity_name,
                "account_type": r.account_type,
                "balance": r.balance,
                "method": r.method,
                "status": r.status,
                "confirmed_balance": r.confirmed_balance,
                "difference": r.difference,
                "exception_notes": r.exception_notes,
            }
            for r in requests
        ]
    return result
