"""Unit tests for the Codal attachment download service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.codal_attachment_service import CodalAttachmentDownloadService


@pytest.fixture
def session() -> AsyncSession:
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def service(session: AsyncSession) -> CodalAttachmentDownloadService:
    # Mock merge to return the same row so tests can observe status changes.
    session.merge = MagicMock(side_effect=lambda row: row)
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
