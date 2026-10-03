"""Super Admin company catalog and company-user assignment."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_superadmin
from core.database import get_db
from core.tenancy import normalize_role
from models.company import CompanyStatus
from models.user import User, UserRole
from repositories.company_repository import CompanyRepository
from schemas.auth import UserResponse
from schemas.company import (
    CompanyCreateRequest,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdateRequest,
    CompanyUserCreateRequest,
)
from services.audit_service import AuditService
from services.auth_service import AuthService
from services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> CompanyListResponse:
    rows = await CompanyService(db).list_companies()
    return CompanyListResponse(
        total=len(rows),
        companies=[CompanyResponse.model_validate(row) for row in rows],
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> CompanyResponse:
    try:
        company = await CompanyService(db).create(
            name=payload.name,
            code=payload.code,
            logo=payload.logo,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await AuditService(db).log(
        action="COMPANY_CREATED",
        entity_type="company",
        entity_id=str(company.id),
        user=superadmin,
        request=request,
        ip_address=get_client_ip(request),
        details={"name": company.name, "code": company.code},
        message=f"{superadmin.full_name} created company {company.name}.",
        company_id=company.id,
    )
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    payload: CompanyUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> CompanyResponse:
    service = CompanyService(db)
    company = await service.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    data = payload.model_dump(exclude_unset=True)
    try:
        company = await service.update(company, **data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await AuditService(db).log(
        action="COMPANY_UPDATED",
        entity_type="company",
        entity_id=str(company.id),
        user=superadmin,
        request=request,
        ip_address=get_client_ip(request),
        details={"updated_fields": sorted(data.keys())},
        message=f"{superadmin.full_name} updated company {company.name}.",
        company_id=company.id,
    )
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.post("/{company_id}/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_company_user(
    company_id: int,
    payload: CompanyUserCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> UserResponse:
    if payload.company_id != company_id:
        raise HTTPException(status_code=400, detail="company_id in the body must match the URL.")
    company = await CompanyRepository(db).get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    if company.status != CompanyStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Cannot create users for an inactive company.")
    role = normalize_role(payload.role)
    if role not in {UserRole.HR, UserRole.COMPANY_ADMIN}:
        raise HTTPException(status_code=400, detail="Only HR or Company Admin can be assigned to a company.")
    auth = AuthService(db)
    try:
        user = await auth.create_user(
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            role=role,
            acting_admin=superadmin,
            company_id=company.id,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await AuditService(db).log(
        action="USER_CREATED",
        entity_type="user",
        entity_id=str(user.id),
        user=superadmin,
        request=request,
        ip_address=get_client_ip(request),
        details={"email": user.email, "role": user.role.value, "company_id": company.id},
        message=(
            f"{superadmin.full_name} created {user.role.value} {user.full_name} "
            f"for {company.name}."
        ),
        company_id=company.id,
    )
    await db.commit()
    return UserResponse.model_validate(user)
