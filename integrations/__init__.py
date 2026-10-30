"""Integration adapters (cache, queue, storage, notifications, observability, search).

Importing a single adapter must not drag every other backend into the process:
this package used to import all submodules eagerly, so ``apps/api/metrics``
pulled in the OTel exporter, S3 clients and the queue broker just to reach
``prometheus_exporter`` (measured ~1.6s of cold import).  Names stay importable
from the package — ``from integrations import PrometheusExporter`` still works —
but each one is resolved on first use (PEP 562).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from integrations.cache import KeyBuilder, MemoryCache, RedisClient, TTLManager
    from integrations.filesystems import (
        LocalStorage,
        PathManager,
        RetentionManager,
        S3CompatibleStorage,
    )
    from integrations.notifications import (
        EmailSender,
        NotificationTemplates,
        SmsSender,
        TelegramSender,
        WebhookSender,
    )
    from integrations.observability import (
        ErrorReporter,
        OTelExporter,
        PrometheusExporter,
        StructuredLogger,
    )
    from integrations.queue import Broker, Consumer, DeadLetterQueue, Publisher, RetryQueue
    from integrations.search import AliasManager, DocumentMapper, IndexClient, QueryClient

__all__ = [
    "KeyBuilder",
    "MemoryCache",
    "RedisClient",
    "TTLManager",
    "LocalStorage",
    "S3CompatibleStorage",
    "PathManager",
    "RetentionManager",
    "EmailSender",
    "SmsSender",
    "TelegramSender",
    "WebhookSender",
    "NotificationTemplates",
    "OTelExporter",
    "PrometheusExporter",
    "StructuredLogger",
    "ErrorReporter",
    "Broker",
    "Consumer",
    "Publisher",
    "DeadLetterQueue",
    "RetryQueue",
    "IndexClient",
    "QueryClient",
    "DocumentMapper",
    "AliasManager",
]

# name -> submodule that defines it
_EXPORTS: dict[str, str] = {
    "KeyBuilder": "integrations.cache",
    "MemoryCache": "integrations.cache",
    "RedisClient": "integrations.cache",
    "TTLManager": "integrations.cache",
    "LocalStorage": "integrations.filesystems",
    "S3CompatibleStorage": "integrations.filesystems",
    "PathManager": "integrations.filesystems",
    "RetentionManager": "integrations.filesystems",
    "EmailSender": "integrations.notifications",
    "SmsSender": "integrations.notifications",
    "TelegramSender": "integrations.notifications",
    "WebhookSender": "integrations.notifications",
    "NotificationTemplates": "integrations.notifications",
    "OTelExporter": "integrations.observability",
    "PrometheusExporter": "integrations.observability",
    "StructuredLogger": "integrations.observability",
    "ErrorReporter": "integrations.observability",
    "Broker": "integrations.queue",
    "Consumer": "integrations.queue",
    "Publisher": "integrations.queue",
    "DeadLetterQueue": "integrations.queue",
    "RetryQueue": "integrations.queue",
    "IndexClient": "integrations.search",
    "QueryClient": "integrations.search",
    "DocumentMapper": "integrations.search",
    "AliasManager": "integrations.search",
}


def __getattr__(name: str) -> Any:
    """Resolve a public adapter lazily and cache it on the package."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
