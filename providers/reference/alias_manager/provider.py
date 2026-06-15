from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.reference.alias_manager.dictionary import AliasDictionary
from providers.reference.alias_manager.resolver import AliasResolver

logger = get_logger(__name__)


class AliasManagerProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="alias_manager")
        self.dictionary = AliasDictionary()
        self.resolver = AliasResolver(self.dictionary)
        self.resolver.add_static_mappings()

    async def fetch(self, name: str | None = None, **kwargs: Any) -> Result[Any]:
        if not name:
            return Result.ok(self.dictionary.to_dict())
        resolved = self.resolver.resolve(name)
        aliases = self.dictionary.get_aliases(resolved)
        return Result.ok(
            {
                "input": name,
                "canonical": resolved,
                "aliases": aliases,
            }
        )

    async def add_alias(self, canonical: str, alias: str) -> Result[dict[str, Any]]:
        self.dictionary.add_alias(canonical, alias)
        logger.info("Added alias %s -> %s", alias, canonical)
        return Result.ok({"canonical": canonical, "alias": alias})

    async def remove_alias(self, alias: str) -> Result[bool]:
        self.dictionary.remove_alias(alias)
        return Result.ok(True)

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self.dictionary._aliases)} canonical entries"}
