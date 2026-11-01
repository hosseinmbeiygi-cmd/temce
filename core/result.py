"""Compatibility shim for ``Result``.

The canonical implementation lives in ``core.typing.result``. This module is
kept so existing ``from core.result import Result`` imports continue to work;
new code should import from ``core.typing``.
"""

from core.typing import PaginatedResult, Result

__all__ = ["PaginatedResult", "Result"]
