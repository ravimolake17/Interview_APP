"""Tenant isolation against the live PostgreSQL database (TEST 1-7)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.security import hash_password
from core.tenancy import TenantDenied, build_scope
from models.candidate import Candidate, CandidateStatus
from models.company import Company
from models.user import User, UserRole
from repositories.candidate_repository import CandidateRepository
from repositories.user_repository import UserRepository
from services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


async def _company(db, code: str) -> Company:
    result = await db.execute(select(Company).where(Company.code == code))
    company = result.scalar_one_or_none()
    if company is None:
        pytest.skip(f"Company {code} is not migrated yet. Run alembic upgrade head.")
    return company


async def _ensure_user(db, *, email: str, role: UserRole, company_id: int | None, password: str) -> User:
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user is None:
        user = await repo.create(
            email=email,
            full_name=email.split("@")[0],
            password_hash=hash_password(password),
            role=role,
            company_id=company_id,
        )
    else:
        user.role = role
        user.company_id = company_id
        user.is_active = True
        user.password_hash = hash_password(password)
        await db.flush()
    return user


async def _ensure_candidate(db, *, company_id: int, suffix: str) -> Candidate:
    candidate_id = f"TNT-{company_id}-{suffix}"
    repo = CandidateRepository(db)
    existing = await repo.get_by_candidate_id(candidate_id)
    if existing:
        existing.company_id = company_id
        await db.flush()
        return existing
    row = Candidate(
        candidate_id=candidate_id,
        company_id=company_id,
        full_name=f"Tenant {suffix}",
        email=f"{suffix.lower()}.{company_id}@tenancy.test",
        resume_score=80,
        status=CandidateStatus.SHORTLISTED,
    )
    db.add(row)
    await db.flush()
    return row


async def test_tenant_isolation_scenarios():
    async with AsyncSessionLocal() as db:
        parkon = await _company(db, "RRPARKON")
        kabel = await _company(db, "RRKABEL")
        password = "TenancyTest!1"
        parkon_hr = await _ensure_user(
            db, email="tenancy.parkon.hr@test.local", role=UserRole.HR, company_id=parkon.id, password=password
        )
        kabel_hr = await _ensure_user(
            db, email="tenancy.kabel.hr@test.local", role=UserRole.HR, company_id=kabel.id, password=password
        )
        parkon_admin = await _ensure_user(
            db,
            email="tenancy.parkon.admin@test.local",
            role=UserRole.COMPANY_ADMIN,
            company_id=parkon.id,
            password=password,
        )
        kabel_admin = await _ensure_user(
            db,
            email="tenancy.kabel.admin@test.local",
            role=UserRole.COMPANY_ADMIN,
            company_id=kabel.id,
            password=password,
        )
        superadmin = await UserRepository(db).get_by_email("superadmin@rrglobal.com")
        if superadmin is None:
            pytest.skip("SuperAdmin seed is missing.")
        parkon_cand = await _ensure_candidate(db, company_id=parkon.id, suffix="PARKON")
        kabel_cand = await _ensure_candidate(db, company_id=kabel.id, suffix="KABEL")
        await db.commit()

        repo = CandidateRepository(db)

        # TEST 1
        parkon_rows = await repo.list_by_status(None, company_id=build_scope(parkon_hr).filter_company_id)
        parkon_ids = {row.candidate_id for row in parkon_rows}
        assert parkon_cand.candidate_id in parkon_ids
        assert kabel_cand.candidate_id not in parkon_ids
        assert await repo.get_by_candidate_id(kabel_cand.candidate_id, company_id=parkon.id) is None

        # TEST 2
        kabel_rows = await repo.list_by_status(None, company_id=build_scope(kabel_hr).filter_company_id)
        kabel_ids = {row.candidate_id for row in kabel_rows}
        assert kabel_cand.candidate_id in kabel_ids
        assert parkon_cand.candidate_id not in kabel_ids

        # TEST 3
        assert build_scope(parkon_admin).filter_company_id == parkon.id
        with pytest.raises(TenantDenied):
            build_scope(parkon_admin, requested_company_id=kabel.id)

        # TEST 4
        assert build_scope(kabel_admin).filter_company_id == kabel.id
        with pytest.raises(TenantDenied):
            build_scope(kabel_admin, requested_company_id=parkon.id)

        # TEST 5
        super_scope = build_scope(superadmin)
        assert super_scope.filter_company_id is None
        all_ids = {
            row.candidate_id
            for row in await repo.list_by_status(None, company_id=super_scope.filter_company_id)
        }
        assert parkon_cand.candidate_id in all_ids
        assert kabel_cand.candidate_id in all_ids

        # TEST 6
        created = await AuthService(db).create_user(
            email=f"kabel.hr.{uuid.uuid4().hex[:8]}@test.local",
            full_name="Kabel HR Created",
            password=password,
            role=UserRole.HR,
            acting_admin=superadmin,
            company_id=kabel.id,
        )
        await db.commit()
        assert created.company_id == kabel.id
        assert build_scope(created).filter_company_id == kabel.id
        with pytest.raises(TenantDenied):
            build_scope(created, requested_company_id=parkon.id)

        # TEST 7
        with pytest.raises(TenantDenied):
            build_scope(parkon_hr, requested_company_id=kabel.id)
        with pytest.raises(TenantDenied):
            build_scope(kabel_hr, requested_company_id=parkon.id)
        same = build_scope(parkon_hr, requested_company_id=parkon.id)
        assert same.filter_company_id == parkon.id
