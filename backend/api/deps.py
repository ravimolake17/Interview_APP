"""FastAPI dependencies for authentication."""

import hashlib
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import decode_access_token
from core.tenancy import is_staff_admin
from models.user import User, UserRole
from repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
        )
    request.state.user = user
    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_staff_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


async def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin access required.",
        )
    return current_user


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user = await UserRepository(db).get_by_id(int(payload["sub"]))
        if user and user.is_active:
            request.state.user = user
            return user
    except Exception:
        return None
    return None


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    if not value:
        return None
    return value[:512]


def get_request_id(request: Request) -> str:
    existing = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
    if existing:
        return existing[:64]
    cached = getattr(request.state, "request_id", None)
    if cached:
        return cached
    generated = uuid.uuid4().hex
    request.state.request_id = generated
    return generated


def get_session_id(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return None


def resolve_location_label(ip_address: str | None) -> str | None:
    """Best-effort coarse location label without external geo lookups."""
    if not ip_address:
        return None
    if ip_address in {"127.0.0.1", "::1"} or ip_address.startswith("127."):
        return "Localhost"
    if (
        ip_address.startswith("10.")
        or ip_address.startswith("192.168.")
        or ip_address.startswith("172.16.")
        or ip_address.startswith("172.17.")
        or ip_address.startswith("172.18.")
        or ip_address.startswith("172.19.")
        or ip_address.startswith("172.2")
        or ip_address.startswith("172.3")
    ):
        return "Private network"
    return None
