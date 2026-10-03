"""LangGraph nodes for Agent 4 interview loop with parallel Agent 6 evaluation."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langgraph.types import interrupt

from datetime import datetime, timezone

from agents.evaluation_agent.evaluator import evaluate_answer_with_llama
from agents.interview_agent.adaptive import generate_adaptive_followups
from agents.interview_agent.followup_generator import (
    answer_is_thin,
    answer_warrants_followup,
    build_turn_ack,
)
from agents.interview_agent.candidate_qna import (
    CLOSING_THANK_YOU,
    MAX_QNA_TURNS,
    QNA_OPENING,
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


def present_question(state: InterviewAgentState) -> dict[str, Any]:
    questions = list(state.get("Questions") or [])
    index = int(state.get("CurrentIndex") or 0)
    phase = str(state.get("InterviewPhase") or "QUESTIONS")
    pending_reply = str(state.get("PendingAiReply") or "").strip()

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
                "CurrentQuestion": qna_prompt_question(QNA_OPENING, turn=0),
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
            "CurrentQuestion": qna_prompt_question(QNA_OPENING, turn=0),
            "AnswerText": None,
            "RemainingQuestions": 0,
            "PendingFollowUpMode": False,
            "InterviewPhase": "CANDIDATE_QNA",
            "CandidateQnaTurns": 0,
        }

    # If Agent 6 requested follow-ups, ask those before advancing the bank.
    followups = list(state.get("FollowUps") or [])
    if state.get("PendingFollowUpMode") and followups:
        fu = followups[0]
        question = {
            "id": fu.get("id") or f"followup-{index}",
            "order": index + 1,
            "category_id": "adaptive_followup",
            "category_name": "Agent 6 adaptive follow-up",
            "difficulty": fu.get("difficulty") or "medium",
            "question_text": fu.get("question_text"),
            "intent": fu.get("reason") or "Probe gaps from Agent 6 evaluation",
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
            "CurrentQuestion": qna_prompt_question(QNA_OPENING, turn=0),
            "AnswerText": None,
            "RemainingQuestions": 0,
            "PendingFollowUpMode": False,
            "InterviewPhase": "CANDIDATE_QNA",
            "CandidateQnaTurns": 0,
        }

    question = dict(questions[index])
    return {
        "Status": "AWAITING_ANSWER",
        "CurrentQuestion": question,
        "AnswerText": None,
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

        job_position = str((state.get("EvaluationContext") or {}).get("job_position") or "")
        result = generate_candidate_qna_reply(answer, job_position=job_position, turn=turns)
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

    from agents.interview_agent.followup_generator import generate_followups

    def _draft_followups():
        # Agent 4 drafts in parallel while Agent 6 evaluates.
        return generate_followups(
            question_id=question_id,
            question_text=question_text,
            candidate_answer=answer,
            max_followups=1,
            skill_hints=skill_tags,
        )

    # Parallel fan-out: Agent 6 evaluation ∥ Agent 4 draft follow-ups
    evaluation, draft_followups = await asyncio.gather(
        loop.run_in_executor(_executor, _evaluate),
        loop.run_in_executor(_executor, _draft_followups),
    )
    eval_dict = evaluation.model_dump(mode="json")

    def _refine_followups():
        if not answer_warrants_followup(answer, eval_dict, is_followup=is_followup):
            return []
        refined = generate_adaptive_followups(
            question_id=question_id,
            question_text=question_text,
            candidate_answer=answer,
            evaluation=eval_dict,
            skill_hints=skill_tags,
            max_followups=1,
        )
        return refined[:1]

    followups = await loop.run_in_executor(_executor, _refine_followups)

    history = list(state.get("TurnHistory") or [])
    history.append(
        {
            "question": question,
            "answer_text": answer,
            "evaluation": eval_dict,
            "agent6_feedback": evaluation.feedback_for_agent4,
            "follow_ups": [fu.model_dump(mode="json") for fu in followups],
        }
    )

    questions = list(state.get("Questions") or [])
    index = int(state.get("CurrentIndex") or 0)
    time_up = _time_up(state)
    remaining_after = max(0, len(questions) - (index + (0 if is_followup else 1)))
    duration_extended = bool(state.get("DurationExtended")) or (
        time_up and remaining_after > 0
    )

    # Stay on the planned bank. Rephrase only when the candidate actually answered
    # but left a useful gap — never when they skipped or gave no answer.
    next_index = index
    pending_followup = False
    followup_payload = [fu.model_dump(mode="json") for fu in followups]
    allow_followups = (
        (not time_up)
        and (not is_followup)
        and answer_warrants_followup(answer, eval_dict, is_followup=is_followup)
        and bool(followup_payload)
    )

    if is_followup:
        pending_followup = False
        followup_payload = []
        next_index = index + 1
    elif allow_followups:
        pending_followup = True
        next_index = index
    else:
        pending_followup = False
        followup_payload = []
        next_index = index + 1

    total = len(questions)
    done_bank = (not pending_followup) and next_index >= total
    next_q: dict[str, Any] | None = None
    if pending_followup and followup_payload:
        next_q = followup_payload[0]
    elif next_index < total:
        next_q = questions[next_index]
    elif done_bank:
        next_q = {"category_name": "your questions", "skill_tags": []}

    return {
        "Questions": questions,
        "TurnHistory": history,
        "FollowUps": followup_payload if pending_followup else [],
        "LatestEvaluation": eval_dict,
        "Agent6Feedback": evaluation.feedback_for_agent4,
        "PendingFollowUpMode": pending_followup,
        "CurrentIndex": next_index if not pending_followup else index,
        "RemainingQuestions": max(0, total - (next_index if not pending_followup else index)),
        "Status": "TURN_COMPLETE",
        "InterviewPhase": "CANDIDATE_QNA" if done_bank else "QUESTIONS",
        "DurationExtended": duration_extended,
        "TurnAck": build_turn_ack(
            evaluation=eval_dict,
            next_question=next_q,
            unanswered=answer_is_thin(answer),
            next_is_followup=pending_followup,
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
