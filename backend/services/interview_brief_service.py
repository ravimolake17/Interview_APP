"""Shorten company/department interview briefs for spoken Agent 4 use."""

from __future__ import annotations

import logging
import re

from agents.shared.llama_client import call_llama_json, llama_available

logger = logging.getLogger(__name__)

# Spoken intro budget for TTS at interview start.
_MAX_SPOKEN_WORDS = 55
_SOFT_LIMIT_CHARS = 420


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ")).strip()


def heuristic_shorten(text: str, *, max_words: int = _MAX_SPOKEN_WORDS) -> str:
    cleaned = _clean(text)
    if not cleaned:
        return ""
    # Prefer first 1–2 sentences.
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    out: list[str] = []
    for part in parts:
        candidate = " ".join(out + [part]).strip()
        if len(candidate.split()) > max_words and out:
            break
        out.append(part)
        if len(" ".join(out).split()) >= max_words:
            break
    spoken = " ".join(out).strip() or cleaned
    words = spoken.split()
    if len(words) > max_words:
        spoken = " ".join(words[:max_words]).rstrip(",;:") + "."
    return spoken


def shorten_company_intro(raw: str, *, company_name: str = "") -> str:
    """Return a short spoken company introduction (LLM when available)."""
    cleaned = _clean(raw)
    if not cleaned:
        return ""
    if len(cleaned.split()) <= _MAX_SPOKEN_WORDS and len(cleaned) <= _SOFT_LIMIT_CHARS:
        return cleaned

    if llama_available():
        try:
            data = call_llama_json(
                (
                    "You write short spoken company introductions for a live AI interview. "
                    "Rewrite the company text into 2–3 warm spoken sentences, max 55 words. "
                    "Keep only public-facing facts. No markdown. "
                    'Return JSON: {"spoken_intro":"..."}'
                ),
                f"Company: {company_name or 'the company'}\n\nSource text:\n{cleaned[:4000]}",
                temperature=0.3,
                max_tokens=400,
            )
            spoken = _clean(str((data or {}).get("spoken_intro") or ""))
            if spoken:
                return heuristic_shorten(spoken)
        except Exception:
            logger.exception("Company intro LLM shorten failed; using heuristic")

    return heuristic_shorten(cleaned)


def role_summary_from_jd(jd_text: str, *, job_position: str = "", max_words: int = 70) -> str:
    """Compact role overview for end-of-interview Q&A."""
    cleaned = _clean(jd_text)
    if not cleaned and not job_position:
        return ""
    if llama_available() and cleaned:
        try:
            data = call_llama_json(
                (
                    "Summarize this job description for a candidate in a live interview. "
                    "2–4 spoken sentences covering the role purpose and main responsibilities. "
                    "Max 70 words. No markdown. "
                    'Return JSON: {"role_summary":"..."}'
                ),
                f"Job title: {job_position or 'the role'}\n\nJD:\n{cleaned[:5000]}",
                temperature=0.3,
                max_tokens=500,
            )
            summary = _clean(str((data or {}).get("role_summary") or ""))
            if summary:
                return heuristic_shorten(summary, max_words=max_words)
        except Exception:
            logger.exception("Role summary LLM failed; using heuristic")
    if cleaned:
        return heuristic_shorten(cleaned, max_words=max_words)
    return f"This interview is for the {job_position} role." if job_position else ""


async def load_interview_reference_briefs(db, candidate) -> dict[str, str]:
    """Company spoken intro, department brief, and role summary for Agent 4."""
    from sqlalchemy import func, select

    from models.job_posting import JobPosting
    from repositories.company_repository import CompanyRepository
    from repositories.department_repository import DepartmentRepository

    company_intro = ""
    company_name = ""
    department_name = ""
    department_brief = ""
    company_id = getattr(candidate, "company_id", None)
    job_position = (getattr(candidate, "job_position", None) or "").strip()

    if company_id:
        company = await CompanyRepository(db).get_by_id(int(company_id))
        if company:
            company_name = (company.name or "").strip()
            company_intro = _clean(
                company.interview_intro_spoken or company.interview_intro or ""
            )

        if job_position:
            result = await db.execute(
                select(JobPosting)
                .where(
                    JobPosting.company_id == int(company_id),
                    func.lower(JobPosting.title) == job_position.lower(),
                )
                .limit(1)
            )
            job = result.scalar_one_or_none()
            if job and (job.department or "").strip():
                department_name = job.department.strip()
                dept = await DepartmentRepository(db).get_by_name(
                    department_name, company_id=int(company_id)
                )
                if dept:
                    department_brief = _clean(
                        dept.interview_brief or dept.description or ""
                    )

    role_summary = role_summary_from_jd(
        getattr(candidate, "jd_text", None) or "",
        job_position=job_position,
    )
    return {
        "company_name": company_name,
        "company_intro": company_intro,
        "department_name": department_name,
        "department_brief": department_brief,
        "role_summary": role_summary,
    }
