"""Multipart upload filenames must never traverse the filesystem.

The three file-upload endpoints accept a client-supplied multipart filename:

* ``POST /api/v1/quotes/import-bulk`` and ``POST /api/v1/codal/import-bulk``
  derive the target symbol from the filename stem.
* ``POST /api/v1/symbols/import`` uses the filename's suffix for its
  allow-list (the symbol itself comes from the file content).

A filename such as ``../../etc/passwd.csv`` must therefore collapse to a single
path component (``passwd``) before it reaches an importer, a log line or any
storage layer — and an unsupported extension must stay rejected no matter how
many directory segments the filename carries.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.typing import Result

AUTH = {"Authorization": "Bearer test-token"}

# (client-supplied multipart filename, expected derived symbol)
TRAVERSAL_NAMES = [
    ("../../etc/passwd.csv", "passwd"),
    ("..\\..\\windows\\system32\\evil.csv", "evil"),
    ("/tmp/evil.csv", "evil"),
    ("....//....//etc/passwd.csv", "passwd"),
    ("./nested/../فولاد.csv", "فولاد"),
]


class _FakeSession:
    """Stand-in for ``async_session_factory()``: no real database is touched."""

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _RecordingImportService:
    """Captures the symbol/filename each upload endpoint passes to the importer."""

    calls: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    async def import_from_bytes(
        self,
        *,
        symbol: str,
        content: bytes,
        filename: str,
        data_source: str,
    ) -> Result[dict[str, Any]]:
        type(self).calls.append(
            {
                "symbol": symbol,
                "filename": filename,
                "size": len(content),
                "data_source": data_source,
            }
        )
        return Result.ok({"total_rows": 1, "imported": 1, "updated": 0})


class _QuoteRecorder(_RecordingImportService):
    calls: list[dict[str, Any]] = []


class _CodalRecorder(_RecordingImportService):
    calls: list[dict[str, Any]] = []


@pytest.fixture(autouse=True)
def _reset_recorders() -> None:
    _QuoteRecorder.calls.clear()
    _CodalRecorder.calls.clear()


@pytest.fixture
def no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the endpoints open a session object without a live PostgreSQL.

    The upload handlers import ``async_session_factory`` inside the function
    body, so patching the attribute on ``core.database`` is picked up at call
    time. ``raising=True`` keeps the fixture honest: if that import style ever
    changes, the test fails loudly instead of silently hitting the real DB.
    """
    import core.database as db

    monkeypatch.setattr(db, "async_session_factory", lambda: _FakeSession())


def _assert_single_component(symbol: str) -> None:
    """The one security property: a derived symbol is never a path."""
    assert symbol
    assert "/" not in symbol and "\\" not in symbol
    assert Path(symbol).name == symbol
    assert symbol not in {".", ".."}


@pytest.mark.parametrize(("filename", "expected"), TRAVERSAL_NAMES)
async def test_quotes_import_derives_single_component_symbol(
    admin_client: Any,
    no_db: None,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    expected: str,
) -> None:
    import apps.api.endpoints.quotes as quotes_module

    # quotes.py binds QuoteImportService at module import time, so the
    # endpoint's own module attribute is the patch target.
    monkeypatch.setattr(quotes_module, "QuoteImportService", _QuoteRecorder)

    res = await admin_client.post(
        "/api/v1/quotes/import-bulk",
        files=[("files", (filename, b"date,close\n2024-01-01,10\n", "text/csv"))],
        headers=AUTH,
    )

    assert res.status_code == 200, res.text
    assert len(_QuoteRecorder.calls) == 1
    symbol = _QuoteRecorder.calls[0]["symbol"]
    assert symbol == expected
    _assert_single_component(symbol)


@pytest.mark.parametrize(("filename", "expected"), TRAVERSAL_NAMES)
async def test_codal_import_derives_single_component_symbol(
    admin_client: Any,
    no_db: None,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    expected: str,
) -> None:
    import services.codal_import_service as codal_module

    monkeypatch.setattr(codal_module, "CodalImportService", _CodalRecorder)

    res = await admin_client.post(
        "/api/v1/codal/import-bulk",
        files=[
            (
                "files",
                (filename, "symbol,date,title\nفولاد,2024-01-01,x\n".encode(), "text/csv"),
            )
        ],
        headers=AUTH,
    )

    assert res.status_code == 200, res.text
    assert len(_CodalRecorder.calls) == 1
    symbol = _CodalRecorder.calls[0]["symbol"]
    assert symbol == expected
    _assert_single_component(symbol)


async def test_persian_filename_still_works(
    admin_client: Any, no_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import apps.api.endpoints.quotes as quotes_module

    monkeypatch.setattr(quotes_module, "QuoteImportService", _QuoteRecorder)

    res = await admin_client.post(
        "/api/v1/quotes/import-bulk",
        files=[("files", ("فولاد.csv", b"date,close\n2024-01-01,10\n", "text/csv"))],
        headers=AUTH,
    )

    assert res.status_code == 200, res.text
    assert _QuoteRecorder.calls[0]["symbol"] == "فولاد"


async def test_symbols_import_rejects_traversal_filename_with_bad_extension(
    app: Any,
    admin_client: Any,
) -> None:
    """The suffix allow-list runs before any importer or database work.

    ``get_instrument_import_service`` opens a DB session while FastAPI resolves
    dependencies, so it is overridden here: the rejection must not depend on a
    live database, and the importer must never be constructed for a bad suffix.
    """
    from apps.api.dependencies import get_instrument_import_service

    called: list[str] = []

    class _StubImporter:
        async def import_from_bytes(self, filename: str, content: bytes) -> Result[Any]:
            called.append(filename)
            raise AssertionError("importer must not run for an unsupported extension")

    app.dependency_overrides[get_instrument_import_service] = _StubImporter

    res = await admin_client.post(
        "/api/v1/instruments/import",
        files=[("file", ("../../etc/passwd.exe", b"MZ", "application/octet-stream"))],
        headers=AUTH,
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is False
    assert "Unsupported file extension" in body["error"]["message"]
    assert called == []


async def test_symbols_import_accepts_traversal_filename_without_writing_outside(
    app: Any,
    admin_client: Any,
) -> None:
    """The endpoint parses the bytes; the filename is only used for its suffix."""
    from apps.api.dependencies import get_instrument_import_service

    seen: list[tuple[str, int]] = []

    class _FakeImporter:
        async def import_from_bytes(self, filename: str, content: bytes) -> Result[Any]:
            seen.append((filename, len(content)))
            return Result.ok(
                SimpleNamespace(
                    total_rows=1,
                    imported=1,
                    parse_errors=[],
                    import_errors=[],
                )
            )

    app.dependency_overrides[get_instrument_import_service] = lambda: _FakeImporter()

    res = await admin_client.post(
        "/api/v1/instruments/import",
        files=[
            (
                "file",
                ("../../etc/passwd.csv", "symbol,name\nفولاد,فولاد مبارکه\n".encode(), "text/csv"),
            )
        ],
        headers=AUTH,
    )

    assert res.status_code == 200, res.text
    assert res.json()["success"] is True
    # Nothing is written to disk, and the raw filename is never turned into a path.
    assert seen and seen[0][1] > 0
    assert not Path("../../etc/passwd.csv").exists()
    assert not Path("passwd.csv").exists()
