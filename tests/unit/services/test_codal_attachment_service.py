"""Unit tests for the Codal attachment download service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.codal import CodalAttachmentModel
from core.exceptions import NotFoundError
from core.result import Result
from services.codal_attachment_service import CodalAttachmentDownloadService


@pytest.fixture
def session() -> AsyncSession:
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def service(session: AsyncSession) -> CodalAttachmentDownloadService:
    # Audit fix (C8): session.merge is an ASYNC method on AsyncSession — a
    # MagicMock returned the row synchronously, so `await session.merge(row)`
    # raised TypeError and the empty-response branch was never reached.
    session.merge = AsyncMock(side_effect=lambda row: row)  # type: ignore[method-assign]
    return CodalAttachmentDownloadService(session)


class TestHelpers:
    def test_extension_for_known_types(self, service: CodalAttachmentDownloadService) -> None:
        assert service._extension_for("pdf", "application/pdf") == ".pdf"
        assert service._extension_for("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == ".xlsx"
        assert service._extension_for("html", "text/html") == ".html"
        assert service._extension_for("other", "application/octet-stream") == ".bin"

    def test_guess_mime(self, service: CodalAttachmentDownloadService) -> None:
        assert service._guess_mime("http://x/file.pdf") == "application/pdf"
        assert service._guess_mime("http://x/file.xlsx") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert service._guess_mime("http://x/file.html") == "text/html"
        assert service._guess_mime("http://x/file.bin") == "application/octet-stream"

    def test_make_key(self, service: CodalAttachmentDownloadService) -> None:
        from brsapi.models.codal import CodalAttachmentModel

        row = CodalAttachmentModel(
            id=1,
            announcement_id=10,
            symbol="فولاد",
            code="12345",
            attachment_type="pdf",
        )
        key = service._make_key(row, "application/pdf")
        assert key.startswith("codal/فولاد/12345_pdf")
        assert key.endswith(".pdf")


class TestDownloadOne:
    @pytest.mark.asyncio
    async def test_missing_url_returns_false(self, service: CodalAttachmentDownloadService) -> None:
        from brsapi.models.codal import CodalAttachmentModel

        row = CodalAttachmentModel(
            id=1,
            announcement_id=10,
            symbol="فولاد",
            code="12345",
            attachment_type="pdf",
        )
        row.status = "pending"
        result = await service._download_one(row)
        assert result is False
        assert row.status == "error"

    @pytest.mark.asyncio
    async def test_empty_response_returns_false(self, service: CodalAttachmentDownloadService) -> None:
        from brsapi.models.codal import CodalAttachmentModel

        row = CodalAttachmentModel(
            id=1,
            announcement_id=10,
            symbol="فولاد",
            code="12345",
            attachment_type="pdf",
            source_url="http://x/file.pdf",
        )
        row.status = "pending"

        # Mock httpx client to return empty content
        mock_resp = MagicMock()
        mock_resp.content = b""
        mock_resp.headers = {}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        service._http_client = mock_client

        result = await service._download_one(row)
        assert result is False
        assert row.status == "error"


class _FakeS3:
    def __init__(
        self,
        read_result: Result[bytes] | None = None,
        write_result: Result[str] | None = None,
    ) -> None:
        self.read_result = read_result if read_result is not None else Result.ok(b"")
        self.write_result = write_result if write_result is not None else Result.ok("key")
        self.read_calls: list[str] = []
        self.write_calls: list[tuple[str, bytes, str]] = []
        self.closed = False

    async def read(self, key: str) -> Result[bytes]:
        self.read_calls.append(key)
        return self.read_result

    async def write(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Result[str]:
        self.write_calls.append((key, data, content_type))
        return self.write_result

    async def close(self) -> None:
        self.closed = True


def _s3_row(**overrides: object) -> CodalAttachmentModel:
    values: dict[str, object] = {
        "id": 1,
        "announcement_id": 10,
        "symbol": "فولاد",
        "code": "12345",
        "attachment_type": "pdf",
        "storage_type": "s3",
        "storage_path": "codal/فولاد/12345_pdf.pdf",
        "status": "done",
    }
    values.update(overrides)
    return CodalAttachmentModel(**values)


@pytest.fixture
def s3_service(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> CodalAttachmentDownloadService:
    session.merge = AsyncMock(side_effect=lambda row: row)  # type: ignore[method-assign]
    monkeypatch.setattr(
        "services.codal_attachment_service.data_path",
        lambda *args, **kwargs: tmp_path,
    )
    return CodalAttachmentDownloadService(session, storage_type="s3")


class TestS3Backend:
    @pytest.mark.asyncio
    async def test_persist_writes_to_s3(self, s3_service: CodalAttachmentDownloadService) -> None:
        fake = _FakeS3()
        s3_service._s3_storage = fake
        s3_service._write_local = AsyncMock(  # type: ignore[method-assign]
            side_effect=AssertionError("must not write local")
        )

        key = await s3_service._persist(_s3_row(), b"abc", "application/pdf")

        assert key == "codal/فولاد/12345_pdf.pdf"
        assert fake.write_calls == [(key, b"abc", "application/pdf")]

    @pytest.mark.asyncio
    async def test_persist_failure_surfaces_code(self, s3_service: CodalAttachmentDownloadService) -> None:
        s3_service._s3_storage = _FakeS3(write_result=Result.fail("denied", code="forbidden"))

        with pytest.raises(RuntimeError, match="forbidden"):
            await s3_service._persist(_s3_row(), b"abc", "application/pdf")

    @pytest.mark.asyncio
    async def test_content_reads_from_s3(self, s3_service: CodalAttachmentDownloadService) -> None:
        s3_service._s3_storage = _FakeS3(read_result=Result.ok(b"xyz"))
        assert await s3_service.get_attachment_content(_s3_row()) == b"xyz"

    @pytest.mark.asyncio
    async def test_content_falls_back_to_legacy_local_copy(
        self, s3_service: CodalAttachmentDownloadService, tmp_path: Path
    ) -> None:
        legacy = tmp_path / "codal/فولاد/12345_pdf.pdf"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"legacy")
        s3_service._s3_storage = _FakeS3(read_result=Result.fail("missing", code="not_found"))

        assert await s3_service.get_attachment_content(_s3_row()) == b"legacy"

    @pytest.mark.asyncio
    async def test_content_missing_without_legacy_returns_empty(
        self, s3_service: CodalAttachmentDownloadService
    ) -> None:
        s3_service._s3_storage = _FakeS3(read_result=Result.fail("missing", code="not_found"))
        assert await s3_service.get_attachment_content(_s3_row()) == b""

    @pytest.mark.asyncio
    async def test_stream_reads_from_s3(self, s3_service: CodalAttachmentDownloadService) -> None:
        s3_service._s3_storage = _FakeS3(read_result=Result.ok(b"xyz"))
        iterator = await s3_service.get_attachment_stream(_s3_row())
        assert [chunk async for chunk in iterator] == [b"xyz"]

    @pytest.mark.asyncio
    async def test_stream_missing_raises_not_found(self, s3_service: CodalAttachmentDownloadService) -> None:
        s3_service._s3_storage = _FakeS3(read_result=Result.fail("missing", code="not_found"))
        with pytest.raises(NotFoundError):
            await s3_service.get_attachment_stream(_s3_row())

    @pytest.mark.asyncio
    async def test_stream_timeout_degrades_to_empty(self, s3_service: CodalAttachmentDownloadService) -> None:
        s3_service._s3_storage = _FakeS3(read_result=Result.fail("timed out", code="timeout"))
        iterator = await s3_service.get_attachment_stream(_s3_row())
        assert [chunk async for chunk in iterator] == [b""]

    @pytest.mark.asyncio
    async def test_close_releases_s3_client(self, s3_service: CodalAttachmentDownloadService) -> None:
        fake = _FakeS3()
        s3_service._s3_storage = fake
        await s3_service.close()
        assert fake.closed is True
