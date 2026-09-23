# contracts/events.py — Event payloads defined in contracts/events.md
# Read-only contract layer. Consumers (api, frontend) import from here.
from __future__ import annotations

from pydantic import BaseModel


class PRECOMPUTATION_PROGRESS(BaseModel):
    group: str                     # "A" | "B" | "C"
    completed: int
    total: int
    percent: float
    current_symbol: str


class PRECOMPUTATION_GROUP_COMPLETED(BaseModel):
    group: str
    total_processed: int
    failed: int
    timestamp: str                # ISO-8601


class PRECOMPUTATION_COMPLETED(BaseModel):
    total: int
    success: int
    failed: int
    avg_dri: float
    duration_seconds: float
    timestamp: str                # ISO-8601


class SYMBOL_RESULT_UPDATED(BaseModel):
    symbol: str
    group: str                   # "A" | "B" | "C"
    armor_score: float
    data_dri: float
    is_unreliable: bool
