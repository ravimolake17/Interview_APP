"""Agent 7 — final HR recommendation report."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.recommendation_agent.graph import RecommendationLangGraphAgent
from agents.recommendation_agent.report_builder import gather_evidence
from agents.recommendation_agent.schemas import HrRecommendationReport, HrRecommendationResponse
from agents.shared.llama_client import llama_available, llama_model_id
from core.chroma_runtime import chroma_status
from core.chroma_store import index_hr_outcome
from repositories.candidate_repository import CandidateRepository
from repositories.hr_recommendation_repository import HrRecommendationRepository
from repositories.interview_evaluation_repository import InterviewEvaluationRepository
from repositories.interview_question_set_repository import InterviewQuestionSetRepository
from services.interview_answer_report import build_interview_answer_report


class RecommendationNotReady(Exception):
    """HR report cannot be generated until the interview has been attempted."""


class RecommendationAgentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.candidate_repo = CandidateRepository(db)
        self.report_repo = HrRecommendationRepository(db)
        self.eval_repo = InterviewEvaluationRepository(db)
        self.questions_repo = InterviewQuestionSetRepository(db)

    def _capabilities(self, *, interview_ready: bool = False) -> dict[str, Any]:
        return {
            "meta_llama": llama_available(),
            "chroma_memory": bool(chroma_status().get("ready")),
            "langgraph": True,
            "screening_context": True,
            "interview_scores": interview_ready,
        }

    async def _interview_report(self, candidate_id: str, candidate) -> dict[str, Any]:
        eval_rows = await self.eval_repo.list_for_candidate(candidate_id, limit=100)
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
            evaluations=eval_rows,
            planned_oral_questions=planned,
            turn_history=turn_history,
        )

    def _to_response(self, candidate, row=None, report: HrRecommendationReport | None = None) -> HrRecommendationResponse:
        if report is None and row is not None:
            report = HrRecommendationReport.model_validate(row.report_json or {})
        if report is None:
            report = HrRecommendationReport()
        return HrRecommendationResponse(
            candidate_id=candidate.candidate_id,
            report_id=row.id if row else None,
            full_name=candidate.full_name,
            job_position=candidate.job_position,
            report=report,
            created_at=row.created_at if row else None,
            capabilities=self._capabilities(interview_ready=bool(report.interview_attempted)),
        )

    async def get_status(self, candidate_id: str) -> dict[str, Any]:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")
        row = await self.report_repo.get_latest(candidate_id)
        evals = await self.eval_repo.list_for_candidate(candidate_id, limit=100)
        report = await self._interview_report(candidate_id, candidate)
        interview_ready = bool(report.get("interview_attempted"))
        return {
            "candidate_id": candidate_id,
            "llama_ready": llama_available(),
            "model": llama_model_id(),
            "report_ready": row is not None,
            "latest": self._to_response(candidate, row).model_dump(mode="json") if row else None,
            "evaluations_count": len(evals),
            "interview_ready": interview_ready,
            "interview_score": report.get("interview_score"),
            "questions_total": report.get("questions_total"),
            "questions_answered": report.get("questions_answered"),
            "incomplete": report.get("incomplete"),
            "left_early": report.get("left_early"),
            "capabilities": self._capabilities(interview_ready=interview_ready),
        }

    async def get_report(self, candidate_id: str) -> HrRecommendationResponse:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")
        row = await self.report_repo.get_latest(candidate_id)
        if not row:
            raise ValueError("No Agent 7 report yet. Generate the recommendation first.")
        return self._to_response(candidate, row)

    async def list_reports(self, *, limit: int = 40, company_id: int | None = None) -> list[dict[str, Any]]:
        rows = await self.report_repo.list_recent(limit=limit, company_id=company_id)
        out: list[dict[str, Any]] = []
        for row, candidate in rows:
            out.append(
                {
                    "report_id": row.id,
                    "candidate_id": candidate.candidate_id,
                    "full_name": candidate.full_name,
                    "job_position": candidate.job_position,
                    "decision": row.decision,
                    "overall_score": row.overall_score,
                    "screening_score": row.screening_score,
                    "interview_score": row.interview_score,
                    "stage": row.stage,
                    "executive_summary": row.executive_summary,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
            )
        return out

    async def generate_report(
        self,
        candidate_id: str,
        *,
        force: bool = False,
        extra_evaluations: list[dict[str, Any]] | None = None,
    ) -> HrRecommendationResponse:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        if not force:
            existing = await self.report_repo.get_latest(candidate_id)
            if existing:
                return self._to_response(candidate, existing)

        eval_rows = await self.eval_repo.list_for_candidate(candidate_id, limit=100)
        interview_report = await self._interview_report(candidate_id, candidate)
        if not interview_report.get("interview_attempted"):
            raise RecommendationNotReady(
                "The HR report cannot be generated until Agent 6 has interview evidence. "
                "Wait until the candidate answers MCQ/oral questions, or until they leave or complete the interview."
            )
        evaluations = [
            {
                "score": row.score,
                "verdict": row.verdict,
                "evaluation": row.evaluation_json,
                "question_text": row.question_text,
            }
            for row in eval_rows
        ]
        for item in extra_evaluations or []:
            if item:
                evaluations.append(item)
        evidence = gather_evidence(
            candidate=candidate,
            evaluations=evaluations,
            interview_report=interview_report,
        )
        agent = RecommendationLangGraphAgent()
        result = await agent.generate(candidate_id=candidate_id, evidence=evidence)
        if result.get("Status") == "FAILED":
            raise RuntimeError(result.get("Error") or "Agent 7 recommendation failed.")
        report = HrRecommendationReport.model_validate(result.get("Report") or {})

        row = await self.report_repo.create(
            candidate_id=candidate_id,
            decision=report.decision,
            overall_score=report.overall_score,
            screening_score=report.screening_score,
            interview_score=report.interview_score,
            stage=report.stage,
            executive_summary=report.executive_summary,
            report_json=report.model_dump(mode="json"),
            model=report.model,
            company_id=candidate.company_id,
        )
        index_hr_outcome(
            candidate_id=candidate_id,
            role=candidate.job_position or "",
            decision=report.decision,
            score=report.overall_score,
            summary=report.executive_summary,
            source="agent7",
        )
        return self._to_response(candidate, row, report)
