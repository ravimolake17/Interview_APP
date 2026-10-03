"""JWT login, refresh, and logout."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from core.security import (
    create_access_token,
    generate_refresh_token_value,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from models.company import CompanyStatus
from models.user import User, UserRole
from repositories.refresh_token_repository import RefreshTokenRepository
from repositories.user_repository import UserRepository
from core.tenancy import is_company_admin, is_super_admin, normalize_role


class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if not user or not user.is_active:
            raise ValueError("Invalid email or password.")
        if not is_super_admin(user):
            company = user.company
            if user.company_id is None:
                raise ValueError("User is not assigned to a company.")
            if company is not None and company.status != CompanyStatus.ACTIVE:
                raise ValueError("This company account is inactive.")
        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password.")
        await self.users.update_last_login(user)
        return user

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        access = create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
            settings=self.settings,
        )
        refresh_value = generate_refresh_token_value()
        await self.refresh_tokens.create(
            user.id,
            hash_refresh_token(refresh_value),
            refresh_token_expiry(self.settings),
        )
        return access, refresh_value

    async def rotate_refresh_token(self, refresh_token: str) -> tuple[User, str, str]:
        """Issue a new access token without rotating the refresh token.

        Rotating on every refresh caused mid-session logouts: parallel 401s or
        a second tab reused the previous refresh value after it was revoked.
        The same refresh token stays valid until logout or expiry; active use
        slides the 7-day window.
        """
        token_hash = hash_refresh_token(refresh_token)
        record = await self.refresh_tokens.get_valid_by_hash(token_hash)
        if not record:
            raise ValueError("Invalid or expired refresh token.")

        user = await self.users.get_by_id(record.user_id)
        if not user or not user.is_active:
            raise ValueError("User account is inactive.")

        record.expires_at = refresh_token_expiry(self.settings)
        access = create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
            settings=self.settings,
        )
        return user, access, refresh_token

    async def logout(self, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        record = await self.refresh_tokens.get_valid_by_hash(token_hash)
        if record:
            await self.refresh_tokens.revoke(record)

    async def create_user(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
        role: UserRole,
        acting_admin: User,
        company_id: int | None = None,
        is_active: bool = True,
    ) -> User:
        role = normalize_role(role)
        if is_super_admin(acting_admin):
            allowed = {UserRole.HR, UserRole.COMPANY_ADMIN, UserRole.SUPERADMIN}
        elif is_company_admin(acting_admin):
            allowed = {UserRole.HR}
        else:
            allowed = set()
        if role not in allowed:
            raise ValueError("You are not allowed to create a user with that role.")
        if role == UserRole.SUPERADMIN:
            company_id = None
        elif is_super_admin(acting_admin):
            if company_id is None:
                raise ValueError("Assign this user to a company.")
        else:
            company_id = acting_admin.company_id
            if company_id is None:
                raise ValueError("You are not assigned to a company.")
        existing = await self.users.get_by_email(email)
        if existing:
            raise ValueError("A user with this email already exists.")
        return await self.users.create(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            company_id=company_id,
            is_active=is_active,
        )

    async def update_user(
        self,
        user_id: int,
        *,
        acting_admin: User,
        email: str | None = None,
        full_name: str | None = None,
        password: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        company_id: int | None | object = ...,
    ) -> User:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")

        if not is_super_admin(acting_admin):
            if user.company_id != acting_admin.company_id:
                raise ValueError("User not found.")
            if user.role == UserRole.SUPERADMIN:
                raise ValueError("Only SuperAdmin can manage Super Admin accounts.")
            if is_company_admin(user) and user.id != acting_admin.id:
                raise ValueError("Only SuperAdmin can manage Company Admin accounts.")
            company_id = ...

        if user.id == acting_admin.id:
            if is_active is False:
                raise ValueError("You cannot deactivate your own account.")
            if role is not None and normalize_role(role) != acting_admin.role:
                raise ValueError("You cannot change your own role.")

        if role is not None:
            role = normalize_role(role)
            if not is_super_admin(acting_admin) and role != UserRole.HR:
                raise ValueError("Only SuperAdmin can assign admin roles.")
            if role == UserRole.SUPERADMIN:
                company_id = None
            elif is_super_admin(acting_admin) and company_id is ... and user.company_id is None:
                raise ValueError("Assign this user to a company.")

        if role is not None and user.role == UserRole.SUPERADMIN and role != UserRole.SUPERADMIN:
            remaining = [
                row
                for row in await self.users.list_all()
                if row.role == UserRole.SUPERADMIN and row.is_active and row.id != user.id
            ]
            if not remaining:
                raise ValueError("At least one SuperAdmin must remain active.")

        if is_active is False and user.role == UserRole.SUPERADMIN:
            remaining = [
                row
                for row in await self.users.list_all()
                if row.role == UserRole.SUPERADMIN and row.is_active and row.id != user.id
            ]
            if not remaining:
                raise ValueError("At least one SuperAdmin must remain active.")

        if email is not None and email.casefold() != user.email:
            existing = await self.users.get_by_email(email)
            if existing and existing.id != user.id:
                raise ValueError("A user with this email already exists.")

        password_hash = hash_password(password) if password else None
        return await self.users.update(
            user,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
            company_id=company_id,
        )
