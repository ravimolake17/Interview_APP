"""
Agent 4 LangGraph workflow — live interview turn loop with parallel Agent 6.

START → load_session → present_question → wait_for_answer (interrupt)
     → process_answer_parallel (Agent 6 eval ∥ Agent 4 follow-ups)
     → (more?) present_question : complete → END

Enterprise notes:
  - Meta Llama (via Groq) powers question adaptation + evaluation feedback
  - Agent 6 scores answers vs resume, JD, and internet research
  - Whisper Large-v3 STT supplies answer transcripts; PlayAI TTS speaks questions
  - Checkpoints persist in Postgres (shared runtime)
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from agents.evaluation_agent.evaluator import build_candidate_context
from agents.interview_agent import nodes
from agents.interview_agent.state import InterviewAgentState
from agents.shared.llama_client import llama_model_id
from core.langgraph_runtime import aget_graph_state, ainvoke_graph, get_checkpointer, thread_config
from services.interview_agent_service import InterviewAgentService

logger = logging.getLogger(__name__)


def _route_after_load(state: InterviewAgentState) -> str:
    if state.get("Status") == "FAILED":
        return "end_failed"
    return "present_question"


def _route_after_present(state: InterviewAgentState) -> str:
    if state.get("Status") == "COMPLETED":
        return "complete"
    if state.get("Status") == "FAILED":
        return "end_failed"
    return "wait_for_answer"


def _route_after_process(state: InterviewAgentState) -> str:
    if state.get("Status") == "FAILED":
        return "end_failed"
    if state.get("Status") == "COMPLETED":
        return "complete"
    return "present_question"


def build_interview_graph():
    graph = StateGraph(InterviewAgentState)
    graph.add_node("load_session", nodes.load_session)
    graph.add_node("present_question", nodes.present_question)
    graph.add_node("wait_for_answer", nodes.wait_for_answer)
    graph.add_node("process_answer_parallel", nodes.process_answer_parallel)
    graph.add_node("complete_session", nodes.complete_session)

    graph.add_edge(START, "load_session")
    graph.add_conditional_edges(
        "load_session",
        _route_after_load,
        {"present_question": "present_question", "end_failed": END},
    )
    graph.add_conditional_edges(
        "present_question",
        _route_after_present,
        {
            "wait_for_answer": "wait_for_answer",
            "complete": "complete_session",
            "end_failed": END,
        },
    )
    graph.add_edge("wait_for_answer", "process_answer_parallel")
    graph.add_conditional_edges(
        "process_answer_parallel",
        _route_after_process,
        {
            "present_question": "present_question",
            "complete": "complete_session",
            "end_failed": END,
        },
    )
    graph.add_edge("complete_session", END)
    return graph.compile(checkpointer=get_checkpointer())


class InterviewLangGraphAgent:
    """High-level interface for Agent 4 + Agent 6 parallel interview sessions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.service = InterviewAgentService(db)
        self.graph = build_interview_graph()

    def _config(self, candidate_id: str) -> dict[str, Any]:
        return thread_config("interview", candidate_id)

    async def _evaluation_context(self, candidate_id: str) -> dict[str, str]:
        candidate = await self.service.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            return {}
        snap = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
        return build_candidate_context(
            jd_text=candidate.jd_text,
            evaluation_snapshot=snap,
            job_position=candidate.job_position,
        )

    async def start_session(self, candidate_id: str, *, force_questions: bool = False) -> dict[str, Any]:
        """Ensure Llama questions exist, then run until first answer interrupt."""
        question_set = await self.service.generate_questions(
            candidate_id, force=force_questions
        )
        context = await self._evaluation_context(candidate_id)
        duration = question_set.total_duration_minutes
        if duration is None:
            duration = await self.service.default_duration_minutes()
        initial: InterviewAgentState = {
            "CandidateID": candidate_id,
            "QuestionSetId": question_set.id,
            "Questions": [q.model_dump(mode="json") for q in question_set.questions],
            "CurrentIndex": 0,
            "TurnHistory": [],
            "EvaluationContext": context,
            "Status": "STARTED",
            "Model": llama_model_id(),
            "PlannedDurationMinutes": int(duration) if duration is not None else None,
            "SessionStartedAt": datetime.now(timezone.utc).isoformat(),
            "DurationExtended": False,
            "InterviewPhase": "QUESTIONS",
            "CandidateQnaTurns": 0,
            "PendingAiReply": None,
            "TurnAck": None,
        }
        result = await ainvoke_graph(self.graph, initial, config=self._config(candidate_id))
        await self._maybe_run_agent7(candidate_id, result)
        return dict(result)

    async def submit_answer(self, candidate_id: str, answer_text: str) -> dict[str, Any]:
        """Resume after Whisper STT / typed answer — Agent 6 evaluates in parallel."""
        result = await ainvoke_graph(
            self.graph,
            Command(resume={"answer_text": answer_text}),
            config=self._config(candidate_id),
        )
        await self._maybe_run_agent7(candidate_id, result)
        return dict(result)

    async def hr_skip_or_goto(
        self,
        candidate_id: str,
        *,
        action: str = "skip",
        target_index: int | None = None,
    ) -> dict[str, Any]:
        """HR live control: skip current question/follow-up or jump to a bank index."""
        payload: dict[str, Any] = {"hr_action": action, "answer_text": "__HR_SKIP__"}
        if action == "goto" and target_index is not None:
            payload["target_index"] = int(target_index)
        result = await ainvoke_graph(
            self.graph,
            Command(resume=payload),
            config=self._config(candidate_id),
        )
        await self._maybe_run_agent7(candidate_id, result)
        return dict(result)

    async def hr_add_question(
        self,
        candidate_id: str,
        question_text: str,
        *,
        ask_now: bool = True,
    ) -> dict[str, Any]:
        """Append an HR-authored question; optionally jump to it immediately."""
        from uuid import uuid4

        config = self._config(candidate_id)
        snapshot = await aget_graph_state(self.graph, config)
        if not snapshot or not snapshot.values:
            raise ValueError("No AI interview session found.")
        values = dict(snapshot.values)
        questions = list(values.get("Questions") or [])
        new_q = {
            "id": f"hr-{uuid4().hex[:10]}",
            "order": len(questions) + 1,
            "category_id": "hr_live",
            "category_name": "HR question",
            "difficulty": "medium",
            "question_text": question_text.strip(),
            "intent": "Added live by HR",
            "follow_up_hints": [],
            "estimated_seconds": 120,
            "skill_tags": [],
            "audio_ready": False,
            "added_by_hr": True,
        }
        questions.append(new_q)
        await self.graph.aupdate_state(
            config,
            {
                "Questions": questions,
                "TotalQuestions": len(questions),
                "RemainingQuestions": max(0, len(questions) - int(values.get("CurrentIndex") or 0)),
            },
        )
        if ask_now:
            return await self.hr_skip_or_goto(
                candidate_id,
                action="goto",
                target_index=len(questions) - 1,
            )
        state = await self.get_session_state(candidate_id)
        return dict(state or values)

    async def get_session_state(self, candidate_id: str) -> dict[str, Any] | None:
        snapshot = await aget_graph_state(self.graph, self._config(candidate_id))
        if snapshot and snapshot.values:
            return dict(snapshot.values)
        return None

    async def _maybe_run_agent7(self, candidate_id: str, state: Any) -> None:
        payload = dict(state or {})
        if str(payload.get("Status") or "") != "COMPLETED":
            return
        extra: list[dict[str, Any]] = []
        evaluation = payload.get("LatestEvaluation")
        history = list(payload.get("TurnHistory") or [])
        if evaluation and history:
            last = history[-1]
            question = last.get("question") or {}
            if not (question.get("is_candidate_qna") or last.get("candidate_qna")):
                extra.append(
                    {
                        "score": evaluation.get("score"),
                        "verdict": evaluation.get("verdict"),
                        "evaluation": evaluation,
                        "question_text": question.get("question_text"),
                    }
                )
        try:
            from services.recommendation_agent_service import RecommendationAgentService

            await RecommendationAgentService(self.db).generate_report(
                candidate_id,
                force=True,
                extra_evaluations=extra,
            )
        except Exception:
            logger.warning("Agent 7 report skipped for %s", candidate_id, exc_info=True)
