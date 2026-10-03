"""Persist oral interview transcripts and per-answer audio clips."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models.candidate import Candidate

ORAL_KEY = "interview_oral"
BACKEND_ROOT = Path(__file__).resolve().parent.parent
ANSWERS_ROOT = BACKEND_ROOT / "storage" / "interview_answers"
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    cleaned = _SAFE.sub("-", str(value or "").strip())[:80].strip("-")
    return cleaned or "answer"


def answer_audio_dir() -> Path:
    ANSWERS_ROOT.mkdir(parents=True, exist_ok=True)
    return ANSWERS_ROOT


def save_answer_audio(candidate_id: str, question_id: str | None, content: bytes, filename: str = "answer.webm") -> str | None:
    if not content:
        return None
    suffix = Path(filename or "answer.webm").suffix.lower() or ".webm"
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg"}:
        suffix = ".webm"
    folder = answer_audio_dir() / _safe_id(candidate_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe_id(question_id or 'turn')}-{int(datetime.now(timezone.utc).timestamp())}{suffix}"
    path.write_bytes(content)
    return str(path.relative_to(BACKEND_ROOT)).replace("\\", "/")


def resolve_answer_audio(relative_path: str | None) -> Path | None:
    raw = str(relative_path or "").replace("\\", "/").lstrip("/")
    if not raw or ".." in raw.split("/"):
        return None
    path = (BACKEND_ROOT / raw).resolve()
    root = answer_audio_dir().resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


def oral_turns(candidate: Candidate) -> list[dict[str, Any]]:
    snap = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
    oral = snap.get(ORAL_KEY) if isinstance(snap.get(ORAL_KEY), dict) else {}
    return [dict(item) for item in (oral.get("turns") or []) if isinstance(item, dict)]


def sync_oral_from_history(candidate: Candidate, turn_history: list[dict[str, Any]] | None) -> bool:
    """Copy LangGraph TurnHistory answers into the durable candidate snapshot."""
    changed = False
    for turn in turn_history or []:
        if not isinstance(turn, dict):
            continue
        question = turn.get("question") if isinstance(turn.get("question"), dict) else {}
        if question.get("is_candidate_qna") or turn.get("candidate_qna"):
            continue
        answer = str(turn.get("answer_text") or "").strip()
        if not answer:
            continue
        evaluation = turn.get("evaluation") if isinstance(turn.get("evaluation"), dict) else {}
        upsert_oral_turn(
            candidate,
            {
                "question_id": str(question.get("id") or turn.get("question_id") or ""),
                "question_text": str(question.get("question_text") or turn.get("question_text") or ""),
                "answer_text": answer,
                "score": evaluation.get("score"),
                "verdict": evaluation.get("verdict"),
                "evaluation": evaluation,
                "is_followup": bool(question.get("is_followup")),
                "audio_path": turn.get("audio_path") or evaluation.get("audio_path"),
            },
        )
        changed = True
    return changed


def upsert_oral_turn(candidate: Candidate, turn: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in turn.items() if value not in (None, "")}
    payload.setdefault("updated_at", _utcnow())
    qid = str(payload.get("question_id") or "").strip()
    qtext = " ".join(str(payload.get("question_text") or "").split()).lower()
    turns = oral_turns(candidate)
    replaced = False
    for index, existing in enumerate(turns):
        existing_id = str(existing.get("question_id") or "").strip()
        existing_text = " ".join(str(existing.get("question_text") or "").split()).lower()
        if (qid and existing_id == qid) or (qtext and existing_text == qtext):
            merged = dict(existing)
            merged.update(payload)
            turns[index] = merged
            replaced = True
            payload = merged
            break
    if not replaced:
        payload.setdefault("created_at", _utcnow())
        turns.append(payload)
    snapshot = dict(candidate.evaluation_snapshot or {})
    oral = dict(snapshot.get(ORAL_KEY) or {})
    oral["turns"] = turns
    snapshot[ORAL_KEY] = oral
    candidate.evaluation_snapshot = snapshot
    flag_modified(candidate, "evaluation_snapshot")
    return payload
