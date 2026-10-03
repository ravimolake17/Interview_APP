from agents.screening_agent.services.ai_parser import _truncate
from services.screening_integration_service import _names_look_like_different_people


def test_truncate_keeps_experience_instead_of_only_the_header():
    header = "Anita Sharma\nanita@example.com\n"
    fluff = "SUMMARY\n" + ("lorem ipsum dolor sit amet. " * 80) + "\n"
    experience = (
        "EXPERIENCE\n"
        "Backend Developer at Acme 2021 - 2024\n"
        "Built FastAPI services and PostgreSQL reporting.\n"
    )
    education = "EDUCATION\nB.Tech Computer Science 2020\n"
    text = header + fluff + experience + education

    truncated, was_truncated = _truncate(text, max_chars=900)

    assert was_truncated is True
    assert "Anita Sharma" in truncated
    assert "EXPERIENCE" in truncated
    assert "Backend Developer at Acme" in truncated
    assert "EDUCATION" in truncated


def test_distinct_candidate_names_are_not_merged():
    assert _names_look_like_different_people("Anita Sharma", "Rahul Verma") is True
    assert _names_look_like_different_people("Anita Sharma", "Anita K Sharma") is False
    assert _names_look_like_different_people("Candidate", "Rahul Verma") is False
