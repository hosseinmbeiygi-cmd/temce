"""Unit tests for ``sync_shareholders`` — the fetch-date stamping fallback.

``Shareholder.php`` returns the LATEST composition and carries no ``date``
field, so ``sync_shareholders`` stamps every record with the fetch date
(Gregorian ``YYYY-MM-DD``) to keep the ``date`` column non-NULL on the
latest-status sync path (daily 13:30 job + manual full-market backfill).
"""

from datetime import datetime
from unittest.mock import AsyncMock

from brsapi.services.sync_service import BrsApiSyncService, SyncReport


async def test_sync_shareholders_stamps_fetch_date():
    svc = BrsApiSyncService(client=None, session=None)
    svc._lookup_ins_id = AsyncMock(return_value="12345")
    captured: dict = {}

    async def _fake_sync(**kwargs):
        captured["parser"] = kwargs["parser"]
        return SyncReport(endpoint="/Tsetmc/Shareholder.php", success=True, items_count=1)

    svc.sync = _fake_sync  # type: ignore[method-assign]

    report = await svc.sync_shareholders(None, "فولاد")

    assert report.success is True
    records = captured["parser"]([
        {"id": 7, "name": "سهامدار الف", "volume": 10, "percent": 1.0, "change": 0},
    ])
    # The API payload has no date — the fetch date is stamped on every record.
    assert records[0]["date"] == datetime.now().strftime("%Y-%m-%d")
    assert records[0]["symbol"] == "فولاد"
    assert records[0]["ins_id"] == "12345"
    svc._lookup_ins_id.assert_awaited_once()
