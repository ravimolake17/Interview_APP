"""
LangGraph workflow definition for the Interview Scheduler Agent.

Workflow:
  START → Load Candidate → Generate Token → Create Slots → Send Email
       → Wait For Selection (interrupt) → Validate → Reserve
       → Prepare in-app interview room → Save → Confirmation Email → END
"""

import logging

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from agents.scheduler_agent.nodes import SchedulerNodes
from agents.scheduler_agent.state import SchedulerState
from core.langgraph_runtime import (
    aget_graph_state,
    ainvoke_graph,
    get_checkpointer,
    thread_config,
)
from repositories.candidate_repository import CandidateRepository
from repositories.interview_repository import InterviewRepository
from repositories.slot_repository import SlotRepository
from repositories.token_repository import TokenRepository
from services.email_service import EmailService
from services.slot_service import SlotService
from services.token_service import TokenService

logger = logging.getLogger(__name__)

_compiled_graph = None


def _route_after_validation(state: SchedulerState) -> str:
    if state.get("Status") == "FAILED":
        return "end_failed"
    return "reserve_slot"


def build_scheduler_graph(nodes: SchedulerNodes):
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(SchedulerState)

    graph.add_node("load_candidate", nodes.load_candidate)
    graph.add_node("generate_secure_scheduling_token", nodes.generate_secure_scheduling_token)
    graph.add_node("create_available_time_slots", nodes.create_available_time_slots)
    graph.add_node("send_congratulations_email", nodes.send_congratulations_email)
    graph.add_node("wait_for_candidate_slot_selection", nodes.wait_for_candidate_slot_selection)
    graph.add_node("validate_slot", nodes.validate_slot)
    graph.add_node("reserve_slot", nodes.reserve_slot)
    graph.add_node("prepare_interview_room", nodes.prepare_interview_room)
    graph.add_node("save_interview_details", nodes.save_interview_details)
    graph.add_node("send_confirmation_email", nodes.send_confirmation_email)

    graph.add_edge(START, "load_candidate")
    graph.add_edge("load_candidate", "generate_secure_scheduling_token")
    graph.add_edge("generate_secure_scheduling_token", "create_available_time_slots")
    graph.add_edge("create_available_time_slots", "send_congratulations_email")
    graph.add_edge("send_congratulations_email", "wait_for_candidate_slot_selection")
    graph.add_edge("wait_for_candidate_slot_selection", "validate_slot")
    graph.add_conditional_edges(
        "validate_slot",
        _route_after_validation,
        {"reserve_slot": "reserve_slot", "end_failed": END},
    )
    graph.add_edge("reserve_slot", "prepare_interview_room")
    graph.add_edge("prepare_interview_room", "save_interview_details")
    graph.add_edge("save_interview_details", "send_confirmation_email")
    graph.add_edge("send_confirmation_email", END)

    return graph.compile(checkpointer=get_checkpointer())


def create_nodes_from_session(db: AsyncSession) -> SchedulerNodes:
    candidate_repo = CandidateRepository(db)
    interview_repo = InterviewRepository(db)
    slot_repo = SlotRepository(db)
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    slot_service = SlotService(slot_repo)
    email_service = EmailService()

    return SchedulerNodes(
        candidate_repo=candidate_repo,
        interview_repo=interview_repo,
        slot_repo=slot_repo,
        token_repo=token_repo,
        token_service=token_service,
        slot_service=slot_service,
        email_service=email_service,
    )


class SchedulerAgent:
    """High-level interface for running the Interview Scheduler LangGraph agent."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.nodes = create_nodes_from_session(db)
        self.graph = build_scheduler_graph(self.nodes)

    def _thread_config(self, candidate_id: str) -> dict:
        return thread_config("scheduler", candidate_id)

    async def start_invite_workflow(self, candidate_id: str) -> dict:
        """
        Start the scheduler workflow after Agent 1 shortlists a candidate.
        Runs until the interrupt point (waiting for slot selection).

        If HR later updates email and resends, reuse the existing interrupt
        instead of restarting the LangGraph thread (that would drop slot wait).
        """
        initial_state: SchedulerState = {
            "CandidateID": candidate_id,
            "Status": "STARTED",
        }
        config = self._thread_config(candidate_id)
        snapshot = await aget_graph_state(self.graph, config)
        values = dict(snapshot.values) if snapshot and snapshot.values else {}
        nxt = [str(n) for n in (getattr(snapshot, "next", None) or [])]
        if any("wait_for_candidate_slot_selection" in n for n in nxt):
            resent = await self._resend_existing_invite(candidate_id, values)
            if resent:
                return resent

        result = await ainvoke_graph(self.graph, initial_state, config=config)
        return dict(result)

    async def _resend_existing_invite(self, candidate_id: str, values: dict) -> dict | None:
        """Resend the scheduling email from current DB contact + existing token."""
        link = (values.get("SchedulingLink") or "").strip()
        token = (values.get("Token") or "").strip()
        if not link or not token:
            return None

        candidate = await self.nodes.candidate_repo.get_by_candidate_id(candidate_id)
        email = (candidate.email if candidate else None) or values.get("Email")
        name = (candidate.full_name if candidate else None) or values.get("CandidateName")
        job_position = values.get("JobPosition") or (
            candidate.job_position if candidate else ""
        )
        if not email:
            return None

        brand_state = dict(values)
        brand_state["CandidateID"] = candidate_id
        company_name, company_code = await self.nodes._company_brand(brand_state)
        result = self.nodes.email_service.send_congratulations_email(
            candidate_name=name or "Candidate",
            candidate_email=email,
            scheduling_link=link,
            job_position=job_position or "",
            company_code=company_code,
            company_name=company_name,
            smtp=await self.nodes._smtp_for_state(brand_state),
        )
        logger.info("Resent scheduling invite for %s using existing LangGraph interrupt", candidate_id)
        return {
            **values,
            "Email": email,
            "CandidateName": name,
            "Status": "INVITE_SENT",
            "Token": token,
            "SchedulingLink": link,
            "ThreadId": result.get("id", ""),
        }

    async def resume_with_slot(
        self,
        candidate_id: str,
        slot_id: int,
        slot: dict,
        *,
        token: str | None = None,
    ) -> dict:
        """Resume the graph after the candidate selects a slot.

        If the interrupt checkpoint is gone (MemorySaver + server reload),
        finish the booking from Postgres so the candidate is not blocked.
        """
        from langgraph.types import Command

        config = self._thread_config(candidate_id)
        snapshot = await aget_graph_state(self.graph, config)
        values = dict(snapshot.values) if snapshot and snapshot.values else {}
        nxt = list(getattr(snapshot, "next", None) or [])
        can_resume = bool(values) and bool(nxt)

        if can_resume:
            try:
                resume_data = {"slot_id": slot_id, "slot": slot}
                result = await ainvoke_graph(
                    self.graph, Command(resume=resume_data), config=config
                )
                return dict(result)
            except Exception:
                logger.exception(
                    "LangGraph slot resume failed for %s; booking from database",
                    candidate_id,
                )

        return await self.complete_booking_from_db(
            candidate_id, slot_id, slot, token=token or values.get("Token")
        )

    async def complete_booking_from_db(
        self,
        candidate_id: str,
        slot_id: int,
        slot: dict,
        *,
        token: str | None = None,
    ) -> dict:
        """Run post-selection nodes without a live LangGraph interrupt."""
        from services.job_position import resolve_job_position_from_jd

        candidate = await self.nodes.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            return {"Status": "FAILED", "Error": f"Candidate {candidate_id} not found."}

        company_name, company_code = await self.nodes._company_brand(
            {"CandidateID": candidate_id, "CompanyName": None, "CompanyCode": None}
        )
        state: dict = {
            "CandidateID": candidate.candidate_id,
            "CandidateName": candidate.full_name,
            "Email": candidate.email,
            "JobPosition": resolve_job_position_from_jd(
                jd_text=candidate.jd_text,
                jd_original_filename=candidate.jd_original_filename,
                stored_job_position=candidate.job_position,
            ),
            "CompanyName": company_name,
            "CompanyCode": company_code,
            "Token": (token or "").strip(),
            "SlotId": slot_id,
            "SelectedSlot": slot,
            "Status": "SLOT_SELECTED",
        }
        for step in (
            self.nodes.validate_slot,
            self.nodes.reserve_slot,
            self.nodes.prepare_interview_room,
            self.nodes.save_interview_details,
            self.nodes.send_confirmation_email,
        ):
            update = await step(state)
            if update:
                state.update(update)
            if str(state.get("Status") or "") == "FAILED":
                return state
        return state

    async def get_workflow_state(self, candidate_id: str) -> dict | None:
        config = self._thread_config(candidate_id)
        snapshot = await aget_graph_state(self.graph, config)
        if snapshot and snapshot.values:
            return dict(snapshot.values)
        return None
