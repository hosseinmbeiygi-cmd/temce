"""Regression tests for ``BrsApiSyncService.sync_codal``.

Locks in two production fixes:
1. ``start_page > 1`` used to never fetch anything (the while-loop guard
   compared against ``total_pages_api=1``), so a resume backfill returned
   ``0 items in 0.0 min``.
2. ``stop_date`` stops the pagination once a page is entirely older than
   the requested Jalali cutoff (used for "last month" backfills).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from brsapi.services.sync_service import BrsApiSyncService, _normalize_codal_date


class _FakeResp:
    """Mirrors the Result envelope: .success + .value(BrsApiResponse)."""

    def __init__(self, data: dict):
        self.success = True
        self.error = None
        self.value = type("V", (), {"data": data, "raw_bytes": None})()


class _FakeClient:
    def __init__(self, pages: list[dict]):
        self._pages = pages
        self.calls: list[int] = []

    async def fetch(self, _endpoint, params=None, category_override=None):  # noqa: ANN001
        page = int(params["page"])
        self.calls.append(page)
        if page - 1 >= len(self._pages):
            return _FakeResp({"count_page": 0, "announcements": []})
        return _FakeResp(self._pages[page - 1])


def _page(count_page: int, *dates: str) -> dict:
    return {
        "count_page": count_page,
        "announcements": [
            {
                "l18": "فملی",
                "l30": "ملی صنایع مس ایران",
                "title": "گزارش فعالیت ماهانه",
                "code": f"ن-{i}",
                "date_title": d,
                "date_send": d,
                "date_publish": d,
                "time_send": "08:00:00",
                "time_publish": "08:00:00",
                "link": "",
                "link_pdf": "",
                "link_excel": "",
                "link_attachment": "",
            }
            for i, d in enumerate(dates)
        ],
    }


def _make_session():
    class _R:
        def __iter__(self):
            return iter([])

        def fetchall(self):
            return []

        def scalar_one_or_none(self):
            return None

        def scalars(self):
            return []

    class _S:
        def add(self, _obj):
            return None

        async def commit(self):
            return None

        async def rollback(self):
            return None

        async def flush(self):
            return None

        async def execute(self, _stmt, _params=None):
            return _R()

    return _S()


async def _run_sync(session, client, *, start_page=1, stop_date=None, backfill=True, max_pages=None):
    svc = BrsApiSyncService(client=client)
    # Bypass real DB: bulk_insert returns len(records) as "inserted", and the
    # instrument-ref lookup is already a no-op via the fake session.
    with patch("brsapi.services.sync_service.asyncio.sleep", new=AsyncMock()), patch(
        "brsapi.services.sync_service.BulkUpsertRepository.bulk_insert",
        new=AsyncMock(side_effect=lambda records, **kw: len(records)),
    ):
        report = await svc.sync_codal(
            session,
            backfill=backfill,
            start_page=start_page,
            stop_date=stop_date,
            max_pages=max_pages,
        )
    return report


def test_start_page_greater_than_one_fetches_pages():
    """Resume from page 175 must actually fetch (regression for the 0-item bug)."""
    pages = [_page(300, "1405/05/01", "1405/04/30") for _ in range(200)]
    client = _FakeClient(pages)
    report = asyncio_run(_run_sync, _make_session(), client, start_page=175, max_pages=3)
    assert report.success is True
    assert client.calls[0] == 175, f"first fetched page should be 175, got {client.calls[0]}"
    assert len(client.calls) == 3  # 175, 176, 177


def test_stop_date_stops_when_page_older_than_cutoff():
    """A page entirely older than stop_date terminates the walk."""
    pages = [
        _page(100, "1405/04/20", "1405/04/19"),  # newer than cutoff → keep going
        _page(100, "1405/04/10", "1405/04/09"),  # older than cutoff → stop
        _page(100, "1405/03/01", "1405/02/28"),
    ]
    client = _FakeClient(pages)
    report = asyncio_run(_run_sync, _make_session(), client, stop_date="1405-04-14")
    assert report.success is True
    assert client.calls == [1, 2], f"should stop after page 2, got {client.calls}"


def test_normalize_codal_date_handles_persian_and_arabic_digits():
    assert _normalize_codal_date("۱۴۰۵/۰۵/۰۳") == "1405-05-03"
    assert _normalize_codal_date("١٤٠٥/٠٥/٠٣") == "1405-05-03"  # Arabic-Indic digits
    assert _normalize_codal_date("1405-05-03") == "1405-05-03"
    assert _normalize_codal_date("") == ""
    assert _normalize_codal_date(None) == ""


def asyncio_run(fn, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
    import asyncio

    return asyncio.run(fn(*args, **kwargs))
