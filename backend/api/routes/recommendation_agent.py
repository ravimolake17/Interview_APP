"""Agent 7 — HR recommendation report API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agents.recommendation_agent.schemas import (
    GenerateRecommendationRequest,
    HrRecommendationResponse,
)
from api.deps import get_client_ip, get_current_user
from api.tenancy import accessible_candidate, get_tenant_scope
from core.tenancy import TenantScope
from models.candidate import Candidate
from core.database import get_db
from models.user import User
from services.audit_service import AuditService
from services.recommendation_agent_service import RecommendationAgentService, RecommendationNotReady

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview/agent7", tags=["Recommendation Agent (Agent 7)"])


@router.get("/candidates/{candidate_id}/status")
async def get_recommendation_status(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> dict:
    try:
        return await RecommendationAgentService(db).get_status(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/candidates/{candidate_id}/report", response_model=HrRecommendationResponse)
async def get_recommendation_report(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _tenant: Candidate = Depends(accessible_candidate),
) -> HrRecommendationResponse:
    try:
        return await RecommendationAgentService(db).get_report(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/generate", response_model=HrRecommendationResponse)
async def generate_recommendation_report(
    candidate_id: str,
    request: Request,
    payload: GenerateRecommendationRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _tenant: Candidate = Depends(accessible_candidate),
) -> HrRecommendationResponse:
    force = bool(payload.force) if payload else False
    service = RecommendationAgentService(db)
    try:
        result = await service.generate_report(candidate_id, force=force)
    except RecommendationNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent 7 report failed for %s", candidate_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await AuditService(db).log(
        action="HR_RECOMMENDATION_GENERATED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "decision": result.report.decision,
            "overall_score": result.report.overall_score,
            "stage": result.report.stage,
        },
        message=(
            f"Agent 7 recommended {result.report.decision} for {candidate_id} "
            f"(score {result.report.overall_score:.0f})."
        ),
    )
    await db.commit()
    return result


@router.get("/reports")
async def list_recommendation_reports(
    db: AsyncSession = Depends(get_db),
    scope: TenantScope = Depends(get_tenant_scope),
) -> dict:
    items = await RecommendationAgentService(db).list_reports(company_id=scope.filter_company_id)
    return {"reports": items}
