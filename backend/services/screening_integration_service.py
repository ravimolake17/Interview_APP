"""Bridge Agent 1 (resume screening) with Agent 2 (interview scheduler)."""

import hashlib
import logging
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from agents.scheduler_agent.graph import SchedulerAgent
from core.chroma_store import (
    index_hr_outcome,
    index_resume_profile,
    retrieve_similar_resumes,
    summarize_similar_hits,
)
from core.config import get_settings
from models.candidate import Candidate, CandidateStatus
from models.interview import InterviewStatus
from repositories.candidate_repository import CandidateRepository
from repositories.company_repository import CompanyRepository
from repositories.interview_repository import InterviewRepository
from repositories.token_repository import TokenRepository
from services.blueprint_service import BlueprintService
from services.job_position import resolve_job_position_from_jd
from agents.screening_agent.schemas.ats import Decision, EvaluationResponse, SchedulingInfo
from agents.screening_agent.schemas.resume import ParsedResume
from agents.screening_agent.services.resume_parser import extract_emails_from_text

logger = logging.getLogger(__name__)

PLACEHOLDER_EMAIL_DOMAIN = "@screening.local"


class CandidateAlreadyScreenedElsewhereError(ValueError):
    """Raised when the same person (matched by email) already belongs to another company."""

    def __init__(self, email: str, company_name: str | None = None) -> None:
        self.email = email
        self.company_name = company_name
        if company_name:
            message = (
                f"This candidate ({email}) has already been screened at {company_name}. "
                "The same person cannot be screened at another company."
            )
        else:
            message = (
                f"This candidate ({email}) has already been screened at another company. "
                "The same person cannot be screened twice across companies."
            )
        super().__init__(message)


def is_placeholder_email(email: str | None) -> bool:
    """True for missing/generated contacts that must not identify a real person."""
    value = (email or "").strip().lower()
    if not value:
        return True
    return value.endswith(PLACEHOLDER_EMAIL_DOMAIN) or value.startswith("no-email-")


def normalize_candidate_emails(*values: str | None) -> list[str]:
    """Deduplicate real emails; placeholders are ignored."""
    seen: set[str] = set()
    emails: list[str] = []
    for raw in values:
        cleaned = (raw or "").strip().lower()
        if not cleaned or is_placeholder_email(cleaned) or cleaned in seen:
            continue
        seen.add(cleaned)
        emails.append(cleaned)
    return emails


async def ensure_not_screened_elsewhere(
    db: AsyncSession,
    *,
    emails: list[str] | tuple[str, ...] | None,
    company_id: int,
) -> None:
    """Block screening when this email already exists only at a different company.

    Identity is email, not name. Same-company re-screens remain allowed.
    """
    normalized = normalize_candidate_emails(*(emails or []))
    if not normalized:
        return

    repo = CandidateRepository(db)
    for email in normalized:
        if await repo.list_by_email(email, company_id=company_id):
            return

    for email in normalized:
        other = await repo.get_by_email_outside_company(email, company_id)
        if other is None:
            continue
        company = await CompanyRepository(db).get_by_id(other.company_id)
        raise CandidateAlreadyScreenedElsewhereError(
            email, company.name if company else None
        )


DECISION_TO_STATUS: dict[Decision, CandidateStatus] = {
    "Shortlisted": CandidateStatus.SHORTLISTED,
    "Needs Review": CandidateStatus.NEEDS_REVIEW,
    "Rejected": CandidateStatus.REJECTED,
}

def _attach_screening_chroma_memory(
    candidate: Candidate,
    snapshot: dict[str, Any],
    *,
    skills: list[str],
    summary: str,
    decision: str,
    jd_text: str,
) -> None:
    """Index this resume and attach similar past cases. Never raises."""
    try:
        role = candidate.job_position or ""
        hits = retrieve_similar_resumes(jd_text=jd_text or summary, role=role, n_results=5)
        similar = summarize_similar_hits(hits, exclude_id=candidate.candidate_id)
        snapshot["chroma_similar_resumes"] = similar
        index_resume_profile(
            candidate_id=candidate.candidate_id,
            role=role,
            skills=skills,
            summary=summary,
            score=float(candidate.resume_score or 0),
            decision=decision,
            jd_text=jd_text,
        )
        index_hr_outcome(
            candidate_id=candidate.candidate_id,
            role=role,
            decision=decision,
            score=float(candidate.resume_score or 0),
            summary=summary,
            source="screening",
        )
    except Exception:
        logger.debug("Chroma screening memory skipped for %s", candidate.candidate_id, exc_info=True)


# Interview / proctoring metadata stored under evaluation_snapshot — keep on same-JD re-screen.
PRESERVED_SNAPSHOT_KEYS = ("agent5", "interview_runtime")


def _extract_email(evaluation: EvaluationResponse) -> str | None:
    emails = evaluation.candidate_details.emails
    return emails[0].strip().lower() if emails else None


def _extract_emails(evaluation: EvaluationResponse) -> list[str]:
    return normalize_candidate_emails(*(evaluation.candidate_details.emails or []))


def emails_from_parsed_resume(
    parsed_resume: ParsedResume | dict | None = None,
    *extra_texts: str | None,
) -> list[str]:
    """Collect identity emails from parsed resume text/sections before scoring."""
    texts: list[str] = [value for value in extra_texts if value]
    if isinstance(parsed_resume, ParsedResume):
        texts.append(parsed_resume.source_text or "")
        for section in parsed_resume.sections:
            texts.append(section.raw_text or "")
            for item in section.items or []:
                if isinstance(item, dict):
                    texts.append(str(item.get("value") or ""))
                    texts.append(str(item.get("text") or ""))
                else:
                    texts.append(str(item or ""))
    elif isinstance(parsed_resume, dict):
        texts.append(str(parsed_resume.get("source_text") or ""))
        for section in parsed_resume.get("sections") or []:
            if not isinstance(section, dict):
                continue
            texts.append(str(section.get("raw_text") or ""))
            for item in section.get("items") or []:
                if isinstance(item, dict):
                    texts.append(str(item.get("value") or ""))
                    texts.append(str(item.get("text") or ""))
                else:
                    texts.append(str(item or ""))
    found: list[str] = []
    for text in texts:
        found.extend(extract_emails_from_text(text))
    return normalize_candidate_emails(*found)


def _names_look_like_different_people(left: str | None, right: str | None) -> bool:
    """True when two extracted names are both real and clearly not the same person."""
    def tokens(value: str | None) -> list[str]:
        return [part for part in re.sub(r"[^a-z]+", " ", (value or "").casefold()).split() if part]

    first = tokens(left)
    second = tokens(right)
    if len(first) < 2 or len(second) < 2:
        return False
    if first == second:
        return False
    if first[-1] == second[-1] and (first[0] == second[0] or first[0] in second or second[0] in first):
        return False
    return True


def _extract_phone(evaluation: EvaluationResponse) -> str | None:
    phones = evaluation.candidate_details.phones
    return phones[0] if phones else None


def _build_evaluation_snapshot(
    evaluation: EvaluationResponse,
    parsed_resume: ParsedResume | None = None,
) -> dict[str, Any]:
    snapshot = evaluation.model_dump(mode="json")
    if parsed_resume is not None:
        snapshot["resume_text"] = parsed_resume.source_text
        snapshot["parsed_resume"] = parsed_resume.model_dump(mode="json")
    return snapshot


def _normalize_jd_text(jd_text: str | None) -> str:
    return re.sub(r"\s+", " ", (jd_text or "").strip().lower())


def _jd_identity_key(
    jd_text: str | None,
    jd_file_url: str | None,
    jd_original_filename: str | None,
) -> str | None:
    # Prefer JD content. Each upload stores a unique file URL, so URL-first
    # matching would treat the same JD as a new job on every re-screen.
    normalized = _normalize_jd_text(jd_text)
    if normalized:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"text:{digest}"
    if jd_file_url and jd_file_url.strip():
        return f"url:{jd_file_url.strip()}"
    if jd_original_filename and jd_original_filename.strip():
        return f"file:{jd_original_filename.strip().lower()}"
    return None


def same_job_description(
    existing: Candidate,
    *,
    resolved_jd: str | None,
    jd_file_url: str | None = None,
    jd_original_filename: str | None = None,
) -> bool:
    """True when a re-screen targets the same JD as an existing candidate record."""
    if resolved_jd and existing.jd_text:
        return _normalize_jd_text(resolved_jd) == _normalize_jd_text(existing.jd_text)
    # Existing row has no JD text — match stored file URL / filename only.
    new_key = _jd_identity_key(None, jd_file_url, jd_original_filename)
    old_key = _jd_identity_key(
        None,
        existing.jd_file_url,
        existing.jd_original_filename,
    )
    if new_key and old_key:
        return new_key == old_key
    return False


def merge_evaluation_snapshot(
    new_snapshot: dict[str, Any],
    existing_snapshot: dict[str, Any] | None,
    *,
    preserve_interview_history: bool,
) -> dict[str, Any]:
    """Keep proctoring/interview metadata when re-screening the same person for the same JD."""
    if not preserve_interview_history or not existing_snapshot:
        return new_snapshot
    merged = dict(new_snapshot)
    for key in PRESERVED_SNAPSHOT_KEYS:
        value = existing_snapshot.get(key)
        if value:
            merged[key] = value
    return merged


async def find_existing_for_rescreen(
    repo: CandidateRepository,
    *,
    email: str | None,
    resume_file_url: str | None,
    resolved_jd: str | None,
    jd_file_url: str | None,
    jd_original_filename: str | None,
    company_id: int | None = None,
) -> Candidate | None:
    """Match an existing record only when email + JD align; different JD => fresh candidate."""
    if email:
        for candidate in await repo.list_by_email(email, company_id=company_id):
            if same_job_description(
                candidate,
                resolved_jd=resolved_jd,
                jd_file_url=jd_file_url,
                jd_original_filename=jd_original_filename,
            ):
                return candidate
        return None
    if resume_file_url:
        return await repo.get_by_resume_file_url(resume_file_url, company_id=company_id)
    return None


def _resolve_jd_text(jd_text: str | None, evaluation: EvaluationResponse) -> str | None:
    if jd_text and jd_text.strip():
        return jd_text.strip()
    jd = evaluation.extracted_jd_requirements
    parts = [jd.job_title.strip()] if jd.job_title else []
    if jd.responsibilities:
        parts.append("\n".join(jd.responsibilities))
    combined = "\n\n".join(parts).strip()
    return combined or None


def _resolve_contact_email(
    evaluation: EvaluationResponse,
    existing: Candidate | None,
) -> tuple[str, str | None]:
    """Return email to store and an optional HR warning when email was missing."""
    email = _extract_email(evaluation)
    if email:
        return email, None
    if existing:
        return existing.email, (
            "No email found in resume. Updated the existing HR record using the prior contact email."
        )
    placeholder = f"no-email-{uuid.uuid4().hex[:8]}@screening.local"
    return placeholder, (
        "No email found in resume. Candidate was still saved for HR review with a placeholder contact."
    )


async def has_booked_slot(db: AsyncSession, candidate_id: str) -> bool:
    """True when the candidate already scheduled an interview or used their booking link."""
    allowed, _reason = await can_resend_invite(db, candidate_id)
    return not allowed


async def restore_booked_candidates_to_scheduled(
    db: AsyncSession, *, company_id: int | None = None
) -> int:
    """Move shortlisted/needs-review records that already booked back to Interview Scheduled."""
    repo = CandidateRepository(db)
    restored = 0
    for status in (CandidateStatus.SHORTLISTED, CandidateStatus.NEEDS_REVIEW):
        for candidate in await repo.list_by_status(status, company_id=company_id):
            if await has_booked_slot(db, candidate.candidate_id):
                candidate.status = CandidateStatus.INTERVIEW_SCHEDULED
                restored += 1
    if restored:
        await db.flush()
        logger.info(
            "Restored %s booked candidate(s) to INTERVIEW_SCHEDULED after re-screening",
            restored,
        )
    return restored


async def save_screening_evaluation(
    db: AsyncSession,
    evaluation: EvaluationResponse,
    *,
    jd_text: str | None = None,
    parsed_resume: ParsedResume | None = None,
    resume_original_filename: str | None = None,
    resume_file_url: str | None = None,
    jd_original_filename: str | None = None,
    jd_file_url: str | None = None,
    company_id: int | None = None,
) -> tuple[Candidate, str | None]:
    """Persist every screening result so HR can review all candidates."""
    if company_id is None:
        raise ValueError("Screening results must belong to a company.")
    repo = CandidateRepository(db)
    email_from_resume = _extract_email(evaluation)
    resolved_jd = _resolve_jd_text(jd_text, evaluation)
    existing = await find_existing_for_rescreen(
        repo,
        email=email_from_resume,
        resume_file_url=resume_file_url,
        resolved_jd=resolved_jd,
        jd_file_url=jd_file_url,
        jd_original_filename=jd_original_filename,
        company_id=company_id,
    )
    await ensure_not_screened_elsewhere(
        db,
        emails=_extract_emails(evaluation),
        company_id=company_id,
    )

    email, persist_warning = _resolve_contact_email(evaluation, existing)
    status = DECISION_TO_STATUS[evaluation.shortlist_status]
    snapshot = _build_evaluation_snapshot(evaluation, parsed_resume)
    full_name = (evaluation.candidate_details.name or "Candidate").strip() or "Candidate"
    if (
        existing
        and resume_original_filename
        and existing.resume_original_filename
        and existing.resume_original_filename != resume_original_filename
        and _names_look_like_different_people(existing.full_name, full_name)
    ):
        logger.warning(
            "Skipping email-based merge for %s vs %s (different resume files: %s / %s)",
            existing.full_name,
            full_name,
            existing.resume_original_filename,
            resume_original_filename,
        )
        existing = None
        email, persist_warning = _resolve_contact_email(evaluation, None)
    phone = _extract_phone(evaluation)
    resume_score = float(evaluation.score_breakdown.overall_score)
    job_position = resolve_job_position_from_jd(
        jd_text=resolved_jd,
        jd_original_filename=jd_original_filename,
        parsed_job_title=evaluation.extracted_jd_requirements.job_title,
    )

    if existing:
        already_booked = await has_booked_slot(db, existing.candidate_id)
        if already_booked or existing.status == CandidateStatus.INTERVIEW_SCHEDULED:
            status = CandidateStatus.INTERVIEW_SCHEDULED

        snapshot = merge_evaluation_snapshot(
            snapshot,
            existing.evaluation_snapshot,
            preserve_interview_history=True,
        )

        existing.full_name = full_name
        existing.email = email
        existing.phone = phone
        existing.resume_score = resume_score
        existing.job_position = job_position
        existing.status = status
        existing.jd_text = resolved_jd
        existing.evaluation_snapshot = snapshot
        existing.resume_original_filename = resume_original_filename
        existing.resume_file_url = resume_file_url
        existing.jd_original_filename = jd_original_filename
        existing.jd_file_url = jd_file_url
        _attach_screening_chroma_memory(
            existing,
            snapshot,
            skills=list(evaluation.extracted_resume_skills.normalized_skills or [])[:25],
            summary=str(evaluation.final_recommendation or ""),
            decision=str(evaluation.shortlist_status or ""),
            jd_text=resolved_jd or "",
        )
        existing.evaluation_snapshot = snapshot
        flag_modified(existing, "evaluation_snapshot")
        await db.flush()
        logger.info(
            "Re-screened existing candidate %s for same JD — preserved interview/proctoring history",
            existing.candidate_id,
        )
        return existing, persist_warning

    candidate = Candidate(
        candidate_id=f"CAND-{uuid.uuid4().hex[:8].upper()}",
        company_id=company_id,
        full_name=full_name,
        email=email,
        phone=phone,
        resume_score=resume_score,
        job_position=job_position,
        status=status,
        jd_text=resolved_jd,
        evaluation_snapshot=snapshot,
        resume_original_filename=resume_original_filename,
        resume_file_url=resume_file_url,
        jd_original_filename=jd_original_filename,
        jd_file_url=jd_file_url,
    )
    _attach_screening_chroma_memory(
        candidate,
        snapshot,
        skills=list(evaluation.extracted_resume_skills.normalized_skills or [])[:25],
        summary=str(evaluation.final_recommendation or ""),
        decision=str(evaluation.shortlist_status or ""),
        jd_text=resolved_jd or "",
    )
    candidate.evaluation_snapshot = snapshot
    db.add(candidate)
    await db.flush()
    if not email_from_resume:
        logger.warning(
            "Saved screening result without resume email: %s (%s)",
            candidate.candidate_id,
            full_name,
        )
    return candidate, persist_warning


async def can_resend_invite(db: AsyncSession, candidate_id: str) -> tuple[bool, str | None]:
    """Resend is blocked once a slot is booked (used token or scheduled interview)."""
    interview_repo = InterviewRepository(db)
    interview = await interview_repo.get_by_candidate_id(candidate_id)
    if interview and interview.status == InterviewStatus.SCHEDULED:
        return False, "Interview already scheduled — candidate cannot pick another slot."

    token_repo = TokenRepository(db)
    if await token_repo.has_used_token(candidate_id):
        return False, "Candidate already booked a slot using their scheduling link."

    return True, None


def _sync_snapshot_email(candidate: Candidate, email: str) -> None:
    snapshot = candidate.evaluation_snapshot
    if not isinstance(snapshot, dict):
        return
    details = snapshot.get("candidate_details")
    if isinstance(details, dict):
        details["emails"] = [email]
        snapshot["candidate_details"] = details
        candidate.evaluation_snapshot = snapshot
        flag_modified(candidate, "evaluation_snapshot")


async def set_candidate_contact_email(
    db: AsyncSession,
    candidate_id: str,
    email: str,
) -> Candidate:
    """Add or correct a contact email before the scheduling invite is sent."""
    repo = CandidateRepository(db)
    candidate = await repo.get_by_candidate_id(candidate_id)
    if not candidate:
        raise ValueError("Candidate not found.")
    if candidate.status not in {CandidateStatus.SHORTLISTED, CandidateStatus.NEEDS_REVIEW}:
        raise ValueError("Email can only be edited before the interview is scheduled.")
    if await has_booked_slot(db, candidate.candidate_id):
        raise ValueError("Email cannot be changed after the candidate booked a slot.")
    if await TokenRepository(db).has_any_token(candidate.candidate_id):
        raise ValueError("Email cannot be changed after the scheduling invite was sent.")

    normalized = email.strip().lower()
    if is_placeholder_email(normalized):
        raise ValueError("Enter a real email address.")

    await ensure_not_screened_elsewhere(
        db,
        emails=[normalized],
        company_id=candidate.company_id,
    )
    duplicates = await repo.list_by_email(normalized)
    if any(other.candidate_id != candidate.candidate_id for other in duplicates):
        raise ValueError(
            "This email is already assigned to another candidate. "
            "Each candidate must have a unique email address."
        )
    candidate.email = normalized
    _sync_snapshot_email(candidate, normalized)
    await db.flush()
    logger.info("HR set contact email for %s", candidate.candidate_id)
    return candidate


async def save_and_schedule_shortlisted(
    db: AsyncSession,
    evaluation: EvaluationResponse,
    *,
    jd_text: str | None = None,
    parsed_resume: ParsedResume | None = None,
    resume_original_filename: str | None = None,
    resume_file_url: str | None = None,
    jd_original_filename: str | None = None,
    jd_file_url: str | None = None,
    company_id: int | None = None,
) -> SchedulingInfo:
    """
    Persist a shortlisted candidate and start the LangGraph scheduler workflow.
    Called automatically when screening returns shortlist_status == 'Shortlisted'.
    """
    candidate, _persist_warning = await save_screening_evaluation(
        db,
        evaluation,
        jd_text=jd_text,
        parsed_resume=parsed_resume,
        resume_original_filename=resume_original_filename,
        resume_file_url=resume_file_url,
        jd_original_filename=jd_original_filename,
        jd_file_url=jd_file_url,
        company_id=company_id,
    )
    if await has_booked_slot(db, candidate.candidate_id):
        candidate.status = CandidateStatus.INTERVIEW_SCHEDULED
        await db.flush()
        logger.info(
            "Re-screened %s who already booked a slot — kept INTERVIEW_SCHEDULED",
            candidate.candidate_id,
        )
        return SchedulingInfo(
            candidate_id=candidate.candidate_id,
            scheduling_link="",
            token="",
            interview_status="ALREADY_SCHEDULED",
            message="Candidate already booked an interview slot. Screening scores were updated.",
        )

    if not _extract_email(evaluation):
        raise ValueError(
            "Cannot schedule interview: shortlisted candidate has no email in resume."
        )

    candidate.status = CandidateStatus.SHORTLISTED
    await db.flush()

    allowed, reason = await can_resend_invite(db, candidate.candidate_id)
    if not allowed:
        candidate.status = CandidateStatus.INTERVIEW_SCHEDULED
        await db.flush()
        raise ValueError(reason or "Cannot send invite for this candidate.")

    agent = SchedulerAgent(db)
    result = await agent.start_invite_workflow(candidate.candidate_id)

    if result.get("Status") == "FAILED":
        raise RuntimeError(result.get("Error", "Interview scheduler workflow failed."))

    logger.info(
        "Shortlisted candidate %s (%s) — invite sent, token=%s",
        candidate.candidate_id,
        candidate.email,
        result.get("Token", ""),
    )

    blueprint_id = None
    candidate_level = None
    total_questions = None
    if get_settings().blueprint_auto_generate_on_shortlist:
        saved = await BlueprintService(db).ensure_plan_and_questions(candidate.candidate_id)
        if saved:
            row, blueprint = saved
            blueprint_id = row.id
            candidate_level = blueprint.candidate_level
            total_questions = blueprint.total_questions

    return SchedulingInfo(
        candidate_id=candidate.candidate_id,
        scheduling_link=result.get("SchedulingLink", ""),
        token=result.get("Token", ""),
        interview_status=result.get("Status", "INVITE_SENT"),
        message="Interview scheduling invite sent automatically.",
        blueprint_id=blueprint_id,
        candidate_level=candidate_level,
        total_questions=total_questions,
    )


async def promote_to_shortlisted_and_schedule(
    db: AsyncSession,
    candidate_id: str,
) -> SchedulingInfo:
    """HR promotes a Needs Review candidate to Shortlisted and sends invite."""
    repo = CandidateRepository(db)
    candidate = await repo.get_by_candidate_id(candidate_id)
    if not candidate:
        raise ValueError("Candidate not found.")
    if candidate.status != CandidateStatus.NEEDS_REVIEW:
        raise ValueError(
            f"Only NEEDS_REVIEW candidates can be promoted. Current status: {candidate.status.value}"
        )
    if is_placeholder_email(candidate.email):
        raise ValueError("Add a contact email before sending the scheduling invite.")

    allowed, reason = await can_resend_invite(db, candidate_id)
    if not allowed:
        raise ValueError(reason or "Cannot send invite for this candidate.")

    candidate.status = CandidateStatus.SHORTLISTED
    await db.flush()

    agent = SchedulerAgent(db)
    result = await agent.start_invite_workflow(candidate_id)

    if result.get("Status") == "FAILED":
        raise RuntimeError(result.get("Error", "Interview scheduler workflow failed."))

    blueprint_id = None
    candidate_level = None
    total_questions = None
    if get_settings().blueprint_auto_generate_on_shortlist:
        saved = await BlueprintService(db).ensure_plan_and_questions(candidate_id)
        if saved:
            row, blueprint = saved
            blueprint_id = row.id
            candidate_level = blueprint.candidate_level
            total_questions = blueprint.total_questions

    return SchedulingInfo(
        candidate_id=candidate_id,
        scheduling_link=result.get("SchedulingLink", ""),
        token=result.get("Token", ""),
        interview_status=result.get("Status", "INVITE_SENT"),
        message="Candidate shortlisted and interview invite sent.",
        blueprint_id=blueprint_id,
        candidate_level=candidate_level,
        total_questions=total_questions,
    )


async def resend_shortlisted_invite(db: AsyncSession, candidate_id: str) -> SchedulingInfo:
    """Resend scheduling email for a shortlisted candidate who has not booked yet."""
    repo = CandidateRepository(db)
    candidate = await repo.get_by_candidate_id(candidate_id)
    if not candidate:
        raise ValueError("Candidate not found.")
    if candidate.status not in {CandidateStatus.SHORTLISTED, CandidateStatus.INTERVIEW_SCHEDULED}:
        raise ValueError(
            f"Only shortlisted candidates can receive invites. Current status: {candidate.status.value}"
        )

    if is_placeholder_email(candidate.email):
        raise ValueError("Add a contact email before sending the scheduling invite.")

    allowed, reason = await can_resend_invite(db, candidate_id)
    if not allowed:
        raise ValueError(reason or "Cannot resend invite for this candidate.")

    agent = SchedulerAgent(db)
    result = await agent.start_invite_workflow(candidate_id)

    if result.get("Status") == "FAILED":
        raise RuntimeError(result.get("Error", "Interview scheduler workflow failed."))

    # Late email / first successful invite must still produce Agent 3 + 4.
    await BlueprintService(db).ensure_plan_and_questions(candidate_id)

    return SchedulingInfo(
        candidate_id=candidate_id,
        scheduling_link=result.get("SchedulingLink", ""),
        token=result.get("Token", ""),
        interview_status=result.get("Status", "INVITE_SENT"),
        message="Interview invite resent successfully.",
    )


async def reject_candidate(db: AsyncSession, candidate_id: str) -> Candidate:
    """HR rejects a candidate (from Needs Review or Shortlisted before booking)."""
    repo = CandidateRepository(db)
    candidate = await repo.get_by_candidate_id(candidate_id)
    if not candidate:
        raise ValueError("Candidate not found.")
    if candidate.status == CandidateStatus.REJECTED:
        raise ValueError("Candidate is already rejected.")
    if candidate.status == CandidateStatus.INTERVIEW_SCHEDULED:
        raise ValueError("Cannot reject a candidate who already booked an interview slot.")
    if candidate.status not in {CandidateStatus.NEEDS_REVIEW, CandidateStatus.SHORTLISTED}:
        raise ValueError(
            f"Only NEEDS_REVIEW or SHORTLISTED candidates can be rejected. "
            f"Current status: {candidate.status.value}"
        )

    allowed, reason = await can_resend_invite(db, candidate_id)
    if candidate.status == CandidateStatus.SHORTLISTED and not allowed:
        raise ValueError(reason or "Cannot reject this candidate.")

    candidate.status = CandidateStatus.REJECTED
    await db.flush()
    return candidate
