"""Department persistence."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.department import Department


class DepartmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_all(self, *, active_only: bool = False, company_id: int | None = None) -> list[Department]:
        query = (
            select(Department)
            .options(selectinload(Department.company))
            .order_by(Department.sort_order, Department.name)
        )
        if company_id is not None:
            query = query.where(Department.company_id == company_id)
        if active_only:
            query = query.where(Department.is_active.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, department_id: int) -> Department | None:
        result = await self.db.execute(select(Department).where(Department.id == department_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, *, company_id: int | None = None) -> Department | None:
        query = select(Department).where(func.lower(Department.name) == name.strip().lower())
        if company_id is not None:
            query = query.where(Department.company_id == company_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        description: str | None = None,
        sort_order: int = 0,
        is_active: bool = True,
        company_id: int,
    ) -> Department:
        row = Department(
            company_id=company_id,
            name=name.strip(),
            description=(description or "").strip() or None,
            sort_order=sort_order,
            is_active=is_active,
        )
        self.db.add(row)
        await self.db.flush()
        return row
