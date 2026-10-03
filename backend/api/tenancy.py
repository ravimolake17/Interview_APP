"""FastAPI helpers for JWT-based tenant isolation."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.tenancy import TenantDenied, TenantScope, build_scope, parse_company_id
from models.candidate import Candidate
from models.user import User
from repositories.candidate_repository import CandidateRepository


def extract_requested_company_id(request: Request) -> int | None:
    header = request.headers.get("x-company-id")
    query = request.query_params.get("company_id")
    raw = header if header not in (None, "") else query
    return parse_company_id(raw)


async def get_tenant_scope(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> TenantScope:
    try:
        requested = extract_requested_company_id(request)
        return build_scope(current_user, requested)
    except TenantDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def raise_if_denied(exc: TenantDenied) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def require_write_company_id(scope: TenantScope) -> int:
    try:
        return scope.write_company_id()
    except TenantDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def require_scope_allows(scope: TenantScope, resource_company_id: int | None) -> None:
    if not scope.allows(resource_company_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found.",
        )


async def require_candidate_for_user(
    db: AsyncSession,
    user: User,
    candidate_id: str,
    *,
    requested_company_id: int | None = None,
) -> Candidate:
    try:
        scope = build_scope(user, requested_company_id)
    except TenantDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    candidate = await CandidateRepository(db).get_by_candidate_id(candidate_id)
    if not candidate or not scope.allows(candidate.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate


async def accessible_candidate(
    candidate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Candidate:
    try:
        requested = extract_requested_company_id(request)
    except TenantDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return await require_candidate_for_user(
        db,
        user,
        candidate_id,
        requested_company_id=requested,
    )


def company_id_for_actor(user: User | None, request: Request | None = None) -> int:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    try:
        requested = extract_requested_company_id(request) if request is not None else None
        return build_scope(user, requested).write_company_id()
    except TenantDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
