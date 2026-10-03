"""SuperAdmin Data Management — business entities via existing ORM services."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_superadmin
from core.database import get_db
from data.superadmin_table_policy import sanitize_for_audit
from models.user import User
from repositories.user_repository import UserRepository
from schemas.auth import CreateUserRequest, UpdateUserRequest
from schemas.department import DepartmentCreate, DepartmentUpdate
from schemas.jobs import JobPostingCreate, JobPostingUpdate
from schemas.settings import CompanySettings
from schemas.superadmin import (
    DataEntityInfo,
    DataListResponse,
    RelatedImpactResponse,
    SuperAdminCandidateUpdate,
    SuperAdminCompanyUpdate,
    SuperAdminDepartmentCreate,
    SuperAdminDepartmentUpdate,
    SuperAdminJobCreate,
    SuperAdminJobUpdate,
    SuperAdminUserCreate,
    SuperAdminUserUpdate,
)
from services.application_settings_service import ApplicationSettingsService
from services.audit_service import AuditService
from services.superadmin_data_service import SuperAdminDataService

router = APIRouter(prefix="/superadmin/data", tags=["SuperAdmin Data"])


async def _log_change(
    db: AsyncSession,
    *,
    request: Request,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: str | None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    reason: str | None = None,
    message: str,
) -> None:
    await AuditService(db).log(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user=actor,
        request=request,
        ip_address=get_client_ip(request),
        details={"reason": reason} if reason else None,
        old_value=sanitize_for_audit(old_value) if old_value else None,
        new_value=sanitize_for_audit(new_value) if new_value else None,
        message=message,
    )


@router.get("/catalog", response_model=list[DataEntityInfo])
async def data_catalog(
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(get_current_superadmin),
) -> list[DataEntityInfo]:
    rows = await SuperAdminDataService(db).catalog()
    return [DataEntityInfo.model_validate(row) for row in rows]


@router.get("/{entity}", response_model=DataListResponse)
async def list_data_records(
    entity: str,
    search: str = Query("", max_length=120),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(get_current_superadmin),
) -> DataListResponse:
    service = SuperAdminDataService(db)
    if entity == "users":
        payload = await service.list_users(search=search, limit=limit, offset=offset)
    elif entity == "candidates":
        payload = await service.list_candidates(
            search=search, status=status_filter, limit=limit, offset=offset
        )
    elif entity == "jobs":
        payload = await service.list_jobs(search=search, limit=limit, offset=offset)
    elif entity == "departments":
        payload = await service.list_departments(search=search, limit=limit, offset=offset)
    elif entity == "company":
        company = await ApplicationSettingsService(db).get_company()
        payload = {"total": 1, "records": [company.model_dump()]}
    else:
        raise HTTPException(status_code=404, detail="Unknown Data Management entity.")
    return DataListResponse.model_validate(payload)


@router.get("/{entity}/{record_id}/impact", response_model=RelatedImpactResponse)
async def data_record_impact(
    entity: str,
    record_id: str,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(get_current_superadmin),
) -> RelatedImpactResponse:
    payload = await SuperAdminDataService(db).related_impact(entity, record_id)
    return RelatedImpactResponse.model_validate(payload)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_data_user(
    payload: SuperAdminUserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    user_payload = CreateUserRequest.model_validate(payload.model_dump(exclude={"reason"}))
    record = await SuperAdminDataService(db).create_user(user_payload, superadmin)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_CREATE",
        entity_type="users",
        entity_id=str(record["id"]),
        new_value={"email": record["email"], "role": record["role"], "full_name": record["full_name"]},
        reason=payload.reason,
        message=f"{superadmin.full_name} created user {record['email']}.",
    )
    await db.commit()
    return record


@router.patch("/users/{user_id}")
async def update_data_user(
    user_id: int,
    payload: SuperAdminUserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    before = await UserRepository(db).get_by_id(user_id)
    if not before:
        raise HTTPException(status_code=404, detail="User not found.")
    old = {
        "email": before.email,
        "full_name": before.full_name,
        "role": before.role.value if hasattr(before.role, "value") else str(before.role),
        "is_active": before.is_active,
    }
    user_payload = UpdateUserRequest.model_validate(
        payload.model_dump(exclude={"reason"}, exclude_unset=True)
    )
    record = await SuperAdminDataService(db).update_user(user_id, user_payload, superadmin)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_UPDATE",
        entity_type="users",
        entity_id=str(user_id),
        old_value=old,
        new_value={k: record[k] for k in ("email", "full_name", "role", "is_active")},
        reason=payload.reason,
        message=f"{superadmin.full_name} updated user {record['email']}.",
    )
    await db.commit()
    return record


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_data_job(
    payload: SuperAdminJobCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    job_payload = JobPostingCreate.model_validate(payload.model_dump(exclude={"reason"}))
    record = await SuperAdminDataService(db).create_job(job_payload)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_CREATE",
        entity_type="jobs",
        entity_id=str(record["id"]),
        new_value={"title": record["title"], "department": record.get("department"), "status": record["status"]},
        reason=payload.reason,
        message=f"{superadmin.full_name} created job {record['title']}.",
    )
    await db.commit()
    return record


@router.patch("/jobs/{job_id}")
async def update_data_job(
    job_id: int,
    payload: SuperAdminJobUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    job_payload = JobPostingUpdate.model_validate(
        payload.model_dump(exclude={"reason", "expected_updated_at"}, exclude_unset=True)
    )
    result = await SuperAdminDataService(db).update_job(job_id, job_payload, payload.expected_updated_at)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_UPDATE",
        entity_type="jobs",
        entity_id=str(job_id),
        old_value=result.get("old"),
        new_value=result.get("new"),
        reason=payload.reason,
        message=f"{superadmin.full_name} updated job {job_id}.",
    )
    await db.commit()
    return result["record"]


@router.delete("/jobs/{job_id}")
async def delete_data_job(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    result = await SuperAdminDataService(db).close_or_delete_job(job_id)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_DELETE" if result.get("action") == "deleted" else "SUPER_ADMIN_UPDATE",
        entity_type="jobs",
        entity_id=str(job_id),
        old_value=result.get("old") or result.get("record"),
        new_value={"status": "Closed"} if result.get("action") == "closed" else None,
        message=f"{superadmin.full_name} {result.get('action')} job {job_id}.",
    )
    await db.commit()
    return result


@router.post("/departments", status_code=status.HTTP_201_CREATED)
async def create_data_department(
    payload: SuperAdminDepartmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    dept_payload = DepartmentCreate.model_validate(payload.model_dump(exclude={"reason"}))
    record = await SuperAdminDataService(db).create_department(dept_payload)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_CREATE",
        entity_type="departments",
        entity_id=str(record["id"]),
        new_value={"name": record["name"]},
        reason=payload.reason,
        message=f"{superadmin.full_name} created department {record['name']}.",
    )
    await db.commit()
    return record


@router.patch("/departments/{department_id}")
async def update_data_department(
    department_id: int,
    payload: SuperAdminDepartmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    dept_payload = DepartmentUpdate.model_validate(
        payload.model_dump(exclude={"reason", "expected_updated_at"}, exclude_unset=True)
    )
    result = await SuperAdminDataService(db).update_department(
        department_id, dept_payload, payload.expected_updated_at
    )
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_UPDATE",
        entity_type="departments",
        entity_id=str(department_id),
        old_value=result.get("old"),
        new_value=result.get("new"),
        reason=payload.reason,
        message=f"{superadmin.full_name} updated department {department_id}.",
    )
    await db.commit()
    return result["record"]


@router.delete("/departments/{department_id}")
async def deactivate_data_department(
    department_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    result = await SuperAdminDataService(db).deactivate_department(department_id)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_UPDATE",
        entity_type="departments",
        entity_id=str(department_id),
        old_value={"is_active": True},
        new_value={"is_active": False},
        message=f"{superadmin.full_name} deactivated department {department_id}.",
    )
    await db.commit()
    return result


@router.patch("/candidates/{candidate_id}")
async def update_data_candidate(
    candidate_id: str,
    payload: SuperAdminCandidateUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    values = payload.model_dump(exclude={"reason"}, exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="No fields to update.")
    result = await SuperAdminDataService(db).update_candidate(candidate_id, values)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_UPDATE",
        entity_type="candidate",
        entity_id=candidate_id,
        old_value=result.get("old"),
        new_value=result.get("new"),
        reason=payload.reason,
        message=f"{superadmin.full_name} updated candidate {candidate_id}.",
    )
    await db.commit()
    return result["record"]


@router.patch("/company")
async def update_data_company(
    payload: SuperAdminCompanyUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> dict:
    company_payload = CompanySettings.model_validate(payload.model_dump(exclude={"reason"}))
    before = await ApplicationSettingsService(db).get_company()
    result = await ApplicationSettingsService(db).save_company(company_payload, superadmin.id)
    await _log_change(
        db,
        request=request,
        actor=superadmin,
        action="SUPER_ADMIN_UPDATE",
        entity_type="company",
        entity_id="settings",
        old_value=before.model_dump(),
        new_value=result.model_dump(),
        reason=payload.reason,
        message=f"{superadmin.full_name} updated company settings.",
    )
    await db.commit()
    return result.model_dump()
