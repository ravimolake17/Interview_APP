"""LangGraph nodes for Agent 4 interview loop with parallel Agent 6 evaluation."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langgraph.types import interrupt

from datetime import datetime, timezone

from agents.evaluation_agent.evaluator import evaluate_answer_with_llama
from agents.interview_agent.followup_generator import (
    build_turn_ack,
    should_treat_as_unanswered,
)
from agents.interview_agent.candidate_qna import (
    CLOSING_THANK_YOU,
    MAX_QNA_TURNS,
    build_qna_opening,
    generate_candidate_qna_reply,
    qna_prompt_question,
)
from agents.interview_agent.state import InterviewAgentState
from agents.shared.llama_client import llama_model_id

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_seconds(state: InterviewAgentState) -> float:
    started = str(state.get("SessionStartedAt") or "").strip()
    if not started:
        return 0.0
    try:
        started_at = datetime.fromisoformat(started.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return max(0.0, (_utc_now() - started_at).total_seconds())


def _planned_seconds(state: InterviewAgentState) -> float:
    minutes = state.get("PlannedDurationMinutes")
    try:
        value = float(minutes)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, value * 60.0)


def _time_up(state: InterviewAgentState) -> bool:
    planned = _planned_seconds(state)
    if planned <= 0:
        return False
    return _elapsed_seconds(state) >= planned


def load_session(state: InterviewAgentState) -> dict[str, Any]:
    questions = list(state.get("Questions") or [])
    if not questions:
        return {
            "Status": "FAILED",
            "Error": "No interview questions loaded. Generate Agent 4 questions first.",
            "CurrentIndex": 0,
            "TotalQuestions": 0,
            "RemainingQuestions": 0,
        }
    return {
        "Status": "IN_PROGRESS",
        "Error": None,
        "CurrentIndex": int(state.get("CurrentIndex") or 0),
        "TotalQuestions": len(questions),
        "RemainingQuestions": len(questions),
        "TurnHistory": list(state.get("TurnHistory") or []),
        "FollowUps": [],
        "LatestEvaluation": None,
        "Agent6Feedback": None,
        "PendingFollowUpMode": False,
        "Model": llama_model_id(),
        "InterviewPhase": state.get("InterviewPhase") or "QUESTIONS",
        "DurationExtended": bool(state.get("DurationExtended")),
        "CandidateQnaTurns": int(state.get("CandidateQnaTurns") or 0),
        "PendingAiReply": state.get("PendingAiReply"),
        "TurnAck": None,
        "SessionStartedAt": state.get("SessionStartedAt") or _utc_now().isoformat(),
        "PlannedDurationMinutes": state.get("PlannedDurationMinutes"),
    }


def _qna_opening_from_state(state: InterviewAgentState) -> str:
    ctx = state.get("EvaluationContext") or {}
    return build_qna_opening(role_summary=str(ctx.get("role_summary") or ""))


def present_question(state: InterviewAgentState) -> dict[str, Any]:
    questions = list(state.get("Questions") or [])
    index = int(state.get("CurrentIndex") or 0)
    phase = str(state.get("InterviewPhase") or "QUESTIONS")
    pending_reply = str(state.get("PendingAiReply") or "").strip()
    qna_opening = _qna_opening_from_state(state)

    if phase == "CANDIDATE_QNA":
        turns = int(state.get("CandidateQnaTurns") or 0)
        if pending_reply:
            return {
                "Status": "AWAITING_ANSWER",
                "CurrentQuestion": qna_prompt_question(pending_reply, turn=turns, closing=False),
                "AnswerText": None,
                "PendingAiReply": None,
                "RemainingQuestions": 0,
                "PendingFollowUpMode": False,
                "InterviewPhase": "CANDIDATE_QNA",
            }
        if turns <= 0:
            return {
                "Status": "AWAITING_ANSWER",
                "CurrentQuestion": qna_prompt_question(qna_opening, turn=0),
                "AnswerText": None,
                "RemainingQuestions": 0,
                "PendingFollowUpMode": False,
                "InterviewPhase": "CANDIDATE_QNA",
            }
        return {
            "Status": "COMPLETED",
            "CurrentQuestion": qna_prompt_question(CLOSING_THANK_YOU, turn=turns, closing=True),
            "RemainingQuestions": 0,
            "PendingFollowUpMode": False,
            "InterviewPhase": "DONE",
        }

    if index >= len(questions) and not state.get("PendingFollowUpMode"):
        return {
            "Status": "AWAITING_ANSWER",
            "CurrentQuestion": qna_prompt_question(qna_opening, turn=0),
            "AnswerText": None,
            "RemainingQuestions": 0,
            "PendingFollowUpMode": False,
            "InterviewPhase": "CANDIDATE_QNA",
            "CandidateQnaTurns": 0,
        }

    # Mid-interview adaptive follow-ups are disabled — only the fixed bank is asked.
    # (Prep-time planned follow-ups are already rows inside Questions.)
    from core.config import get_settings as _get_settings

    live_adaptive = bool(getattr(_get_settings(), "interview_live_adaptive_followups", False))
    followups = list(state.get("FollowUps") or []) if live_adaptive else []
    if live_adaptive and state.get("PendingFollowUpMode") and followups:
        fu = followups[0]
        question = {
            "id": fu.get("id") or f"followup-{index}",
            "order": index + 1,
            "category_id": "planned_followup",
            "category_name": "Follow-up",
            "difficulty": fu.get("difficulty") or "medium",
            "question_text": fu.get("question_text"),
            "intent": fu.get("reason") or "Planned follow-up",
            "skill_tags": list((state.get("CurrentQuestion") or {}).get("skill_tags") or []),
            "is_followup": True,
            "parent_question_id": fu.get("parent_question_id"),
        }
        return {
            "Status": "AWAITING_ANSWER",
            "CurrentQuestion": question,
            "AnswerText": None,
            "FollowUps": followups[1:],
            "PendingFollowUpMode": len(followups) > 1,
            "RemainingQuestions": max(0, len(questions) - index) + max(0, len(followups) - 1),
        }

    if index >= len(questions):
        return {
            "Status": "AWAITING_ANSWER",
            "CurrentQuestion": qna_prompt_question(qna_opening, turn=0),
            "AnswerText": None,
            "RemainingQuestions": 0,
            "PendingFollowUpMode": False,
            "InterviewPhase": "CANDIDATE_QNA",
            "CandidateQnaTurns": 0,
        }

    question = dict(questions[index])
    # Candidate-facing label only — never expose Agent 6 / adaptive internals.
    cat = str(question.get("category_name") or "")
    if "agent 6" in cat.lower() or "adaptive" in cat.lower():
        question["category_name"] = "Follow-up" if question.get("is_followup") or question.get("planned") else "Interview question"
    elif question.get("planned") or (
        question.get("is_followup") and str(question.get("category_id") or "") in {"planned_followup", "adaptive_followup"}
    ):
        question["category_name"] = "Follow-up"
    return {
        "Status": "AWAITING_ANSWER",
        "CurrentQuestion": question,
        "AnswerText": None,
        "FollowUps": [] if not live_adaptive else list(state.get("FollowUps") or []),
        "RemainingQuestions": max(0, len(questions) - index),
        "PendingFollowUpMode": False,
    }


def wait_for_answer(state: InterviewAgentState) -> dict[str, Any]:
    """Interrupt until HR/candidate supplies an answer transcript (Whisper STT or typed)."""
    payload = interrupt(
        {
            "type": "await_answer",
            "candidate_id": state.get("CandidateID"),
            "question": state.get("CurrentQuestion"),
            "index": state.get("CurrentIndex"),
            "latest_evaluation": state.get("LatestEvaluation"),
        }
    )
    answer = ""
    hr_action = None
    target_index = None
    if isinstance(payload, dict):
        hr_action = str(payload.get("hr_action") or "").strip().lower() or None
        if payload.get("target_index") is not None:
            try:
                target_index = int(payload.get("target_index"))
            except (TypeError, ValueError):
                target_index = None
        answer = str(payload.get("answer_text") or payload.get("AnswerText") or "").strip()
        if hr_action in {"skip", "next", "goto"}:
            answer = "__HR_SKIP__"
    elif isinstance(payload, str):
        answer = payload.strip()
    return {
        "AnswerText": answer,
        "Status": "ANSWER_RECEIVED",
        "HrAction": hr_action,
        "HrTargetIndex": target_index,
    }


async def process_answer_parallel(state: InterviewAgentState) -> dict[str, Any]:
    """Run Agent 6 evaluation and Agent 4 follow-up drafting in parallel, then merge."""
    question = state.get("CurrentQuestion") or {}
    answer = (state.get("AnswerText") or "").strip()
    hr_action = str(state.get("HrAction") or "").strip().lower()
    if not answer and hr_action not in {"skip", "next", "goto"}:
        return {"Status": "FAILED", "Error": "Empty answer received."}

    questions = list(state.get("Questions") or [])
    index = int(state.get("CurrentIndex") or 0)
    total = len(questions)
    is_qna = bool(question.get("is_candidate_qna")) or str(state.get("InterviewPhase") or "") == "CANDIDATE_QNA"

    if is_qna:
        history = list(state.get("TurnHistory") or [])
        turns = int(state.get("CandidateQnaTurns") or 0) + 1
        if answer == "__HR_SKIP__" or hr_action in {"skip", "next", "goto"}:
            closing = qna_prompt_question(CLOSING_THANK_YOU, turn=turns, closing=True)
            history.append(
                {
                    "question": question,
                    "answer_text": "[Skipped by HR]",
                    "evaluation": None,
                    "candidate_qna": True,
                    "hr_skipped": True,
                }
            )
            return {
                "TurnHistory": history,
                "CurrentQuestion": closing,
                "PendingAiReply": None,
                "InterviewPhase": "DONE",
                "CandidateQnaTurns": turns,
                "Status": "COMPLETED",
                "RemainingQuestions": 0,
                "PendingFollowUpMode": False,
                "HrAction": None,
                "HrTargetIndex": None,
                "Model": llama_model_id(),
            }

        ctx = state.get("EvaluationContext") or {}
        prior_qna = [
            str(turn.get("answer_text") or "").strip()
            for turn in history
            if isinstance(turn, dict) and turn.get("candidate_qna") and str(turn.get("answer_text") or "").strip()
        ]
        result = generate_candidate_qna_reply(
            answer,
            job_position=str(ctx.get("job_position") or ""),
            turn=turns,
            role_summary=str(ctx.get("role_summary") or ""),
            department_brief=str(ctx.get("department_brief") or ""),
            department_name=str(ctx.get("department_name") or ""),
            company_intro=str(ctx.get("company_intro") or ""),
            prior_answers=prior_qna,
        )
        history.append(
            {
                "question": question,
                "answer_text": answer,
                "evaluation": None,
                "candidate_qna": True,
                "allowed": result.get("allowed"),
                "closing": result.get("closing"),
            }
        )
        if result.get("closing") or turns >= MAX_QNA_TURNS:
            return {
                "TurnHistory": history,
                "CurrentQuestion": qna_prompt_question(
                    str(result.get("reply") or CLOSING_THANK_YOU),
                    turn=turns,
                    closing=True,
                ),
                "PendingAiReply": None,
                "InterviewPhase": "DONE",
                "CandidateQnaTurns": turns,
                "Status": "COMPLETED",
                "RemainingQuestions": 0,
                "PendingFollowUpMode": False,
                "HrAction": None,
                "HrTargetIndex": None,
                "Model": llama_model_id(),
            }
        return {
            "TurnHistory": history,
            "PendingAiReply": str(result.get("reply") or ""),
            "InterviewPhase": "CANDIDATE_QNA",
            "CandidateQnaTurns": turns,
            "Status": "TURN_COMPLETE",
            "RemainingQuestions": 0,
            "PendingFollowUpMode": False,
            "HrAction": None,
            "HrTargetIndex": None,
            "LatestEvaluation": None,
            "Model": llama_model_id(),
        }

    # HR live controls — advance without Agent 6 scoring.
    if answer == "__HR_SKIP__" or hr_action in {"skip", "next", "goto"}:
        history = list(state.get("TurnHistory") or [])
        history.append(
            {
                "question": question,
                "answer_text": "[Skipped by HR]",
                "evaluation": None,
                "agent6_feedback": None,
                "follow_ups": [],
                "hr_skipped": True,
            }
        )
        followups = list(state.get("FollowUps") or [])
        is_followup_q = bool(question.get("is_followup"))

        if hr_action == "goto" and state.get("HrTargetIndex") is not None:
            next_index = max(0, min(int(state.get("HrTargetIndex")), total))
            pending_followup = False
            followup_payload: list[Any] = []
        elif is_followup_q:
            # Skip current follow-up; continue remaining queue or advance bank.
            if followups:
                pending_followup = True
                followup_payload = followups
                next_index = index
            else:
                pending_followup = False
                followup_payload = []
                next_index = index + 1 if index < total else index
        else:
            pending_followup = False
            followup_payload = []
            next_index = index + 1 if index < total else index

        done = (not pending_followup) and next_index >= total
        next_q = None
        if pending_followup and followup_payload:
            next_q = followup_payload[0]
        elif next_index < total:
            next_q = questions[next_index]
        elif done:
            next_q = {"category_name": "your questions", "skill_tags": []}
        return {
            "Questions": questions,
            "TurnHistory": history,
            "FollowUps": followup_payload if pending_followup else [],
            "LatestEvaluation": None,
            "Agent6Feedback": None,
            "PendingFollowUpMode": pending_followup,
            "CurrentIndex": next_index if not pending_followup else index,
            "RemainingQuestions": max(0, total - (next_index if not pending_followup else index)),
            "Status": "TURN_COMPLETE",
            "InterviewPhase": "CANDIDATE_QNA" if done else "QUESTIONS",
            "TurnAck": build_turn_ack(
                unanswered=True,
                next_question=next_q,
                next_is_followup=pending_followup,
            ),
            "Error": None,
            "HrAction": None,
            "HrTargetIndex": None,
            "Model": llama_model_id(),
        }

    context = dict(state.get("EvaluationContext") or {})
    skill_tags = list(question.get("skill_tags") or [])
    question_text = str(question.get("question_text") or "")
    question_id = str(question.get("id") or "unknown")
    is_followup = bool(question.get("is_followup"))
    candidate_id = str(state.get("CandidateID") or "")
    candidate_level = str(context.get("candidate_level") or "") or None

    from core.config import get_settings

    async_eval = bool(getattr(get_settings(), "interview_async_eval", True))

    questions = list(state.get("Questions") or [])
    index = int(state.get("CurrentIndex") or 0)
    total = len(questions)
    time_up = _time_up(state)
    history = list(state.get("TurnHistory") or [])

    # ── Fast path: save answer, advance fixed bank; score later (optional) ──
    if async_eval:
        from services.interview_eval_queue import enqueue_answer_evaluation
        from services.interview_speed_cache import init_followup_budget

        if candidate_id and not state.get("_FollowupBudgetReady"):
            init_followup_budget(candidate_id, total)

        import time as _time

        from agents.shared.latency_trace import record_event, record_ms

        defer_eval = bool(getattr(get_settings(), "interview_defer_eval_until_end", True))
        live_adaptive = bool(getattr(get_settings(), "interview_live_adaptive_followups", False))
        unanswered = should_treat_as_unanswered(answer, None)

        record_event("redis_enqueue_start")
        _enq_t0 = _time.perf_counter()
        from services.interview_speed_cache import claim_eval_job, get_pending_stt_correction

        pending_stt = get_pending_stt_correction(candidate_id, question_id) if question_id else None
        # During live interview: only enqueue when NOT deferring, and never for thin/skip answers.
        if (
            not defer_eval
            and not unanswered
            and claim_eval_job(candidate_id, question_id or "unknown", answer)
        ):
            enqueue_answer_evaluation(
                {
                    "candidate_id": candidate_id,
                    "question": question,
                    "answer_text": answer,
                    "context": context,
                    "is_followup": is_followup,
                    "turn_history": history[-8:],
                    "raw_transcript": (pending_stt or {}).get("raw_transcript") or answer,
                    "needs_llm_correction": bool((pending_stt or {}).get("needs_llm_correction")),
                    "correction_payload": pending_stt,
                    "retry_count": 0,
                }
            )
        elif unanswered:
            logger.info(
                "Skipped eval for thin/unanswered turn candidate=%s question=%s",
                candidate_id,
                question_id,
            )
        record_ms("redis_enqueue_ms", (_time.perf_counter() - _enq_t0) * 1000.0)
        record_event("redis_enqueue_end")

        # Never inject adaptive follow-ups during the live interview.
        # Prep-time planned follow-ups are already fixed rows in Questions.
        if not live_adaptive:
            try:
                from services.interview_speed_cache import clear_pending_followups

                clear_pending_followups(candidate_id)
            except Exception:
                pass

        # Always walk the fixed bank forward.
        next_index = index + 1

        history.append(
            {
                "question": question,
                "answer_text": answer,
                "evaluation": None,
                "eval_pending": bool(not unanswered and defer_eval),
                "skipped_thin": unanswered,
                "agent6_feedback": None,
                "follow_ups": [],
            }
        )

        remaining_after = max(0, total - next_index)
        duration_extended = bool(state.get("DurationExtended")) or (
            time_up and remaining_after > 0
        )
        done_bank = next_index >= total
        next_q: dict[str, Any] | None = None
        if next_index < total:
            next_q = questions[next_index]
        elif done_bank:
            next_q = {"category_name": "your questions", "skill_tags": []}

        return {
            "Questions": questions,
            "TurnHistory": history,
            # Clear any leftover adaptive FU queue so the next present_question
            # cannot resurface "Agent 6 adaptive follow-up".
            "FollowUps": [],
            "LatestEvaluation": None,
            "Agent6Feedback": None,
            "PendingFollowUpMode": False,
            "CurrentIndex": next_index,
            "RemainingQuestions": max(0, total - next_index),
            "Status": "TURN_COMPLETE",
            "InterviewPhase": "CANDIDATE_QNA" if done_bank else "QUESTIONS",
            "DurationExtended": duration_extended,
            "TurnAck": build_turn_ack(
                evaluation=None,
                next_question=next_q,
                unanswered=unanswered,
                next_is_followup=bool((next_q or {}).get("is_followup") or (next_q or {}).get("planned")),
            ),
            "Error": None,
            "Model": llama_model_id(),
            "_FollowupBudgetReady": True,
        }

    # ── Legacy sync path (INTERVIEW_ASYNC_EVAL=false) ──
    # Still do not generate live adaptive follow-ups — fixed bank only.
    loop = asyncio.get_running_loop()

    def _evaluate():
        return evaluate_answer_with_llama(
            question_text=question_text,
            candidate_answer=answer,
            context=context,
            skill_tags=skill_tags,
            use_web=False,
            use_chroma=False,
        )

    evaluation = await loop.run_in_executor(_executor, _evaluate)
    eval_dict = evaluation.model_dump(mode="json")
    unanswered = should_treat_as_unanswered(answer, eval_dict)

    history.append(
        {
            "question": question,
            "answer_text": answer,
            "evaluation": eval_dict,
            "agent6_feedback": evaluation.feedback_for_agent4,
            "follow_ups": [],
            "skipped_thin": unanswered,
        }
    )

    remaining_after = max(0, len(questions) - (index + 1))
    duration_extended = bool(state.get("DurationExtended")) or (
        time_up and remaining_after > 0
    )
    next_index = index + 1
    done_bank = next_index >= total
    next_q = questions[next_index] if next_index < total else (
        {"category_name": "your questions", "skill_tags": []} if done_bank else None
    )

    return {
        "Questions": questions,
        "TurnHistory": history,
        "FollowUps": [],
        "LatestEvaluation": eval_dict,
        "Agent6Feedback": evaluation.feedback_for_agent4,
        "PendingFollowUpMode": False,
        "CurrentIndex": next_index,
        "RemainingQuestions": max(0, total - next_index),
        "Status": "TURN_COMPLETE",
        "InterviewPhase": "CANDIDATE_QNA" if done_bank else "QUESTIONS",
        "DurationExtended": duration_extended,
        "TurnAck": build_turn_ack(
            evaluation=eval_dict,
            next_question=next_q,
            unanswered=unanswered,
            next_is_followup=bool((next_q or {}).get("is_followup") or (next_q or {}).get("planned")),
        ),
        "Error": None,
        "Model": llama_model_id(),
    }


def complete_session(state: InterviewAgentState) -> dict[str, Any]:
    current = state.get("CurrentQuestion") or {}
    keep = current if current.get("is_closing") else qna_prompt_question(
        CLOSING_THANK_YOU, turn=int(state.get("CandidateQnaTurns") or 0), closing=True
    )
    return {
        "Status": "COMPLETED",
        "CurrentQuestion": keep,
        "RemainingQuestions": 0,
        "PendingFollowUpMode": False,
        "InterviewPhase": "DONE",
    }
