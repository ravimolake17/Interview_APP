"""Agent 4 question bank uniqueness (templates + chroma fallback)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from agents.blueprint_agent.generator import _looks_like_resume_summary, _topic_signals
from agents.interview_agent.followup_generator import build_turn_ack
from agents.interview_agent.question_bank import question_edit_policy
from agents.interview_agent.question_generator import (
    generate_questions_from_blueprint,
    is_spoken_interview_question,
    looks_like_resume_summary,
    sanitize_topic,
)
from agents.shared.llama_client import resolve_groq_model

RESUME_BLURB = (
    "Motivated and research-oriented MCA graduate with strong expertise in AI "
    "and machine learning seeking challenging opportunities"
)


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


def test_resume_summary_is_rejected_as_topic_and_question():
    assert looks_like_resume_summary(RESUME_BLURB)
    assert _looks_like_resume_summary(RESUME_BLURB)
    assert sanitize_topic(RESUME_BLURB, fallback="your project") == "your project"
    assert not is_spoken_interview_question(RESUME_BLURB + "?")
    assert not is_spoken_interview_question(
        f"On the {RESUME_BLURB} work, what did you personally own?"
    )
    assert is_spoken_interview_question(
        "On the Dental Mesh Segmentation work, what did you personally own?"
    )


def test_agent3_topic_signals_drop_resume_profile_blurbs():
    labels = _topic_signals(
        [RESUME_BLURB, "Tater-Check", "Dental Mesh Segmentation"],
        "your project",
        4,
    )
    assert labels == ["Tater-Check", "Dental Mesh Segmentation"]
    assert all(RESUME_BLURB.casefold() not in item.casefold() for item in labels)


def test_question_bank_ignores_resume_profile_signals():
    blueprint = {
        "input_summary": {"job_title": "AI Engineer"},
        "skill_focus_plan": [{"skill_name": "Python"}],
        "category_breakdown": [
            {
                "category_id": "introductory_questions",
                "category_name": "Introductory Questions",
                "question_count": 1,
                "difficulty_mix": {"easy": 1},
                "candidate_resume_signals": [RESUME_BLURB],
            },
            {
                "category_id": "project_related_questions",
                "category_name": "Project-Related Questions",
                "question_count": 2,
                "difficulty_mix": {"medium": 2},
                # Old blueprints may still carry profile prose as a "project" signal.
                "candidate_resume_signals": [RESUME_BLURB],
            },
            {
                "category_id": "skills_jd_keyword_questions",
                "category_name": "Skills",
                "question_count": 1,
                "difficulty_mix": {"medium": 1},
                "jd_signals": ["Python"],
            },
        ],
    }
    with patch(
        "agents.interview_agent.question_generator.retrieve_interview_questions",
        return_value=[],
    ):
        questions = generate_questions_from_blueprint(blueprint, job_title="AI Engineer")

    joined = " ".join(q.question_text for q in questions).casefold()
    assert "motivated" not in joined
    assert "research-oriented" not in joined
    assert "graduate with" not in joined
    for q in questions:
        assert is_spoken_interview_question(q.question_text)
        for tag in q.skill_tags:
            assert not looks_like_resume_summary(tag)
            assert "motivated" not in tag.casefold()


def test_turn_ack_skips_resume_blurb_skill_tags():
    ack = build_turn_ack(
        evaluation={"verdict": "adequate"},
        next_question={
            "category_name": "Project-Related Questions",
            "skill_tags": [RESUME_BLURB],
        },
    )
    assert "motivated" not in ack.casefold()
    assert "Let's move to project-related questions." in ack
    clean = build_turn_ack(
        evaluation={"verdict": "adequate"},
        next_question={
            "category_name": "Project-Related Questions",
            "skill_tags": ["Tater-Check"],
        },
    )
    assert "Next, a short question on Tater-Check." in clean


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
    hr_preview = question_edit_policy(
        now=datetime(2026, 9, 17, 12, 0, tzinfo=tz),
        start_at=start,
        interview_status="SCHEDULED",
        live_started=False,
    )
    assert open_window["allowed"] is True
    assert cutoff["allowed"] is False
    assert "10 minutes" in str(cutoff["reason"])
    assert started["allowed"] is False
    assert "started" in str(started["reason"]).lower()
    assert done["allowed"] is False
    assert "completed" in str(done["reason"]).lower()
    assert hr_preview["allowed"] is True


def test_hr_intervention_runtime_does_not_count_as_live_start():
    from types import SimpleNamespace

    from services.interview_room_service import live_interview_started, plan_is_locked

    preview = SimpleNamespace(
        evaluation_snapshot={"agent5": {"interview_runtime": {"state": "HR_INTERVENTION"}}}
    )
    live = SimpleNamespace(
        evaluation_snapshot={"agent5": {"interview_runtime": {"state": "AI_INTERVIEW_ACTIVE"}}}
    )
    assert live_interview_started(preview) is False
    assert plan_is_locked(preview) is False
    assert live_interview_started(live) is True
    assert plan_is_locked(live) is True
