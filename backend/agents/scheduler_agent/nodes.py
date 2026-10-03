"""
LangGraph node implementations for the Interview Scheduler Agent.

Each workflow step is a separate node as specified in the requirements.
"""

import logging
from typing import Any

from langgraph.types import interrupt

from agents.scheduler_agent.state import SchedulerState
from core.config import get_settings
from repositories.candidate_repository import CandidateRepository
from repositories.company_repository import CompanyRepository
from repositories.interview_repository import InterviewRepository
from repositories.slot_repository import SlotRepository
from repositories.token_repository import TokenRepository
from services.email_service import EmailService
from services.join_token_service import JoinTokenService
from services.job_position import resolve_job_position_from_jd
from services.slot_service import SlotService
from services.token_service import TokenService

logger = logging.getLogger(__name__)
settings = get_settings()


class SchedulerNodes:
    """Container for all LangGraph node functions with injected dependencies."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        interview_repo: InterviewRepository,
        slot_repo: SlotRepository,
        token_repo: TokenRepository,
        token_service: TokenService,
        slot_service: SlotService,
        email_service: EmailService,
    ) -> None:
        self.candidate_repo = candidate_repo
        self.interview_repo = interview_repo
        self.slot_repo = slot_repo
        self.token_repo = token_repo
        self.token_service = token_service
        self.slot_service = slot_service
        self.email_service = email_service

    async def _smtp_for_state(self, state: SchedulerState):
        candidate = await self.candidate_repo.get_by_candidate_id(state["CandidateID"])
        company_id = candidate.company_id if candidate else None
        from services.application_settings_service import ApplicationSettingsService

        return await ApplicationSettingsService(self.candidate_repo.db).resolve_smtp(company_id)

    async def _company_brand(self, state: SchedulerState) -> tuple[str | None, str | None]:
        name = state.get("CompanyName")
        code = state.get("CompanyCode")
        if name and code:
            return name, code
        candidate = await self.candidate_repo.get_by_candidate_id(state["CandidateID"])
        if candidate and candidate.company_id:
            company = await CompanyRepository(self.candidate_repo.db).get_by_id(candidate.company_id)
            if company:
                return company.name, company.code
        return name, code

    async def load_candidate(self, state: SchedulerState) -> dict[str, Any]:
        """Load candidate details from the database."""
        candidate_id = state["CandidateID"]
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            return {"Status": "FAILED", "Error": f"Candidate {candidate_id} not found."}

        company_name = None
        company_code = None
        if candidate.company_id:
            company = await CompanyRepository(self.candidate_repo.db).get_by_id(candidate.company_id)
            if company:
                company_name = company.name
                company_code = company.code

        return {
            "Candidate": {
                "id": candidate.id,
                "candidate_id": candidate.candidate_id,
                "full_name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "resume_score": candidate.resume_score,
                "status": candidate.status.value,
                "company_id": candidate.company_id,
            },
            "CandidateID": candidate.candidate_id,
            "Email": candidate.email,
            "CandidateName": candidate.full_name,
            "ResumeScore": candidate.resume_score,
            "JobPosition": resolve_job_position_from_jd(
                jd_text=candidate.jd_text,
                jd_original_filename=candidate.jd_original_filename,
                stored_job_position=candidate.job_position,
            ),
            "CompanyName": company_name,
            "CompanyCode": company_code,
            "Status": "CANDIDATE_LOADED",
        }

    async def generate_secure_scheduling_token(self, state: SchedulerState) -> dict[str, Any]:
        """Generate a UUID token valid for 48 hours."""
        schedule_token, scheduling_link = await self.token_service.create_token(state["CandidateID"])
        logger.info("Scheduling invite link for %s: %s", state["CandidateID"], scheduling_link)
        return {
            "Token": schedule_token.token,
            "SchedulingLink": scheduling_link,
            "Status": "TOKEN_GENERATED",
        }

    async def create_available_time_slots(self, state: SchedulerState) -> dict[str, Any]:
        """Seed available interview slots if not already present."""
        candidate = await self.candidate_repo.get_by_candidate_id(state["CandidateID"])
        if not candidate or not candidate.company_id:
            return {"Status": "FAILED", "Error": "Candidate company is missing."}
        result = await self.slot_service.create_available_slots(
            company_id=candidate.company_id
        )
        logger.info(
            "Interview slots synced: created=%s removed=%s total=%s",
            result.get("created"),
            result.get("removed"),
            result.get("total"),
        )
        return {"Status": "SLOTS_CREATED"}

    async def send_congratulations_email(self, state: SchedulerState) -> dict[str, Any]:
        """Send congratulations email with scheduling link."""
        company_name, company_code = await self._company_brand(state)
        result = self.email_service.send_congratulations_email(
            candidate_name=state["CandidateName"],
            candidate_email=state["Email"],
            scheduling_link=state["SchedulingLink"],
            job_position=state.get("JobPosition", ""),
            company_code=company_code,
            company_name=company_name,
            smtp=await self._smtp_for_state(state),
        )
        return {
            "Status": "INVITE_SENT",
            "ThreadId": result.get("id", ""),
        }

    async def wait_for_candidate_slot_selection(self, state: SchedulerState) -> dict[str, Any]:
        """
        Interrupt the graph and wait for the candidate to select a slot.
        Resumes when book-slot API calls Command(resume=...) with slot data.
        """
        selected = interrupt(
            {
                "message": "Waiting for candidate to select an interview slot.",
                "candidate_id": state["CandidateID"],
                "token": state["Token"],
            }
        )
        return {
            "SelectedSlot": selected.get("slot"),
            "SlotId": selected.get("slot_id"),
            "Status": "SLOT_SELECTED",
        }

    async def validate_slot(self, state: SchedulerState) -> dict[str, Any]:
        """Validate the selected slot is still available."""
        slot_id = state.get("SlotId")
        if not slot_id:
            return {"Status": "FAILED", "Error": "No slot selected."}

        slot = await self.slot_service.get_slot_by_id(slot_id)
        if not slot:
            return {"Status": "FAILED", "Error": "Selected slot does not exist."}
        if slot.is_booked:
            return {"Status": "FAILED", "Error": "Selected slot is already booked."}
        if await self.slot_service.is_holiday(slot.date, slot.company_id):
            return {"Status": "FAILED", "Error": "That date is a company holiday."}
        if not await self.slot_service.is_slot_open(slot):
            return {"Status": "FAILED", "Error": "That time slot has already passed. Please pick a later time."}

        return {
            "SelectedSlot": {
                "id": slot.id,
                "date": str(slot.date),
                "start_time": str(slot.start_time),
                "end_time": str(slot.end_time),
            },
            "Status": "SLOT_VALIDATED",
        }

    async def reserve_slot(self, state: SchedulerState) -> dict[str, Any]:
        """Reserve the slot with row-level locking to prevent double booking."""
        slot_id = state["SlotId"]
        candidate_id = state["CandidateID"]
        reserved = await self.slot_service.reserve_slot(slot_id, candidate_id)
        if not reserved:
            return {"Status": "FAILED", "Error": "Could not reserve slot — it may have been taken."}
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if candidate and reserved.company_id != candidate.company_id:
            reserved.is_booked = False
            reserved.booked_candidate = None
            return {"Status": "FAILED", "Error": "Slot does not belong to this company."}
        return {"Status": "SLOT_RESERVED"}

    async def prepare_interview_room(self, state: SchedulerState) -> dict[str, Any]:
        """AI interview runs in the in-app room (Agent 5 media + Agent 4). No Google Meet."""
        return {
            "CalendarEventID": None,
            "MeetingLink": "",
            "Status": "INTERVIEW_ROOM_READY",
        }

    async def save_interview_details(self, state: SchedulerState) -> dict[str, Any]:
        """Persist interview record to PostgreSQL."""
        from datetime import date, time

        slot = state["SelectedSlot"]
        interview_date = date.fromisoformat(slot["date"])
        interview_time = time.fromisoformat(slot["start_time"])

        join_service = JoinTokenService()
        raw_join_token = join_service.generate_token_value()
        join_token_hash = join_service.hash_token(raw_join_token)
        from services.blueprint_service import BlueprintService

        duration_minutes = await BlueprintService(self.candidate_repo.db).planned_duration_minutes(
            state["CandidateID"]
        )
        join_expires_at = join_service.compute_expiry(
            interview_date,
            interview_time,
            duration_minutes=duration_minutes,
        )
        join_link = join_service.build_join_link(raw_join_token)

        candidate = await self.candidate_repo.get_by_candidate_id(state["CandidateID"])
        await self.interview_repo.create(
            candidate_id=state["CandidateID"],
            company_id=candidate.company_id if candidate else None,
            scheduled_date=interview_date,
            scheduled_time=interview_time,
            meeting_link=join_link,
            calendar_event_id=None,
            join_token_hash=join_token_hash,
            join_token_expires_at=join_expires_at,
        )

        from models.candidate import CandidateStatus

        await self.candidate_repo.update_status(state["CandidateID"], CandidateStatus.INTERVIEW_SCHEDULED)

        schedule_token = await self.token_repo.get_by_token(state["Token"])
        if schedule_token:
            await self.token_repo.mark_used(schedule_token)

        from sqlalchemy.orm.attributes import flag_modified

        candidate = await self.candidate_repo.get_by_candidate_id(state["CandidateID"])
        if candidate is not None:
            snapshot = dict(candidate.evaluation_snapshot or {})
            agent5_meta = dict(snapshot.get("agent5") or {})
            agent5_meta["join_link"] = join_link
            snapshot["agent5"] = agent5_meta
            candidate.evaluation_snapshot = snapshot
            flag_modified(candidate, "evaluation_snapshot")

        return {
            "Status": "INTERVIEW_SAVED",
            "MeetingLink": join_link,
            "JoinLink": join_link,
            "JoinToken": raw_join_token,
        }

    async def send_confirmation_email(self, state: SchedulerState) -> dict[str, Any]:
        """Send confirmation email with hashed join link (not raw Meet URL)."""
        slot = state["SelectedSlot"]
        join_link = state.get("JoinLink") or state.get("MeetingLink") or ""
        if not join_link:
            interview = await self.interview_repo.get_by_candidate_id(state["CandidateID"])
            if interview and interview.meeting_link:
                join_link = interview.meeting_link
        if not join_link:
            logger.error(
                "Confirmation email missing join link for candidate %s",
                state.get("CandidateID"),
            )
        company_name, company_code = await self._company_brand(state)
        self.email_service.send_confirmation_email(
            candidate_name=state["CandidateName"],
            candidate_email=state["Email"],
            interview_date=slot["date"],
            interview_time=slot["start_time"],
            join_link=join_link,
            job_position=state.get("JobPosition") or "",
            company_code=company_code,
            company_name=company_name,
            smtp=await self._smtp_for_state(state),
        )
        return {"Status": "COMPLETED"}
