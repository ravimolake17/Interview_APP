"""Prep-time planned follow-up materialization."""

from __future__ import annotations

from agents.interview_agent.planned_followups import materialize_planned_followups
from agents.interview_agent.followup_generator import answer_is_thin, should_treat_as_unanswered


def test_materialize_inserts_one_followup_for_5_to_9_bank():
    bank = [
        {
            "id": f"q-{i}",
            "order": i,
            "question_text": f"Question {i}?",
            "skill_tags": ["FastAPI"],
            "follow_up_hints": ["Probe: tradeoffs"],
            "difficulty": "medium",
        }
        for i in range(1, 6)
    ]
    out = materialize_planned_followups(bank)
    fus = [q for q in out if q.get("is_followup")]
    assert len(fus) == 1
    assert fus[0].get("planned") is True
    assert "parent_question_id" in fus[0]
    assert len(out) == 6


def test_materialize_zero_when_bank_small():
    bank = [{"id": "q-1", "question_text": "Hello?", "skill_tags": [], "follow_up_hints": []}]
    out = materialize_planned_followups(bank)
    assert all(not q.get("is_followup") for q in out)


def test_thin_answers_include_sorry_and_dont_know():
    assert answer_is_thin("sorry")
    assert answer_is_thin("I don't know")
    assert answer_is_thin("[No response]")
    assert should_treat_as_unanswered("sorry I don't know", None)
    assert not answer_is_thin(
        "I built a FastAPI service with Redis caching and PostgreSQL for interview workflows."
    )
