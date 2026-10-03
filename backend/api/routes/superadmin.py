"""SuperAdmin control plane: Database Console, LLM, and system health."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_superadmin
from api.tenancy import get_tenant_scope, require_write_company_id
from core.config import get_settings
from core.database import get_db
from core.tenancy import TenantScope
from data.superadmin_table_policy import require_policy, sanitize_for_audit
from models.user import User
from repositories.company_repository import CompanyRepository
from repositories.screening_job_repository import ScreeningJobRepository
from schemas.settings import (
    AIModelSettings,
    CompanySettings,
    IntegrationStatus,
    IntegrationUpdate,
    ScreeningPolicySettings,
    SmtpAccountSettings,
    SmtpAccountUpdate,
)
from schemas.superadmin import (
    DatabaseOverview,
    DatabaseRowUpdate,
    DatabaseRowsResponse,
    DatabaseTableInfo,
    DatabaseTableStat,
    PlatformRuntime,
    SuperAdminSystemResponse,
)
from services.application_settings_service import ApplicationSettingsService
from services.audit_service import AuditService
from services.superadmin_database_service import SuperAdminDatabaseService

router = APIRouter(prefix="/superadmin", tags=["SuperAdmin"])

_OVERVIEW_TABLES = (
    ("Users", "users"),
    ("Candidates", "candidate"),
    ("Jobs", "job_postings"),
    ("Departments", "departments"),
    ("Audit logs", "audit_logs"),
)


@router.get("/system", response_model=SuperAdminSystemResponse)
async def get_system_overview(
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(get_current_superadmin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> SuperAdminSystemResponse:
    settings = get_settings()
    connected = True
    health = "Healthy"
    message = "Database connection is healthy."
    table_stats: list[DatabaseTableStat] = []
    try:
        await db.execute(text("SELECT 1"))
        for label, table_name in _OVERVIEW_TABLES:
            try:
                count = await db.scalar(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                table_stats.append(DatabaseTableStat(name=label, rows=int(count or 0)))
            except Exception:
                table_stats.append(DatabaseTableStat(name=label, rows=0))
    except Exception:
        connected = False
        health = "Unavailable"
        message = "Database is unavailable."

    users = (await db.execute(select(User.role, func.count()).group_by(User.role))).all()
    role_counts = {str(role.value if hasattr(role, "value") else role): int(count) for role, count in users}
    queue = await ScreeningJobRepository(db).count_by_status()
    service = ApplicationSettingsService(db)
    company_id = scope.filter_company_id
    return SuperAdminSystemResponse(
        database=DatabaseOverview(
            engine="PostgreSQL",
            connected=connected,
            environment="Development" if settings.debug else "Production",
            health=health,
            tables=table_stats,
            message=message,
        ),
        integration=await service.get_integration_status(),
        ai_model=await service.get_ai_model(),
        company=await service.get_company(company_id),
        screening_policy=await service.get_screening_policy(company_id),
        smtp_accounts=await service.list_smtp_accounts(),
        platform=PlatformRuntime(
            frontend_url=settings.frontend_url,
            access_token_minutes=settings.jwt_access_token_expire_minutes,
            refresh_token_days=settings.jwt_refresh_token_expire_days,
            smtp_host=settings.smtp_host or "not configured",
            smtp_from=settings.smtp_from_email,
            smtp_configured=bool(settings.smtp_host and settings.smtp_user),
            interview_duration_minutes=(await service.get_interview_availability(company_id)).slot_minutes,
            token_expiry_hours=settings.token_expiry_hours,
        ),
        users={
            "total": sum(role_counts.values()),
            "hr": role_counts.get("HR", 0),
            "admin": role_counts.get("ADMIN", 0) + role_counts.get("COMPANY_ADMIN", 0),
            "company_admin": role_counts.get("COMPANY_ADMIN", 0) + role_counts.get("ADMIN", 0),
            "superadmin": role_counts.get("SUPERADMIN", 0),
        },
        screening_queue={
            "pending": queue.get("pending", 0),
            "processing": queue.get("processing", 0),
            "completed": queue.get("completed", 0),
            "failed": queue.get("failed", 0),
        },
    )


@router.patch("/ai-model", response_model=AIModelSettings)
async def update_llm_settings(
    payload: AIModelSettings,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> AIModelSettings:
    result = await ApplicationSettingsService(db).save_ai_model(payload, superadmin.id)
    await db.commit()
    return result


@router.patch("/company", response_model=CompanySettings)
async def update_company_settings(
    payload: CompanySettings,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> CompanySettings:
    company_id = require_write_company_id(scope)
    service = ApplicationSettingsService(db)
    before = await service.get_company(company_id)
    result = await service.save_company(payload, superadmin.id, company_id=company_id)
    await AuditService(db).log(
        action="SUPER_ADMIN_UPDATE",
        entity_type="company",
        entity_id="settings",
        user=superadmin,
        request=request,
        ip_address=get_client_ip(request),
        old_value=sanitize_for_audit(before.model_dump()),
        new_value=sanitize_for_audit(result.model_dump()),
        message=f"{superadmin.full_name} updated company settings.",
        company_id=company_id,
    )
    await db.commit()
    return result


@router.patch("/screening-policy", response_model=ScreeningPolicySettings)
async def update_screening_policy(
    payload: ScreeningPolicySettings,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> ScreeningPolicySettings:
    company_id = require_write_company_id(scope)
    result = await ApplicationSettingsService(db).save_screening_policy(
        payload, superadmin.id, company_id=company_id
    )
    await db.commit()
    return result


@router.patch("/integration", response_model=IntegrationStatus)
async def update_integration_secrets(
    payload: IntegrationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> IntegrationStatus:
    service = ApplicationSettingsService(db)
    result = await service.save_integration(payload, superadmin.id)
    await AuditService(db).log(
        action="SUPER_ADMIN_UPDATE",
        entity_type="settings",
        entity_id="integration",
        user=superadmin,
        request=request,
        ip_address=get_client_ip(request),
        new_value=sanitize_for_audit(result.model_dump()),
        message=f"{superadmin.full_name} updated API keys and public URLs.",
    )
    await db.commit()
    return result


@router.patch("/smtp/{company_id}", response_model=SmtpAccountSettings)
async def update_company_smtp(
    company_id: int,
    payload: SmtpAccountUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
) -> SmtpAccountSettings:
    company = await CompanyRepository(db).get_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    result = await ApplicationSettingsService(db).save_smtp_account(
        company_id, payload, superadmin.id
    )
    await AuditService(db).log(
        action="SUPER_ADMIN_UPDATE",
        entity_type="smtp",
        entity_id=str(company_id),
        user=superadmin,
        request=request,
        ip_address=get_client_ip(request),
        new_value=sanitize_for_audit(result.model_dump()),
        message=f"{superadmin.full_name} updated SMTP for {company.name}.",
        company_id=company_id,
    )
    await db.commit()
    return result


@router.get("/database/tables", response_model=list[DatabaseTableInfo])
async def list_database_tables(
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(get_current_superadmin),
) -> list[DatabaseTableInfo]:
    rows = await SuperAdminDatabaseService(db).list_tables()
    return [DatabaseTableInfo.model_validate(row) for row in rows]


@router.get("/database/tables/{schema}/{table}", response_model=DatabaseRowsResponse)
async def list_database_rows(
    schema: str,
    table: str,
    limit: int = Query(25, ge=1, le=50),
    offset: int = Query(0, ge=0),
    search: str = Query("", max_length=120),
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(get_current_superadmin),
) -> DatabaseRowsResponse:
    payload = await SuperAdminDatabaseService(db).list_rows(
        schema, table, limit=limit, offset=offset, search=search
    )
    return DatabaseRowsResponse.model_validate(payload)


@router.patch("/database/tables/{schema}/{table}/rows/{row_id}")
async def update_database_row(
    schema: str,
    table: str,
    row_id: str,
    _payload: DatabaseRowUpdate,
    _superadmin: User = Depends(get_current_superadmin),
) -> None:
    require_policy(schema, table, write=True)


@router.delete("/database/tables/{schema}/{table}/rows/{row_id}")
async def delete_database_row(
    schema: str,
    table: str,
    row_id: str,
    _superadmin: User = Depends(get_current_superadmin),
) -> None:
    require_policy(schema, table, write=True)
