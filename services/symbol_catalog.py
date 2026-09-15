"""Facade over ``domain.instruments.symbol_catalog`` — kept for API compat.

All existing imports (``all_symbols``, ``search``, ``sector_summary``,
``finglish_symbol_candidates``) keep working; logic and data now live in the
domain layer (ADR-0001 Phase 1: repositories must not import services).
"""

from __future__ import annotations

from domain.instruments.symbol_catalog import (
    _CATALOG,
    _TRANSLIT_REGEXES,
    DEFAULT_LIMIT,
    MARKET_SECTORS,
    all_symbols,
    finglish_symbol_candidates,
    search,
    sector_summary,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MARKET_SECTORS",
    "all_symbols",
    "finglish_symbol_candidates",
    "search",
    "sector_summary",
    "_CATALOG",
    "_TRANSLIT_REGEXES",
]
