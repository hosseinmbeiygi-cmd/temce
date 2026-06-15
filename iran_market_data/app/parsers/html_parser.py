from __future__ import annotations

import pandas as pd
from bs4 import BeautifulSoup


def parse_tables_with_pandas(url_or_html: str) -> list[pd.DataFrame]:
    """Parse HTML tables using pandas read_html.

    Args:
        url_or_html: URL or HTML string containing tables.

    Returns:
        List of DataFrames, one per table found.
    """
    tables = pd.read_html(url_or_html)
    return tables


def extract_links(html: str, selector: str = "a") -> list[dict[str, str]]:
    """Extract links from HTML using a CSS selector.

    Args:
        html: HTML content to parse.
        selector: CSS selector for link elements.

    Returns:
        List of dicts with 'text' and 'href' keys.
    """
    soup = BeautifulSoup(html, "lxml")

    links: list[dict[str, str]] = []

    for a in soup.select(selector):
        href = a.get("href")
        text = a.get_text(strip=True)

        if href:
            links.append(
                {
                    "text": text,
                    "href": href,
                }
            )

    return links
