"""Background Agent 6 evaluation queue — does not block the live question loop."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.database import AsyncSessionLocal
from core.redis_client import queue_pop
from services.interview_speed_cache import (
    EVAL_QUEUE,
    enqueue_eval_job,
    followup_budget_remaining,
    push_pending_followup,
)

logger = logging.getLogger(__name__)

_QUEUE = EVAL_QUEUE


def enqueue_answer_evaluation(job: dict[str, Any]) -> None:
    enqueue_eval_job(job)


async def _persist_and_maybe_followup(job: dict[str, Any], eval_dict: dict[str, Any]) -> None:
    from agents.interview_agent.adaptive import generate_adaptive_followups
    from agents.interview_agent.followup_generator import (
        answer_warrants_followup,
        asked_followup_keys,
    )
    from repositories.candidate_repository import CandidateRepository
    from repositories.interview_evaluation_repository import InterviewEvaluationRepository

    candidate_id = str(job.get("candidate_id") or "")
    question = dict(job.get("question") or {})
    answer = str(job.get("answer_text") or "")
    is_followup = bool(question.get("is_followup") or job.get("is_followup"))
    # End-of-interview feedback / role Q&A must never be scored or persisted.
    if (
        question.get("is_candidate_qna")
        or question.get("is_closing")
        or str(question.get("category_id") or "").strip().lower() == "candidate_qna"
        or str(question.get("id") or "").lower().startswith("qna-")
        or job.get("candidate_qna")
    ):
        return
    prior = asked_followup_keys(list(job.get("turn_history") or []))
    level = str((job.get("context") or {}).get("candidate_level") or "") or None

    async with AsyncSessionLocal() as db:
        candidate = await CandidateRepository(db).get_by_candidate_id(candidate_id)
        if candidate is None:
            return
        try:
            await InterviewEvaluationRepository(db).create(
                candidate_id=candidate_id,
                question_id=str(question.get("id") or "") or None,
                question_text=str(question.get("question_text") or ""),
                answer_text=answer,
                score=float(eval_dict.get("score") or 0),
                verdict=str(eval_dict.get("verdict") or "adequate"),
                evaluation_json=dict(eval_dict),
                model=str(eval_dict.get("model") or ""),
                company_id=int(candidate.company_id),
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to persist async evaluation for %s", candidate_id)
            await db.rollback()

    if is_followup:
        return
    if followup_budget_remaining(candidate_id) <= 0:
        return
    if not answer_warrants_followup(answer, eval_dict, is_followup=False):
        return

    loop = asyncio.get_running_loop()

    def _build():
        return generate_adaptive_followups(
            question_id=str(question.get("id") or "unknown"),
            question_text=str(question.get("question_text") or ""),
            candidate_answer=answer,
            evaluation=eval_dict,
            skill_hints=list(question.get("skill_tags") or []),
            max_followups=1,
            already_asked=prior,
            candidate_level=level,
        )

    followups = await loop.run_in_executor(None, _build)
    if not followups:
        return
    from agents.interview_agent.followup_generator import followup_invents_team_context

    fu = followups[0].model_dump(mode="json")
    fu["source_answer"] = answer
    if followup_invents_team_context(str(fu.get("question_text") or ""), answer):
        logger.info(
            "Dropped invented team follow-up for %s (answer had no team language)",
            candidate_id,
        )
        return
    if push_pending_followup(candidate_id, fu):
        logger.info(
            "Queued deferred follow-up for %s (parent=%s)",
            candidate_id,
            question.get("id"),
        )
        # Best-effort TTS for the follow-up so speaking it is fast.
        try:
            from agents.interview_agent.tts_service import synthesize_speech, tts_available
            from services.interview_speed_cache import cache_tts_audio

            if tts_available():
                text = str(fu.get("question_text") or "").strip()
                qid = str(fu.get("id") or "").strip()
                if text and qid:
                    result = await loop.run_in_executor(None, synthesize_speech, text)
                    cache_tts_audio(candidate_id, qid, result.get("audio_bytes") or b"")
        except Exception:
            logger.debug("Follow-up TTS pre-gen skipped", exc_info=True)


async def _run_one(job: dict[str, Any]) -> None:
    from agents.evaluation_agent.evaluator import evaluate_answer_with_llama

    question = dict(job.get("question") or {})
    answer = str(job.get("answer_text") or "")
    context = dict(job.get("context") or {})
    skill_tags = list(question.get("skill_tags") or [])

    loop = asyncio.get_running_loop()

    def _eval():
        return evaluate_answer_with_llama(
            question_text=str(question.get("question_text") or ""),
            candidate_answer=answer,
            context=context,
            skill_tags=skill_tags,
            use_web=False,
            use_chroma=False,
        )

    evaluation = await loop.run_in_executor(None, _eval)
    eval_dict = evaluation.model_dump(mode="json")
    await _persist_and_maybe_followup(job, eval_dict)


_worker_task: asyncio.Task | None = None


async def _worker_loop() -> None:
    logger.info("Interview eval worker started (queue=%s)", _QUEUE)
    while True:
        try:
            job = await asyncio.to_thread(queue_pop, _QUEUE, timeout_seconds=2)
            if not job:
                await asyncio.sleep(0.05)
                continue
            if not isinstance(job, dict):
                continue
            await _run_one(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Interview eval worker tick failed")
            await asyncio.sleep(0.5)


async def start_interview_eval_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker_loop(), name="interview-eval-worker")


async def stop_interview_eval_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None
