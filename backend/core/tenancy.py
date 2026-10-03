"""Shared-database tenant isolation. Never trust a client-supplied company_id."""

from __future__ import annotations

from dataclasses import dataclass

from models.user import User, UserRole


class TenantDenied(Exception):
    """Raised when a user attempts to leave their company boundary."""

    def __init__(self, message: str, status_code: int = 403) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def is_super_admin(user: User) -> bool:
    return user.role == UserRole.SUPERADMIN


def is_company_admin(user: User) -> bool:
    return user.role in {UserRole.COMPANY_ADMIN, UserRole.ADMIN}


def is_staff_admin(user: User) -> bool:
    return is_super_admin(user) or is_company_admin(user)


def normalize_role(role: UserRole | str) -> UserRole:
    value = role.value if isinstance(role, UserRole) else str(role)
    if value == "ADMIN":
        return UserRole.COMPANY_ADMIN
    return UserRole(value)


@dataclass(frozen=True)
class TenantScope:
    user_id: int
    role: UserRole
    company_id: int | None
    unrestricted: bool

    @property
    def filter_company_id(self) -> int | None:
        """WHERE company_id = ? value. None means Super Admin, all companies."""
        return None if self.unrestricted and self.company_id is None else self.company_id

    def write_company_id(self) -> int:
        if self.company_id is None:
            raise TenantDenied("Select a company before creating or updating records.")
        return self.company_id

    def allows(self, resource_company_id: int | None) -> bool:
        if resource_company_id is None:
            return self.unrestricted
        if self.unrestricted and self.company_id is None:
            return True
        return resource_company_id == self.company_id


def build_scope(user: User, requested_company_id: int | None = None) -> TenantScope:
    """Resolve tenant scope from the authenticated user.

    Super Admin may optionally scope to one company.
    Company Admin / HR always use the company_id stored on their user row.
    A mismatched requested_company_id is rejected, not silently ignored.
    """
    if is_super_admin(user):
        return TenantScope(
            user_id=user.id,
            role=user.role,
            company_id=requested_company_id,
            unrestricted=True,
        )
    if user.company_id is None:
        raise TenantDenied("User is not assigned to a company.")
    if requested_company_id is not None and requested_company_id != user.company_id:
        raise TenantDenied("Cannot access another company's data.")
    return TenantScope(
        user_id=user.id,
        role=user.role,
        company_id=user.company_id,
        unrestricted=False,
    )


def parse_company_id(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TenantDenied("Invalid company_id.") from exc
    if parsed <= 0:
        raise TenantDenied("Invalid company_id.")
    return parsed


def same_company(left: int | None, right: int | None) -> bool:
    return left is not None and right is not None and left == right
