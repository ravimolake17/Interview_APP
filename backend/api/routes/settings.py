"""Authenticated profile/preferences and admin application settings."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_current_user
from api.tenancy import get_tenant_scope, require_write_company_id
from core.database import get_db
from core.tenancy import TenantScope, is_super_admin
from models.user import User, UserRole
from repositories.user_repository import UserRepository
from schemas.auth import UserResponse
from schemas.settings import (
    AIModelSettings,
    CompanySettings,
    ConnectionTestResponse,
    IntegrationStatus,
    IntegrationUpdate,
    InterviewAvailabilitySettings,
    PreferenceSettings,
    ProfileUpdate,
    SettingsBundle,
)
from services.application_settings_service import ApplicationSettingsService
from services.audit_service import AuditService
from services.slot_service import SlotService
from repositories.slot_repository import SlotRepository

router = APIRouter(prefix="/settings", tags=["Settings"])


async def _audit(
    db: AsyncSession,
    request: Request,
    user: User,
    action: str,
    message: str,
    details: dict | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> None:
    await AuditService(db).log(
        action=action,
        entity_type="settings",
        entity_id=str(user.id),
        user=user,
        request=request,
        details=details or {},
        old_value=old_value,
        new_value=new_value,
        message=message,
    )


@router.get("", response_model=SettingsBundle)
async def get_settings_bundle(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> SettingsBundle:
    service = ApplicationSettingsService(db)
    company_id = scope.filter_company_id or user.company_id
    return SettingsBundle(
        profile=UserResponse.model_validate(user),
        company=await service.get_company(company_id),
        preferences=await service.get_preferences(user.id),
        integration=await service.get_integration_status(),
        ai_model=await service.get_ai_model(),
        interview_availability=await service.get_interview_availability(company_id),
        smtp_accounts=await service.list_smtp_accounts() if is_super_admin(user) else [],
    )


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    payload: ProfileUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserResponse:
    repo = UserRepository(db)
    duplicate = await repo.get_by_email(str(payload.email))
    if duplicate and duplicate.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    before = {
        "email": user.email,
        "full_name": user.full_name,
        "job_title": user.job_title,
        "phone": user.phone,
    }
    updated = await repo.update(
        user,
        email=str(payload.email),
        full_name=payload.full_name,
        job_title=payload.job_title,
        phone=payload.phone,
    )
    await _audit(
        db,
        request,
        user,
        "PROFILE_UPDATED",
        f"{updated.full_name} updated their profile.",
        {"updated_fields": sorted(payload.model_fields_set)},
        old_value=before,
        new_value={
            "email": updated.email,
            "full_name": updated.full_name,
            "job_title": updated.job_title,
            "phone": updated.phone,
        },
    )
    await db.commit()
    return UserResponse.model_validate(updated)


@router.patch("/company", response_model=CompanySettings)
async def update_company(
    payload: CompanySettings,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> CompanySettings:
    company_id = require_write_company_id(scope)
    result = await ApplicationSettingsService(db).save_company(
        payload, admin.id, company_id=company_id
    )
    await _audit(
        db,
        request,
        admin,
        "COMPANY_SETTINGS_UPDATED",
        f"{admin.full_name} updated company settings.",
        {"company_name": payload.company_name},
    )
    await db.commit()
    return result


@router.patch("/preferences", response_model=PreferenceSettings)
async def update_preferences(
    payload: PreferenceSettings,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PreferenceSettings:
    result = await ApplicationSettingsService(db).save_preferences(user.id, payload)
    await _audit(
        db,
        request,
        user,
        "USER_PREFERENCES_UPDATED",
        f"{user.full_name} updated appearance and notification preferences.",
    )
    await db.commit()
    return result


@router.patch("/ai-model", response_model=AIModelSettings)
async def update_ai_model(
    payload: AIModelSettings,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AIModelSettings:
    if admin.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SuperAdmin can change LLM settings.",
        )
    result = await ApplicationSettingsService(db).save_ai_model(payload, admin.id)
    await _audit(
        db,
        request,
        admin,
        "AI_SETTINGS_UPDATED",
        f"{admin.full_name} updated AI model settings.",
        {
            "provider": payload.provider,
            "model_id": payload.model_id,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
            "prompt_style": payload.prompt_style,
        },
    )
    await db.commit()
    return result


@router.patch("/integration", response_model=IntegrationStatus)
async def update_integration(
    payload: IntegrationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if admin.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SuperAdmin can change API keys and endpoints.",
        )
    result = await ApplicationSettingsService(db).save_integration(payload, admin.id)
    await _audit(
        db,
        request,
        admin,
        "INTEGRATION_SETTINGS_UPDATED",
        f"{admin.full_name} updated API keys and public URLs.",
        {"updated_fields": sorted(payload.model_fields_set)},
    )
    await db.commit()
    return result


@router.post("/integration/test", response_model=ConnectionTestResponse)
async def test_integration(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ConnectionTestResponse:
    if admin.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SuperAdmin can view integration status.",
        )
    integration = await ApplicationSettingsService(db).get_integration_status()
    return ConnectionTestResponse(
        ok=True,
        status="healthy",
        version="3.0.0",
        provider_configured=integration.api_key_configured,
        message=integration.message,
    )


@router.get("/interview-availability", response_model=InterviewAvailabilitySettings)
async def get_interview_availability(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> InterviewAvailabilitySettings:
    company_id = scope.filter_company_id or user.company_id
    return await ApplicationSettingsService(db).get_interview_availability(company_id)


@router.patch("/interview-availability")
async def update_interview_availability(
    payload: InterviewAvailabilitySettings,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    scope: TenantScope = Depends(get_tenant_scope),
) -> dict:
    company_id = require_write_company_id(scope)
    service = ApplicationSettingsService(db)
    before = await service.get_interview_availability(company_id)
    result = await service.save_interview_availability(payload, admin.id, company_id=company_id)
    sync = await SlotService(SlotRepository(db)).create_available_slots(result, company_id=company_id)
    await _audit(
        db,
        request,
        admin,
        "INTERVIEW_HOURS_UPDATED",
        f"{admin.full_name} updated interview days, hours, and holidays.",
        details={
            "weekdays": result.weekdays,
            "start_time": result.start_time.strftime("%H:%M"),
            "end_time": result.end_time.strftime("%H:%M"),
            "slot_minutes": result.slot_minutes,
            "weeks_ahead": result.weeks_ahead,
            "holidays": [item.model_dump(mode="json") for item in result.holidays],
            "created": sync["created"],
            "removed": sync["removed"],
        },
        old_value=before.model_dump(mode="json"),
        new_value=result.model_dump(mode="json"),
    )
    await db.commit()
    return {
        "availability": result.model_dump(mode="json"),
        "created": sync["created"],
        "removed": sync["removed"],
        "total": sync["total"],
    }
