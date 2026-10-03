"""SuperAdmin Data Management using existing ORM models and business rules."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.candidate import Candidate, CandidateStatus
from models.department import Department
from models.interview import Interview
from models.job_posting import JobPosting, JobPostingStatus
from models.user import User, UserRole
from repositories.candidate_repository import CandidateRepository
from repositories.department_repository import DepartmentRepository
from repositories.job_posting_repository import JobPostingRepository
from schemas.auth import CreateUserRequest, UpdateUserRequest, UserResponse
from schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from schemas.jobs import JobPostingCreate, JobPostingUpdate, JobPostingResponse
from services.auth_service import AuthService
from services.superadmin_database_service import map_db_error


def _user_payload(user: User) -> dict[str, Any]:
    return UserResponse.model_validate(user).model_dump(mode="json")


def _job_payload(job: JobPosting, applicants: int = 0) -> dict[str, Any]:
    return JobPostingResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        experience=job.experience,
        location=job.location,
        description=job.description,
        skills=list(job.skills or []),
        status=job.status.value if isinstance(job.status, JobPostingStatus) else str(job.status),
        applicants=applicants,
        jd_original_filename=job.jd_original_filename,
        jd_file_url=job.jd_file_url,
        created_at=job.created_at,
        updated_at=job.updated_at,
    ).model_dump(mode="json")


class SuperAdminDataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def catalog(self) -> list[dict[str, Any]]:
        users = int(await self.db.scalar(select(func.count()).select_from(User)) or 0)
        candidates = int(await self.db.scalar(select(func.count()).select_from(Candidate)) or 0)
        jobs = int(await self.db.scalar(select(func.count()).select_from(JobPosting)) or 0)
        departments = int(await self.db.scalar(select(func.count()).select_from(Department)) or 0)
        return [
            {"id": "users", "label": "Users", "rows": users, "create": True, "update": True, "delete": "soft"},
            {"id": "candidates", "label": "Candidates", "rows": candidates, "create": False, "update": True, "delete": False},
            {"id": "jobs", "label": "Jobs", "rows": jobs, "create": True, "update": True, "delete": "conditional"},
            {"id": "departments", "label": "Departments", "rows": departments, "create": True, "update": True, "delete": "soft"},
            {"id": "company", "label": "Company", "rows": 1, "create": False, "update": True, "delete": False},
        ]

    async def list_users(self, *, search: str, limit: int, offset: int) -> dict[str, Any]:
        query = select(User)
        if search:
            like = f"%{search.strip()}%"
            query = query.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
        total = int(await self.db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = (
            await self.db.execute(query.order_by(User.email).limit(limit).offset(offset))
        ).scalars().all()
        return {"total": total, "records": [_user_payload(user) for user in rows]}

    async def create_user(self, payload: CreateUserRequest, actor: User) -> dict[str, Any]:
        try:
            user = await AuthService(self.db).create_user(
                email=str(payload.email),
                full_name=payload.full_name,
                password=payload.password,
                role=UserRole(payload.role),
                acting_admin=actor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _user_payload(user)

    async def update_user(self, user_id: int, payload: UpdateUserRequest, actor: User) -> dict[str, Any]:
        fields = payload.model_dump(exclude_unset=True)
        try:
            user = await AuthService(self.db).update_user(
                user_id,
                acting_admin=actor,
                email=str(fields["email"]) if "email" in fields else None,
                full_name=fields.get("full_name"),
                password=fields.get("password"),
                role=UserRole(payload.role) if "role" in fields and payload.role else None,
                is_active=fields.get("is_active"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _user_payload(user)

    async def list_candidates(self, *, search: str, status: str | None, limit: int, offset: int) -> dict[str, Any]:
        query = select(Candidate)
        if status:
            try:
                query = query.where(Candidate.status == CandidateStatus(status))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid candidate status.") from exc
        if search:
            like = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Candidate.full_name.ilike(like),
                    Candidate.email.ilike(like),
                    Candidate.job_position.ilike(like),
                    Candidate.candidate_id.ilike(like),
                )
            )
        total = int(await self.db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = (
            await self.db.execute(query.order_by(Candidate.created_at.desc()).limit(limit).offset(offset))
        ).scalars().all()
        return {
            "total": total,
            "records": [
                {
                    "id": row.id,
                    "candidate_id": row.candidate_id,
                    "full_name": row.full_name,
                    "email": row.email,
                    "phone": row.phone,
                    "job_position": row.job_position,
                    "status": row.status.value,
                    "resume_score": row.resume_score,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
        }

    async def update_candidate(self, candidate_id: str, values: dict[str, Any]) -> dict[str, Any]:
        candidate = await CandidateRepository(self.db).get_by_candidate_id(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found.")
        old = {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "job_position": candidate.job_position,
            "status": candidate.status.value,
        }
        if "full_name" in values and values["full_name"]:
            candidate.full_name = str(values["full_name"]).strip()
        if "email" in values and values["email"]:
            candidate.email = str(values["email"]).strip()
        if "phone" in values:
            candidate.phone = (str(values["phone"]).strip() or None) if values["phone"] is not None else None
        if "job_position" in values:
            candidate.job_position = (str(values["job_position"]).strip() or None) if values["job_position"] else None
        if "status" in values and values["status"]:
            try:
                candidate.status = CandidateStatus(values["status"])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid candidate status.") from exc
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise map_db_error(exc) from exc
        new = {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "job_position": candidate.job_position,
            "status": candidate.status.value,
        }
        return {
            "id": candidate.candidate_id,
            "old": old,
            "new": new,
            "record": {**new, "id": candidate.id, "candidate_id": candidate.candidate_id, "resume_score": candidate.resume_score},
        }

    async def list_jobs(self, *, search: str, limit: int, offset: int) -> dict[str, Any]:
        query = select(JobPosting)
        if search:
            like = f"%{search.strip()}%"
            query = query.where(
                or_(
                    JobPosting.title.ilike(like),
                    JobPosting.department.ilike(like),
                    JobPosting.location.ilike(like),
                )
            )
        total = int(await self.db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = (
            await self.db.execute(query.order_by(JobPosting.updated_at.desc()).limit(limit).offset(offset))
        ).scalars().all()
        counts = await self._applicant_counts()
        return {
            "total": total,
            "records": [
                _job_payload(job, counts.get((job.title or "").strip().casefold(), 0))
                for job in rows
            ],
        }

    async def create_job(self, payload: JobPostingCreate) -> dict[str, Any]:
        if payload.department:
            await self._require_active_department(payload.department)
        try:
            job = await JobPostingRepository(self.db).create(
                title=payload.title.strip(),
                department=payload.department,
                experience=payload.experience,
                location=payload.location,
                description=payload.description,
                skills=payload.skills or [],
                status=JobPostingStatus(payload.status),
            )
        except IntegrityError as exc:
            await self.db.rollback()
            raise map_db_error(exc) from exc
        return _job_payload(job)

    async def update_job(
        self, job_id: int, payload: JobPostingUpdate, expected_updated_at: datetime | None
    ) -> dict[str, Any]:
        job = await JobPostingRepository(self.db).get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        if (
            expected_updated_at
            and job.updated_at
            and job.updated_at.replace(microsecond=0) != expected_updated_at.replace(microsecond=0)
        ):
            raise HTTPException(
                status_code=409,
                detail="This job was changed by someone else. Reload and try again.",
            )
        old = {
            "title": job.title,
            "department": job.department,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        }
        data = payload.model_dump(exclude_unset=True)
        if "department" in data and data["department"]:
            await self._require_active_department(data["department"])
        if "title" in data and data["title"]:
            job.title = data["title"].strip()
        if "department" in data:
            job.department = data["department"]
        if "experience" in data:
            job.experience = data["experience"]
        if "location" in data:
            job.location = data["location"]
        if "description" in data:
            job.description = data["description"]
        if "skills" in data and data["skills"] is not None:
            job.skills = data["skills"]
        if "status" in data and data["status"]:
            job.status = JobPostingStatus(data["status"])
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise map_db_error(exc) from exc
        new = {
            "title": job.title,
            "department": job.department,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        }
        return {"old": old, "new": new, "record": _job_payload(job)}

    async def close_or_delete_job(self, job_id: int) -> dict[str, Any]:
        job = await JobPostingRepository(self.db).get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        applicants = (await self._applicant_counts()).get((job.title or "").strip().casefold(), 0)
        if applicants:
            job.status = JobPostingStatus.CLOSED
            await self.db.flush()
            return {
                "action": "closed",
                "message": f"This job has {applicants} linked candidates, so it was closed instead of deleted.",
                "record": _job_payload(job, applicants),
            }
        old = {"title": job.title, "status": job.status.value if hasattr(job.status, "value") else str(job.status)}
        await JobPostingRepository(self.db).delete(job)
        return {"action": "deleted", "old": old}

    async def list_departments(self, *, search: str, limit: int, offset: int) -> dict[str, Any]:
        query = select(Department)
        if search:
            query = query.where(Department.name.ilike(f"%{search.strip()}%"))
        total = int(await self.db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = (
            await self.db.execute(query.order_by(Department.sort_order, Department.name).limit(limit).offset(offset))
        ).scalars().all()
        records = []
        for row in rows:
            jobs = int(
                await self.db.scalar(
                    select(func.count())
                    .select_from(JobPosting)
                    .where(func.lower(JobPosting.department) == row.name.lower())
                )
                or 0
            )
            payload = DepartmentResponse.model_validate(row).model_dump(mode="json")
            payload["job_count"] = jobs
            records.append(payload)
        return {"total": total, "records": records}

    async def create_department(self, payload: DepartmentCreate) -> dict[str, Any]:
        repo = DepartmentRepository(self.db)
        if await repo.get_by_name(payload.name):
            raise HTTPException(status_code=409, detail="A department with this name already exists.")
        try:
            row = await repo.create(
                name=payload.name,
                description=payload.description,
                sort_order=payload.sort_order,
                is_active=payload.is_active,
            )
        except IntegrityError as exc:
            await self.db.rollback()
            raise map_db_error(exc) from exc
        return DepartmentResponse.model_validate(row).model_dump(mode="json")

    async def update_department(
        self, department_id: int, payload: DepartmentUpdate, expected_updated_at: datetime | None
    ) -> dict[str, Any]:
        repo = DepartmentRepository(self.db)
        row = await repo.get_by_id(department_id)
        if not row:
            raise HTTPException(status_code=404, detail="Department not found.")
        if (
            expected_updated_at
            and row.updated_at
            and row.updated_at.replace(microsecond=0) != expected_updated_at.replace(microsecond=0)
        ):
            raise HTTPException(
                status_code=409,
                detail="This department was changed by someone else. Reload and try again.",
            )
        old = {"name": row.name, "is_active": row.is_active}
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"]:
            existing = await repo.get_by_name(data["name"])
            if existing and existing.id != row.id:
                raise HTTPException(status_code=409, detail="A department with this name already exists.")
            row.name = data["name"].strip()
        if "description" in data:
            row.description = (data["description"] or "").strip() or None
        if "is_active" in data and data["is_active"] is not None:
            row.is_active = data["is_active"]
        if "sort_order" in data and data["sort_order"] is not None:
            row.sort_order = data["sort_order"]
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise map_db_error(exc) from exc
        new = {"name": row.name, "is_active": row.is_active}
        return {"old": old, "new": new, "record": DepartmentResponse.model_validate(row).model_dump(mode="json")}

    async def deactivate_department(self, department_id: int) -> dict[str, Any]:
        row = await DepartmentRepository(self.db).get_by_id(department_id)
        if not row:
            raise HTTPException(status_code=404, detail="Department not found.")
        jobs = int(
            await self.db.scalar(
                select(func.count())
                .select_from(JobPosting)
                .where(func.lower(JobPosting.department) == row.name.lower())
            )
            or 0
        )
        row.is_active = False
        await self.db.flush()
        message = "Department deactivated. Job postings keep this department name until they are edited."
        if jobs:
            message = (
                f"Cannot remove this department from history. {jobs} jobs still list it; it was deactivated instead."
            )
        return {
            "action": "deactivated",
            "job_count": jobs,
            "message": message,
            "record": DepartmentResponse.model_validate(row).model_dump(mode="json"),
        }

    async def _require_active_department(self, name: str) -> Department:
        row = await DepartmentRepository(self.db).get_by_name(name)
        if not row or not row.is_active:
            raise HTTPException(status_code=400, detail="Choose an active department from the catalog.")
        return row

    async def _applicant_counts(self) -> dict[str, int]:
        result = await self.db.execute(
            select(Candidate.job_position, func.count())
            .where(Candidate.job_position.is_not(None))
            .group_by(Candidate.job_position)
        )
        counts: dict[str, int] = {}
        for position, count in result.all():
            if position:
                counts[position.strip().casefold()] = int(count)
        return counts

    async def related_impact(self, entity: str, record_id: str) -> dict[str, Any]:
        if entity == "departments":
            row = await DepartmentRepository(self.db).get_by_id(int(record_id))
            if not row:
                raise HTTPException(status_code=404, detail="Department not found.")
            jobs = int(
                await self.db.scalar(
                    select(func.count())
                    .select_from(JobPosting)
                    .where(func.lower(JobPosting.department) == row.name.lower())
                )
                or 0
            )
            return {"can_hard_delete": False, "related": {"jobs": jobs}, "recommendation": "deactivate"}
        if entity == "jobs":
            job = await JobPostingRepository(self.db).get_by_id(int(record_id))
            if not job:
                raise HTTPException(status_code=404, detail="Job not found.")
            applicants = (await self._applicant_counts()).get((job.title or "").strip().casefold(), 0)
            return {
                "can_hard_delete": applicants == 0,
                "related": {"candidates": applicants},
                "recommendation": "close" if applicants else "delete",
            }
        if entity == "candidates":
            interviews = int(
                await self.db.scalar(
                    select(func.count()).select_from(Interview).where(Interview.candidate_id == record_id)
                )
                or 0
            )
            return {"can_hard_delete": False, "related": {"interviews": interviews}, "recommendation": "set_status"}
        if entity == "users":
            return {"can_hard_delete": False, "related": {}, "recommendation": "deactivate"}
        raise HTTPException(status_code=404, detail="Unknown entity.")
