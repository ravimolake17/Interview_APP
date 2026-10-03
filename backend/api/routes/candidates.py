"""Seed endpoint for testing Agent 1 → Agent 2 integration."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.tenancy import get_tenant_scope, require_write_company_id
from core.database import get_db
from core.tenancy import TenantScope
from models.user import User
from models.candidate import Candidate, CandidateStatus
from repositories.candidate_repository import CandidateRepository

router = APIRouter(prefix="/candidates/seed", tags=["Candidates (Manual Seed)"])


class CreateCandidateRequest(BaseModel):
    candidate_id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    resume_score: float = Field(ge=0, le=100)


class CandidateResponse(BaseModel):
    candidate_id: str
    full_name: str
    email: str
    resume_score: float
    status: str

    model_config = {"from_attributes": True}


@router.post("", response_model=CandidateResponse, status_code=201)
async def create_candidate(
    request: CreateCandidateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
):
    """Create a shortlisted candidate (simulates Agent 1 output)."""
    repo = CandidateRepository(db)
    existing = await repo.get_by_candidate_id(request.candidate_id)
    if existing:
        raise HTTPException(status_code=409, detail="Candidate already exists.")

    candidate = Candidate(
        candidate_id=request.candidate_id,
        company_id=require_write_company_id(scope),
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
        resume_score=request.resume_score,
        status=CandidateStatus.SHORTLISTED,
    )
    db.add(candidate)
    await db.flush()

    return CandidateResponse(
        candidate_id=candidate.candidate_id,
        full_name=candidate.full_name,
        email=candidate.email,
        resume_score=candidate.resume_score,
        status=candidate.status.value,
    )
