"""HR candidate review and management routes."""

import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_admin, get_current_superadmin, get_current_user
from api.tenancy import get_tenant_scope, require_candidate_for_user
from core.database import get_db
from core.tenancy import TenantScope
from models.candidate import Candidate, CandidateStatus
from models.interview import InterviewStatus
from models.job_posting import JobPostingStatus
from models.user import User
from repositories.audit_log_repository import AuditLogRepository
from repositories.candidate_repository import CandidateRepository
from repositories.company_repository import CompanyRepository
from repositories.hr_recommendation_repository import HrRecommendationRepository
from repositories.interview_repository import InterviewRepository
from repositories.job_posting_repository import JobPostingRepository
from repositories.token_repository import TokenRepository
from schemas.hr import (
    AuditLogEntry,
    AuditLogListResponse,
    DashboardStatsResponse,
    HRCandidateDetailResponse,
    HRCandidateListResponse,
    HRCandidateSummary,
    InviteDeliveryCandidate,
    InviteDeliveryStats,
    RejectActionResponse,
    ResendInviteResponse,
    ShortlistActionResponse,
    UpdateCandidateEmailRequest,
    UpdateCandidateEmailResponse,
)
from services.audit_service import AuditService
from services.interview_completion_service import (
    has_finished_interview,
    snapshot_shows_completed,
    sync_completed_interviews,
)
from services.interview_room_service import in_app_room_url
from services.screening_integration_service import (
    CandidateAlreadyScreenedElsewhereError,
    can_resend_invite,
    is_placeholder_email,
    promote_to_shortlisted_and_schedule,
    reject_candidate,
    resend_shortlisted_invite,
    restore_booked_candidates_to_scheduled,
    set_candidate_contact_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hr", tags=["HR Candidate Management"])

STATUS_FILTERS: dict[str, CandidateStatus | None] = {
    "all": None,
    "shortlisted": CandidateStatus.SHORTLISTED,
    "needs_review": CandidateStatus.NEEDS_REVIEW,
    "rejected": CandidateStatus.REJECTED,
    "interview_scheduled": CandidateStatus.INTERVIEW_SCHEDULED,
    "interview_completed": CandidateStatus.INTERVIEW_COMPLETED,
}


def _extract_score_fields(snapshot: dict | None) -> dict:
    if not snapshot:
        return {}
    breakdown = snapshot.get("score_breakdown") or {}
    return {
        "final_recommendation": snapshot.get("final_recommendation"),
        "matched_skills": breakdown.get("matched_skills") or [],
        "missing_skills": breakdown.get("missing_skills") or [],
        "strengths": breakdown.get("strengths") or [],
        "concerns": breakdown.get("concerns") or [],
    }


def _extract_resume_fields(snapshot: dict | None) -> dict:
    if not snapshot:
        return {}
    parsed_resume = snapshot.get("parsed_resume") or {}
    return {
        "resume_sections": parsed_resume.get("sections") or [],
        "resume_text": snapshot.get("resume_text") or parsed_resume.get("source_text") or "",
    }


def _format_years(value: float | int | None) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0:
        return None
    return f"{numeric:g}"


def _is_valid_education_line(text: str) -> bool:
    value = re.sub(r"^#+\s*", "", str(text or "")).strip()
    if not value or len(value) > 400:
        return False
    if re.fullmatch(r"education|academic qualifications?|qualification", value, re.I):
        return False
    return True


def _summarize_experience_entries(entries: list[dict], limit: int = 2) -> str | None:
    if not entries:
        return None
    lines: list[str] = []
    for entry in entries[:limit]:
        role = entry.get("role") or entry.get("job_title") or "Role"
        company = entry.get("company") or ""
        years = _format_years(entry.get("duration_years"))
        line = str(role)
        if company:
            line += f" @ {company}"
        if years:
            line += f" ({years} yrs)"
        lines.append(line)
    return " · ".join(lines) if lines else None


def _extract_experience_summary(snapshot: dict | None) -> str | None:
    if not snapshot:
        return None

    breakdown = snapshot.get("score_breakdown") or {}
    exp = breakdown.get("experience_assessment") or snapshot.get("experience_assessment") or {}
    parsed_resume = snapshot.get("parsed_resume") or {}
    entries = parsed_resume.get("experience_entries") or []

    entry_summary = _summarize_experience_entries(entries)
    if entry_summary:
        return entry_summary

    total = (
        parsed_resume.get("total_experience_years")
        or exp.get("candidate_total_experience_years")
        or snapshot.get("candidate_experience_years")
    )
    total_text = _format_years(total)
    if total_text:
        return f"{total_text} yrs total"

    relevant = exp.get("candidate_relevant_experience_years")
    if relevant is None:
        relevant = snapshot.get("candidate_relevant_experience_years")
    relevant_text = _format_years(relevant)
    if relevant_text:
        return f"{relevant_text} yrs relevant"

    if entries:
        suffix = "s" if len(entries) != 1 else ""
        return f"{len(entries)} role{suffix} listed"

    return None


def _extract_education_summary(snapshot: dict | None) -> str | None:
    if not snapshot:
        return None

    education = snapshot.get("candidate_education")
    if isinstance(education, list) and education:
        cleaned = [str(item).strip() for item in education if _is_valid_education_line(item)][:2]
        if cleaned:
            return " · ".join(cleaned)

    parsed_resume = snapshot.get("parsed_resume") or {}
    parsed_education = parsed_resume.get("education")
    if isinstance(parsed_education, list) and parsed_education:
        cleaned = [str(item).strip() for item in parsed_education if _is_valid_education_line(item)][:2]
        if cleaned:
            return " · ".join(cleaned)

    return None


async def _build_summary(
    candidate: Candidate,
    db: AsyncSession,
    *,
    interview_result: str | None = None,
) -> HRCandidateSummary:
    interview_repo = InterviewRepository(db)
    token_repo = TokenRepository(db)
    interview = await interview_repo.get_by_candidate_id(candidate.candidate_id)
    interview_completed = bool(
        (interview and interview.status == InterviewStatus.COMPLETED)
        or snapshot_shows_completed(candidate.evaluation_snapshot)
        or candidate.status == CandidateStatus.INTERVIEW_COMPLETED
        or await has_finished_interview(db, candidate)
    )
    interview_scheduled = bool(
        interview
        and interview.status == InterviewStatus.SCHEDULED
        and not interview_completed
    )
    invite_used = await token_repo.has_used_token(candidate.candidate_id)
    invite_sent = await token_repo.has_any_token(candidate.candidate_id)
    booked = interview_scheduled or invite_used
    if interview_completed and candidate.status not in {
        CandidateStatus.INTERVIEW_COMPLETED,
        CandidateStatus.REJECTED,
    }:
        candidate.status = CandidateStatus.INTERVIEW_COMPLETED
        await db.flush()
    elif booked and candidate.status in {
        CandidateStatus.SHORTLISTED,
        CandidateStatus.NEEDS_REVIEW,
    }:
        candidate.status = CandidateStatus.INTERVIEW_SCHEDULED
        await db.flush()
    can_resend = (
        candidate.status == CandidateStatus.SHORTLISTED
        and not interview_scheduled
        and not invite_used
        and not is_placeholder_email(candidate.email)
    )
    email_missing = is_placeholder_email(candidate.email)
    can_edit_email = (
        candidate.status in {CandidateStatus.SHORTLISTED, CandidateStatus.NEEDS_REVIEW}
        and not interview_scheduled
        and not invite_used
        and not invite_sent
    )
    return HRCandidateSummary(
        candidate_id=candidate.candidate_id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        resume_score=candidate.resume_score,
        job_position=candidate.job_position,
        status=candidate.status.value,
        created_at=candidate.created_at,
        resume_original_filename=candidate.resume_original_filename,
        resume_file_url=candidate.resume_file_url,
        jd_original_filename=candidate.jd_original_filename,
        jd_file_url=candidate.jd_file_url,
        interview_scheduled=interview_scheduled,
        interview_completed=interview_completed,
        invite_used=invite_used,
        invite_sent=invite_sent,
        can_resend_invite=can_resend,
        email_missing=email_missing,
        can_edit_email=can_edit_email,
        experience_summary=_extract_experience_summary(candidate.evaluation_snapshot),
        education_summary=_extract_education_summary(candidate.evaluation_snapshot),
        interview_result=interview_result,
    )


@router.get("/candidates", response_model=HRCandidateListResponse)
async def list_candidates(
    status: str = Query(
        "all",
        description="shortlisted | interview_scheduled | interview_completed | needs_review | rejected | all",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> HRCandidateListResponse:
    """List candidates grouped by screening status for HR review."""
    normalized = status.strip().lower().replace(" ", "_")
    if normalized not in STATUS_FILTERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status filter. Use one of: {', '.join(STATUS_FILTERS)}",
        )

    await restore_booked_candidates_to_scheduled(db, company_id=scope.filter_company_id)
    await sync_completed_interviews(db, company_id=scope.filter_company_id)

    repo = CandidateRepository(db)
    candidates = await repo.list_by_status(
        STATUS_FILTERS[normalized], company_id=scope.filter_company_id
    )
    decisions = await HrRecommendationRepository(db).latest_decisions(
        [c.candidate_id for c in candidates]
    )
    summaries = [
        await _build_summary(
            c, db, interview_result=decisions.get(c.candidate_id)
        )
        for c in candidates
    ]

    return HRCandidateListResponse(
        status_filter=normalized,
        total=len(summaries),
        candidates=summaries,
    )


@router.get("/candidates/{candidate_id}", response_model=HRCandidateDetailResponse)
async def get_candidate_detail(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: TenantScope = Depends(get_tenant_scope),
) -> HRCandidateDetailResponse:
    """Full candidate profile with JD and evaluation snapshot for HR review."""
    candidate = await require_candidate_for_user(
        db,
        current_user,
        candidate_id,
        requested_company_id=scope.company_id,
    )

    report = await HrRecommendationRepository(db).get_latest(candidate_id)
    summary = await _build_summary(
        candidate,
        db,
        interview_result=report.decision if report else None,
    )
    score_fields = _extract_score_fields(candidate.evaluation_snapshot)
    resume_fields = _extract_resume_fields(candidate.evaluation_snapshot)
    interview_repo = InterviewRepository(db)
    interview = await interview_repo.get_by_candidate_id(candidate_id)

    snapshot = dict(candidate.evaluation_snapshot or {})
    agent5_meta = dict(snapshot.get("agent5") or {})
    join_link = agent5_meta.get("join_link")

    return HRCandidateDetailResponse(
        **summary.model_dump(),
        jd_text=candidate.jd_text,
        evaluation_snapshot=candidate.evaluation_snapshot,
        **score_fields,
        **resume_fields,
        scheduled_date=interview.scheduled_date if interview else None,
        scheduled_time=interview.scheduled_time if interview else None,
        meeting_link=in_app_room_url(
            interview.meeting_link if interview else None,
            join_link,
        ),
        join_link=join_link,
        calendar_event_id=interview.calendar_event_id if interview else None,
    )


@router.patch("/candidates/{candidate_id}/email", response_model=UpdateCandidateEmailResponse)
async def update_candidate_email(
    candidate_id: str,
    payload: UpdateCandidateEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UpdateCandidateEmailResponse:
    """HR can add or correct a contact email before the scheduling invite is sent."""
    candidate = await require_candidate_for_user(db, current_user, candidate_id)
    previous_email = candidate.email

    try:
        updated = await set_candidate_contact_email(db, candidate_id, str(payload.email))
    except CandidateAlreadyScreenedElsewhereError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await AuditService(db).log(
        action="CANDIDATE_EMAIL_UPDATED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        old_value={"email": previous_email},
        new_value={"email": updated.email},
        details={
            "candidate_name": updated.full_name,
            "job_position": updated.job_position,
        },
        message=(
            f"{current_user.full_name} updated contact email for {updated.full_name} "
            f"({candidate_id}) to {updated.email}."
        ),
        company_id=updated.company_id,
    )
    await db.commit()
    return UpdateCandidateEmailResponse(
        message="Email saved. You can now send the scheduling invite.",
        candidate_id=updated.candidate_id,
        email=updated.email,
    )


@router.post("/candidates/{candidate_id}/shortlist", response_model=ShortlistActionResponse)
async def shortlist_candidate(
    candidate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShortlistActionResponse:
    """Promote a Needs Review candidate to Shortlisted and send scheduling email."""
    candidate = await require_candidate_for_user(db, current_user, candidate_id)
    previous_status = candidate.status.value if candidate else None

    try:
        scheduling = await promote_to_shortlisted_and_schedule(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    candidate_name = candidate.full_name if candidate else candidate_id
    await AuditService(db).log(
        action="CANDIDATE_SHORTLISTED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "previous_status": previous_status,
            "new_status": CandidateStatus.SHORTLISTED.value,
            "candidate_name": candidate_name,
            "candidate_email": candidate.email if candidate else None,
            "job_position": candidate.job_position if candidate else None,
        },
        message=(
            f"{current_user.full_name} shortlisted {candidate_name} ({candidate_id}) "
            f"from {previous_status or 'unknown'} to Shortlisted and sent interview invite"
            + (f" for {candidate.job_position}" if candidate and candidate.job_position else "")
            + "."
        ),
        company_id=candidate.company_id if candidate else None,
    )
    await db.commit()

    return ShortlistActionResponse(
        message=scheduling.message,
        candidate_id=scheduling.candidate_id,
        status=CandidateStatus.SHORTLISTED.value,
        scheduling_link=scheduling.scheduling_link,
        token=scheduling.token,
    )


@router.post("/candidates/{candidate_id}/reject", response_model=RejectActionResponse)
async def reject_candidate_route(
    candidate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RejectActionResponse:
    """Reject a Needs Review or Shortlisted candidate."""
    candidate = await require_candidate_for_user(db, current_user, candidate_id)
    previous_status = candidate.status.value if candidate else None

    try:
        updated = await reject_candidate(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await AuditService(db).log(
        action="CANDIDATE_REJECTED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "previous_status": previous_status,
            "new_status": CandidateStatus.REJECTED.value,
            "candidate_name": updated.full_name,
            "candidate_email": updated.email,
            "job_position": updated.job_position,
        },
        message=(
            f"{current_user.full_name} rejected {updated.full_name} ({candidate_id}) "
            f"from {previous_status or 'unknown'} to Rejected"
            + (f" for {updated.job_position}" if updated.job_position else "")
            + "."
        ),
        company_id=updated.company_id,
    )
    await db.commit()

    return RejectActionResponse(
        message="Candidate rejected.",
        candidate_id=updated.candidate_id,
        status=updated.status.value,
    )


@router.post("/candidates/{candidate_id}/resend-invite", response_model=ResendInviteResponse)
async def resend_invite(
    candidate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResendInviteResponse:
    """Resend scheduling email for shortlisted candidates who have not booked a slot."""
    candidate = await require_candidate_for_user(db, current_user, candidate_id)

    try:
        scheduling = await resend_shortlisted_invite(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    candidate_name = candidate.full_name if candidate else candidate_id
    await AuditService(db).log(
        action="INVITE_RESENT",
        entity_type="candidate",
        entity_id=candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "candidate_name": candidate_name,
            "candidate_email": candidate.email if candidate else None,
            "job_position": candidate.job_position if candidate else None,
        },
        message=(
            f"{current_user.full_name} resent scheduling invite to {candidate_name} "
            f"({candidate.email if candidate else candidate_id})"
            + (f" for {candidate.job_position}" if candidate and candidate.job_position else "")
            + "."
        ),
        company_id=candidate.company_id if candidate else None,
    )
    await db.commit()

    return ResendInviteResponse(
        message=scheduling.message,
        candidate_id=scheduling.candidate_id,
        scheduling_link=scheduling.scheduling_link,
        token=scheduling.token,
    )


@router.get("/candidates/{candidate_id}/invite-status")
async def get_invite_status(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check whether HR can resend an invite for this candidate."""
    candidate = await require_candidate_for_user(db, current_user, candidate_id)

    allowed, reason = await can_resend_invite(db, candidate_id)
    summary = await _build_summary(candidate, db)
    return {
        "candidate_id": candidate_id,
        "can_resend_invite": allowed and summary.can_resend_invite,
        "reason": reason,
        "interview_scheduled": summary.interview_scheduled,
        "invite_used": summary.invite_used,
    }


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    company_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_superadmin),
) -> AuditLogListResponse:
    """Recent HR and screening audit trail (SuperAdmin only)."""
    audit = AuditService(db)
    await audit.backfill_missing_screening_audits()
    await audit.repair_unattributed_screening_audits()
    await audit.repair_missing_audit_company_ids()
    entries = await AuditLogRepository(db).list_recent(limit=limit, company_id=company_id)
    companies = {row.id: row.name for row in await CompanyRepository(db).list_all()}
    payload = []
    for entry in entries:
        item = AuditLogEntry.model_validate(entry)
        payload.append(
            item.model_copy(
                update={
                    "company_id": entry.company_id,
                    "company_name": companies.get(entry.company_id) if entry.company_id else None,
                }
            )
        )
    return AuditLogListResponse(total=len(payload), entries=payload)


def _status_label(status: CandidateStatus) -> str:
    labels = {
        CandidateStatus.NEEDS_REVIEW: "Needs Review",
        CandidateStatus.SHORTLISTED: "Shortlisted",
        CandidateStatus.REJECTED: "Rejected",
        CandidateStatus.INTERVIEW_SCHEDULED: "Interview Scheduled",
        CandidateStatus.INTERVIEW_COMPLETED: "Interview Completed",
        CandidateStatus.PENDING: "Pending",
    }
    return labels.get(status, status.value)


def _month_key(dt: datetime) -> str:
    return dt.strftime("%b %Y")


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    scope: TenantScope = Depends(get_tenant_scope),
) -> DashboardStatsResponse:
    """Aggregate recruitment metrics from candidates and saved job postings."""
    await restore_booked_candidates_to_scheduled(db, company_id=scope.filter_company_id)
    await sync_completed_interviews(db, company_id=scope.filter_company_id)
    repo = CandidateRepository(db)
    candidates = await repo.list_by_status(None, company_id=scope.filter_company_id)

    status_counts: dict[str, int] = {}
    jobs: dict[str, dict] = {}
    monthly_scores: dict[str, list[float]] = {}
    skill_counts: dict[str, int] = {}

    total_score = 0.0
    for candidate in candidates:
        status_key = candidate.status.value
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        total_score += float(candidate.resume_score or 0)

        job_key = (candidate.job_position or "Unassigned Role").strip() or "Unassigned Role"
        job_entry = jobs.setdefault(
            job_key,
            {
                "name": job_key,
                "applicants": 0,
                "avgScore": 0.0,
                "_scores": [],
            },
        )
        job_entry["applicants"] += 1
        job_entry["_scores"].append(float(candidate.resume_score or 0))

        month = _month_key(candidate.created_at)
        monthly_scores.setdefault(month, []).append(float(candidate.resume_score or 0))

        snapshot = candidate.evaluation_snapshot or {}
        breakdown = snapshot.get("score_breakdown") or {}
        for skill in breakdown.get("matched_skills") or []:
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

    status_colors = {
        CandidateStatus.NEEDS_REVIEW.value: "#F59E0B",
        CandidateStatus.SHORTLISTED.value: "#22C55E",
        CandidateStatus.REJECTED.value: "#EF4444",
        CandidateStatus.INTERVIEW_SCHEDULED.value: "#2563EB",
        CandidateStatus.INTERVIEW_COMPLETED.value: "#0D9488",
        CandidateStatus.PENDING.value: "#94A3B8",
    }
    status_distribution = [
        {
            "name": _status_label(CandidateStatus(key)),
            "value": count,
            "color": status_colors.get(key, "#94A3B8"),
        }
        for key, count in status_counts.items()
    ]

    applications_per_job = []
    postings = await JobPostingRepository(db).list_all(company_id=scope.filter_company_id)
    active_jobs = 0
    jobs_by_title = {
        str(key).strip().casefold(): value
        for key, value in jobs.items()
        if str(key).strip()
    }
    for posting in postings:
        if posting.status == JobPostingStatus.ACTIVE:
            active_jobs += 1
        title = (posting.title or "").strip()
        stats_entry = jobs_by_title.get(title.casefold(), {})
        scores = list(stats_entry.get("_scores") or [])
        applications_per_job.append(
            {
                "name": title[:28] or "Untitled role",
                "applicants": int(stats_entry.get("applicants") or 0),
                "avgScore": round(sum(scores) / len(scores), 1) if scores else 0,
            }
        )
    applications_per_job.sort(key=lambda item: item["applicants"], reverse=True)

    match_trend = [
        {
            "month": month,
            "avgScore": round(sum(scores) / len(scores), 1),
            "screened": len(scores),
        }
        for month, scores in sorted(
            monthly_scores.items(),
            key=lambda item: datetime.strptime(item[0], "%b %Y"),
        )
    ]

    top_skills = [
        {"skill": skill, "count": count}
        for skill, count in sorted(skill_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]

    total = len(candidates)
    shortlisted = status_counts.get(CandidateStatus.SHORTLISTED.value, 0)
    interview_scheduled = status_counts.get(CandidateStatus.INTERVIEW_SCHEDULED.value, 0)
    interview_completed = status_counts.get(CandidateStatus.INTERVIEW_COMPLETED.value, 0)
    rejected = status_counts.get(CandidateStatus.REJECTED.value, 0)
    pending_reviews = status_counts.get(CandidateStatus.NEEDS_REVIEW.value, 0)

    pending = status_counts.get(CandidateStatus.PENDING.value, 0)

    # Each stage uses the actual status count (mutually exclusive buckets).
    hiring_funnel = [
        {"stage": "Screened", "count": total},
        {"stage": "Needs Review", "count": pending_reviews},
        {"stage": "Shortlisted", "count": shortlisted},
        {"stage": "Interview Scheduled", "count": interview_scheduled},
        {"stage": "Interview Completed", "count": interview_completed},
        {"stage": "Rejected", "count": rejected},
    ]
    if pending > 0:
        hiring_funnel.insert(1, {"stage": "Pending", "count": pending})

    token_ids = await TokenRepository(db).candidate_ids_with_tokens()
    invite_rows = []
    issued = 0
    not_issued = 0
    awaiting_booking = 0
    booked = interview_scheduled
    for candidate in candidates:
        has_token = candidate.candidate_id in token_ids
        if candidate.status == CandidateStatus.INTERVIEW_SCHEDULED or (
            candidate.status == CandidateStatus.SHORTLISTED and has_token
        ):
            issued += 1
        if candidate.status == CandidateStatus.SHORTLISTED and not has_token:
            not_issued += 1
        if candidate.status == CandidateStatus.SHORTLISTED:
            awaiting_booking += 1
            invite_rows.append(
                InviteDeliveryCandidate(
                    candidate_id=candidate.candidate_id,
                    full_name=candidate.full_name,
                    email=candidate.email,
                    job_position=candidate.job_position,
                    invite_sent=has_token,
                    can_resend=True,
                )
            )

    invite_delivery = InviteDeliveryStats(
        issued=issued,
        not_issued=not_issued,
        awaiting_booking=awaiting_booking,
        booked=booked,
        candidates=invite_rows,
    )

    return DashboardStatsResponse(
        total_candidates=total,
        active_jobs=active_jobs,
        ai_screened=total,
        pending_reviews=pending_reviews,
        shortlisted=shortlisted,
        rejected=rejected,
        interview_scheduled=interview_scheduled,
        interview_completed=interview_completed,
        average_match_score=round(total_score / total, 1) if total else 0.0,
        status_distribution=status_distribution,
        applications_per_job=applications_per_job,
        match_trend=match_trend,
        top_skills=top_skills,
        hiring_funnel=hiring_funnel,
        invite_delivery=invite_delivery,
    )
