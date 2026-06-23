from __future__ import annotations

from core.paths import validate_safe_path


def extract_text_from_pdf(file_path: str) -> list[dict[str, str | None]]:
    """Extract text from each page of a PDF file.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of dicts with 'page' and 'text' keys.
    """
    import pdfplumber

    safe_path = validate_safe_path(file_path)
    pages_text: list[dict[str, str | None]] = []

    with pdfplumber.open(str(safe_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            pages_text.append(
                {
                    "page": page_number,
                    "text": text,
                }
            )

    return pages_text
