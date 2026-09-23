"""Unit tests for the Codal download & parse service.

Covers:
  - ``CodalDownloadSummary`` defaults
  - ``download_and_import_all`` with zero rows (short-circuit)
  - successful download + parse pipeline
  - URL normalization for relative / bare links
  - download failures and parse errors
  - ``close()`` releasing the http client

Uses a fake AsyncSession and a mocked httpx client — no network or DB.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.codal_download_service import CodalDownloadService, CodalDownloadSummary

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_session(rows: list[tuple[Any, ...]]) -> MagicMock:
    """Build a fake AsyncSession whose execute() returns the given rows."""
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows)
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add_all = MagicMock()
    return session


def _make_row(
    code: str = "12345",
    symbol: str = "فولاد",
    link: str = "",
    link_excel: str = "https://api.brsapi.ir/files/fa.xlsx",
    link_pdf: str = "",
    date_publish: str = "2026-01-15",
    title: str = "گزارش عملکرد ماهانه",
) -> tuple[Any, ...]:
    return (code, symbol, link, link_excel, link_pdf, date_publish, title)


def _make_client(content: bytes = b"<html><tr><td>x</td></tr></html>", error: Exception | None = None) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    if error is not None:
        resp.raise_for_status.side_effect = error
    client = MagicMock()
    client.get = AsyncMock(side_effect=error) if error is not None else AsyncMock(return_value=resp)
    return client


# ── Tests ─────────────────────────────────────────────────────────────────


class TestCodalDownloadSummary:
    def test_defaults(self) -> None:
        summary = CodalDownloadSummary()
        assert summary.total_announcements == 0
        assert summary.downloaded == 0
        assert summary.skipped == 0
        assert summary.failed == 0
        assert summary.parsed == 0
        assert summary.parse_errors == 0
        assert summary.errors == []
        assert summary.elapsed_seconds == 0.0


class TestDownloadAndImportAll:
    @pytest.mark.asyncio
    async def test_no_rows_short_circuits(self, tmp_path) -> None:
        """With zero unprocessed rows the service returns immediately."""
        session = _make_session([])
        service = CodalDownloadService(session, download_dir=str(tmp_path), concurrency=2)

        summary = await service.download_and_import_all(max_announcements=10)

        assert summary.total_announcements == 0
        assert summary.downloaded == 0
        session.commit.assert_not_awaited()
        session.execute.assert_awaited_once()
        assert summary.elapsed_seconds >= 0.0

    @pytest.mark.asyncio
    async def test_downloads_and_parses_all_rows(self, tmp_path) -> None:
        """Every announcement with a link is downloaded, parsed and stored."""
        rows = [
            _make_row(code="1", symbol="فولاد", link_excel="https://api.brsapi.ir/files/fa1.xlsx"),
            _make_row(code="2", symbol="خودرو", link_excel="https://api.brsapi.ir/files/fa2.xlsx"),
        ]
        session = _make_session(rows)
        service = CodalDownloadService(session, download_dir=str(tmp_path), concurrency=2)
        service._http_client = _make_client()

        with (
            patch(
                "services.codal_download_service.parse_report",
                return_value={"title": "گزارش", "table_count": 1, "raw_rows_count": 3, "tables": []},
            ),
            patch(
                "services.codal_download_service._parse_filename",
                return_value={"report_type": "ن-۳۰", "date": "14030101"},
            ),
            patch(
                "services.codal_financial_import_service.CodalFinancialImportService",
                return_value=MagicMock(import_all=AsyncMock(return_value=MagicMock(imported=2, updated=0))),
            ),
        ):
            summary = await service.download_and_import_all(max_announcements=10, batch_size=1)

        assert summary.total_announcements == 2
        assert summary.downloaded == 2
        assert summary.parsed == 2
        assert summary.failed == 0
        # 2 batches (batch_size=1) flushed, then a final commit.
        assert session.flush.await_count == 2
        session.commit.assert_awaited_once()
        # Files should be written under per-symbol directories.
        assert (tmp_path / "فولاد").exists()
        assert (tmp_path / "خودرو").exists()

    @pytest.mark.asyncio
    async def test_normalizes_relative_and_bare_links(self, tmp_path) -> None:
        """Relative links get the BrsApi base prepended; bare links get https://."""
        rows = [
            _make_row(code="1", symbol="فولاد", link_excel="/files/fa1.xlsx"),
            _make_row(code="2", symbol="خودرو", link_excel="codal.ir/files/fa2.xlsx"),
        ]
        session = _make_session(rows)
        service = CodalDownloadService(session, download_dir=str(tmp_path), concurrency=2)
        client = _make_client()
        service._http_client = client

        with (
            patch(
                "services.codal_download_service.parse_report",
                return_value={"title": "t", "table_count": 0, "raw_rows_count": 0, "tables": []},
            ),
            patch("services.codal_download_service._parse_filename", return_value=None),
            patch(
                "services.codal_financial_import_service.CodalFinancialImportService",
                return_value=MagicMock(import_all=AsyncMock(return_value=MagicMock(imported=0, updated=0))),
            ),
        ):
            summary = await service.download_and_import_all(max_announcements=10)

        assert summary.downloaded == 2
        called_urls = [call.args[0] for call in client.get.await_args_list]
        assert "https://api.brsapi.ir/files/fa1.xlsx" in called_urls
        assert "https://codal.ir/files/fa2.xlsx" in called_urls

    @pytest.mark.asyncio
    async def test_download_failure_counts_and_records_error(self, tmp_path) -> None:
        """Failed downloads are tallied and appended to summary.errors."""
        rows = [_make_row(code="1", symbol="فولاد")]
        session = _make_session(rows)
        service = CodalDownloadService(session, download_dir=str(tmp_path), concurrency=2)
        service._http_client = _make_client(error=RuntimeError("connection reset"))

        summary = await service.download_and_import_all(max_announcements=10)

        assert summary.total_announcements == 1
        assert summary.downloaded == 0
        assert summary.failed == 1
        assert summary.errors and "connection reset" in summary.errors[0]

    @pytest.mark.asyncio
    async def test_already_downloaded_file_skips_network(self, tmp_path) -> None:
        """A file already on disk (>100 bytes) counts as downloaded without hitting the network."""
        rows = [_make_row(code="1", symbol="فولاد", date_publish="2026-01-15")]
        session = _make_session(rows)
        service = CodalDownloadService(session, download_dir=str(tmp_path), concurrency=2)
        client = _make_client()
        service._http_client = client

        # Pre-create the exact file path the service would use.
        # (Filename format after the C2 fix includes a sha1-digest of the link.)
        sym_dir = tmp_path / "فولاد"
        sym_dir.mkdir(parents=True, exist_ok=True)
        import hashlib as _hashlib

        raw_link = "https://api.brsapi.ir/files/fa.xlsx"  # default _make_row excel link
        digest = _hashlib.sha1(raw_link.encode("utf-8")).hexdigest()[:8]
        existing = sym_dir / f"فولاد_codal_2026-01-15_{digest}.xlsx"
        existing.write_bytes(b"x" * 200)  # > 100 bytes

        with (
            patch(
                "services.codal_download_service.parse_report",
                return_value={"title": "t", "table_count": 1, "raw_rows_count": 3, "tables": []},
            ),
            patch(
                "services.codal_download_service._parse_filename",
                return_value={"report_type": "ن-۳۰", "date": "14030101"},
            ),
            patch(
                "services.codal_financial_import_service.CodalFinancialImportService",
                return_value=MagicMock(import_all=AsyncMock(return_value=MagicMock(imported=1, updated=0))),
            ),
        ):
            summary = await service.download_and_import_all(max_announcements=10)

        assert summary.downloaded == 1  # "exists" is counted as downloaded
        assert summary.parsed == 1
        assert summary.failed == 0
        client.get.assert_not_awaited()  # no network call for existing files

    @pytest.mark.asyncio
    async def test_parse_error_counts_separately(self, tmp_path) -> None:
        """A downloaded file that fails to parse increments parse_errors."""
        rows = [_make_row(code="1", symbol="فولاد")]
        session = _make_session(rows)
        service = CodalDownloadService(session, download_dir=str(tmp_path), concurrency=2)
        service._http_client = _make_client()

        with (
            patch(
                "services.codal_download_service.parse_report",
                return_value={"error": "Failed to read file"},
            ),
            patch("services.codal_download_service._parse_filename", return_value=None),
            patch(
                "services.codal_financial_import_service.CodalFinancialImportService",
                return_value=MagicMock(import_all=AsyncMock(return_value=MagicMock(imported=0, updated=0))),
            ),
        ):
            summary = await service.download_and_import_all(max_announcements=10)

        assert summary.downloaded == 1
        assert summary.parsed == 0
        assert summary.parse_errors == 1
        assert summary.errors and "parse error" in summary.errors[0]


class TestClose:
    @pytest.mark.asyncio
    async def test_close_releases_http_client(self) -> None:
        session = _make_session([])
        service = CodalDownloadService(session, download_dir=".", concurrency=1)
        client = MagicMock()
        client.aclose = AsyncMock()
        service._http_client = client

        await service.close()

        client.aclose.assert_awaited_once()
        assert service._http_client is None
