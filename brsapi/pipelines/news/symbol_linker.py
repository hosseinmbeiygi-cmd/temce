from __future__ import annotations

from typing import Any


class NewsSymbolLinker:
    """Linker for extracting and linking market symbols from news articles.

    Unused by the live pipeline (nothing imports it) and kept only for
    interface compatibility: the working implementation is
    ``providers.news.parser.NewsParser.extract_symbols``, which resolves
    against the static catalog. Its own 8-symbol candidate set was removed —
    wire this to the catalog-backed extractor, never back to a hard-coded
    list, or it will under-tag and mis-tag news again.
    """

    def extract_symbols(self, text: str) -> list[str]:
        from providers.news.parser import NewsParser

        return NewsParser().extract_symbols(text)

    def link_symbols(self, article: dict[str, Any]) -> dict[str, Any]:
        result = dict(article)
        text = f"{article.get('title', '')} {article.get('content', '')}"
        symbols = self.extract_symbols(text)
        result["symbols"] = symbols
        return result

    def batch_link(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.link_symbols(a) for a in articles]
