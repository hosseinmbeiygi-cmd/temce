"""One bad bar must not roll back the rest of its batch.

Audit DB-07. Each INSERT ran inside the caller's transaction: on PostgreSQL the
first failure aborts the transaction, every following row fails with "current
transaction is aborted", and the final commit raises — while the report still
claimed the rows were written.
"""

from __future__ import annotations

import pytest

from brsapi.quality import normalize_jalali_date
from brsapi.services.history_fetch_service import HistoryFetchService

FAIL_DATE = normalize_jalali_date("1404-02-24")


class _Session:
    def __init__(self) -> None:
        self.nested = 0
        self.commits = 0
        self.attempted: list[str] = []

    def begin_nested(self):
        self.nested += 1
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def execute(self, _stmt, params=None):
        date = (params or {}).get("date")
        self.attempted.append(date)
        if date == FAIL_DATE:
            raise RuntimeError("boom")

    async def commit(self) -> None:
        self.commits += 1


def _bar(date: str, close: float = 100.0) -> dict:
    return {"date": date, "open": 100.0, "high": 105.0, "low": 95.0, "close": close, "volume": 10}


async def test_a_failed_row_does_not_abort_the_remaining_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session()
    service = HistoryFetchService(session=session)

    async def _fetch(_symbol, _start, _end):
        return [_bar("1404-02-23"), _bar("1404-02-24"), _bar("1404-02-25")]

    monkeypatch.setattr(service, "fetch_history", _fetch)

    reports = await service.sync_crypto_history(symbols=["BTCUSDT"], date_start="1404-01-01")

    assert len(reports) == 1
    report = reports[0]
    assert report.record_count == 2, "rows after the failure must still be written"
    assert report.failed_count == 1
    assert session.nested == 3, "every row must run in its own SAVEPOINT"
    assert session.commits == 1
