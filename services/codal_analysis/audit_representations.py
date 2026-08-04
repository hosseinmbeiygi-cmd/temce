from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

STANDARD_REPRESENTATIONS = [
    "Management has fulfilled its responsibility for preparation of financial statements",
    "All transactions have been recorded in the accounting records",
    "All known misstatements have been corrected",
    "All related party transactions have been disclosed",
    "All subsequent events have been identified and disclosed",
    "There is no fraud involving management or employees with significant roles",
    "The company has complied with all laws and regulations",
    "All litigation and claims have been disclosed",
    "All assets are owned and free from liens except as disclosed",
    "All liabilities and commitments have been recorded and disclosed",
    "No plans or intentions exist that may affect carrying values of assets/liabilities",
    "All guarantees have been disclosed",
    "Management has assessed going concern and believes it is appropriate",
    "All estimates and judgments are reasonable under the circumstances",
]


@dataclass
class RepresentationItem:
    description: str
    is_obtained: bool = False
    date_obtained: str = ""
    exceptions: str = ""


@dataclass
class RepresentationLetter:
    entity: str = ""
    period: str = ""
    addressee: str = ""
    date: str = ""
    items: list[RepresentationItem] = field(default_factory=list)
    all_obtained: bool = False
    missing_count: int = 0


class RepresentationManager:
    """ISA 580: Written Representations"""

    @classmethod
    def create_letter(cls, entity: str, period: str, addressee: str = "Auditor") -> RepresentationLetter:
        rl = RepresentationLetter(entity=entity, period=period, addressee=addressee)
        for rep in STANDARD_REPRESENTATIONS:
            rl.items.append(RepresentationItem(description=rep))
        return rl

    @classmethod
    def obtain_representation(cls, letter: RepresentationLetter, index: int, date: str = "", exceptions: str = "") -> None:
        if 0 <= index < len(letter.items):
            letter.items[index].is_obtained = True
            letter.items[index].date_obtained = date
            letter.items[index].exceptions = exceptions

    @classmethod
    def obtain_all(cls, letter: RepresentationLetter, date: str = "") -> None:
        for item in letter.items:
            item.is_obtained = True
            item.date_obtained = date

    @classmethod
    def check_completeness(cls, letter: RepresentationLetter) -> None:
        missing = [i for i in letter.items if not i.is_obtained]
        letter.all_obtained = len(missing) == 0
        letter.missing_count = len(missing)

    @classmethod
    def date_letter(cls, letter: RepresentationLetter, date: str) -> None:
        letter.date = date


def format_representation_for_response(letter: RepresentationLetter) -> dict[str, Any]:
    return {
        "entity": letter.entity,
        "period": letter.period,
        "addressee": letter.addressee,
        "date": letter.date,
        "all_obtained": letter.all_obtained,
        "missing_count": letter.missing_count,
        "items": [
            {
                "description": i.description,
                "is_obtained": i.is_obtained,
                "date_obtained": i.date_obtained,
                "exceptions": i.exceptions,
            }
            for i in letter.items
        ],
        "status": "complete" if letter.all_obtained else f"missing {letter.missing_count} items",
    }
