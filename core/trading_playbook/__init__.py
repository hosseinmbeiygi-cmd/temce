"""📚 Trading playbook — offline knowledge base of trading scenarios (:mod:`.engine`).

Content lives in ``playbook_1050.json``; the PDF edition is in ``docs/trading_playbook``.
"""

from __future__ import annotations

from core.trading_playbook import engine
from core.trading_playbook.engine import (
    Answer,
    Match,
    Playbook,
    PlaybookEntry,
    PositionSnapshot,
    answer,
    buy_price_from_message,
    extract_prices,
    load,
    position_snapshot,
)

__all__ = [
    "Answer",
    "Match",
    "Playbook",
    "PlaybookEntry",
    "PositionSnapshot",
    "answer",
    "buy_price_from_message",
    "engine",
    "extract_prices",
    "load",
    "position_snapshot",
]
