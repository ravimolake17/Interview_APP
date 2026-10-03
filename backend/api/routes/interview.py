"""FastAPI routes for interview scheduling."""

import logging

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, get_current_user, get_optional_user
from api.tenancy import get_tenant_scope
from core.tenancy import TenantScope
from agents.scheduler_agent.graph import SchedulerAgent
from core.database import get_db
from models.candidate import CandidateStatus
from models.interview import InterviewStatus
from models.user import User
from repositories.candidate_repository import CandidateRepository
from repositories.company_repository import CompanyRepository
from repositories.interview_repository import InterviewRepository
from repositories.slot_repository import SlotRepository
from repositories.token_repository import TokenRepository
from schemas.interview import (
    BookSlotRequest,
    BookSlotResponse,
    CalendarInterviewResponse,
    CalendarWeekResponse,
    InterviewDetailsResponse,
    JoinInterviewResponse,
    SendInviteRequest,
    SendInviteResponse,
    SlotResponse,
    TokenValidationResponse,
)
from services.agent5_bootstrap_service import bootstrap_agent5_session, snapshot_payload_from_bootstrap
from services.audit_service import AuditService
from services.blueprint_service import BlueprintService
from services.interview_room_service import in_app_room_url
from services.join_token_service import (
    JoinTokenService,
    candidate_join_window,
    format_join_window_time,
)
from services.application_settings_service import ApplicationSettingsService
from services.screening_integration_service import can_resend_invite
from services.slot_service import SlotService, company_now
from core.trusted_time import trusted_utc_now
from services.token_service import TokenService
from services.job_position import resolve_job_position_from_jd
from sqlalchemy.orm.attributes import flag_modified
from core.security import hash_refresh_token
from models.candidate import Candidate
from models.interview import Interview

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview", tags=["Interview Scheduler"])


def _join_http_error(status_code: int, message: str, company=None) -> HTTPException:
    if company is None:
        return HTTPException(status_code=status_code, detail=message)
    return HTTPException(
        status_code=status_code,
        detail={
            "message": message,
            "company_name": company.name,
            "company_code": company.code,
        },
    )


async def _company_brand(db: AsyncSession, candidate) -> tuple[str | None, str | None]:
    if not candidate or not getattr(candidate, "company_id", None):
        return None, None
    company = await CompanyRepository(db).get_by_id(int(candidate.company_id))
    if not company:
        return None, None
    return company.name, company.code


@router.post("/send-invite", response_model=SendInviteResponse)
async def send_invite(
    payload: SendInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """
    Triggered when Agent 1 shortlists a candidate.
    Starts the LangGraph scheduler workflow and sends the congratulations email.
    """
    candidate_repo = CandidateRepository(db)
    candidate = await candidate_repo.get_by_candidate_id(payload.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if candidate.status != CandidateStatus.SHORTLISTED:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate must be SHORTLISTED. Current status: {candidate.status.value}",
        )

    allowed, reason = await can_resend_invite(db, payload.candidate_id)
    if not allowed:
        raise HTTPException(status_code=409, detail=reason or "Cannot send invite.")

    agent = SchedulerAgent(db)
    result = await agent.start_invite_workflow(payload.candidate_id)

    if result.get("Status") == "FAILED":
        raise HTTPException(status_code=500, detail=result.get("Error", "Workflow failed."))

    actor = current_user.full_name if current_user else "System"
    await AuditService(db).log(
        action="INTERVIEW_INVITE_SENT",
        entity_type="candidate",
        entity_id=payload.candidate_id,
        user=current_user,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "candidate_name": candidate.full_name,
            "candidate_email": candidate.email,
            "job_position": candidate.job_position,
        },
        message=(
            f"{actor} sent interview invite to {candidate.full_name} ({candidate.email})"
            + (f" for {candidate.job_position}" if candidate.job_position else "")
            + "."
        ),
    )
    await db.commit()

    return SendInviteResponse(
        message="Interview invite sent successfully.",
        thread_id=result.get("ThreadId", ""),
        token=result.get("Token", ""),
        scheduling_link=result.get("SchedulingLink", ""),
    )


@router.get("/token/{token}", response_model=TokenValidationResponse)
async def validate_token(token: str, db: AsyncSession = Depends(get_db)):
    """Validate scheduling token and return candidate details with available slots."""
    token_service = TokenService(TokenRepository(db))
    schedule_token, error = await token_service.validate_token(token)

    if not schedule_token:
        return TokenValidationResponse(valid=False, error=error)

    candidate_repo = CandidateRepository(db)
    candidate = await candidate_repo.get_by_candidate_id(schedule_token.candidate_id)
    if not candidate:
        return TokenValidationResponse(valid=False, error="Candidate not found.")
    company_name, company_code = await _company_brand(db, candidate)

    interview_repo = InterviewRepository(db)
    existing_interview = await interview_repo.get_by_candidate_id(schedule_token.candidate_id)
    if existing_interview and existing_interview.status == InterviewStatus.SCHEDULED:
        return TokenValidationResponse(
            valid=False,
            already_booked=True,
            candidate_id=candidate.candidate_id,
            full_name=candidate.full_name,
            email=candidate.email,
            company_name=company_name,
            company_code=company_code,
            error="Interview already scheduled.",
        )

    if error:
        return TokenValidationResponse(
            valid=False,
            candidate_id=candidate.candidate_id,
            full_name=candidate.full_name,
            email=candidate.email,
            company_name=company_name,
            company_code=company_code,
            error=error,
        )

    slot_service = SlotService(SlotRepository(db))
    slots = await slot_service.get_available_slots(company_id=candidate.company_id)
    tz_name = None
    try:
        tz_name = (await ApplicationSettingsService(db).get_company(candidate.company_id)).timezone
    except Exception:
        tz_name = "Asia/Kolkata"
    now = company_now(tz_name)

    return TokenValidationResponse(
        valid=True,
        candidate_id=candidate.candidate_id,
        full_name=candidate.full_name,
        email=candidate.email,
        job_position=resolve_job_position_from_jd(
            jd_text=candidate.jd_text,
            jd_original_filename=candidate.jd_original_filename,
            stored_job_position=candidate.job_position,
        ),
        company_name=company_name,
        company_code=company_code,
        slots=[SlotResponse.model_validate(s) for s in slots],
        server_now=now,
        server_today=now.date(),
        timezone=tz_name,
    )


@router.get("/available-slots", response_model=list[SlotResponse])
async def get_available_slots(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """Return unbooked interview slots for the authenticated user's company."""
    if current_user is None or not current_user.company_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    slot_service = SlotService(SlotRepository(db))
    slots = await slot_service.get_available_slots(company_id=current_user.company_id)
    return [SlotResponse.model_validate(s) for s in slots]


@router.post("/book-slot", response_model=BookSlotResponse)
async def book_slot(
    payload: BookSlotRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Book an interview slot and resume the LangGraph workflow."""
    token_service = TokenService(TokenRepository(db))
    schedule_token, error = await token_service.validate_token(payload.token)
    if not schedule_token or error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Invalid token.",
        )

    candidate_id = schedule_token.candidate_id
    candidate = await CandidateRepository(db).get_by_candidate_id(candidate_id)
    slot_repo = SlotRepository(db)
    slot = await slot_repo.get_by_id(payload.slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found.")
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if slot.company_id != candidate.company_id:
        raise HTTPException(status_code=404, detail="Slot not found.")
    if slot.is_booked:
        raise HTTPException(status_code=409, detail="Slot is already booked.")
    if await SlotService(slot_repo).is_holiday(slot.date, slot.company_id):
        raise HTTPException(status_code=409, detail="That date is a company holiday.")
    if not await SlotService(slot_repo).is_slot_open(slot):
        raise HTTPException(status_code=409, detail="That time slot has already passed. Please pick a later time.")

    slot_data = {
        "id": slot.id,
        "date": str(slot.date),
        "start_time": str(slot.start_time),
        "end_time": str(slot.end_time),
    }

    agent = SchedulerAgent(db)
    result = await agent.resume_with_slot(
        candidate_id, payload.slot_id, slot_data, token=payload.token
    )

    if result.get("Status") == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.get("Error", "Booking failed."),
        )

    candidate_name = candidate.full_name if candidate else candidate_id
    join_link = result.get("JoinLink") or result.get("MeetingLink", "")
    if not join_link and candidate:
        interview = await InterviewRepository(db).get_by_candidate_id(candidate_id)
        if interview and interview.meeting_link:
            join_link = interview.meeting_link

    if candidate and join_link:
        snapshot = dict(candidate.evaluation_snapshot or {})
        agent5_meta = dict(snapshot.get("agent5") or {})
        agent5_meta["join_link"] = join_link
        company = (
            await CompanyRepository(db).get_by_id(candidate.company_id)
            if candidate.company_id
            else None
        )
        try:
            payload = bootstrap_agent5_session(
                candidate_id=candidate.candidate_id,
                full_name=candidate.full_name,
                email=candidate.email,
                existing_snapshot=agent5_meta,
                company_code=company.code if company else None,
            )
            agent5_meta.update(snapshot_payload_from_bootstrap(payload))
            agent5_meta["join_link"] = join_link
        except Exception:
            logger.exception("Agent5 pre-bootstrap after booking failed for %s (non-fatal)", candidate_id)
        snapshot["agent5"] = agent5_meta
        candidate.evaluation_snapshot = snapshot
        flag_modified(candidate, "evaluation_snapshot")

    # Agent 2 books the slot (LangGraph or DB fallback). Agents 3 and 4 are
    # follow-on services and must still run after a late invite.
    if candidate:
        await BlueprintService(db).ensure_plan_and_questions(candidate_id)

    await AuditService(db).log(
        action="INTERVIEW_SCHEDULED",
        entity_type="candidate",
        entity_id=candidate_id,
        user=None,
        request=request,
        ip_address=get_client_ip(request),
        details={
            "candidate_name": candidate_name,
            "candidate_email": candidate.email if candidate else None,
            "job_position": candidate.job_position if candidate else None,
            "interview_date": str(slot.date),
            "interview_time": str(slot.start_time),
            "slot_id": slot.id,
            "meeting_link": join_link,
            "join_link": join_link,
        },
        message=(
            f"{candidate_name} booked interview on {slot.date} at {slot.start_time}"
            + (
                f" for {candidate.job_position}"
                if candidate and candidate.job_position
                else ""
            )
            + (" (in-app interview room)" if join_link else "")
            + "."
        ),
    )
    await db.commit()

    return BookSlotResponse(
        message="Interview scheduled successfully.",
        interview_date=slot.date,
        interview_time=slot.start_time,
        join_link=None,
        status=result.get("Status", "COMPLETED"),
    )


@router.get("/details/{candidate_id}", response_model=InterviewDetailsResponse)
async def get_interview_details(candidate_id: str, db: AsyncSession = Depends(get_db)):
    """Get interview details for a candidate."""
    candidate_repo = CandidateRepository(db)
    candidate = await candidate_repo.get_by_candidate_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    interview_repo = InterviewRepository(db)
    interview = await interview_repo.get_by_candidate_id(candidate_id)

    join_link = None
    if interview and interview.join_token_hash:
        meta = dict((candidate.evaluation_snapshot or {}).get("agent5") or {})
        join_link = meta.get("join_link")

    return InterviewDetailsResponse(
        candidate_id=candidate.candidate_id,
        full_name=candidate.full_name,
        email=candidate.email,
        job_position=candidate.job_position,
        scheduled_date=interview.scheduled_date if interview else None,
        scheduled_time=interview.scheduled_time if interview else None,
        meeting_link=in_app_room_url(
            interview.meeting_link if interview else None,
            join_link,
        ),
        join_link=join_link,
        calendar_event_id=interview.calendar_event_id if interview else None,
        status=interview.status.value if interview else "NOT_SCHEDULED",
        created_at=interview.created_at if interview else None,
    )


@router.get("/join/{token}", response_model=JoinInterviewResponse)
async def join_interview(
    token: str,
    role: str | None = Query(None, description="Pass 'hr' to skip identity gates and enter the room directly"),
    db: AsyncSession = Depends(get_db),
) -> JoinInterviewResponse:
    """Public gate: exchange hashed join token for Agent5 verification session."""
    from datetime import datetime, timezone

    from models.interview import InterviewStatus

    participant_role = "hr" if str(role or "").strip().lower() == "hr" else "candidate"

    token_hash = hash_refresh_token(token.strip())
    interview = await InterviewRepository(db).get_by_join_token_hash(token_hash)
    if interview is None:
        raise HTTPException(status_code=404, detail="Invalid or expired interview link.")

    candidate = await db.scalar(
        select(Candidate).where(Candidate.candidate_id == interview.candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    company = (
        await CompanyRepository(db).get_by_id(candidate.company_id)
        if candidate.company_id
        else None
    )

    if interview.status != InterviewStatus.SCHEDULED:
        raise _join_http_error(409, "This interview is no longer active.", company)
    expires_at = interview.join_token_expires_at
    if expires_at is not None:
        expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if trusted_utc_now() > expiry:
            raise _join_http_error(410, "This interview link has expired.", company)

    if participant_role == "candidate":
        settings_service = ApplicationSettingsService(db)
        company_settings = await settings_service.get_company(candidate.company_id)
        availability = await settings_service.get_interview_availability(candidate.company_id)
        tz_name = getattr(company_settings, "timezone", None)
        opens_at, _starts_at, closes_at = candidate_join_window(
            interview.scheduled_date,
            interview.scheduled_time,
            duration_minutes=availability.slot_minutes,
            tz_name=tz_name,
        )
        now = company_now(tz_name)
        if now < opens_at:
            raise _join_http_error(
                403,
                (
                    f"The interview room opens at {format_join_window_time(opens_at)}. "
                    "Please join then to complete identity verification and start your interview."
                ),
                company,
            )
        if now > closes_at:
            raise _join_http_error(
                410,
                "This interview session is no longer available. Please contact HR if you need assistance.",
                company,
            )

    snapshot = dict(candidate.evaluation_snapshot or {})
    agent5_meta = dict(snapshot.get("agent5") or {})
    try:
        payload = bootstrap_agent5_session(
            candidate_id=candidate.candidate_id,
            full_name=candidate.full_name,
            email=candidate.email,
            existing_snapshot=agent5_meta,
            participant_role=participant_role,
            company_code=company.code if company else None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent5 bootstrap failed while joining interview for %s", candidate.candidate_id)
        raise HTTPException(
            status_code=500,
            detail=(
                "Interview verification could not start. "
                "Check AGENT5_SECRET_KEY and that PostgreSQL schema 'agent5' is available."
            ),
        ) from exc

    # Never overwrite the candidate session token with an HR-scoped token.
    if participant_role == "candidate":
        agent5_meta.update(snapshot_payload_from_bootstrap(payload))
    else:
        agent5_meta.setdefault("session_id", payload["agent5_session_id"])
        agent5_meta.setdefault("proctoring_url", payload["proctoring_url"])
        agent5_meta.setdefault("monitor_url", payload["monitor_url"])

    meta_join = agent5_meta.get("join_link")
    if not meta_join:
        join_service = JoinTokenService()
        agent5_meta["join_link"] = join_service.build_join_link(token.strip())
    snapshot["agent5"] = agent5_meta
    candidate.evaluation_snapshot = snapshot
    flag_modified(candidate, "evaluation_snapshot")
    await db.commit()

    return JoinInterviewResponse(
        candidate_id=candidate.candidate_id,
        candidate_name=candidate.full_name,
        interview_date=interview.scheduled_date,
        interview_time=interview.scheduled_time,
        session_id=str(payload["agent5_session_id"]),
        agent5_token=str(payload["agent5_token"]),
        proctoring_url=str(payload["proctoring_url"]),
        participant_role=participant_role,
        company_name=company.name if company else None,
        company_code=company.code if company else None,
    )


@router.get("/calendar", response_model=CalendarWeekResponse)
async def get_interview_calendar(
    week_start: date | None = Query(None, description="Sunday of the week (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    scope: TenantScope = Depends(get_tenant_scope),
):
    """HR calendar view — scheduled interviews with candidate name and ID."""
    tz_name = "Asia/Kolkata"
    try:
        company = await ApplicationSettingsService(db).get_company(scope.filter_company_id)
        tz_name = company.timezone or tz_name
    except Exception:
        tz_name = "Asia/Kolkata"
    now = company_now(tz_name)
    if week_start is None:
        today = now.date()
        week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    week_end = week_start + timedelta(days=6)

    interview_repo = InterviewRepository(db)
    blueprint_service = BlueprintService(db)
    rows = await interview_repo.list_scheduled_for_week(
        week_start, week_end, company_id=scope.filter_company_id
    )

    interviews: list[CalendarInterviewResponse] = []
    for interview, candidate in rows:
        duration = await blueprint_service.planned_duration_minutes(candidate.candidate_id)
        end_time = interview_repo.compute_end_time(
            interview.scheduled_time,
            duration,
        )
        interviews.append(
            CalendarInterviewResponse(
                interview_id=interview.id,
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.full_name,
                candidate_email=candidate.email,
                job_position=candidate.job_position,
                scheduled_date=interview.scheduled_date,
                start_time=interview.scheduled_time,
                end_time=end_time,
                meeting_link=in_app_room_url(
                    interview.meeting_link,
                    dict((candidate.evaluation_snapshot or {}).get("agent5") or {}).get("join_link"),
                ),
                status=interview.status.value,
            )
        )

    return CalendarWeekResponse(
        week_start=week_start,
        week_end=week_end,
        interviews=interviews,
        server_now=now,
        server_today=now.date(),
        timezone=tz_name,
    )
