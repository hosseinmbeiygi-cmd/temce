"""Basic raw-data validation for the AllSymbols scanner.

Scope guard: this module performs *shape and sanity* checks only.  It
deliberately does **not** compute technical indicators, scores or derived
features — those belong to the precompute scope.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

# Numeric fields produced by ``TsetmcParser.parse_all_symbols`` that must be
# real numbers when present.  Non-numeric values mean the upstream payload
# changed shape and the row must not enter the warm layer.
_NUMERIC_FIELDS: tuple[str, ...] = (
    "price_last",
    "price_close",
    "price_yesterday",
    "price_first",
    "price_min",
    "price_max",
    "trade_volume",
    "trade_value",
    "trade_count",
    "base_volume",
    "market_value",
)

# Price fields that must never be negative.
_NON_NEGATIVE_FIELDS: tuple[str, ...] = ("price_last", "price_close", "price_yesterday")


@dataclass(frozen=True)
class RawRejection:
    """A single dropped row and the reason it was dropped."""

    symbol: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"symbol": self.symbol, "reason": self.reason}


@dataclass
class RawValidationReport:
    """Outcome of a raw validation pass."""

    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[RawRejection] = field(default_factory=list)
    duplicate_symbols: int = 0

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def total_seen(self) -> int:
        return self.accepted_count + self.rejected_count + self.duplicate_symbols

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted_count,
            "rejected": self.rejected_count,
            "duplicates": self.duplicate_symbols,
            "total_seen": self.total_seen,
            "rejection_reasons": [item.as_dict() for item in self.rejected[:50]],
        }


class RawQuoteValidator:
    """Basic gate between the API response and the storage layers."""

    def __init__(self, *, allow_duplicates: bool = False) -> None:
        self._allow_duplicates = allow_duplicates

    def validate(self, rows: Iterable[Any]) -> RawValidationReport:
        report = RawValidationReport()
        seen: set[str] = set()

        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                report.rejected.append(RawRejection("", f"row {index}: not a mapping"))
                continue

            # Symbol is the storage key for both the hot and warm layers, so a
            # row without one is unusable — never fall back to ins_id, which
            # would leave an empty symbol in the accepted set.
            symbol = str(row.get("symbol") or "").strip()
            if not symbol:
                report.rejected.append(RawRejection("", f"row {index}: missing symbol"))
                continue

            problem = self._row_problem(row)
            if problem is not None:
                report.rejected.append(RawRejection(symbol, problem))
                continue

            if symbol in seen and not self._allow_duplicates:
                report.duplicate_symbols += 1
                continue
            seen.add(symbol)

            report.accepted.append(dict(row))

        return report

    @staticmethod
    def _row_problem(row: Mapping[str, Any]) -> str | None:
        for name in _NUMERIC_FIELDS:
            value = row.get(name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"{name} is not numeric ({type(value).__name__})"

        for name in _NON_NEGATIVE_FIELDS:
            value = row.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value < 0:
                return f"{name} is negative"

        if row.get("fetched_at") is None:
            return "missing fetched_at"

        return None
