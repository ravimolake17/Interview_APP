"""Agent 3 service — build blueprint request from screening data and persist results."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.blueprint_agent.generator import generate_interview_blueprint
from agents.blueprint_agent.graph import run_blueprint_graph
from agents.blueprint_agent.schemas import (
    AtsMatchResult,
    InterviewBlueprintRequest,
    InterviewBlueprintResponse,
)
from models.candidate import Candidate
from models.interview_blueprint import InterviewBlueprint
from repositories.blueprint_repository import BlueprintRepository
from repositories.candidate_repository import CandidateRepository
from services.application_settings_service import ApplicationSettingsService

logger = logging.getLogger(__name__)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_blueprint_request_from_snapshot(
    *,
    evaluation_snapshot: dict[str, Any] | None,
    jd_text: str | None = None,
    resume_score: float | None = None,
    job_position: str | None = None,
) -> InterviewBlueprintRequest:
    """Map Agent 1 evaluation_snapshot (+ JD text) into Agent 3 request payload."""
    snap = evaluation_snapshot or {}
    parsed_resume = _as_dict(snap.get("parsed_resume"))
    candidate_details = _as_dict(snap.get("candidate_details"))
    extracted_skills = _as_dict(snap.get("extracted_resume_skills"))
    jd_json = _as_dict(snap.get("extracted_jd_requirements"))
    match = _as_dict(snap.get("match_analysis"))
    score = _as_dict(snap.get("score_breakdown"))

    resume_json: dict[str, Any]
    if parsed_resume:
        resume_json = dict(parsed_resume)
    else:
        resume_json = {
            "name": candidate_details.get("name") or "Candidate",
            "emails": _as_list(candidate_details.get("emails")),
            "phones": _as_list(candidate_details.get("phones")),
            "skills": extracted_skills.get("normalized_skills")
            or extracted_skills.get("items")
            or extracted_skills,
            "education": _as_list(snap.get("candidate_education")),
            "certifications": _as_list(snap.get("candidate_certifications")),
            "source_text": snap.get("resume_text") or "",
            "candidate_experience_years": snap.get("candidate_experience_years"),
            "candidate_relevant_experience_years": snap.get(
                "candidate_relevant_experience_years"
            ),
        }

    if not resume_json.get("source_text") and snap.get("resume_text"):
        resume_json["source_text"] = snap["resume_text"]

    resolved_jd_text = (jd_text or "").strip()
    if not resolved_jd_text and jd_json:
        parts: list[str] = []
        if jd_json.get("job_title"):
            parts.append(str(jd_json["job_title"]))
        responsibilities = _as_list(jd_json.get("responsibilities"))
        if responsibilities:
            parts.append("\n".join(str(item) for item in responsibilities))
        resolved_jd_text = "\n\n".join(parts).strip()

    if not resolved_jd_text:
        title = (
            (job_position or "").strip()
            or str(jd_json.get("job_title") or "").strip()
            or "Open Role"
        )
        if not jd_json.get("job_title"):
            jd_json = {**jd_json, "job_title": title}
        resolved_jd_text = (
            f"{title}\n\nJob description was not extracted. "
            "Plan a general competency interview using the resume and ATS match."
        )

    matched_skills = (
        _as_list(score.get("matched_skills"))
        or _as_list(match.get("matched_required_skills"))
        or _as_list(match.get("matched_preferred_skills"))
    )
    missing_skills = (
        _as_list(score.get("missing_skills"))
        or _as_list(match.get("missing_required_skills"))
        or _as_list(match.get("missing_preferred_skills"))
    )
    weak_areas = _as_list(score.get("concerns")) or _as_list(match.get("weak_areas"))

    overall_score = score.get("overall_score")
    if overall_score is None:
        overall_score = resume_score if resume_score is not None else 0.0

    status = str(snap.get("shortlist_status") or score.get("decision") or "Shortlisted")

    return InterviewBlueprintRequest(
        resume_json=resume_json,
        jd_text=resolved_jd_text,
        jd_json=jd_json,
        ats_match_result=AtsMatchResult(
            overall_score=float(overall_score),
            status=status,
            matched_skills=[str(s) for s in matched_skills],
            missing_skills=[str(s) for s in missing_skills],
            weak_areas=[str(s) for s in weak_areas],
        ),
        ats_evaluation_result=snap,
    )


class BlueprintService:
    """Generate and persist Agent 3 interview blueprints."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = BlueprintRepository(db)
        self.candidate_repo = CandidateRepository(db)

    def generate(self, payload: InterviewBlueprintRequest) -> InterviewBlueprintResponse:
        """Legacy sync entry — prefer generate_via_graph for enterprise flows."""
        return generate_interview_blueprint(payload)

    async def generate_via_graph(
        self,
        payload: InterviewBlueprintRequest,
        *,
        candidate_id: str = "adhoc",
    ) -> tuple[InterviewBlueprintResponse, dict[str, Any]]:
        """LangGraph path: retry primary planner, then safe fallback blueprint."""
        return await run_blueprint_graph(payload, candidate_id=candidate_id)

    async def generate_and_save_for_candidate(
        self,
        candidate_id: str,
        *,
        force: bool = False,
        candidate_level: str | None = None,
        total_duration_minutes: int | None = None,
    ) -> tuple[InterviewBlueprint, InterviewBlueprintResponse]:
        candidate = await self.candidate_repo.get_by_candidate_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        has_overrides = candidate_level is not None or total_duration_minutes is not None
        if not force and not has_overrides:
            existing = await self.repo.get_latest_for_candidate(candidate_id)
            if existing:
                await self._ensure_interview_questions(candidate_id, force=False)
                return existing, InterviewBlueprintResponse.model_validate(
                    existing.blueprint_json
                )

        payload = build_blueprint_request_from_snapshot(
            evaluation_snapshot=candidate.evaluation_snapshot,
            jd_text=candidate.jd_text,
            resume_score=candidate.resume_score,
            job_position=candidate.job_position,
        )
        if candidate_level:
            payload.candidate_level = candidate_level  # type: ignore[assignment]
        payload.total_duration_minutes = (
            total_duration_minutes
            if total_duration_minutes is not None
            else await self.default_duration_minutes()
        )

        blueprint, meta = await self.generate_via_graph(payload, candidate_id=candidate_id)
        if meta.get("used_fallback"):
            logger.warning(
                "Agent 3 fallback blueprint saved for %s after %s attempt(s): %s",
                candidate_id,
                meta.get("attempts"),
                meta.get("error"),
            )
        row = await self._persist(candidate, blueprint)
        await self._ensure_interview_questions(candidate.candidate_id, force=True)
        return row, blueprint

    async def ensure_plan_and_questions(
        self,
        candidate_id: str,
    ) -> tuple[InterviewBlueprint, InterviewBlueprintResponse] | None:
        """Create Agent 3 + Agent 4 when missing.

        Used after a late invite (HR added email later) and after slot booking
        so the rest of the pipeline still runs even if Agent 2 used the
        database fallback instead of a live LangGraph interrupt.
        """
        try:
            return await self.generate_and_save_for_candidate(
                candidate_id, force=False
            )
        except Exception:
            logger.exception(
                "Agent 3/4 pipeline ensure failed for %s (non-fatal)",
                candidate_id,
            )
            return None

    async def generate_and_save_from_evaluation(
        self,
        candidate: Candidate,
        *,
        evaluation_snapshot: dict[str, Any] | None = None,
        jd_text: str | None = None,
    ) -> tuple[InterviewBlueprint, InterviewBlueprintResponse] | None:
        """Best-effort generation after shortlist. Uses LangGraph retry/fallback."""
        try:
            snapshot = evaluation_snapshot or candidate.evaluation_snapshot
            payload = build_blueprint_request_from_snapshot(
                evaluation_snapshot=snapshot,
                jd_text=jd_text or candidate.jd_text,
                resume_score=candidate.resume_score,
                job_position=candidate.job_position,
            )
            payload.total_duration_minutes = await self.default_duration_minutes()
            blueprint, meta = await self.generate_via_graph(
                payload, candidate_id=candidate.candidate_id
            )
            row = await self._persist(candidate, blueprint)
            await self._ensure_interview_questions(candidate.candidate_id, force=True)
            logger.info(
                "Agent 3 blueprint saved for %s — level=%s questions=%s fallback=%s",
                candidate.candidate_id,
                blueprint.candidate_level,
                blueprint.total_questions,
                meta.get("used_fallback"),
            )
            return row, blueprint
        except Exception:
            logger.exception(
                "Agent 3 blueprint generation failed for %s (non-fatal)",
                candidate.candidate_id,
            )
            return None

    async def get_latest(self, candidate_id: str) -> InterviewBlueprint | None:
        return await self.repo.get_latest_for_candidate(candidate_id)

    async def _ensure_interview_questions(self, candidate_id: str, *, force: bool = False) -> None:
        """Create Agent 4 questions automatically once an Agent 3 plan exists."""
        try:
            from services.interview_agent_service import InterviewAgentService

            await InterviewAgentService(self.db).generate_questions(
                candidate_id, force=force
            )
        except Exception:
            logger.exception(
                "Agent 4 question auto-generation failed for %s (non-fatal)",
                candidate_id,
            )

    async def default_duration_minutes(self) -> int:
        return await ApplicationSettingsService(self.db).get_default_interview_minutes()

    async def planned_duration_minutes(self, candidate_id: str) -> int:
        row = await self.get_latest(candidate_id)
        if row:
            alloc = (row.blueprint_json or {}).get("time_allocation") or {}
            minutes = alloc.get("total_duration_minutes")
            if minutes is not None:
                try:
                    return int(minutes)
                except (TypeError, ValueError):
                    pass
        return await self.default_duration_minutes()

    async def _persist(
        self,
        candidate: Candidate,
        blueprint: InterviewBlueprintResponse,
    ) -> InterviewBlueprint:
        job_title = blueprint.input_summary.job_title or candidate.job_position
        return await self.repo.create(
            candidate_id=candidate.candidate_id,
            blueprint_version=blueprint.blueprint_version,
            candidate_level=blueprint.candidate_level,
            total_questions=blueprint.total_questions,
            job_title=job_title,
            blueprint_json=blueprint.model_dump(mode="json"),
            company_id=candidate.company_id,
        )
