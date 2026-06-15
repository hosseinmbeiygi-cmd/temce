from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


class AliasDictionary:
    def __init__(self) -> None:
        self._aliases: dict[str, set[str]] = {}
        self._canonical: dict[str, str] = {}

    def add_alias(self, canonical: str, alias: str) -> None:
        canonical = canonical.strip().upper()
        alias = alias.strip().upper()
        self._aliases.setdefault(canonical, set()).add(alias)
        self._canonical[alias] = canonical

    def add_aliases(self, canonical: str, aliases: list[str]) -> None:
        for alias in aliases:
            self.add_alias(canonical, alias)

    def get_canonical(self, name: str) -> str:
        name = name.strip().upper()
        return self._canonical.get(name, name)

    def get_aliases(self, canonical: str) -> list[str]:
        return list(self._aliases.get(canonical.upper(), set()))

    def remove_alias(self, alias: str) -> None:
        alias = alias.strip().upper()
        canonical = self._canonical.pop(alias, None)
        if canonical and alias in self._aliases.get(canonical, set()):
            self._aliases[canonical].discard(alias)

    def load_from_dict(self, mapping: dict[str, list[str]]) -> None:
        for canonical, aliases in mapping.items():
            self.add_aliases(canonical, aliases)

    def to_dict(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._aliases.items()}

    def clear(self) -> None:
        self._aliases.clear()
        self._canonical.clear()
