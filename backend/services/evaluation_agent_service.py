"""Agent 6 evaluation service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.evaluation_agent.evaluator import (
    build_candidate_context,
    evaluate_answer_with_llama,
)
from agents.evaluation_agent.graph import EvaluationLangGraphAgent
from agents.evaluation_agent.schemas import EvaluationResult, EvaluateAnswerResponse
from agents.shared.llama_client import llama_available, llama_model_id
from core.chroma_runtime import chroma_status
from core.chroma_store import index_evaluation_example
from repositories.candidate_repository import CandidateRepository
from repositories.interview_evaluation_repository import InterviewEvaluationRepository
from repositories.interview_question_set_repository import InterviewQuestionSetRepository
from services.interview_answer_report import build_interview_answer_report


class EvaluationAgentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.candidate_repo = CandidateRepository(db)
        self.eval_repo = InterviewEvaluationRepository(db)
        self.questions_repo = InterviewQuestionSetRepository(db)

    async def _answer_report(self, candidate_id: str, candidate) -> dict[str, Any]:
        rows = await self.eval_repo.list_for_candidate(candidate_id, limit=100)
        question_set = await self.questions_repo.get_latest(candidate_id)
        planned = list(question_set.questions_json or []) if question_set else []
        turn_history: list[Any] = []
        try:
            from agents.interview_agent.graph import InterviewLangGraphAgent

            state = await InterviewLangGraphAgent(self.db).get_session_state(candidate_id)
            turn_history = list((state or {}).get("TurnHistory") or [])
        except Exception:
            turn_history = []
        if turn_history:
            from services.interview_oral_store import sync_oral_from_history

            if sync_oral_from_history(candidate, turn_history):
                try:
                    await self.db.commit()
                except Exception:
                    await self.db.rollback()
        return build_interview_answer_report(
            candidate=candidate,
            evaluations=rows,
            planned_oral_questions=planned,
            turn_history=turn_history,
        )

    async def _context(self, candidate_id: str) -> dict[str, str]:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")
        snap = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
        return build_candidate_context(
            jd_text=candidate.jd_text,
            evaluation_snapshot=snap,
            job_position=candidate.job_position,
        )

    async def get_status(self, candidate_id: str) -> dict[str, Any]:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")
        rows = await self.eval_repo.list_for_candidate(candidate_id, limit=100)
        report = await self._answer_report(candidate_id, candidate)
        return {
            "candidate_id": candidate_id,
            "llama_ready": llama_available(),
            "model": llama_model_id(),
            "evaluations_count": len(rows),
            "latest": rows[0].evaluation_json if rows else None,
            "report": report,
            "capabilities": {
                "meta_llama": llama_available(),
                "resume_jd_context": True,
                "web_research": True,
                "langgraph": True,
                "chroma_memory": bool(chroma_status().get("ready")),
                "parallel_with_agent4": True,
            },
        }

    async def evaluate(
        self,
        candidate_id: str,
        *,
        question_id: str,
        question_text: str,
        candidate_answer: str,
        skill_tags: list[str] | None = None,
        use_web: bool = True,
        use_langgraph: bool = True,
    ) -> EvaluateAnswerResponse:
        context = await self._context(candidate_id)

        if use_langgraph:
            agent = EvaluationLangGraphAgent()
            result = await agent.evaluate(
                candidate_id=candidate_id,
                question_id=question_id,
                question_text=question_text,
                candidate_answer=candidate_answer,
                context=context,
                skill_tags=skill_tags,
                use_web=use_web,
            )
            evaluation = EvaluationResult.model_validate(result.get("Evaluation") or {})
        else:
            evaluation = evaluate_answer_with_llama(
                question_text=question_text,
                candidate_answer=candidate_answer,
                context=context,
                skill_tags=skill_tags,
                use_web=use_web,
            )

        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")
        await self.eval_repo.create(
            candidate_id=candidate_id,
            question_id=question_id or None,
            question_text=question_text,
            answer_text=candidate_answer,
            score=evaluation.score,
            verdict=evaluation.verdict,
            evaluation_json=evaluation.model_dump(mode="json"),
            model=evaluation.model,
            company_id=candidate.company_id,
        )
        index_evaluation_example(
            question_text=question_text,
            answer_text=candidate_answer,
            score=evaluation.score,
            verdict=evaluation.verdict,
            role=str(context.get("job_position") or ""),
            skills=skill_tags,
        )
        return EvaluateAnswerResponse(
            candidate_id=candidate_id,
            evaluation=evaluation,
            context_used={
                "job_position": context.get("job_position"),
                "skills": context.get("skills"),
                "has_jd": bool(context.get("jd_text")),
                "has_resume_summary": bool(context.get("resume_summary")),
                "web_enabled": use_web,
            },
        )

    async def list_evaluations(self, candidate_id: str) -> dict[str, Any]:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")
        rows = await self.eval_repo.list_for_candidate(candidate_id, limit=100)
        report = await self._answer_report(candidate_id, candidate)
        evaluations = [
            {
                "id": row.id,
                "question_id": row.question_id,
                "question_text": row.question_text,
                "answer_text": row.answer_text,
                "score": row.score,
                "verdict": row.verdict,
                "evaluation": row.evaluation_json,
                "model": row.model,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
        return {
            "candidate_id": candidate_id,
            "evaluations": evaluations,
            "report": report,
        }
