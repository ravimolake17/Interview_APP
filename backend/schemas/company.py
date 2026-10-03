"""Company (tenant) API contracts."""

from datetime import datetime

from pydantic import BaseModel, Field


class CompanyResponse(BaseModel):
    id: int
    name: str
    code: str
    logo: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    total: int
    companies: list[CompanyResponse]


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=2, max_length=64)
    logo: str | None = Field(default=None, max_length=512)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=2, max_length=64)
    logo: str | None = Field(default=None, max_length=512)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class CompanyUserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(pattern="^(HR|COMPANY_ADMIN|ADMIN)$")
    company_id: int
    is_active: bool = True
