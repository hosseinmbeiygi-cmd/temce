from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


class TestPdfParser:
    """Tests for PDF parser function."""

    @pytest.fixture
    def sample_pdf_file(self) -> Path:
        """Create a minimal valid PDF file for testing."""
        # Minimal PDF: just enough to be parsed by pdfplumber
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n"
            b"<< /Type /Catalog /Pages 2 0 R >>\n"
            b"endobj\n"
            b"2 0 obj\n"
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
            b"endobj\n"
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
            b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
            b"endobj\n"
            b"4 0 obj\n"
            b"<< /Length 44 >>\n"
            b"stream\n"
            b"BT /F1 12 Tf 100 700 Td (Hello PDF!) Tj ET\n"
            b"endstream\n"
            b"endobj\n"
            b"5 0 obj\n"
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
            b"endobj\n"
            b"xref\n"
            b"0 6\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000266 00000 n \n"
            b"0000000360 00000 n \n"
            b"trailer\n"
            b"<< /Size 6 /Root 1 0 R >>\n"
            b"startxref\n"
            b"433\n"
            b"%%EOF"
        )

        tmpfile = Path(tempfile.mktemp(suffix=".pdf"))
        tmpfile.write_bytes(pdf_content)
        yield tmpfile
        tmpfile.unlink(missing_ok=True)

    def test_extract_text_from_pdf(self, sample_pdf_file: Path) -> None:
        """extract_text_from_pdf should return a list of pages."""
        from iran_market_data.app.parsers.pdf_parser import extract_text_from_pdf

        pages = extract_text_from_pdf(str(sample_pdf_file))
        assert isinstance(pages, list)
        assert len(pages) >= 1

    def test_extract_text_page_structure(self, sample_pdf_file: Path) -> None:
        """Each page should have 'page' and 'text' keys."""
        from iran_market_data.app.parsers.pdf_parser import extract_text_from_pdf

        pages = extract_text_from_pdf(str(sample_pdf_file))
        page = pages[0]
        assert "page" in page
        assert "text" in page
        assert page["page"] == 1

    def test_extract_text_nonexistent_file(self) -> None:
        """Extracting from a nonexistent file should raise an error."""
        from iran_market_data.app.parsers.pdf_parser import extract_text_from_pdf

        with pytest.raises(Exception):
            extract_text_from_pdf("/nonexistent/file.pdf")

    def test_extract_text_lazy_import(self) -> None:
        """Importing the module should work without pdfplumber installed."""
        import iran_market_data.app.parsers.pdf_parser

        # Just importing should not fail
        assert iran_market_data.app.parsers.pdf_parser.extract_text_from_pdf is not None

