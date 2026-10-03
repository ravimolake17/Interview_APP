"""SuperAdmin system overview and Data Management contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from schemas.auth import CreateUserRequest, UpdateUserRequest
from schemas.department import DepartmentCreate, DepartmentUpdate
from schemas.jobs import JobPostingCreate, JobPostingUpdate
from schemas.settings import (
    AIModelSettings,
    CompanySettings,
    IntegrationStatus,
    ScreeningPolicySettings,
    SmtpAccountSettings,
)


class DatabaseTableStat(BaseModel):
    name: str
    rows: int
    access: str = "read"


class DatabaseOverview(BaseModel):
    engine: str = "PostgreSQL"
    connected: bool
    environment: str
    health: str
    message: str
    tables: list[DatabaseTableStat] = Field(default_factory=list)


class PlatformRuntime(BaseModel):
    frontend_url: str
    access_token_minutes: int
    refresh_token_days: int
    smtp_host: str
    smtp_from: str
    smtp_configured: bool
    interview_duration_minutes: int
    token_expiry_hours: int


class DatabaseTableInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
    schema_name: str = Field(validation_alias="schema", serialization_alias="schema")
    name: str
    label: str = ""
    rows: int
    access: str = "read"
    notes: str = ""


class DatabaseColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool
    default: str | None = None
    primary_key: bool = False
    editable: bool = False


class DatabaseRow(BaseModel):
    id: str | None = None
    data: dict


class DatabaseRowsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
    schema_name: str = Field(validation_alias="schema", serialization_alias="schema")
    table: str
    label: str = ""
    access: str = "read"
    notes: str = ""
    primary_key: list[str] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    columns: list[DatabaseColumnInfo] = Field(default_factory=list)
    rows: list[DatabaseRow] = Field(default_factory=list)


class DatabaseRowUpdate(BaseModel):
    values: dict = Field(default_factory=dict)


class SuperAdminSystemResponse(BaseModel):
    database: DatabaseOverview
    integration: IntegrationStatus
    ai_model: AIModelSettings
    company: CompanySettings
    screening_policy: ScreeningPolicySettings
    platform: PlatformRuntime
    users: dict[str, int]
    screening_queue: dict[str, int]
    smtp_accounts: list[SmtpAccountSettings] = Field(default_factory=list)


class DataEntityInfo(BaseModel):
    id: str
    label: str
    rows: int
    create: bool = False
    update: bool = False
    delete: str | bool = False


class DataListResponse(BaseModel):
    total: int
    records: list[dict[str, Any]] = Field(default_factory=list)


class SuperAdminCandidateUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    job_position: str | None = Field(default=None, max_length=255)
    status: Literal["PENDING", "SHORTLISTED", "NEEDS_REVIEW", "REJECTED", "INTERVIEW_SCHEDULED"] | None = None
    reason: str | None = Field(default=None, max_length=500)


class SuperAdminJobCreate(JobPostingCreate):
    reason: str | None = Field(default=None, max_length=500)


class SuperAdminJobUpdate(JobPostingUpdate):
    expected_updated_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class SuperAdminDepartmentCreate(DepartmentCreate):
    reason: str | None = Field(default=None, max_length=500)


class SuperAdminDepartmentUpdate(DepartmentUpdate):
    expected_updated_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class SuperAdminUserCreate(CreateUserRequest):
    reason: str | None = Field(default=None, max_length=500)


class SuperAdminUserUpdate(UpdateUserRequest):
    reason: str | None = Field(default=None, max_length=500)


class SuperAdminCompanyUpdate(CompanySettings):
    reason: str | None = Field(default=None, max_length=500)


class RelatedImpactResponse(BaseModel):
    can_hard_delete: bool
    related: dict[str, int] = Field(default_factory=dict)
    recommendation: str
