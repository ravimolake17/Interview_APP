"""Company catalog and bootstrap of per-tenant defaults."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.application_setting import ApplicationSetting
from models.company import Company, CompanyStatus
from models.department import Department
from repositories.company_repository import CompanyRepository


class CompanyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = CompanyRepository(db)

    async def list_companies(self) -> list[Company]:
        return await self.repo.list_all()

    async def get(self, company_id: int) -> Company | None:
        return await self.repo.get_by_id(company_id)

    async def create(
        self,
        *,
        name: str,
        code: str,
        logo: str | None = None,
        status: str = CompanyStatus.ACTIVE,
        template_company_id: int | None = None,
    ) -> Company:
        existing = await self.repo.get_by_code(code)
        if existing:
            raise ValueError("A company with this code already exists.")
        company = await self.repo.create(name=name, code=code, logo=logo, status=status)
        await self._clone_departments(company.id, template_company_id)
        await self._clone_settings(company.id, template_company_id)
        return company

    async def update(
        self,
        company: Company,
        *,
        name: str | None = None,
        code: str | None = None,
        logo: str | None = None,
        status: str | None = None,
    ) -> Company:
        if name is not None:
            company.name = name.strip()
        if code is not None:
            duplicate = await self.repo.get_by_code(code)
            if duplicate and duplicate.id != company.id:
                raise ValueError("A company with this code already exists.")
            company.code = code.strip().upper()
        if logo is not None:
            company.logo = logo.strip() or None
        if status is not None:
            company.status = status
        await self.db.flush()
        return company

    async def _clone_departments(self, company_id: int, template_company_id: int | None) -> None:
        if template_company_id is None:
            return
        result = await self.db.execute(
            select(Department).where(Department.company_id == template_company_id).order_by(Department.sort_order)
        )
        for row in result.scalars().all():
            self.db.add(
                Department(
                    company_id=company_id,
                    name=row.name,
                    description=row.description,
                    is_active=row.is_active,
                    sort_order=row.sort_order,
                )
            )
        await self.db.flush()

    async def _clone_settings(self, company_id: int, template_company_id: int | None) -> None:
        source_key = f"company:{template_company_id}" if template_company_id else "global"
        result = await self.db.execute(
            select(ApplicationSetting).where(
                ApplicationSetting.scope_key == source_key,
                ApplicationSetting.namespace.in_(
                    ("interview_availability", "screening_policy", "notifications")
                ),
            )
        )
        target_key = f"company:{company_id}"
        for row in result.scalars().all():
            self.db.add(
                ApplicationSetting(
                    scope_key=target_key,
                    namespace=row.namespace,
                    data=dict(row.data or {}),
                    updated_by_user_id=row.updated_by_user_id,
                )
            )
        await self.db.flush()
