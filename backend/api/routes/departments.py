"""Department catalog: staff can list active rows; SuperAdmin manages them."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_admin, get_current_user
from api.tenancy import get_tenant_scope, require_scope_allows, require_write_company_id
from core.database import get_db
from core.tenancy import TenantScope, is_super_admin
from models.department import Department
from models.user import User
from repositories.company_repository import CompanyRepository
from repositories.department_repository import DepartmentRepository
from schemas.department import (
    DepartmentCreate,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentUpdate,
)
from services.audit_service import AuditService

router = APIRouter(prefix="/departments", tags=["Departments"])


def _to_response(row: Department) -> DepartmentResponse:
    payload = DepartmentResponse.model_validate(row)
    company = getattr(row, "company", None)
    if company is not None:
        payload.company_name = company.name
    return payload


async def _resolve_company_id(
    db: AsyncSession,
    admin: User,
    scope: TenantScope,
    requested_company_id: int | None,
) -> int:
    if is_super_admin(admin):
        company_id = requested_company_id or scope.filter_company_id
        if company_id is None:
            raise HTTPException(status_code=400, detail="Select a company for this department.")
        company = await CompanyRepository(db).get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")
        return company_id
    company_id = require_write_company_id(scope)
    if requested_company_id is not None and requested_company_id != company_id:
        raise HTTPException(status_code=403, detail="Cannot create a department for another company.")
    return company_id


@router.get("", response_model=DepartmentListResponse)
async def list_departments(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> DepartmentListResponse:
    company_id = scope.filter_company_id
    if company_id is None:
        return DepartmentListResponse(total=0, departments=[])
    rows = await DepartmentRepository(db).list_all(active_only=True, company_id=company_id)
    return DepartmentListResponse(
        total=len(rows),
        departments=[_to_response(row) for row in rows],
    )


@router.get("/manage", response_model=DepartmentListResponse)
async def list_all_departments(
    include_all: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> DepartmentListResponse:
    repo = DepartmentRepository(db)
    if is_super_admin(admin) and include_all:
        rows = await repo.list_all(active_only=False)
    else:
        company_id = scope.filter_company_id
        if company_id is None and is_super_admin(admin):
            rows = await repo.list_all(active_only=False)
        elif company_id is None:
            raise HTTPException(status_code=400, detail="Select a company before listing departments.")
        else:
            rows = await repo.list_all(active_only=False, company_id=company_id)
    return DepartmentListResponse(
        total=len(rows),
        departments=[_to_response(row) for row in rows],
    )


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> DepartmentResponse:
    repo = DepartmentRepository(db)
    company_id = await _resolve_company_id(db, admin, scope, payload.company_id)
    if await repo.get_by_name(payload.name, company_id=company_id):
        raise HTTPException(status_code=400, detail="A department with this name already exists.")
    row = await repo.create(
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        company_id=company_id,
    )
    await AuditService(db).log(
        action="DEPARTMENT_CREATED",
        entity_type="department",
        entity_id=str(row.id),
        user=admin,
        request=request,
        ip_address=get_client_ip(request),
        details={"name": row.name, "company_id": company_id},
        message=f"{admin.full_name} created department {row.name}.",
        company_id=company_id,
    )
    await db.commit()
    await db.refresh(row)
    company = await CompanyRepository(db).get_by_id(company_id)
    row.company = company
    return _to_response(row)


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> DepartmentResponse:
    repo = DepartmentRepository(db)
    row = await repo.get_by_id(department_id)
    if not row:
        raise HTTPException(status_code=404, detail="Department not found.")
    if not is_super_admin(admin):
        require_scope_allows(scope, row.company_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        existing = await repo.get_by_name(data["name"], company_id=row.company_id)
        if existing and existing.id != row.id:
            raise HTTPException(status_code=400, detail="A department with this name already exists.")
        row.name = data["name"].strip()
    if "description" in data:
        row.description = (data["description"] or "").strip() or None
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = data["is_active"]
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = data["sort_order"]
    await AuditService(db).log(
        action="DEPARTMENT_UPDATED",
        entity_type="department",
        entity_id=str(row.id),
        user=admin,
        request=request,
        ip_address=get_client_ip(request),
        details={"name": row.name, "updated_fields": sorted(data.keys())},
        message=f"{admin.full_name} updated department {row.name}.",
        company_id=row.company_id,
    )
    await db.commit()
    await db.refresh(row)
    company = await CompanyRepository(db).get_by_id(row.company_id)
    row.company = company
    return _to_response(row)
