"""
Scheduled job definitions.

Each public symbol in this module is discovered by
``JobRegistry.register_module()`` and made available to the
``JobDispatcher`` for scheduling via APScheduler.
"""

# ── Scheduled job re-exports (see definitions/ package for full registry) ──
# This module is kept for backwards compatibility with direct imports.
# New imports should use: from jobs.definitions import BackfillHistoricalDataJob

from jobs.definitions import BackfillHistoricalDataJob  # noqa: F401

__all__ = ["BackfillHistoricalDataJob"]
