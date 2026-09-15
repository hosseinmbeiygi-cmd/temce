from __future__ import annotations

import re

from core.logging import get_logger
from providers.reference.alias_manager.dictionary import AliasDictionary

logger = get_logger(__name__)


class AliasResolver:
    def __init__(self, dictionary: AliasDictionary | None = None) -> None:
        self.dictionary = dictionary or AliasDictionary()
        self._patterns: dict[str, re.Pattern] = {}

    def add_pattern(self, pattern_name: str, pattern: str) -> None:
        self._patterns[pattern_name] = re.compile(pattern, re.IGNORECASE)

    def resolve(self, name: str) -> str:
        name_upper = name.strip().upper()
        canonical = self.dictionary.get_canonical(name_upper)
        if canonical != name_upper:
            return canonical
        for _pattern_name, pattern in self._patterns.items():
            match = pattern.match(name)
            if match:
                resolved = match.group(1) if match.groups() else ""
                if resolved:
                    return self.dictionary.get_canonical(resolved)
        return name.strip()

    def resolve_batch(self, names: list[str]) -> dict[str, str]:
        return {name: self.resolve(name) for name in names}

    def add_static_mappings(self) -> None:
        iran_common = {
            "فولاد": ["فولاد مبارکه", "فولادمبارکه", "فسرب", "فولاد اصفهان"],
            "خودرو": ["ایران خودرو", "ایرانخودرو", "خوساز"],
            "وبملت": ["بانک ملت", "ملت"],
            "فملی": ["ملی صنایع مس", "مس"],
            "کگل": ["گل گهر", "گلگهر"],
        }
        self.dictionary.load_from_dict(iran_common)
