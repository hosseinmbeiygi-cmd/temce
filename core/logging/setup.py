"""Logging bootstrap — thin re-export of the canonical ``setup_logging``.

The actual implementation lives in ``core.logging.__init__`` (it uses the
Unicode-safe ``SafeStreamHandler``).  This module exists for backward
compatibility with imports like ``from core.logging.setup import setup_logging``.
"""

from __future__ import annotations

from core.logging import setup_logging  # noqa: F401  — canonical implementation

setup_root_logger = setup_logging  # compatibility alias


__all__ = ["setup_logging", "setup_root_logger"]
