"""Job postings CRUD for HR dashboard."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_user
from api.tenancy import get_tenant_scope, require_scope_allows, require_write_company_id
from core.database import get_db
from core.tenancy import TenantScope
from models.candidate import Candidate
from models.job_posting import JobPosting, JobPostingStatus
from models.user import User
from repositories.job_posting_repository import JobPostingRepository
from schemas.jobs import (
    JobDuplicateCheckResponse,
    JobPostingCreate,
    JobPostingListResponse,
    JobPostingResponse,
    JobPostingUpdate,
)
from services.audit_service import AuditService
from services.job_posting_service import (
    JobDuplicateError,
    find_duplicate_job,
    store_job_from_jd,
)
from services.job_position import apply_jd_content_title, is_filename_as_title

router = APIRouter(prefix="/jobs", tags=["Job Postings"])


async def _applicants_by_title(
    db: AsyncSession, company_id: int | None = None
) -> dict[str, list[dict[str, str]]]:
    query = select(Candidate.job_position, Candidate.candidate_id, Candidate.full_name).where(
        Candidate.job_position.is_not(None)
    )
    if company_id is not None:
        query = query.where(Candidate.company_id == company_id)
    result = await db.execute(query)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for position, candidate_id, full_name in result.all():
        title = str(position or "").strip()
        if not title:
            continue
        grouped[title.casefold()].append(
            {
                "candidate_id": str(candidate_id),
                "full_name": str(full_name or "Candidate").strip() or "Candidate",
            }
        )
    return dict(grouped)


def _to_response(
    job: JobPosting, applicants_by_title: dict[str, list[dict[str, str]]]
) -> JobPostingResponse:
    rows = applicants_by_title.get(job.title.strip().casefold(), [])
    return JobPostingResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        experience=job.experience,
        location=job.location,
        description=job.description,
        skills=list(job.skills or []),
        status=job.status.value if isinstance(job.status, JobPostingStatus) else str(job.status),
        applicants=len(rows),
        applicant_list=rows,
        jd_original_filename=job.jd_original_filename,
        jd_file_url=job.jd_file_url,
        jd_text=job.jd_text,
        parsed_jd=job.parsed_jd,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=JobPostingListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> JobPostingListResponse:
    repo = JobPostingRepository(db)
    jobs = await repo.list_all(company_id=scope.filter_company_id)
    applicants_by_title = await _applicants_by_title(db, scope.filter_company_id)
    payload = [_to_response(job, applicants_by_title) for job in jobs]
    return JobPostingListResponse(total=len(payload), jobs=payload)


def _job_status_label(value) -> str:
    if isinstance(value, JobPostingStatus):
        return value.value
    return str(value) if value is not None else "—"


def _format_job_value(field: str, value) -> str:
    if value is None or value == "":
        return "—"
    if field == "skills":
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) if value else "—"
        return str(value)
    if field in {"description", "jd_text"} and isinstance(value, str) and len(value) > 80:
        return f"{value[:77]}…"
    if field == "parsed_jd":
        return "updated JD parse data"
    return str(value)


def _job_create_message(user_name: str, job: JobPosting) -> str:
    status = _job_status_label(job.status)
    bits = [f"status {status}"]
    if job.department:
        bits.append(f"department {job.department}")
    if job.location:
        bits.append(f"location {job.location}")
    if job.experience:
        bits.append(f"experience {job.experience}")
    return f"{user_name} created job “{job.title}” ({', '.join(bits)})."


def _job_update_snapshot(job: JobPosting) -> dict:
    return {
        "title": job.title,
        "department": job.department,
        "experience": job.experience,
        "location": job.location,
        "description": job.description,
        "skills": list(job.skills or []),
        "status": _job_status_label(job.status),
        "jd_original_filename": job.jd_original_filename,
        "jd_file_url": job.jd_file_url,
        "jd_text": job.jd_text,
        "parsed_jd": job.parsed_jd,
    }


def _build_job_changes(before: dict, after: dict, fields: list[str]) -> list[dict]:
    changes: list[dict] = []
    for field in fields:
        old = before.get(field)
        new = after.get(field)
        if field == "skills":
            old_key = [str(x).casefold() for x in (old or [])]
            new_key = [str(x).casefold() for x in (new or [])]
            if old_key == new_key:
                continue
        elif old == new:
            continue
        changes.append(
            {
                "field": field,
                "from": _format_job_value(field, old),
                "to": _format_job_value(field, new),
            }
        )
    return changes


def _job_update_message(user_name: str, title: str, changes: list[dict]) -> str:
    if not changes:
        return f"{user_name} updated job “{title}” (no field values changed)."

    # Prefer a natural status-only sentence when that is the only change.
    if len(changes) == 1 and changes[0]["field"] == "status":
        change = changes[0]
        return (
            f"{user_name} updated “{title}” job status from {change['from']} to {change['to']}."
        )

    parts = []
    for change in changes:
        label = change["field"].replace("_", " ")
        if change["field"] in {"description", "jd_text", "parsed_jd", "jd_file_url"}:
            parts.append(f"{label} updated")
        else:
            parts.append(f"{label} {change['from']} → {change['to']}")
    return f"{user_name} updated job “{title}”: {'; '.join(parts)}."


def _duplicate_http_error(exc: JobDuplicateError, applicants_by_title: dict) -> HTTPException:
    existing = _to_response(exc.job, applicants_by_title)
    return HTTPException(
        status_code=409,
        detail={
            "code": "JOB_DUPLICATE",
            "reason": exc.reason,
            "message": str(exc),
            "existing": existing.model_dump(mode="json"),
        },
    )


@router.get("/duplicates", response_model=JobDuplicateCheckResponse)
async def check_job_duplicate(
    title: str | None = None,
    jd_file_url: str | None = None,
    db: AsyncSession = Depends(get_db),
    scope: TenantScope = Depends(get_tenant_scope),
) -> JobDuplicateCheckResponse:
    company_id = scope.filter_company_id
    if company_id is None:
        raise HTTPException(status_code=400, detail="Select a company before checking jobs.")
    duplicate = await find_duplicate_job(
        db,
        title=title,
        jd_file_url=jd_file_url,
        company_id=company_id,
    )
    if not duplicate:
        return JobDuplicateCheckResponse(duplicate=False)
    applicants_by_title = await _applicants_by_title(db, company_id)
    return JobDuplicateCheckResponse(
        duplicate=True,
        reason=duplicate.reason,  # type: ignore[arg-type]
        existing=_to_response(duplicate.job, applicants_by_title),
    )


@router.post("", response_model=JobPostingResponse, status_code=201)
async def create_job(
    payload: JobPostingCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> JobPostingResponse:
    company_id = require_write_company_id(scope)
    applicants_by_title = await _applicants_by_title(db, company_id)
    try:
        if payload.parsed_jd or payload.jd_text or payload.jd_file_url:
            job = await store_job_from_jd(
                db,
                jd_text=payload.jd_text,
                jd_original_filename=payload.jd_original_filename,
                jd_file_url=payload.jd_file_url,
                parsed_jd=payload.parsed_jd,
                title_override=payload.title,
                department=payload.department or "Hiring",
                location=payload.location or "India",
                experience=payload.experience,
                description=payload.description,
                skills=payload.skills or None,
                company_id=company_id,
                on_duplicate=payload.on_duplicate,
            )
            job.department = payload.department or job.department
            job.experience = payload.experience or job.experience
            job.location = payload.location or job.location
            if payload.description:
                job.description = payload.description
            if payload.skills:
                job.skills = payload.skills
            job.status = JobPostingStatus(payload.status)
            await db.flush()
        else:
            title = payload.title.strip()
            duplicate = await find_duplicate_job(db, title=title, company_id=company_id)
            if duplicate:
                if payload.on_duplicate == "replace":
                    job = duplicate.job
                    job.department = payload.department or job.department
                    job.experience = payload.experience or job.experience
                    job.location = payload.location or job.location
                    job.description = payload.description or job.description
                    if payload.skills:
                        job.skills = payload.skills
                    job.status = JobPostingStatus(payload.status)
                    await db.flush()
                elif payload.on_duplicate == "rename":
                    raise HTTPException(
                        status_code=400,
                        detail="Choose a different job title to save without replacing the existing one.",
                    )
                else:
                    raise _duplicate_http_error(
                        JobDuplicateError(duplicate.job, duplicate.reason),
                        applicants_by_title,
                    )
            else:
                repo = JobPostingRepository(db)
                job = await repo.create(
                    company_id=company_id,
                    title=title,
                    department=payload.department,
                    experience=payload.experience,
                    location=payload.location,
                    description=payload.description,
                    skills=payload.skills or [],
                    status=JobPostingStatus(payload.status),
                    jd_original_filename=payload.jd_original_filename,
                    jd_file_url=payload.jd_file_url,
                    jd_text=payload.jd_text,
                    parsed_jd=payload.parsed_jd,
                )
    except JobDuplicateError as exc:
        raise _duplicate_http_error(exc, applicants_by_title) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status_label = _job_status_label(job.status)
    await AuditService(db).log(
        action="JOB_CREATED",
        entity_type="job",
        entity_id=str(job.id),
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "title": job.title,
            "department": job.department,
            "status": status_label,
            "location": job.location,
            "experience": job.experience,
        },
        message=_job_create_message(current_user.full_name, job),
        company_id=job.company_id,
    )
    await db.commit()
    await db.refresh(job)
    applicants_by_title = await _applicants_by_title(db, scope.filter_company_id)
    return _to_response(job, applicants_by_title)


@router.patch("/{job_id}", response_model=JobPostingResponse)
async def update_job(
    job_id: int,
    payload: JobPostingUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> JobPostingResponse:
    repo = JobPostingRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    require_scope_allows(scope, job.company_id)

    data = payload.model_dump(exclude_unset=True)
    before = _job_update_snapshot(job)

    if "title" in data and data["title"]:
        conflict = await repo.get_by_title(data["title"], company_id=job.company_id)
        if conflict and conflict.id != job.id:
            raise HTTPException(status_code=400, detail="A job with this title already exists.")
        job.title = data["title"].strip()

    for field in ("department", "experience", "location", "description", "skills",
                  "jd_original_filename", "jd_file_url", "jd_text", "parsed_jd"):
        if field in data:
            setattr(job, field, data[field])

    jd_text = job.jd_text
    parsed = dict(job.parsed_jd or {})
    if payload.parsed_jd is not None or payload.jd_text is not None:
        content_title = apply_jd_content_title(parsed, jd_text)
        job.parsed_jd = parsed or job.parsed_jd
        incoming_title = (data.get("title") or "").strip()
        filename = payload.jd_original_filename or job.jd_original_filename
        if content_title and content_title != "Open Position":
            if not incoming_title or is_filename_as_title(incoming_title, filename):
                job.title = content_title

    if "status" in data and data["status"] is not None:
        job.status = JobPostingStatus(data["status"])

    after = _job_update_snapshot(job)
    changes = _build_job_changes(before, after, sorted(data.keys()))
    await AuditService(db).log(
        action="JOB_UPDATED",
        entity_type="job",
        entity_id=str(job.id),
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "title": job.title,
            "previous_title": before["title"],
            "previous_status": before["status"],
            "status": after["status"],
            "updated_fields": sorted(data.keys()),
            "changes": changes,
        },
        message=_job_update_message(current_user.full_name, job.title, changes),
        company_id=job.company_id,
    )
    await db.commit()
    await db.refresh(job)
    applicants_by_title = await _applicants_by_title(db, job.company_id)
    return _to_response(job, applicants_by_title)


@router.delete(
    "/{job_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_job(
    job_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> Response:
    repo = JobPostingRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    require_scope_allows(scope, job.company_id)

    title = job.title
    status_label = _job_status_label(job.status)
    applicants_by_title = await _applicants_by_title(db, job.company_id)
    linked = len(applicants_by_title.get(title.strip().casefold(), []))

    # Block delete when candidates are linked by job title.
    if linked > 0:
        await AuditService(db).log(
            action="JOB_DELETED",
            entity_type="job",
            entity_id=str(job_id),
            user=current_user,
            request=request,
            ip_address=get_client_ip(request),
            status="FAILURE",
            details={
                "title": title,
                "status": status_label,
                "department": job.department,
                "location": job.location,
                "linked_candidates": linked,
                "reason": "candidates_linked",
            },
            message=(
                f"{current_user.full_name} could not delete job “{title}” — "
                f"{linked} candidate{'s' if linked != 1 else ''} still linked."
            ),
            company_id=job.company_id,
        )
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail=(
                f'Cannot delete "{title}" while {linked} candidate'
                f"{'s are' if linked != 1 else ' is'} linked. "
                "Remove or reassign candidates first."
            ),
        )

    await AuditService(db).log(
        action="JOB_DELETED",
        entity_type="job",
        entity_id=str(job_id),
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "title": title,
            "status": status_label,
            "department": job.department,
            "location": job.location,
            "linked_candidates": 0,
        },
        message=(
            f"{current_user.full_name} deleted job “{title}” "
            f"(was {status_label}"
            + (f", {job.department}" if job.department else "")
            + ")."
        ),
        company_id=job.company_id,
    )
    await repo.delete(job)
    await db.commit()
    return Response(status_code=204)
