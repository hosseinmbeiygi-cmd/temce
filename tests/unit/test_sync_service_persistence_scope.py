"""Persistence-scope tests for ``BrsApiSyncService.sync``.

Pins down two dangerous behaviours found in the audit:

1. A "full refresh" must be scoped when the payload only covers one slice
   (one symbol). A bare ``TRUNCATE`` deletes every other slice.
2. A failed insert rolls the transaction back, so the error log must report
   ``items_count=0`` (persisted rows), not the number of attempted rows.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from brsapi.models.tsetmc import SymbolSnapshotModel
from brsapi.services import sync_service as sync_service_module
from brsapi.services.sync_service import BrsApiSyncService

ENDPOINT = SimpleNamespace(path="/Test/Endpoint.php", category=SimpleNamespace(value="test"))


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeClient:
    def __init__(self, data) -> None:
        self.data = data

    async def fetch(self, endpoint, params=None, category_override=None):
        return SimpleNamespace(
            success=True,
            value=SimpleNamespace(
                is_empty=not self.data,
                data=self.data,
                raw_bytes=None,
                status_code=200,
            ),
        )


def _records(n: int):
    return [
        {"symbol": f"S{i}", "fetched_at": datetime(2026, 10, 28, 9, 30, 0), "price_last": float(i)}
        for i in range(n)
    ]


async def test_scoped_refresh_deletes_only_the_filtered_slice(monkeypatch) -> None:
    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient(_records(1)), session=session)
    calls: dict[str, list] = {"delete": [], "truncate": [], "insert": []}

    async def fake_delete(self, column, value):
        calls["delete"].append((column, value))
        return 1

    async def fake_truncate(self):
        calls["truncate"].append(True)

    async def fake_bulk(self, records, **kwargs):
        calls["insert"].append(len(records))
        return len(records)

    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "delete_where", fake_delete)
    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "truncate", fake_truncate)
    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "bulk_insert", fake_bulk)

    report = await service.sync(
        ENDPOINT,
        parser=lambda data: data,
        model_class=SymbolSnapshotModel,
        truncate_first=True,
        replace_filter={"symbol": "S0"},
        session=session,
    )

    assert report.success is True
    assert calls["delete"] == [("symbol", "S0")]
    assert calls["truncate"] == []
    assert calls["insert"] == [1]


async def test_multi_key_or_empty_replace_filter_never_truncates(monkeypatch) -> None:
    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient(_records(1)), session=session)
    calls: list[tuple[str, object]] = []

    async def fake_delete(self, column, value):
        calls.append(("delete", (column, value)))
        return 0

    async def fake_truncate(self):
        calls.append(("truncate", None))

    async def fake_bulk(self, records, **kwargs):
        calls.append(("insert", len(records)))
        return len(records)

    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "delete_where", fake_delete)
    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "truncate", fake_truncate)
    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "bulk_insert", fake_bulk)

    for bad_filter in ({"symbol": "S0", "ins_id": "1"}, {}):
        with pytest.raises(ValueError, match="replace_filter"):
            await service.sync(
                ENDPOINT,
                parser=lambda data: data,
                model_class=SymbolSnapshotModel,
                truncate_first=True,
                replace_filter=bad_filter,
                session=session,
            )
    assert calls == []


async def test_snapshot_sync_invalidates_market_aggregate_cache(monkeypatch) -> None:
    import core.agg_invalidation as agg_invalidation

    calls: list[str] = []

    async def fake_publish(token: str) -> None:
        calls.append(token)

    monkeypatch.setattr(agg_invalidation, "publish_agg_token", fake_publish)

    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient(_records(2)), session=session)

    async def fake_bulk(self, records, **kwargs):
        return len(records)

    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "bulk_insert", fake_bulk)

    report = await service.sync(
        ENDPOINT,
        parser=lambda data: data,
        model_class=SymbolSnapshotModel,
        session=session,
    )

    assert report.success is True
    assert len(calls) == 1


async def test_non_snapshot_sync_does_not_invalidate_market_cache(monkeypatch) -> None:
    import core.agg_invalidation as agg_invalidation
    from brsapi.models.tsetmc import IndexValueModel

    calls: list[str] = []

    async def fake_publish(token: str) -> None:
        calls.append(token)

    monkeypatch.setattr(agg_invalidation, "publish_agg_token", fake_publish)

    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient(_records(1)), session=session)

    async def fake_bulk(self, records, **kwargs):
        return len(records)

    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "bulk_insert", fake_bulk)

    await service.sync(
        ENDPOINT,
        parser=lambda data: data,
        model_class=IndexValueModel,
        session=session,
    )

    assert calls == []


async def test_gold_pro_replaces_each_section_without_truncate(monkeypatch) -> None:
    session = FakeSession()
    data = {
        "data": {
            "gold": [{"symbol": "G", "price": 1}],
            "currency": [{"symbol": "C", "price": 2}],
            "cryptocurrency": [{"name": "Bitcoin", "symbol": "BTC", "price": 3}],
        }
    }
    service = BrsApiSyncService(client=FakeClient(data), session=session)
    calls: dict[str, list] = {"delete": [], "truncate": [], "insert": []}

    async def fake_delete(self, column, value):
        calls["delete"].append((column, value))
        return 0

    async def fake_truncate(self):
        calls["truncate"].append(True)

    async def fake_bulk(self, records, **kwargs):
        calls["insert"].append(len(records))
        return len(records)

    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "delete_where", fake_delete)
    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "truncate", fake_truncate)
    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "bulk_insert", fake_bulk)

    reports = await service.sync_gold_currency_pro(session)

    assert [r.success for r in reports] == [True, True, True]
    assert calls["delete"] == [
        ("section", "gold"),
        ("section", "currency"),
        ("section", "cryptocurrency"),
    ]
    assert calls["truncate"] == []
    # One commit per section + the final commit in the method.
    assert session.commits >= 4


async def test_partial_batch_failure_rolls_back_and_reports_zero_persisted(monkeypatch) -> None:
    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient(_records(5)), session=session)
    batches = 0

    async def flaky_bulk(self, records, **kwargs):
        nonlocal batches
        batches += 1
        if batches == 1:
            return len(records)
        raise RuntimeError("insert failed")

    monkeypatch.setattr(sync_service_module.BulkUpsertRepository, "bulk_insert", flaky_bulk)

    report = await service.sync(
        ENDPOINT,
        parser=lambda data: data,
        model_class=SymbolSnapshotModel,
        batch_size=2,
        session=session,
    )

    assert report.success is False
    assert session.rollbacks == 1
    log = session.added[-1]
    assert log.status == "error"
    assert log.items_count == 0
    assert "5 attempted rows" in log.error_message
    assert "rolled back" in log.error_message


async def test_empty_response_is_committed_so_dedup_sees_it() -> None:
    session = FakeSession()
    service = BrsApiSyncService(client=FakeClient([]), session=session)

    report = await service.sync(
        ENDPOINT,
        parser=lambda data: data,
        model_class=SymbolSnapshotModel,
        session=session,
    )

    assert report.success is True
    assert report.items_count == 0
    assert session.commits == 1
    assert session.added[-1].status == "success"
