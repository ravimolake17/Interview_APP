"""Login, refresh, logout, and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_admin, get_current_user
from core.database import get_db
from core.security import hash_refresh_token
from core.tenancy import is_super_admin, normalize_role
from models.user import User, UserRole
from repositories.refresh_token_repository import RefreshTokenRepository
from repositories.user_repository import UserRepository
from schemas.auth import (
    CreateUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from services.audit_service import AuditService
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _token_response(user: User, access: str, refresh: str) -> TokenResponse:
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    auth = AuthService(db)
    try:
        user = await auth.authenticate(payload.email, payload.password)
        access, refresh = await auth.issue_tokens(user)
        await db.commit()
    except ValueError as exc:
        await AuditService(db).log(
            action="USER_LOGIN",
            entity_type="user",
            entity_id=None,
            user=None,
            request=request,
            status="FAILURE",
            details={"email": str(payload.email)},
            message=f"Failed login attempt for {payload.email}.",
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    await AuditService(db).log(
        action="USER_LOGIN",
        entity_type="user",
        entity_id=str(user.id),
        user=user,
        request=request,
        status="SUCCESS",
        message=f"{user.full_name} signed in.",
    )
    await db.commit()
    return _token_response(user, access, refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    auth = AuthService(db)
    try:
        user, access, refresh = await auth.rotate_refresh_token(payload.refresh_token)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _token_response(user, access, refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def logout(
    payload: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    token_hash = hash_refresh_token(payload.refresh_token)
    record = await RefreshTokenRepository(db).get_valid_by_hash(token_hash)
    user = await UserRepository(db).get_by_id(record.user_id) if record else None

    auth = AuthService(db)
    await auth.logout(payload.refresh_token)

    await AuditService(db).log(
        action="USER_LOGOUT",
        entity_type="user",
        entity_id=str(user.id) if user else None,
        user=user,
        request=request,
        ip_address=get_client_ip(request),
        message=f"{user.full_name} signed out." if user else "User signed out.",
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> UserListResponse:
    """List users. Company Admin/HR admins only see their own company."""
    repo = UserRepository(db)
    if is_super_admin(admin):
        users = await repo.list_all()
    else:
        users = await repo.list_all(company_id=admin.company_id)
        users = [user for user in users if user.role != UserRole.SUPERADMIN]
    return UserListResponse(
        total=len(users),
        users=[UserResponse.model_validate(u) for u in users],
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> UserResponse:
    """Create a new HR or admin user in the database (admin only)."""
    auth = AuthService(db)
    try:
        user = await auth.create_user(
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            role=normalize_role(payload.role),
            acting_admin=admin,
            company_id=payload.company_id,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await AuditService(db).log(
        action="USER_CREATED",
        entity_type="user",
        entity_id=str(user.id),
        user=admin,
        request=request,
        ip_address=get_client_ip(request),
        details={"email": user.email, "role": user.role.value, "full_name": user.full_name},
        message=(
            f"{admin.full_name} created {user.role.value} user {user.full_name} "
            f"({user.email})."
        ),
    )
    await db.commit()
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> UserResponse:
    """Update user email, name, password, role, or active status (admin only)."""
    auth = AuthService(db)
    fields_set = payload.model_fields_set
    if not fields_set:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update.")

    before = await UserRepository(db).get_by_id(user_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    before_snapshot = {
        "email": before.email,
        "full_name": before.full_name,
        "role": before.role.value,
        "is_active": before.is_active,
    }

    try:
        user = await auth.update_user(
            user_id,
            acting_admin=admin,
            email=payload.email if "email" in fields_set else None,
            full_name=payload.full_name if "full_name" in fields_set else None,
            password=payload.password if "password" in fields_set else None,
            role=normalize_role(payload.role) if "role" in fields_set and payload.role else None,
            is_active=payload.is_active if "is_active" in fields_set else None,
            company_id=payload.company_id if "company_id" in fields_set else ...,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    change_bits: list[str] = []
    changes: list[dict] = []
    if "email" in fields_set and before_snapshot["email"] != user.email:
        change_bits.append(f"email {before_snapshot['email']} → {user.email}")
        changes.append({"field": "email", "from": before_snapshot["email"], "to": user.email})
    if "full_name" in fields_set and before_snapshot["full_name"] != user.full_name:
        change_bits.append(f"name {before_snapshot['full_name']} → {user.full_name}")
        changes.append({"field": "full_name", "from": before_snapshot["full_name"], "to": user.full_name})
    if "role" in fields_set and before_snapshot["role"] != user.role.value:
        change_bits.append(f"role {before_snapshot['role']} → {user.role.value}")
        changes.append({"field": "role", "from": before_snapshot["role"], "to": user.role.value})
    if "is_active" in fields_set and before_snapshot["is_active"] != user.is_active:
        from_label = "active" if before_snapshot["is_active"] else "inactive"
        to_label = "active" if user.is_active else "inactive"
        change_bits.append(f"status {from_label} → {to_label}")
        changes.append({"field": "is_active", "from": from_label, "to": to_label})
    if "password" in fields_set:
        change_bits.append("password reset")
        changes.append({"field": "password", "from": "••••", "to": "reset"})

    if not change_bits:
        change_bits.append("no field values changed")

    await AuditService(db).log(
        action="USER_UPDATED",
        entity_type="user",
        entity_id=str(user.id),
        user=admin,
        request=request,
        old_value=before_snapshot,
        new_value={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
        },
        details={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "previous": before_snapshot,
            "updated_fields": sorted(fields_set),
            "changes": changes,
        },
        message=(
            f"{admin.full_name} updated user {before_snapshot['full_name']} "
            f"({user.email}): {', '.join(change_bits)}."
        ),
    )
    await db.commit()
    return UserResponse.model_validate(user)
