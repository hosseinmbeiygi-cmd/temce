"""Unit tests for POST /api/v1/instruments/import.

Covers five scenarios end-to-end through the FastAPI app:

1. Happy-path CSV (parsed count, parsed rows committed, no errors).
2. CSV whose header lacks the required ``symbol`` column.
3. CSV whose rows have non-numeric values in numeric columns.
4. Uploads that exceed ``MAX_UPLOAD_BYTES`` (10 MB).
5. Server-error envelope — any uncaught ``Exception`` is converted into a
   clean JSON ``ApiResponse`` with ``success=False`` instead of a 500 stack.

The tests monkeypatch ``InstrumentRepository.save`` so the parsed-row
verification does not depend on whether the test harness actually persists
data (the project's in-memory SQLite setup uses ``NullPool``, which can cause
"no such table: instruments" on later connections of a fresh ``:memory:``).
The parsing logic of ``InstrumentImportService`` is what we primarily want to
cover here; persistence regression is locked in by repository-level tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Mirror tests/unit/test_backend_api.py so module imports resolve identically.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from apps.api.app import app
from apps.api.endpoints.symbols import MAX_UPLOAD_BYTES
from core.result import Result
from repositories.instrument_repository import InstrumentRepository
from services.instrument_import_service import InstrumentImportService


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """HTTPX client wrapping the FastAPI ASGI app — mirrors the existing
    pattern from ``tests/unit/test_backend_api.py``."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _stub_db_save(monkeypatch: pytest.MonkeyPatch):
    """Stub ``InstrumentRepository.save`` so the import endpoint can parse
    and "commit" rows without the test harness needing a multi-connection
    in-memory database. Validates parser/service logic; persistence
    correctness is covered by repository-level integration tests."""
    async def _fake_save(self, entity):
        return Result.ok(entity)

    monkeypatch.setattr(InstrumentRepository, "save", _fake_save)


# ────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_csv_happy_path(client: AsyncClient):
    """1. A small but realistic CSV is parsed, all rows commit, no errors."""
    csv_bytes = (
        "symbol,name,isin,group_code\n"
        "فولاد,Foolad,IRO1FOLD0001,01\n"
        "فملی,Melal,IRO1FMLI0001,01\n"
        "وبملت,BankMellat,IRO1BANK0001,02\n"
    ).encode("utf-8")

    resp = await client.post(
        "/api/v1/instruments/import",
        files={"file": ("symbols.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is True
    assert body["data"]["filename"] == "symbols.csv"
    assert body["data"]["total_rows"] == 3
    assert body["data"]["imported"] == 3
    assert body["data"]["parse_errors"] == []
    assert body["data"]["import_errors"] == []


@pytest.mark.asyncio
async def test_import_csv_missing_symbol_column(client: AsyncClient):
    """2. A CSV whose header doesn't include ``symbol`` returns a friendly
    error in the ``ApiResponse`` envelope."""
    csv_bytes = "name,isin\nFoo,ISIN1\nBar,ISIN2\n".encode("utf-8")

    resp = await client.post(
        "/api/v1/instruments/import",
        files={"file": ("symbols.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is False
    assert "symbol" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_import_csv_malformed_rows(client: AsyncClient):
    """3. Rows with non-numeric values in numeric columns are reported as
    parse errors; the endpoint still returns 200 with a fully populated
    summary so callers can act on each error individually."""
    csv_bytes = (
        "symbol,lot_size,par_value\n"
        "GOOD,100,1000\n"          # valid
        "BAD,bad,2000\n"          # lot_size not numeric
        "BAD2,200,worse\n"        # par_value not numeric
    ).encode("utf-8")

    resp = await client.post(
        "/api/v1/instruments/import",
        files={"file": ("symbols.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["total_rows"] == 3
    assert data["imported"] == 1            # only the "GOOD" row commits
    assert data["import_errors"] == []
    assert len(data["parse_errors"]) == 2
    assert any("lot_size" in e for e in data["parse_errors"])
    assert any("par_value" in e for e in data["parse_errors"])
    # Errors carry row markers so callers can pinpoint where to look.
    assert all("Row" in e for e in data["parse_errors"])


@pytest.mark.asyncio
async def test_import_over_size_file_rejected(client: AsyncClient):
    """4. A file one byte over the limit is rejected before any parsing
    happens; the response is a clean ApiResponse error envelope."""
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)

    resp = await client.post(
        "/api/v1/instruments/import",
        files={"file": ("symbols.csv", oversized, "text/csv")},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is False
    assert "too large" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_import_server_error_envelope(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """5. Any uncaught ``Exception`` raised by the import service is
    wrapped into a 200 ``ApiResponse`` with ``success=False`` — never a
    raw 500 stack — so the front-end can surface the real cause."""
    async def _fake_import_from_bytes(self, filename, content, *, max_errors=50):
        raise RuntimeError("boom from inside the service")

    monkeypatch.setattr(
        InstrumentImportService, "import_from_bytes", _fake_import_from_bytes
    )

    csv_bytes = b"symbol\nفولاد\nفملی\n"
    resp = await client.post(
        "/api/v1/instruments/import",
        files={"file": ("symbols.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is False
    msg = body["error"]["message"]
    assert "Server error" in msg
    assert "boom from inside the service" in msg
