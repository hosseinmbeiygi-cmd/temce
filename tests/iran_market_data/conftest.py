from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_persian_text() -> str:
    return "متن فارسی با ي و ك و ۱۲۳۴۵"


@pytest.fixture
def sample_html_with_table() -> str:
    return """
    <html>
    <body>
        <table>
            <tr><th>Symbol</th><th>Price</th></tr>
            <tr><td>فولاد</td><td>15000</td></tr>
            <tr><td>فملی</td><td>25000</td></tr>
        </table>
        <a href="https://example.com/report.pdf">Download Report</a>
        <a href="https://example.com/data.xlsx">Download Excel</a>
        <a>no href</a>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_with_links() -> str:
    return """
    <html>
    <body>
        <a href="/page1">Page 1</a>
        <a href="/page2">Page 2</a>
        <a href="https://example.com/file.pdf">PDF File</a>
        <span>Not a link</span>
    </body>
    </html>
    """


@pytest.fixture
def sample_json_data() -> dict[str, Any]:
    return {
        "symbol": "فولاد",
        "price": 15000,
        "volume": 5000000,
    }


@pytest.fixture
def temp_raw_storage() -> Any:
    """Create a RawStorage with a temporary directory."""
    from iran_market_data.app.storage.raw_storage import RawStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = RawStorage(base_dir=str(Path(tmpdir) / "raw"))
        yield storage

