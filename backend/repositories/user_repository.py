"""User data access."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.user import User, UserRole


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(
            select(User).options(selectinload(User.company)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.email == email.casefold())
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        full_name: str,
        password_hash: str,
        role: UserRole = UserRole.HR,
        company_id: int | None = None,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email.casefold().strip(),
            full_name=full_name.strip(),
            password_hash=password_hash,
            role=role,
            company_id=company_id,
            is_active=is_active,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def update_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def list_all(self, *, company_id: int | None = None) -> list[User]:
        query = select(User).options(selectinload(User.company)).order_by(User.email)
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        user: User,
        *,
        email: str | None = None,
        full_name: str | None = None,
        job_title: str | None = None,
        phone: str | None = None,
        password_hash: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        company_id: int | None | object = ...,
    ) -> User:
        if email is not None:
            user.email = email.casefold().strip()
        if full_name is not None:
            user.full_name = full_name.strip()
        if job_title is not None:
            user.job_title = job_title.strip() or None
        if phone is not None:
            user.phone = phone.strip() or None
        if password_hash is not None:
            user.password_hash = password_hash
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        if company_id is not ...:
            user.company_id = company_id
        await self.db.flush()
        return user
