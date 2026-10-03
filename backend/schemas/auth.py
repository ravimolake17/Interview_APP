"""Pydantic schemas for authentication."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from schemas.company import CompanyResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    job_title: str | None = None
    phone: str | None = None
    role: str
    is_active: bool = True
    company_id: int | None = None
    company: CompanyResponse | None = None
    last_login_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="HR", pattern="^(HR|ADMIN|COMPANY_ADMIN|SUPERADMIN)$")
    company_id: int | None = None
    is_active: bool = True


class UserListResponse(BaseModel):
    total: int
    users: list[UserResponse]


class UpdateUserRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = Field(default=None, pattern="^(HR|ADMIN|COMPANY_ADMIN|SUPERADMIN)$")
    is_active: bool | None = None
    company_id: int | None = None
