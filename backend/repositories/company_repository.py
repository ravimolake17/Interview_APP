"""Company persistence."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.company import Company


class CompanyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_all(self) -> list[Company]:
        result = await self.db.execute(select(Company).order_by(Company.id))
        return list(result.scalars().all())

    async def get_by_id(self, company_id: int) -> Company | None:
        result = await self.db.execute(select(Company).where(Company.id == company_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Company | None:
        result = await self.db.execute(
            select(Company).where(func.upper(Company.code) == code.strip().upper())
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        code: str,
        logo: str | None = None,
        status: str = "active",
    ) -> Company:
        row = Company(
            name=name.strip(),
            code=code.strip().upper(),
            logo=(logo or "").strip() or None,
            status=status,
        )
        self.db.add(row)
        await self.db.flush()
        return row
