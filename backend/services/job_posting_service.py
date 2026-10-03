"""Create or update job postings from JD parsing / screening."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from models.job_posting import JobPosting, JobPostingStatus
from repositories.job_posting_repository import JobPostingRepository
from services.job_position import apply_jd_content_title, is_filename_as_title

DuplicateAction = Literal["error", "replace", "rename"]


class JobDuplicateError(Exception):
    def __init__(self, job: JobPosting, reason: str) -> None:
        self.job = job
        self.reason = reason
        if reason == "file":
            message = (
                f"This job description is already stored as “{job.title}”. "
                "Replace the existing job or save it under a new name."
            )
        else:
            message = (
                f"A job titled “{job.title}” already exists. "
                "Replace it or save this JD under a different title."
            )
        super().__init__(message)


@dataclass
class JobDuplicate:
    job: JobPosting
    reason: str


def resolve_job_title(
    *,
    parsed_jd: dict[str, Any] | None = None,
    jd_text: str | None = None,
    title_override: str | None = None,
    jd_original_filename: str | None = None,
) -> str:
    parsed = dict(parsed_jd or {})
    content_title = apply_jd_content_title(parsed, jd_text)
    override = (title_override or "").strip()
    if (
        not override
        or override.casefold() == "open position"
        or is_filename_as_title(override, jd_original_filename)
    ):
        title = content_title
    else:
        title = override
    return title.strip() or "Open Position"


def _format_experience_from_parsed(parsed_jd: dict[str, Any] | None) -> str | None:
    if not parsed_jd:
        return None
    minimum = parsed_jd.get("minimum_experience_years")
    maximum = parsed_jd.get("maximum_experience_years")
    preferred = parsed_jd.get("preferred_experience_years")
    if minimum is not None and maximum is not None:
        return f"{minimum}–{maximum} years"
    if minimum is not None:
        return f"{minimum}+ years"
    if preferred is not None:
        return f"{preferred} years preferred"
    return None


def _skills_from_parsed(parsed_jd: dict[str, Any] | None) -> list[str]:
    if not parsed_jd:
        return []
    skills: list[str] = []
    required = parsed_jd.get("required_skills") or {}
    preferred = parsed_jd.get("preferred_skills") or {}
    for source in (required, preferred):
        values = source.get("normalized") or source.get("raw") or []
        if isinstance(values, list):
            skills.extend(str(item).strip() for item in values if str(item).strip())
    seen: set[str] = set()
    output: list[str] = []
    for skill in skills:
        key = skill.casefold()
        if key not in seen:
            seen.add(key)
            output.append(skill)
    return output


def _description_from_parsed(parsed_jd: dict[str, Any] | None, jd_text: str | None) -> str | None:
    if jd_text and jd_text.strip():
        return jd_text.strip()
    if not parsed_jd:
        return None
    parts: list[str] = []
    responsibilities = parsed_jd.get("responsibilities") or []
    if responsibilities:
        parts.append("Responsibilities:\n" + "\n".join(f"- {item}" for item in responsibilities))
    education = parsed_jd.get("education_requirements") or []
    if education:
        parts.append("Education:\n" + "\n".join(f"- {item}" for item in education))
    return "\n\n".join(parts).strip() or None


async def find_duplicate_job(
    db: AsyncSession,
    *,
    title: str | None = None,
    jd_file_url: str | None = None,
    company_id: int | None = None,
    exclude_id: int | None = None,
) -> JobDuplicate | None:
    repo = JobPostingRepository(db)
    file_url = (jd_file_url or "").strip()
    if file_url:
        existing = await repo.get_by_jd_file_url(file_url, company_id=company_id)
        if existing and existing.id != exclude_id:
            return JobDuplicate(job=existing, reason="file")
    cleaned_title = (title or "").strip()
    if cleaned_title:
        existing = await repo.get_by_title(cleaned_title, company_id=company_id)
        if existing and existing.id != exclude_id:
            return JobDuplicate(job=existing, reason="title")
    return None


async def apply_jd_to_job(
    job: JobPosting,
    *,
    jd_text: str | None = None,
    jd_original_filename: str | None = None,
    jd_file_url: str | None = None,
    parsed_jd: dict[str, Any] | None = None,
    title: str | None = None,
    department: str | None = None,
    location: str | None = None,
    experience: str | None = None,
    description: str | None = None,
    skills: list[str] | None = None,
) -> JobPosting:
    parsed = dict(parsed_jd or job.parsed_jd or {})
    if title:
        job.title = title
    parsed_experience = _format_experience_from_parsed(parsed)
    parsed_description = _description_from_parsed(parsed, jd_text)
    parsed_skills = _skills_from_parsed(parsed)
    if department:
        job.department = department
    if experience:
        job.experience = experience
    elif parsed_experience:
        job.experience = parsed_experience
    if location:
        job.location = location or job.location
    if description:
        job.description = description
    elif parsed_description:
        job.description = parsed_description
    if skills:
        job.skills = skills
    elif parsed_skills:
        job.skills = parsed_skills
    if jd_original_filename:
        job.jd_original_filename = jd_original_filename
    if jd_file_url:
        job.jd_file_url = jd_file_url
    if jd_text:
        job.jd_text = jd_text
    if parsed:
        job.parsed_jd = parsed
    if job.status == JobPostingStatus.DRAFT:
        job.status = JobPostingStatus.ACTIVE
    return job


async def store_job_from_jd(
    db: AsyncSession,
    *,
    jd_text: str | None = None,
    jd_original_filename: str | None = None,
    jd_file_url: str | None = None,
    parsed_jd: dict[str, Any] | None = None,
    title_override: str | None = None,
    department: str | None = "Hiring",
    location: str | None = "India",
    experience: str | None = None,
    description: str | None = None,
    skills: list[str] | None = None,
    status: JobPostingStatus = JobPostingStatus.ACTIVE,
    company_id: int | None = None,
    on_duplicate: DuplicateAction = "error",
) -> JobPosting:
    if company_id is None:
        raise ValueError("Jobs must belong to a company.")
    repo = JobPostingRepository(db)
    parsed = dict(parsed_jd or {})
    title = resolve_job_title(
        parsed_jd=parsed,
        jd_text=jd_text,
        title_override=title_override,
        jd_original_filename=jd_original_filename,
    )
    duplicate = await find_duplicate_job(
        db,
        title=title,
        jd_file_url=jd_file_url,
        company_id=company_id,
    )
    if duplicate:
        if on_duplicate == "replace":
            await apply_jd_to_job(
                duplicate.job,
                jd_text=jd_text,
                jd_original_filename=jd_original_filename,
                jd_file_url=jd_file_url,
                parsed_jd=parsed,
                title=title if duplicate.reason != "title" else duplicate.job.title,
                department=department,
                location=location,
                experience=experience,
                description=description,
                skills=skills,
            )
            await db.flush()
            return duplicate.job
        if on_duplicate == "rename":
            if title.casefold() == duplicate.job.title.casefold():
                raise ValueError(
                    "Choose a different job title to save this JD without replacing the existing one."
                )
            still_taken = await find_duplicate_job(
                db,
                title=title,
                jd_file_url=None,
                company_id=company_id,
            )
            if still_taken:
                raise JobDuplicateError(still_taken.job, still_taken.reason)
        else:
            raise JobDuplicateError(duplicate.job, duplicate.reason)

    return await repo.create(
        company_id=company_id,
        title=title,
        department=department,
        experience=experience or _format_experience_from_parsed(parsed) or "As per JD",
        location=location,
        description=description or _description_from_parsed(parsed, jd_text),
        skills=skills or _skills_from_parsed(parsed),
        status=status,
        jd_original_filename=jd_original_filename,
        jd_file_url=jd_file_url,
        jd_text=jd_text,
        parsed_jd=parsed or None,
    )


async def upsert_job_from_jd(
    db: AsyncSession,
    *,
    jd_text: str | None = None,
    jd_original_filename: str | None = None,
    jd_file_url: str | None = None,
    parsed_jd: dict[str, Any] | None = None,
    title_override: str | None = None,
    department: str | None = "Hiring",
    location: str | None = "India",
    company_id: int | None = None,
) -> JobPosting:
    """Create a job posting from a parsed JD, replacing an existing match."""
    return await store_job_from_jd(
        db,
        jd_text=jd_text,
        jd_original_filename=jd_original_filename,
        jd_file_url=jd_file_url,
        parsed_jd=parsed_jd,
        title_override=title_override,
        department=department,
        location=location,
        company_id=company_id,
        on_duplicate="replace",
    )
