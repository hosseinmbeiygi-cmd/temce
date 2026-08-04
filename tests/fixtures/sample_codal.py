from __future__ import annotations

from core.ids import new_id
from domain.codal.disclosures import CodalDisclosure


def sample_codal_report(
    id: str | None = None,
    symbol: str = "فولاد",
    report_type: str = "yearly_financial",
) -> CodalDisclosure:
    return CodalDisclosure(
        id=id or new_id("cod"),
        instrument_id="inst_test_001",
        symbol=symbol,
        title="فولاد مبارکه اصفهان",
        disclosure_type=report_type,
        fiscal_year="1402",
        period="12_months",
        category="audited",
        publish_date=None,
        url="https://codal.ir/Reports/12345.pdf",
        summary={
            "total_revenue": 250_000_000_000_000,
            "net_profit": 45_000_000_000_000,
            "eps": 1500,
            "book_value": 8000,
        },
        is_important=False,
        data_source="codal",
    )


def sample_codal_list(count: int = 5) -> list[CodalDisclosure]:
    symbols = ["فولاد", "فملی", "وبانک", "کگل", "خودرو"]
    return [sample_codal_report(symbol=symbols[i % len(symbols)]) for i in range(count)]
