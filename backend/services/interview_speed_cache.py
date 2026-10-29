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


def _asked_fu_key(candidate_id: str) -> str:
    return f"interview:asked_fu:{candidate_id}"


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
    cache_delete(_asked_fu_key(candidate_id))


def init_followup_budget(candidate_id: str, bank_size: int) -> None:
    max_fu = max_interview_followups(bank_size)
    cache_set(
        _budget_key(candidate_id),
        {"max": max_fu, "used": 0, "bank_size": int(bank_size or 0)},
        ttl_seconds=TTL,
    )
    cache_set(_asked_fu_key(candidate_id), [], ttl_seconds=TTL)


def _fu_fingerprint(followup: dict[str, Any]) -> str:
    text = str(followup.get("question_text") or "").strip().casefold()
    # Collapse ownership variants to one fingerprint so they never repeat.
    if (
        "working with others" in text
        or "versus the team" in text
        or "contribution versus" in text
    ):
        return "ownership-team-probe"
    return text[:160]


def asked_followup_fingerprints(candidate_id: str) -> set[str]:
    rows = cache_get_json(_asked_fu_key(candidate_id)) or []
    if not isinstance(rows, list):
        return set()
    return {str(x).casefold() for x in rows if x}


def mark_followup_asked(candidate_id: str, followup: dict[str, Any]) -> None:
    fp = _fu_fingerprint(followup)
    if not fp:
        return
    rows = cache_get_json(_asked_fu_key(candidate_id)) or []
    if not isinstance(rows, list):
        rows = []
    if fp not in rows:
        rows.append(fp)
    cache_set(_asked_fu_key(candidate_id), rows[-40:], ttl_seconds=TTL)


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
    fp = _fu_fingerprint(followup)
    if fp and fp in asked_followup_fingerprints(candidate_id):
        logger.info("Skip duplicate follow-up for %s (%s)", candidate_id, fp[:48])
        return False
    # Also reject invented team probes before they enter the queue.
    try:
        from agents.interview_agent.followup_generator import followup_invents_team_context

        parent_answer = str(followup.get("source_answer") or "")
        if followup_invents_team_context(str(followup.get("question_text") or ""), parent_answer):
            logger.info("Skip invented team follow-up for %s", candidate_id)
            return False
    except Exception:
        pass
    if not consume_followup_budget(candidate_id):
        return False
    # Reserve fingerprint immediately so a second worker cannot queue the same probe.
    mark_followup_asked(candidate_id, followup)
    queue_push(_pending_fu_key(candidate_id), followup)
    return True


def pop_pending_followup(candidate_id: str) -> dict[str, Any] | None:
    item = queue_pop_nowait(_pending_fu_key(candidate_id))
    if isinstance(item, dict):
        mark_followup_asked(candidate_id, item)
        return item
    return None


def enqueue_eval_job(job: dict[str, Any]) -> None:
    queue_push(EVAL_QUEUE, job)
