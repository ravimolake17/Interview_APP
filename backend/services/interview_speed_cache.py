"""Redis-backed interview hot cache: question bank, TTS bytes, pending follow-ups, budget."""

from __future__ import annotations

import logging
from typing import Any

from core.redis_client import cache_delete, cache_get_bytes, cache_get_json, cache_set, queue_pop_nowait, queue_push

logger = logging.getLogger(__name__)

TTL = 86_400  # 24h
EVAL_QUEUE = "interview:eval:queue"


def _qkey(candidate_id: str) -> str:
    return f"interview:questions:{candidate_id}"


def _tts_key(candidate_id: str, question_id: str) -> str:
    return f"interview:tts:{candidate_id}:{question_id}"


def _pending_fu_key(candidate_id: str) -> str:
    return f"interview:pending_fu:{candidate_id}"


def _budget_key(candidate_id: str) -> str:
    return f"interview:fu_budget:{candidate_id}"


def max_interview_followups(bank_size: int) -> int:
    """1 follow-up per ~5 bank questions (matches product bands)."""
    n = max(0, int(bank_size or 0))
    if n >= 14:
        return max(3, n // 5)
    if n >= 10:
        return 2
    if n >= 5:
        return 1
    return 0


def cache_question_bank(candidate_id: str, questions: list[dict[str, Any]]) -> None:
    cache_set(_qkey(candidate_id), {"questions": questions, "total": len(questions)}, ttl_seconds=TTL)
    init_followup_budget(candidate_id, len(questions))


def get_cached_question_bank(candidate_id: str) -> list[dict[str, Any]] | None:
    data = cache_get_json(_qkey(candidate_id))
    if not isinstance(data, dict):
        return None
    rows = data.get("questions")
    return rows if isinstance(rows, list) else None


def cache_tts_audio(candidate_id: str, question_id: str, audio_bytes: bytes) -> None:
    if not audio_bytes or not question_id:
        return
    cache_set(_tts_key(candidate_id, question_id), audio_bytes, ttl_seconds=TTL)


def get_cached_tts_audio(candidate_id: str, question_id: str) -> bytes | None:
    return cache_get_bytes(_tts_key(candidate_id, question_id))


def clear_candidate_speed_cache(candidate_id: str) -> None:
    cache_delete(_qkey(candidate_id))
    cache_delete(_pending_fu_key(candidate_id))
    cache_delete(_budget_key(candidate_id))


def init_followup_budget(candidate_id: str, bank_size: int) -> None:
    max_fu = max_interview_followups(bank_size)
    cache_set(
        _budget_key(candidate_id),
        {"max": max_fu, "used": 0, "bank_size": int(bank_size or 0)},
        ttl_seconds=TTL,
    )


def followup_budget(candidate_id: str) -> dict[str, int]:
    data = cache_get_json(_budget_key(candidate_id)) or {}
    return {
        "max": int(data.get("max") or 0),
        "used": int(data.get("used") or 0),
        "bank_size": int(data.get("bank_size") or 0),
    }


def followup_budget_remaining(candidate_id: str) -> int:
    b = followup_budget(candidate_id)
    return max(0, b["max"] - b["used"])


def consume_followup_budget(candidate_id: str) -> bool:
    b = followup_budget(candidate_id)
    if b["used"] >= b["max"]:
        return False
    b["used"] += 1
    cache_set(_budget_key(candidate_id), b, ttl_seconds=TTL)
    return True


def push_pending_followup(candidate_id: str, followup: dict[str, Any]) -> bool:
    if followup_budget_remaining(candidate_id) <= 0:
        return False
    if not consume_followup_budget(candidate_id):
        return False
    queue_push(_pending_fu_key(candidate_id), followup)
    return True


def pop_pending_followup(candidate_id: str) -> dict[str, Any] | None:
    item = queue_pop_nowait(_pending_fu_key(candidate_id))
    return item if isinstance(item, dict) else None


def enqueue_eval_job(job: dict[str, Any]) -> None:
    queue_push(EVAL_QUEUE, job)
