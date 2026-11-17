"""Pre-generate fixed follow-up questions into the oral bank before the interview.

Budget matches product bands (1 follow-up per ~5 bank questions). During the live
interview we only walk this fixed list — no mid-interview adaptive LLM follow-ups.
"""

from __future__ import annotations

import uuid
from typing import Any

from agents.interview_agent.question_generator import sanitize_topic, shorten_question
from services.interview_speed_cache import max_interview_followups

FOLLOWUP_MAX_WORDS = 22


def _parent_indices(bank_size: int, budget: int) -> list[int]:
    """Evenly spaced parent bank indices that each get one planned follow-up."""
    n = max(0, int(bank_size or 0))
    b = max(0, min(int(budget or 0), n))
    if n <= 0 or b <= 0:
        return []
    if b == 1:
        return [max(0, min(n - 1, n // 2))]
    step = (n - 1) / (b - 1)
    idxs: list[int] = []
    seen: set[int] = set()
    for i in range(b):
        idx = int(round(i * step))
        idx = max(0, min(n - 1, idx))
        if idx in seen:
            # Nudge forward to keep uniqueness.
            for alt in range(idx + 1, n):
                if alt not in seen:
                    idx = alt
                    break
            else:
                for alt in range(idx - 1, -1, -1):
                    if alt not in seen:
                        idx = alt
                        break
        seen.add(idx)
        idxs.append(idx)
    return sorted(idxs)


def _followup_text_from_parent(parent: dict[str, Any]) -> str:
    hints = [str(h).strip() for h in (parent.get("follow_up_hints") or []) if str(h).strip()]
    tags = [sanitize_topic(str(t)) for t in (parent.get("skill_tags") or []) if sanitize_topic(str(t))]
    skill = tags[0] if tags else ""
    if hints:
        hint = hints[0]
        # Hints may be "Probe: tradeoff" style — turn into a spoken question.
        lowered = hint.lower()
        if lowered.startswith("probe:"):
            topic = sanitize_topic(hint.split(":", 1)[-1]) or skill or "that approach"
            text = f"Can you go one level deeper on {topic}?"
        elif "?" in hint:
            text = hint
        else:
            topic = sanitize_topic(hint) or skill or "that"
            text = f"Can you share a concrete example of {topic}?"
    elif skill:
        text = f"How did you apply {skill} in a real situation on that project?"
    else:
        text = "Can you walk through one concrete example from that answer?"
    return shorten_question(text, FOLLOWUP_MAX_WORDS)


def build_planned_followup(parent: dict[str, Any], *, order: int) -> dict[str, Any]:
    parent_id = str(parent.get("id") or "unknown")
    text = _followup_text_from_parent(parent)
    return {
        "id": f"fu-planned-{uuid.uuid4().hex[:10]}",
        "order": order,
        "category_id": "planned_followup",
        "category_name": "Follow-up",
        "difficulty": str(parent.get("difficulty") or "medium"),
        "question_text": text,
        "intent": f"Planned follow-up for {parent_id}",
        "follow_up_hints": [],
        "estimated_seconds": min(90, int(parent.get("estimated_seconds") or 60)),
        "skill_tags": list(parent.get("skill_tags") or [])[:4],
        "is_followup": True,
        "parent_question_id": parent_id,
        "planned": True,
    }


def materialize_planned_followups(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert budgeted follow-ups into the bank immediately after their parents."""
    bank = [dict(q) for q in questions if isinstance(q, dict)]
    if not bank:
        return []
    # Only count non-followup parents for budget (fresh generation has none yet).
    parents = [q for q in bank if not q.get("is_followup")]
    budget = max_interview_followups(len(parents))
    if budget <= 0:
        return bank

    chosen = set(_parent_indices(len(parents), budget))
    out: list[dict[str, Any]] = []
    order = 1
    for i, parent in enumerate(parents):
        parent = dict(parent)
        parent["order"] = order
        order += 1
        out.append(parent)
        if i in chosen:
            fu = build_planned_followup(parent, order=order)
            order += 1
            out.append(fu)
    # Preserve any trailing items that were already followups (rare on fresh gen).
    return out
