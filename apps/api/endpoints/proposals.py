"""Approval Gateway API — Phase 2-5.

Endpoints:
  POST /proposals              — create a new proposal
  GET  /proposals?status=      — list proposals
  POST /proposals/{id}/approve — approve (MFA)
  POST /proposals/{id}/reject  — reject (with reason)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_current_user, get_db_session
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.proposal_service import ProposalService

logger = get_logger(__name__)
router = APIRouter()


def _svc(session=Depends(get_db_session)) -> ProposalService:
    return ProposalService(session=session)


def _user(dep=Depends(get_current_user)) -> dict[str, Any]:
    return dep


@router.post("", summary="ایجاد پیشنهاد معاملاتی جدید")
async def create_proposal(
    body: dict[str, Any] = Body(...),
    svc: ProposalService = Depends(_svc),
    user: dict[str, Any] = Depends(_user),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await svc.create_proposal(
            user_id=user.get("id", "anonymous"),
            strategy_name=body.get("strategy_name", "Untitled"),
            legs=body.get("legs"),
            price=body.get("price"),
            gross_cost=body.get("gross_cost"),
            net_cost=body.get("net_cost"),
            max_loss=body.get("max_loss"),
            margin=body.get("margin"),
            var_95=body.get("var_95"),
            scenario_pnl=body.get("scenario_pnl"),
            ttl_seconds=body.get("ttl_seconds", 3600),
        )
        return ApiResponse(success=True, data=result)
    except Exception as exc:
        logger.exception("Proposal creation failed")
        return ApiResponse(success=False, data=None, error={"message": str(exc)})


@router.get("", summary="لیست پیشنهادها")
async def list_proposals(
    status: str = Query("pending", regex="^(pending|approved|rejected|expired)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: ProposalService = Depends(_svc),
    user: dict[str, Any] = Depends(_user),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        result = await svc.list_proposals(status=status, page=page, page_size=page_size)
        return ApiResponse(success=True, data=result)
    except Exception as exc:
        logger.exception("Proposal listing failed")
        return ApiResponse(success=False, data=None, error={"message": str(exc)})


@router.post("/{proposal_id}/approve", summary="تأیید پیشنهاد")
async def approve_proposal(
    proposal_id: str,
    svc: ProposalService = Depends(_svc),
    user: dict[str, Any] = Depends(_user),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await svc.approve_proposal(
            proposal_id=proposal_id,
            approver_id=user.get("id", "unknown"),
            calc_version="v1",
        )
        return ApiResponse(success=True, data=result)
    except Exception as exc:
        logger.exception("Proposal approval failed")
        return ApiResponse(success=False, data=None, error={"message": str(exc)})


@router.post("/{proposal_id}/reject", summary="رد پیشنهاد")
async def reject_proposal(
    proposal_id: str,
    body: dict[str, Any] = Body(...),
    svc: ProposalService = Depends(_svc),
    user: dict[str, Any] = Depends(_user),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await svc.reject_proposal(
            proposal_id=proposal_id,
            rejector_id=user.get("id", "unknown"),
            reason=body.get("reason", "No reason given"),
        )
        return ApiResponse(success=True, data=result)
    except Exception as exc:
        logger.exception("Proposal rejection failed")
        return ApiResponse(success=False, data=None, error={"message": str(exc)})
