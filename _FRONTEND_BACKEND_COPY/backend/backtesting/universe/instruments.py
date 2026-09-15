from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class InstrumentInfo:
    id: str
    symbol: str
    name: str
    market: str
    instrument_type: str
    group_code: str | None = None
    sector_code: str | None = None
    sub_group_code: str | None = None
    exchange_code: str | None = None
    board_code: str | None = None
    isin: str | None = None
    tick_size: float = 1.0
    lot_size: int = 1
    par_value: int = 1000
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


class InstrumentUniverse:
    BOURSE = "bourse"
    FARABOURSE = "farabourse"
    ENERGY = "energy"
    DERIVATIVES = "derivatives"

    def __init__(self) -> None:
        self._instruments: dict[str, InstrumentInfo] = {}
        self._symbol_index: dict[str, str] = {}

    def add(self, info: InstrumentInfo) -> None:
        self._instruments[info.id] = info
        if info.symbol:
            self._symbol_index[info.symbol] = info.id

    def get_by_id(self, instrument_id: str) -> InstrumentInfo | None:
        return self._instruments.get(instrument_id)

    def get_by_symbol(self, symbol: str) -> InstrumentInfo | None:
        inst_id = self._symbol_index.get(symbol)
        if inst_id:
            return self._instruments.get(inst_id)
        return None

    def all(self) -> list[InstrumentInfo]:
        return list(self._instruments.values())

    def by_market(self, market: str) -> list[InstrumentInfo]:
        return [i for i in self._instruments.values() if i.market == market]

    def by_type(self, instrument_type: str) -> list[InstrumentInfo]:
        return [i for i in self._instruments.values() if i.instrument_type == instrument_type]

    def by_group(self, group_code: str) -> list[InstrumentInfo]:
        return [i for i in self._instruments.values() if i.group_code == group_code]

    def count(self) -> int:
        return len(self._instruments)

    def search(self, query: str) -> list[InstrumentInfo]:
        q = query.lower()
        return [i for i in self._instruments.values() if q in i.symbol.lower() or q in i.name.lower()]

    async def load_from_db(self, db: Any) -> None:
        rows = await db.fetch("SELECT * FROM instruments WHERE status = 'active'")
        for row in rows:
            self.add(
                InstrumentInfo(
                    id=str(row["id"]),
                    symbol=row.get("symbol", ""),
                    name=row.get("name", ""),
                    market=row.get("market_type", ""),
                    instrument_type=row.get("instrument_type", "stock"),
                    group_code=row.get("group_code"),
                    sector_code=row.get("sector_code"),
                    sub_group_code=row.get("sub_group_code"),
                    exchange_code=row.get("exchange_code"),
                    board_code=row.get("board_code"),
                    isin=row.get("isin"),
                    tick_size=float(row.get("tick_size", 1.0)),
                    lot_size=int(row.get("lot_size", 1)),
                    par_value=int(row.get("par_value", 1000)),
                    status=row.get("status", "active"),
                )
            )
        logger.info("Loaded %d instruments from DB", len(rows))
