"""Background Agent 6 evaluation queue — does not block the live question loop.

Phase 1: optional deferred STT LLM correction runs in this worker *before*
Agent 6 scoring so there is no race between correction and evaluation.

Phase 4: single embedded consumer (one per Uvicorn process), bounded parallel
job slots, dead-letter after hard failures, graceful drain on shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.database import AsyncSessionLocal
from core.redis_client import queue_length, queue_move, queue_pop, queue_push
from services.interview_speed_cache import (
    EVAL_QUEUE,
    clear_pending_stt_correction,
    enqueue_eval_job,
    followup_budget_remaining,
    push_pending_followup,
)

logger = logging.getLogger(__name__)

_QUEUE = EVAL_QUEUE
_DLQ = "interview:eval:dlq"
_MAX_CORRECTION_RETRIES = 2

_worker_task: asyncio.Task | None = None
_inflight: set[asyncio.Task] = set()
_stop_event: asyncio.Event | None = None


def enqueue_answer_evaluation(job: dict[str, Any]) -> None:
    enqueue_eval_job(job)


def enqueue_deferred_turn_evaluations(
    *,
    candidate_id: str,
    turn_history: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> int:
    """Enqueue Agent 6 jobs for saved turns after the live interview ends."""
    from services.interview_speed_cache import claim_eval_job

    queued = 0
    ctx = dict(context or {})
    for turn in turn_history or []:
        if not isinstance(turn, dict):
            continue
        if turn.get("hr_skipped") or turn.get("skipped_thin") or turn.get("candidate_qna"):
            continue
        if turn.get("evaluation"):
            continue
        question = dict(turn.get("question") or {})
        if (
            question.get("is_candidate_qna")
            or question.get("is_closing")
            or str(question.get("category_id") or "").strip().lower() == "candidate_qna"
            or str(question.get("id") or "").lower().startswith("qna-")
        ):
            continue
        answer = str(turn.get("answer_text") or "").strip()
        if not answer or answer in {"[Skipped by HR]", "[No response]"}:
            continue
        question_id = str(question.get("id") or "unknown")
        if not claim_eval_job(candidate_id, question_id, answer):
            continue
        enqueue_answer_evaluation(
            {
                "candidate_id": candidate_id,
                "question": question,
                "answer_text": answer,
                "context": ctx,
                "is_followup": bool(question.get("is_followup")),
                "turn_history": [],
                "raw_transcript": answer,
                "needs_llm_correction": False,
                "correction_payload": None,
                "retry_count": 0,
                "deferred_until_end": True,
            }
        )
        queued += 1
    if queued:
        logger.info("Queued %s deferred end-of-interview evaluations for %s", queued, candidate_id)
    return queued


def eval_queue_stats() -> dict[str, int]:
    return {
        "queue_depth": queue_length(_QUEUE),
        "dlq_depth": queue_length(_DLQ),
        "inflight": len(_inflight),
    }


def _eval_concurrency() -> int:
    try:
        from core.config import get_settings

        return max(1, min(8, int(getattr(get_settings(), "interview_eval_concurrency", 2) or 2)))
    except Exception:
        return 2


def _max_job_retries() -> int:
    try:
        from core.config import get_settings

        return max(0, min(5, int(getattr(get_settings(), "interview_eval_max_job_retries", 2) or 2)))
    except Exception:
        return 2


def _worker_enabled() -> bool:
    try:
        from core.config import get_settings

        return bool(getattr(get_settings(), "interview_eval_worker_enabled", True))
    except Exception:
        return True


async def _persist_correction(
    candidate_id: str,
    question: dict[str, Any],
    *,
    raw_transcript: str,
    corrected_transcript: str,
    correction_status: str,
) -> None:
    from repositories.candidate_repository import CandidateRepository
    from services.interview_oral_store import upsert_oral_turn

    async with AsyncSessionLocal() as db:
        candidate = await CandidateRepository(db).get_by_candidate_id(candidate_id)
        if candidate is None:
            return
        try:
            upsert_oral_turn(
                candidate,
                {
                    "question_id": str(question.get("id") or ""),
                    "question_text": str(question.get("question_text") or ""),
                    "answer_text": corrected_transcript,
                    "raw_transcript": raw_transcript,
                    "corrected_transcript": corrected_transcript,
                    "correction_status": correction_status,
                },
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to persist STT correction for %s", candidate_id)
            await db.rollback()


async def _persist_and_maybe_followup(job: dict[str, Any], eval_dict: dict[str, Any], answer: str) -> None:
    from agents.interview_agent.adaptive import generate_adaptive_followups
    from agents.interview_agent.followup_generator import (
        answer_warrants_followup,
        asked_followup_keys,
    )
    from repositories.candidate_repository import CandidateRepository
    from repositories.interview_evaluation_repository import InterviewEvaluationRepository

    candidate_id = str(job.get("candidate_id") or "")
    question = dict(job.get("question") or {})
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
    # Hard-disable mid-interview adaptive follow-up generation.
    # Follow-ups are baked into the question bank at prep time.
    try:
        from core.config import get_settings

        if not bool(getattr(get_settings(), "interview_live_adaptive_followups", False)):
            return
    except Exception:
        return
    if job.get("deferred_until_end"):
        # End-of-interview scoring must never invent live follow-ups.
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
        # Best-effort background TTS after quality gates — never blocks the candidate.
        try:
            from agents.interview_agent.tts_cache_keys import cache_fingerprint
            from agents.interview_agent.tts_service import synthesize_speech, tts_available
            from services.interview_speed_cache import cache_tts_audio

            if tts_available():
                text = str(fu.get("question_text") or "").strip()
                qid = str(fu.get("id") or "").strip()
                if text and qid:
                    result = await loop.run_in_executor(None, synthesize_speech, text)
                    voice = str(result.get("voice") or "female")
                    content_type = str(result.get("content_type") or "audio/wav")
                    cache_tts_audio(
                        candidate_id,
                        qid,
                        result.get("audio_bytes") or b"",
                        voice=voice,
                        content_type=content_type,
                        text_hash=cache_fingerprint(text, voice=voice, content_type=content_type),
                    )
        except Exception:
            logger.debug("Follow-up TTS pre-gen skipped", exc_info=True)


async def _maybe_apply_deferred_correction(job: dict[str, Any]) -> tuple[str, str]:
    """Return (answer_for_eval, correction_status). Correction always completes before eval."""
    visible = str(job.get("answer_text") or "").strip()
    if not job.get("needs_llm_correction"):
        return visible, str((job.get("correction_payload") or {}).get("correction_status") or "deterministic_only")

    payload = dict(job.get("correction_payload") or {})
    source = str(payload.get("visible_text") or job.get("raw_transcript") or visible).strip() or visible
    raw_transcript = str(payload.get("raw_transcript") or job.get("raw_transcript") or source).strip()
    loop = asyncio.get_running_loop()

    def _correct():
        from agents.interview_agent.stt_corrector import apply_deferred_llm_correction

        return apply_deferred_llm_correction(
            source,
            context=dict(payload.get("context") or {}),
            resume_terms=list(payload.get("resume_terms") or []),
            question_text=str(payload.get("question_text") or "") or None,
            candidate_name=str(payload.get("candidate_name") or "") or None,
        )

    try:
        result = await loop.run_in_executor(None, _correct)
        corrected = str(result.get("text") or source).strip() or source
        status = str(result.get("correction_status") or "complete")
        await _persist_correction(
            str(job.get("candidate_id") or ""),
            dict(job.get("question") or {}),
            raw_transcript=raw_transcript,
            corrected_transcript=corrected,
            correction_status=status,
        )
        qid = str((job.get("question") or {}).get("id") or "")
        clear_pending_stt_correction(str(job.get("candidate_id") or ""), qid)
        return corrected, status
    except Exception:
        logger.exception(
            "Deferred STT LLM correction failed for %s; evaluating visible transcript",
            job.get("candidate_id"),
        )
        retry = int(job.get("retry_count") or 0)
        if retry < _MAX_CORRECTION_RETRIES:
            job = dict(job)
            job["retry_count"] = retry + 1
            enqueue_eval_job(job)
            # Re-queued; caller should skip eval this tick.
            raise
        await _persist_correction(
            str(job.get("candidate_id") or ""),
            dict(job.get("question") or {}),
            raw_transcript=raw_transcript,
            corrected_transcript=visible,
            correction_status="failed",
        )
        qid = str((job.get("question") or {}).get("id") or "")
        clear_pending_stt_correction(str(job.get("candidate_id") or ""), qid)
        return visible, "failed"


def _dead_letter(job: dict[str, Any], *, reason: str) -> None:
    payload = dict(job)
    payload["dlq_reason"] = reason[:240]
    try:
        queue_move(_QUEUE, _DLQ, payload)
        logger.error(
            "Eval job dead-lettered candidate=%s question=%s reason=%s",
            payload.get("candidate_id"),
            (payload.get("question") or {}).get("id"),
            reason[:120],
        )
    except Exception:
        logger.exception("Failed to write eval DLQ entry")


async def _run_one(job: dict[str, Any]) -> None:
    from agents.evaluation_agent.evaluator import evaluate_answer_with_llama

    question = dict(job.get("question") or {})
    context = dict(job.get("context") or {})
    skill_tags = list(question.get("skill_tags") or [])

    try:
        answer, _status = await _maybe_apply_deferred_correction(job)
    except Exception:
        # Correction re-queued for retry — do not evaluate yet (avoids race / double score).
        return

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

    try:
        evaluation = await loop.run_in_executor(None, _eval)
        eval_dict = evaluation.model_dump(mode="json")
        await _persist_and_maybe_followup(job, eval_dict, answer)
    except Exception as exc:
        job_retry = int(job.get("job_retry_count") or 0)
        if job_retry < _max_job_retries():
            nxt = dict(job)
            nxt["job_retry_count"] = job_retry + 1
            enqueue_eval_job(nxt)
            logger.warning(
                "Eval job requeued (%s/%s) for %s: %s",
                job_retry + 1,
                _max_job_retries(),
                job.get("candidate_id"),
                exc,
            )
            return
        _dead_letter(job, reason=str(exc))


async def _worker_loop() -> None:
    concurrency = _eval_concurrency()
    sem = asyncio.Semaphore(concurrency)
    logger.info(
        "Interview eval worker started (queue=%s, concurrency=%s, dlq=%s)",
        _QUEUE,
        concurrency,
        _DLQ,
    )
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            job = await asyncio.to_thread(queue_pop, _QUEUE, timeout_seconds=2)
            if not job:
                await asyncio.sleep(0.05)
                continue
            if not isinstance(job, dict):
                continue

            async def _guarded(j: dict[str, Any] = job) -> None:
                async with sem:
                    await _run_one(j)

            task = asyncio.create_task(_guarded(), name="interview-eval-job")
            _inflight.add(task)

            def _done(t: asyncio.Task) -> None:
                _inflight.discard(t)
                try:
                    exc = t.exception()
                except asyncio.CancelledError:
                    return
                except Exception:
                    return
                if exc:
                    logger.exception("Interview eval job task failed", exc_info=exc)

            task.add_done_callback(_done)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Interview eval worker tick failed")
            await asyncio.sleep(0.5)


async def start_interview_eval_worker() -> None:
    global _worker_task, _stop_event
    if not _worker_enabled():
        logger.info("Interview eval worker disabled (INTERVIEW_EVAL_WORKER_ENABLED=false)")
        return
    if _worker_task and not _worker_task.done():
        return
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop(), name="interview-eval-worker")


async def stop_interview_eval_worker() -> None:
    global _worker_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    # Drain in-flight jobs briefly so follow-ups are not cut mid-persist.
    if _inflight:
        pending = list(_inflight)
        try:
            await asyncio.wait(pending, timeout=8.0)
        except Exception:
            logger.debug("Eval worker drain wait interrupted", exc_info=True)
        for task in pending:
            if not task.done():
                task.cancel()
    _inflight.clear()
    _worker_task = None
    _stop_event = None
