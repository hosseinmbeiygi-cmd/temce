from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

class SymbolGroup(str, Enum):
    A = "A"
    B = "B"
    C = "C"

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SKIPPED = "SKIPPED"
    STALE = "STALE"

class GroupProgress(BaseModel):
    total: int = 0
    completed: int = 0
    failed: int = 0
    status: JobStatus = JobStatus.PENDING

class PrecomputeStatusResponse(BaseModel):
    overall_status: JobStatus
    current_group: Optional[SymbolGroup] = None
    total_symbols: int
    completed_symbols: int
    failed_symbols: int
    progress_percent: float
    current_symbol: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = None
    last_update: datetime
    groups: Dict[SymbolGroup, GroupProgress]

class SymbolComputationResult(BaseModel):
    symbol: str
    group: SymbolGroup
    last_price: float
    closing_price: float
    technical_score: float
    liquidity_score: float
    money_flow_score: float
    armor_score: float
    data_dri: float = Field(..., ge=0.0, le=100.0, description="Data Reliability Index")
    is_unreliable: bool = False
    red_flags: List[str] = []
    calculated_at: datetime
    expires_at: datetime
    version: str = "v4.0"
