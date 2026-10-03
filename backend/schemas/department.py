"""Department API contracts."""

from datetime import datetime

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)
    company_id: int | None = Field(default=None, ge=1)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class DepartmentResponse(BaseModel):
    id: int
    company_id: int | None = None
    company_name: str | None = None
    name: str
    description: str | None = None
    is_active: bool
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DepartmentListResponse(BaseModel):
    total: int
    departments: list[DepartmentResponse]
