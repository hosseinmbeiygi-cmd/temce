from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class SymbolChange:
    old_symbol: str
    new_symbol: str
    change_date: date
    instrument_id: str
    reason: str | None = None


class SymbolChangeTracker:
    def __init__(self) -> None:
        self._changes: list[SymbolChange] = []
        self._index_by_old: dict[str, SymbolChange] = {}
        self._index_by_new: dict[str, SymbolChange] = {}

    def add_change(self, change: SymbolChange) -> None:
        self._changes.append(change)
        self._changes.sort(key=lambda c: c.change_date)
        self._index_by_old[change.old_symbol] = change
        self._index_by_new[change.new_symbol] = change

    def get_change_by_old(self, old_symbol: str) -> SymbolChange | None:
        return self._index_by_old.get(old_symbol)

    def get_change_by_new(self, new_symbol: str) -> SymbolChange | None:
        return self._index_by_new.get(new_symbol)

    def resolve_symbol(self, symbol: str, as_of_date: date) -> str:
        change = self._index_by_old.get(symbol)
        if change and change.change_date <= as_of_date:
            return change.new_symbol
        return symbol

    def all_changes(self) -> list[SymbolChange]:
        return list(self._changes)

    def changes_between(self, start: date, end: date) -> list[SymbolChange]:
        return [c for c in self._changes if start <= c.change_date <= end]

    async def load_from_db(self, db: Any) -> None:
        rows = await db.fetch("SELECT * FROM symbol_changes ORDER BY change_date")
        for row in rows:
            self.add_change(
                SymbolChange(
                    old_symbol=str(row["old_symbol"]),
                    new_symbol=str(row["new_symbol"]),
                    change_date=row["change_date"],
                    instrument_id=str(row["instrument_id"]),
                    reason=row.get("reason"),
                )
            )
