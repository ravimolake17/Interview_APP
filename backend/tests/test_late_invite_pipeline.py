"""Late invite + later slot booking must still create Agent 3 and Agent 4."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.interview_agent.question_bank import QuestionBankLockedError
from services.blueprint_service import build_blueprint_request_from_snapshot
from services.interview_agent_service import InterviewAgentService


def _service() -> InterviewAgentService:
    service = InterviewAgentService(AsyncMock())
    candidate = MagicMock()
    candidate.evaluation_snapshot = {}
    candidate.jd_text = "Build APIs"
    candidate.job_position = "Engineer"
    candidate.company_id = 1
    service.candidate_repo.get_by_candidate_id = AsyncMock(return_value=candidate)
    service.questions_repo.get_latest = AsyncMock(return_value=None)
    service.require_question_edits_allowed = AsyncMock(
        side_effect=QuestionBankLockedError("Interview starts in 10 minutes.")
    )
    blueprint = MagicMock()
    blueprint.id = 11
    blueprint.blueprint_json = {"time_allocation": {"total_duration_minutes": 30}}
    blueprint.job_title = "Engineer"
    blueprint.candidate_level = "Entry-level"
    service.blueprint_repo.get_latest_for_candidate = AsyncMock(return_value=blueprint)
    service.tts_cache.clear_for_candidate = AsyncMock()
    service.questions_repo.create = AsyncMock(return_value=MagicMock())
    service.default_duration_minutes = AsyncMock(return_value=30)
    service._to_response = AsyncMock(return_value={"questions_ready": True})
    return service


@pytest.mark.asyncio
async def test_first_question_set_is_created_even_when_edit_lock_started():
    service = _service()
    question = MagicMock()
    question.skill_tags = ["Python"]
    question.question_text = "How do you structure a FastAPI service?"
    question.category_id = "skills_jd_keyword_questions"
    question.difficulty = "medium"
    question.model_dump.return_value = {"id": "q1"}

    with (
        patch(
            "services.interview_agent_service.generate_questions_with_llama",
            return_value=[question],
        ),
        patch("services.interview_agent_service.index_interview_question"),
        patch(
            "services.interview_agent_service.build_candidate_context",
            return_value="ctx",
        ),
    ):
        result = await service.generate_questions("TNT-1-PARKON", force=True)

    assert result == {"questions_ready": True}
    service.require_question_edits_allowed.assert_not_awaited()
    service.questions_repo.create.assert_awaited()


@pytest.mark.asyncio
async def test_regenerating_existing_questions_still_respects_edit_lock():
    service = _service()
    existing = MagicMock()
    existing.questions_json = [{"id": "q1"}]
    existing.blueprint_id = 11
    service.questions_repo.get_latest = AsyncMock(return_value=existing)

    with pytest.raises(QuestionBankLockedError):
        await service.generate_questions("TNT-1-PARKON", force=True)

    service.questions_repo.create.assert_not_awaited()


def test_missing_jd_still_builds_agent3_request():
    payload = build_blueprint_request_from_snapshot(
        evaluation_snapshot={
            "candidate_details": {"name": "Tenant PARKON"},
            "shortlist_status": "Shortlisted",
        },
        jd_text=None,
        resume_score=80,
        job_position=None,
    )
    assert payload.jd_text
    assert payload.jd_json.get("job_title") == "Open Role"
