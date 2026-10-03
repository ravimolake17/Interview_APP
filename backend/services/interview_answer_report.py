"""Build the Agent 6 interview answer report and full-denominator interview score."""

from __future__ import annotations

import re
from typing import Any, Iterable

from agents.evaluation_agent.evaluator import is_non_answer
from models.candidate import Candidate
from services.interview_oral_store import oral_turns
from services.interview_room_service import runtime_from_snapshot

AI_STARTED_STATES = {
    "AI_INTERVIEW_ACTIVE",
    "HR_INTERVENTION",
    "AI_PAUSED",
    "COMPLETED",
    "ENDED",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _option_text(question: dict[str, Any], option_id: str | None) -> str:
    wanted = str(option_id or "").strip().upper()
    if not wanted:
        return ""
    for option in question.get("options") or []:
        if not isinstance(option, dict):
            continue
        if str(option.get("id") or "").strip().upper() == wanted:
            return str(option.get("text") or "").strip()
    return wanted


def _mcq_items(candidate: Candidate) -> list[dict[str, Any]]:
    snap = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
    record = _as_dict(snap.get("interview_mcq"))
    items: list[dict[str, Any]] = []
    for question in record.get("questions") or []:
        if not isinstance(question, dict):
            continue
        selected = str(question.get("answer_option_id") or "").strip().upper() or None
        correct = str(question.get("correct_option_id") or "").strip().upper() or None
        skipped = bool(question.get("skipped"))
        if skipped:
            status = "skipped"
            answer_text = "Skipped"
            score = 0.0
        elif selected:
            status = "answered"
            answer_text = _option_text(question, selected) or selected
            score = 100.0 if selected == correct else 0.0
        else:
            status = "unanswered"
            answer_text = "Not answered"
            score = 0.0
        items.append(
            {
                "kind": "mcq",
                "question_id": str(question.get("id") or ""),
                "question_text": str(question.get("question_text") or "").strip(),
                "answer_text": answer_text,
                "correct_answer": _option_text(question, correct) or correct or "",
                "score": score,
                "max_score": 100.0,
                "verdict": "strong" if score >= 100 else "insufficient",
                "status": status,
                "model": "mcq_key",
                "feedback": "Correct." if score >= 100 else "Incorrect, skipped, or not answered. Counted as 0 against the full MCQ set.",
            }
        )
    return items


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    payload = _as_dict(getattr(row, "evaluation_json", None))
    if key in payload and payload.get(key) not in (None, ""):
        return payload.get(key)
    return getattr(row, key, default)


def _as_turn_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    payload = _as_dict(getattr(row, "evaluation_json", None))
    return {
        "question_id": getattr(row, "question_id", None),
        "question_text": getattr(row, "question_text", None),
        "answer_text": getattr(row, "answer_text", None),
        "score": getattr(row, "score", None),
        "verdict": getattr(row, "verdict", None),
        "model": getattr(row, "model", None),
        "evaluation": payload,
        "audio_path": payload.get("audio_path"),
        "is_followup": payload.get("is_followup"),
    }


def _merge_turn(base: Any, incoming: Any) -> dict[str, Any]:
    merged = _as_turn_dict(base)
    extra = _as_turn_dict(incoming)
    for key, value in extra.items():
        if value in (None, "", [], {}):
            continue
        current = merged.get(key)
        if key == "audio_path" or current in (None, "", [], {}, 0, 0.0):
            merged[key] = value
    return merged


def _eval_maps(evaluations: Iterable[Any]) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    by_id: dict[str, Any] = {}
    by_text: dict[str, Any] = {}
    rows: list[Any] = []
    for row in evaluations or []:
        qid = str(_row_get(row, "question_id") or "").strip()
        text = _norm_text(_row_get(row, "question_text") or "")
        if qid and qid in by_id:
            merged = _merge_turn(by_id[qid], row)
            by_id[qid] = merged
            if text:
                by_text[text] = merged
            continue
        if text and text in by_text:
            merged = _merge_turn(by_text[text], row)
            by_text[text] = merged
            if qid:
                by_id[qid] = merged
            continue
        if qid:
            by_id[qid] = row
        if text:
            by_text[text] = row
        rows.append(row)
    # Rebuild unique row list from maps so merged dicts are used.
    unique: list[Any] = []
    seen: set[int] = set()
    for item in list(by_id.values()) + list(by_text.values()):
        marker = id(item)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(item)
    return by_id, by_text, unique


def _oral_item_from_eval(row: Any, *, kind: str = "oral", status: str = "answered") -> dict[str, Any]:
    payload = _as_dict(_row_get(row, "evaluation_json") if not isinstance(row, dict) else row.get("evaluation"))
    if isinstance(row, dict) and not payload:
        payload = row
    score_raw = _row_get(row, "score")
    try:
        score = float(score_raw) if score_raw is not None else float(payload.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    answer = str(_row_get(row, "answer_text") or "").strip()
    audio_path = str(_row_get(row, "audio_path") or payload.get("audio_path") or "").strip()
    question_id = str(_row_get(row, "question_id") or "").strip()
    answered = status == "answered" and bool(answer) and answer.lower() not in {"not answered", "[skipped by hr]"}
    if answered and is_non_answer(answer):
        score = 0.0
        verdict = "insufficient"
        feedback = (
            "Candidate said they do not know or otherwise declined. "
            "Score 0 — this is not a partial answer."
        )
        gaps = ["Candidate did not answer the question."]
        strengths: list[str] = []
    else:
        verdict = str(_row_get(row, "verdict") or payload.get("verdict") or ("insufficient" if not answered else "adequate"))
        feedback = str(payload.get("feedback_for_agent4") or payload.get("resume_alignment") or payload.get("feedback") or "")
        gaps = list(payload.get("gaps") or [])[:4]
        strengths = list(payload.get("strengths") or [])[:4]
    return {
        "kind": kind,
        "question_id": question_id,
        "question_text": str(_row_get(row, "question_text") or "").strip(),
        "answer_text": answer or "Not answered",
        "correct_answer": "",
        "score": round(score, 1) if answered else 0.0,
        "max_score": 100.0,
        "verdict": verdict,
        "status": "answered" if answered else status,
        "model": str(_row_get(row, "model") or payload.get("model") or ""),
        "feedback": feedback,
        "gaps": gaps,
        "strengths": strengths,
        "has_audio": bool(audio_path),
    }


def _unanswered_oral(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "oral",
        "question_id": str(question.get("id") or ""),
        "question_text": str(question.get("question_text") or "").strip(),
        "answer_text": "Not answered",
        "correct_answer": "",
        "score": 0.0,
        "max_score": 100.0,
        "verdict": "insufficient",
        "status": "unanswered",
        "model": "",
        "feedback": "This planned oral question was not answered. Counted as 0 against the full question set.",
        "gaps": [],
        "strengths": [],
        "has_audio": False,
    }


def _history_rows(turn_history: Iterable[Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for turn in turn_history or []:
        if not isinstance(turn, dict):
            continue
        question = turn.get("question") if isinstance(turn.get("question"), dict) else {}
        evaluation = turn.get("evaluation") if isinstance(turn.get("evaluation"), dict) else {}
        answer = str(turn.get("answer_text") or "").strip()
        rows.append(
            {
                "question_id": str(question.get("id") or turn.get("question_id") or ""),
                "question_text": str(question.get("question_text") or turn.get("question_text") or ""),
                "answer_text": answer,
                "score": evaluation.get("score"),
                "verdict": evaluation.get("verdict"),
                "evaluation": evaluation,
                "model": evaluation.get("model"),
                "is_followup": bool(question.get("is_followup")),
                "audio_path": turn.get("audio_path") or evaluation.get("audio_path"),
            }
        )
    return rows


def _oral_items(
    *,
    planned_questions: list[dict[str, Any]] | None,
    evaluations: Iterable[Any],
    extra_turns: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    combined = list(evaluations or []) + list(extra_turns or [])
    by_id, by_text, rows = _eval_maps(combined)
    used: set[int] = set()
    items: list[dict[str, Any]] = []

    for question in planned_questions or []:
        if not isinstance(question, dict):
            continue
        qid = str(question.get("id") or "").strip()
        text = _norm_text(question.get("question_text") or "")
        row = (by_id.get(qid) if qid else None) or (by_text.get(text) if text else None)
        if row is not None:
            used.add(id(row))
            kind = "followup" if bool(_row_get(row, "is_followup")) else "oral"
            items.append(_oral_item_from_eval(row, kind=kind, status="answered"))
        else:
            items.append(_unanswered_oral(question))

    for row in rows:
        if id(row) in used:
            continue
        kind = "followup" if bool(_row_get(row, "is_followup")) or "follow" in _norm_text(_row_get(row, "question_text")) else "oral"
        items.append(_oral_item_from_eval(row, kind=kind, status="answered"))
    return items


def build_interview_answer_report(
    *,
    candidate: Candidate,
    evaluations: Iterable[Any] | None = None,
    planned_oral_questions: list[dict[str, Any]] | None = None,
    turn_history: Iterable[Any] | None = None,
) -> dict[str, Any]:
    extra_turns = oral_turns(candidate) + _history_rows(turn_history)
    mcq_items = _mcq_items(candidate)
    oral_items = _oral_items(
        planned_questions=list(planned_oral_questions or []),
        evaluations=list(evaluations or []),
        extra_turns=extra_turns,
    )
    items = [*mcq_items, *oral_items]
    answered = [row for row in items if row.get("status") == "answered"]
    unanswered = [row for row in items if row.get("status") in {"unanswered", "skipped"}]
    total = len(items)
    earned = sum(float(row.get("score") or 0) for row in items)
    interview_score = round(earned / total, 1) if total else 0.0

    runtime = runtime_from_snapshot(candidate)
    runtime_state = str(runtime.get("state") or "")
    left_early = runtime_state == "ENDED" or str(runtime.get("left_by") or "") == "candidate"
    interview_attempted = bool(
        answered
        or runtime_state in AI_STARTED_STATES
        or int(runtime.get("room_join_count") or 0) > 0
    )
    incomplete = bool(unanswered) or left_early or runtime_state in {"ENDED", "AI_INTERVIEW_ACTIVE", "HR_INTERVENTION"}
    if runtime_state == "COMPLETED" and not unanswered:
        incomplete = False
        left_early = False

    mcq_correct = sum(1 for row in mcq_items if float(row.get("score") or 0) >= 100)
    return {
        "items": items,
        "interview_score": interview_score,
        "interview_attempted": interview_attempted,
        "incomplete": incomplete and interview_attempted,
        "left_early": left_early and interview_attempted,
        "questions_total": total,
        "questions_answered": len(answered),
        "questions_unanswered": len(unanswered),
        "mcq_total": len(mcq_items),
        "mcq_correct": mcq_correct,
        "oral_total": len(oral_items),
        "oral_answered": sum(1 for row in oral_items if row.get("status") == "answered"),
        "runtime_state": runtime_state,
        "scoring_note": (
            "Interview score is the average of every planned MCQ and oral question. "
            "Unanswered, skipped, or unasked questions count as 0 — not as if they were never on the paper."
        ),
    }
