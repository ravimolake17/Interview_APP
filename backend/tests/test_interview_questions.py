"""Agent 4 question bank uniqueness (templates + chroma fallback)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from agents.interview_agent.question_bank import question_edit_policy
from agents.interview_agent.question_generator import generate_questions_from_blueprint
from agents.shared.llama_client import resolve_groq_model


INTRO_DUP = (
    "If I had two minutes with a hiring manager, what should I remember about you "
    "for this Python Developer (AI/ML Engineer) role?"
)

BLUEPRINT = {
    "input_summary": {"job_title": "Python Developer (AI/ML Engineer)"},
    "skill_focus_plan": [
        {"skill_name": "FastAPI"},
        {"skill_name": "Python"},
        {"skill_name": "PostgreSQL"},
    ],
    "category_breakdown": [
        {
            "category_id": "introductory_questions",
            "category_name": "Introductory Questions",
            "question_count": 2,
            "difficulty_mix": {"hard": 2},
        },
        {
            "category_id": "skills_jd_keyword_questions",
            "category_name": "Skills & JD Keyword-Related Questions",
            "question_count": 4,
            "difficulty_mix": {"hard": 4},
            "jd_signals": ["FastAPI", "Python", "PostgreSQL", "LangGraph"],
        },
        {
            "category_id": "project_related_questions",
            "category_name": "Project-Related Questions",
            "question_count": 2,
            "difficulty_mix": {"easy": 1, "hard": 1},
            "candidate_resume_signals": ["Tater-Check", "Dental Mesh Segmentation"],
        },
    ],
}


def test_resolve_retired_groq_model():
    assert resolve_groq_model("llama-3.3-70b-versatile") == "openai/gpt-oss-120b"
    assert resolve_groq_model("openai/gpt-oss-120b") == "openai/gpt-oss-120b"


def test_question_bank_stays_unique_when_chroma_repeats_intro():
    chroma_hit = {
        "document": INTRO_DUP,
        "metadata": {"category": "introductory_questions"},
    }
    _assert_unique_bank(chroma_hit)


def test_question_bank_rejects_intro_chroma_without_category_metadata():
    _assert_unique_bank({"document": INTRO_DUP, "metadata": {}})


def _assert_unique_bank(chroma_hit: dict) -> None:
    with patch(
        "agents.interview_agent.question_generator.retrieve_interview_questions",
        return_value=[chroma_hit],
    ):
        questions = generate_questions_from_blueprint(
            BLUEPRINT,
            job_title="Python Developer (AI/ML Engineer)",
        )

    texts = [q.question_text for q in questions]
    keys = {t.casefold() for t in texts}
    assert len(texts) == len(keys)
    skill_texts = [q.question_text for q in questions if q.category_id == "skills_jd_keyword_questions"]
    assert skill_texts
    assert all("hiring manager" not in text.casefold() for text in skill_texts)


def test_insert_question_shifts_later_orders():
    from agents.interview_agent.question_bank import insert_manual_question, update_manual_question

    bank = [
        {"id": "q-a", "order": 1, "category_id": "introductory_questions", "category_name": "Intro", "difficulty": "easy", "question_text": "Walk me through your background?"},
        {"id": "q-b", "order": 2, "category_id": "skills_jd_keyword_questions", "category_name": "Skills", "difficulty": "medium", "question_text": "How have you used FastAPI in production?"},
        {"id": "q-c", "order": 3, "category_id": "project_related_questions", "category_name": "Project", "difficulty": "hard", "question_text": "What would you change in Tater-Check?"},
    ]
    inserted = insert_manual_question(
        bank,
        question_text="Give me a production NumPy debugging example.",
        insert_at=2,
        category_id="skills_jd_keyword_questions",
        difficulty="hard",
    )
    assert [item["order"] for item in inserted] == [1, 2, 3, 4]
    assert inserted[1]["question_text"].startswith("Give me a production NumPy")
    assert inserted[2]["id"] == "q-b"
    moved = update_manual_question(
        inserted,
        inserted[1]["id"],
        question_text=inserted[1]["question_text"],
        insert_at=4,
    )
    assert moved[-1]["question_text"].startswith("Give me a production NumPy")
    assert [item["order"] for item in moved] == [1, 2, 3, 4]


def test_question_edits_allowed_until_ten_minutes_before_start():
    tz = timezone(timedelta(hours=5, minutes=30))
    start = datetime(2026, 9, 18, 10, 0, tzinfo=tz)
    open_window = question_edit_policy(
        now=datetime(2026, 9, 18, 9, 49, tzinfo=tz),
        start_at=start,
        interview_status="SCHEDULED",
    )
    cutoff = question_edit_policy(
        now=datetime(2026, 9, 18, 9, 50, tzinfo=tz),
        start_at=start,
        interview_status="SCHEDULED",
    )
    started = question_edit_policy(
        now=datetime(2026, 9, 18, 10, 0, tzinfo=tz),
        start_at=start,
        interview_status="SCHEDULED",
    )
    done = question_edit_policy(
        now=datetime(2026, 9, 18, 11, 0, tzinfo=tz),
        start_at=start,
        interview_status="COMPLETED",
    )
    assert open_window["allowed"] is True
    assert cutoff["allowed"] is False
    assert "10 minutes" in str(cutoff["reason"])
    assert started["allowed"] is False
    assert "started" in str(started["reason"]).lower()
    assert done["allowed"] is False
    assert "completed" in str(done["reason"]).lower()
