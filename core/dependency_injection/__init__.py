"""Dependency-injection public surface.

``Container`` has a single implementation in :mod:`core.dependency_injection.container`.
"""

from __future__ import annotations

from core.dependency_injection.container import Container

container = Container()

__all__ = ["Container", "container"]
