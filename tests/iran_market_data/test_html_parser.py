from __future__ import annotations

from iran_market_data.app.parsers.html_parser import (
    extract_links,
    parse_tables_with_pandas,
)


class TestParseTables:
    """Tests for parse_tables_with_pandas function."""

    def test_parse_simple_html_table(self, sample_html_with_table: str) -> None:
        """parse_tables_with_pandas should find tables in HTML."""
        tables = parse_tables_with_pandas(sample_html_with_table)
        assert len(tables) >= 1

    def test_parse_table_columns(self, sample_html_with_table: str) -> None:
        """Parsed table should have correct columns."""
        tables = parse_tables_with_pandas(sample_html_with_table)
        table = tables[0]
        assert "Symbol" in table.columns or "symbol" in table.columns
        assert "Price" in table.columns or "price" in table.columns

    def test_parse_table_data(self, sample_html_with_table: str) -> None:
        """Parsed table should contain the expected data."""
        tables = parse_tables_with_pandas(sample_html_with_table)
        table = tables[0]

        # Convert to string representation for easier checking
        rows_str = table.to_string()
        assert "فولاد" in rows_str
        assert "فملی" in rows_str

    def test_parse_empty_html(self) -> None:
        """Empty HTML should return empty list or raise."""
        try:
            tables = parse_tables_with_pandas("<html><body></body></html>")
            assert len(tables) == 0
        except ValueError:
            # pandas.read_html may raise for no tables
            pass


class TestExtractLinks:
    """Tests for extract_links function."""

    def test_extract_all_links(self, sample_html_with_links: str) -> None:
        """extract_links should find all anchor tags with href."""
        links = extract_links(sample_html_with_links)
        # 3 links: /page1, /page2, https://example.com/file.pdf
        assert len(links) >= 2

    def test_extract_link_text(self, sample_html_with_links: str) -> None:
        """Extracted links should include text."""
        links = extract_links(sample_html_with_links)
        texts = [link["text"] for link in links]
        assert "Page 1" in texts
        assert "Page 2" in texts

    def test_extract_link_href(self, sample_html_with_links: str) -> None:
        """Extracted links should include href."""
        links = extract_links(sample_html_with_links)
        hrefs = [link["href"] for link in links]
        assert "/page1" in hrefs
        assert "/page2" in hrefs

    def test_extract_links_no_href_skipped(self) -> None:
        """Anchor tags without href should be skipped."""
        html = '<a>No href</a><a href="/valid">Valid</a>'
        links = extract_links(html)
        assert len(links) == 1
        assert links[0]["href"] == "/valid"

    def test_extract_links_empty_html(self) -> None:
        """Empty HTML should return empty list."""
        links = extract_links("")
        assert links == []

    def test_extract_links_custom_selector(self) -> None:
        """Custom CSS selector should work."""
        html = '<div class="link"><a href="/a">A</a></div><span class="link"><a href="/b">B</a></span>'
        links = extract_links(html, selector=".link a")
        assert len(links) == 2

    def test_extract_links_with_file_links(self, sample_html_with_table: str) -> None:
        """Links with file extensions should be extractable."""
        links = extract_links(sample_html_with_table)
        hrefs = [link["href"] for link in links]
        assert any("report.pdf" in h for h in hrefs)
        assert any("data.xlsx" in h for h in hrefs)
