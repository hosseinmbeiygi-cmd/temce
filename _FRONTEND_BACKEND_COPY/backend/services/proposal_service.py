"""Proposal service — Approval Gateway business logic (Phase 2-5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult
from models.approval_gateway import ProposalAuditModel, ProposalModel

logger = get_logger(__name__)


class ProposalService:
    """Business logic for the Approval Gateway MVP."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_proposal(
        self,
        user_id: str,
        strategy_name: str,
        legs: str | None = None,
        price: float | None = None,
        gross_cost: float | None = None,
        net_cost: float | None = None,
        max_loss: float | None = None,
        margin: float | None = None,
        var_95: float | None = None,
        scenario_pnl: str | None = None,
        ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        proposal = ProposalModel(
            id=new_id("prop"),
            user_id=user_id,
            strategy_name=strategy_name,
            legs=legs,
            price=price,
            gross_cost=gross_cost,
            net_cost=net_cost,
            max_loss=max_loss,
            margin=margin,
            var_95=var_95,
            scenario_pnl=scenario_pnl,
            status="pending",
            ttl_seconds=ttl_seconds,
            calc_version="v1",
        )
        self.session.add(proposal)
        await self.session.commit()
        await self.session.refresh(proposal)
        return {"id": proposal.id, "status": proposal.status, "strategy_name": proposal.strategy_name}

    async def list_proposals(
        self, status: str = "pending", page: int = 1, page_size: int = 20
    ) -> PaginatedResult[dict[str, Any]]:
        stmt = (
            select(ProposalModel)
            .where(ProposalModel.status == status)
            .order_by(ProposalModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        proposals = result.scalars().all()
        total = len(proposals)
        items = [
            {
                "id": p.id,
                "strategy_name": p.strategy_name,
                "status": p.status,
                "price": p.price,
                "gross_cost": p.gross_cost,
                "net_cost": p.net_cost,
                "max_loss": p.max_loss,
                "margin": p.margin,
                "var_95": p.var_95,
                "ttl_seconds": p.ttl_seconds,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in proposals
        ]
        return PaginatedResult(items=items, total=total, page=page, page_size=page_size)

    async def approve_proposal(self, proposal_id: str, approver_id: str, calc_version: str = "v1") -> dict[str, Any]:
        stmt = select(ProposalModel).where(ProposalModel.id == proposal_id)
        result = await self.session.execute(stmt)
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != "pending":
            raise ValueError(f"Proposal {proposal_id} is already {proposal.status}")

        proposal.status = "approved"
        proposal.approved_by = approver_id
        proposal.approved_at = datetime.now(UTC)
        proposal.broker_order_id = new_id("broker")
        self.session.add(proposal)

        audit = ProposalAuditModel(
            id=new_id("audit"),
            proposal_id=proposal_id,
            action="approve",
            who=approver_id,
            why="Approved by gateway",
            calc_version=calc_version,
        )
        self.session.add(audit)
        await self.session.commit()

        return {
            "id": proposal.id,
            "status": "approved",
            "broker_order_id": proposal.broker_order_id,
            "approved_by": approver_id,
            "approved_at": proposal.approved_at.isoformat() if proposal.approved_at else None,
        }

    async def reject_proposal(self, proposal_id: str, rejector_id: str, reason: str) -> dict[str, Any]:
        stmt = select(ProposalModel).where(ProposalModel.id == proposal_id)
        result = await self.session.execute(stmt)
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != "pending":
            raise ValueError(f"Proposal {proposal_id} is already {proposal.status}")

        proposal.status = "rejected"
        proposal.reject_reason = reason
        self.session.add(proposal)

        audit = ProposalAuditModel(
            id=new_id("audit"),
            proposal_id=proposal_id,
            action="reject",
            who=rejector_id,
            why=reason,
            calc_version=proposal.calc_version or "v1",
        )
        self.session.add(audit)
        await self.session.commit()

        return {"id": proposal.id, "status": "rejected", "reason": reason}
