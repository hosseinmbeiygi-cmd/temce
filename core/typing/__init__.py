"""Shared typing primitives.

Definitions live in the small focused modules; this package is the public
import surface (``from core.typing import Result``).
"""

from __future__ import annotations

from core.typing.aliases import JsonDict, JsonList, JsonValue
from core.typing.protocols import Entity, Repository, UseCase
from core.typing.result import PaginatedResult, Result

__all__ = [
    "Entity",
    "JsonDict",
    "JsonList",
    "JsonValue",
    "PaginatedResult",
    "Repository",
    "Result",
    "UseCase",
]
