from __future__ import annotations

from typing import Any


class NewsSymbolLinker:
    """Linker for extracting and linking market symbols from news articles."""

    def __init__(self) -> None:
        self._known_symbols = {"فولاد", "فملی", "وبانک", "کگل", "خودرو", "شپنا", "پارس", "حسینا"}

    def extract_symbols(self, text: str) -> list[str]:
        found = []
        for sym in self._known_symbols:
            if sym in text:
                found.append(sym)
        return found

    def link_symbols(self, article: dict[str, Any]) -> dict[str, Any]:
        result = dict(article)
        text = f"{article.get('title', '')} {article.get('content', '')}"
        symbols = self.extract_symbols(text)
        result["symbols"] = symbols
        return result

    def batch_link(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.link_symbols(a) for a in articles]
