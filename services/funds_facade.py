"""D6: Fund Single-Source Facade.

Consolidates duplicated fund logic (type inference, NAV handling,
symbol canonicalization) that was scattered across:
- apps/api/endpoints/funds.py (_infer_fund_type, _snapshot_to_dict, etc.)
- services/fund_service.py
- services/fund_sync_service.py
- services/fund_scoring.py
- repositories/fund_repository.py

All fund-related code should import from here. The old modules remain as
thin re-exports for backward compatibility.
"""

from __future__ import annotations

from services.fund_scoring import FundMetrics, FundScoreResult, compute_fund_score
from services.fund_service import FundService
from services.fund_sync_service import FundSyncService

# Re-export canonical type inference (was duplicated in funds.py endpoint)
try:
    from apps.api.endpoints.funds import _infer_fund_type
except Exception:
    def _infer_fund_type(name: str | None, symbol: str | None = None) -> str:  # type: ignore[no-redef]
        return "سهامی"


__all__ = [
    "FundService",
    "FundSyncService",
    "FundMetrics",
    "FundScoreResult",
    "compute_fund_score",
    "_infer_fund_type",
]
