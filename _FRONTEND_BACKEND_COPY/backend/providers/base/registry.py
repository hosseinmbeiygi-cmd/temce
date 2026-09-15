from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ProviderMetadata:
    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        description: str = "",
        tags: list[str] | None = None,
        dependencies: list[str] | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.tags = tags or []
        self.dependencies = dependencies or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tags": self.tags,
            "dependencies": self.dependencies,
        }


class ProviderRegistryMeta(type):
    _instances: dict[str, Any] = {}
    _providers: dict[str, ProviderMetadata] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    def register(cls, name: str, metadata: ProviderMetadata) -> None:
        cls._providers[name] = metadata
        logger.info("Registered provider metadata: %s v%s", name, metadata.version)

    def get_metadata(cls, name: str) -> ProviderMetadata | None:
        return cls._providers.get(name)

    def list_providers(cls) -> dict[str, ProviderMetadata]:
        return dict(cls._providers)
