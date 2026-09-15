from __future__ import annotations

# Re-export from base.py to avoid code duplication.
# This file exists only for backward compatibility.
from backtesting.strategies.base import BaseStrategy  # noqa: F401

__all__ = ["BaseStrategy"]
