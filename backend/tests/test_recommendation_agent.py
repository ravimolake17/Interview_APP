from types import SimpleNamespace

from agents.recommendation_agent.report_builder import decision_from_scores
from services.interview_answer_report import build_interview_answer_report


def test_hire_when_interview_and_screening_are_strong():
    assert (
        decision_from_scores(
            screening_score=82,
            interview_score=80,
            integrity_risk=5,
            interview_turns=4,
            interview_attempted=True,
        )
        == "HIRE"
    )


def test_hold_before_interview():
    assert (
        decision_from_scores(
            screening_score=72,
            interview_score=0,
            integrity_risk=0,
            interview_turns=0,
        )
        == "HOLD"
    )


def test_high_screening_without_interview_is_hold_not_consider():
    assert (
        decision_from_scores(
            screening_score=94,
            interview_score=0,
            integrity_risk=0,
            interview_turns=0,
            interview_attempted=False,
        )
        == "HOLD"
    )


def test_reject_on_high_integrity_risk():
    assert (
        decision_from_scores(
            screening_score=90,
            interview_score=88,
            integrity_risk=80,
            interview_turns=3,
            interview_attempted=True,
        )
        == "REJECT"
    )


def test_incomplete_strong_interview_is_consider_not_hire():
    assert (
        decision_from_scores(
            screening_score=90,
            interview_score=80,
            integrity_risk=5,
            interview_turns=5,
            interview_attempted=True,
            incomplete=True,
        )
        == "CONSIDER"
    )


def test_score_uses_total_questions_not_attended_only():
    candidate = SimpleNamespace(
        evaluation_snapshot={
            "interview_mcq": {
                "questions": [
                    {
                        "id": f"mcq-{i}",
                        "question_text": f"Q{i}",
                        "options": [{"id": "A", "text": "Yes"}, {"id": "B", "text": "No"}],
                        "correct_option_id": "A",
                        "answer_option_id": "A" if i < 5 else None,
                        "skipped": False,
                    }
                    for i in range(20)
                ]
            }
        }
    )
    report = build_interview_answer_report(candidate=candidate, evaluations=[], planned_oral_questions=[])
    assert report["questions_total"] == 20
    assert report["questions_answered"] == 5
    assert report["mcq_correct"] == 5
    assert report["interview_score"] == 25.0
    assert report["interview_attempted"] is True


def test_oral_unanswered_count_as_zero_after_room_join():
    candidate = SimpleNamespace(
        evaluation_snapshot={
            "agent5": {"interview_runtime": {"room_join_count": 1, "state": "ENDED", "left_by": "candidate"}}
        }
    )
    evals = [
        SimpleNamespace(
            id=1,
            question_id="q1",
            question_text="Explain Python GIL",
            answer_text="Global interpreter lock",
            score=80,
            verdict="strong",
            evaluation_json={"feedback_for_agent4": "Solid"},
            model="test",
        )
    ]
    planned = [
        {"id": "q1", "question_text": "Explain Python GIL"},
        {"id": "q2", "question_text": "What is a REST API?"},
    ]
    report = build_interview_answer_report(
        candidate=candidate,
        evaluations=evals,
        planned_oral_questions=planned,
    )
    assert report["interview_attempted"] is True
    assert report["left_early"] is True
    assert report["questions_total"] == 2
    assert report["questions_answered"] == 1
    assert report["interview_score"] == 40.0
    assert report["items"][1]["status"] == "unanswered"
    assert report["items"][1]["score"] == 0.0


def test_oral_turn_history_matches_despite_punctuation():
    candidate = SimpleNamespace(evaluation_snapshot={})
    planned = [
        {"id": "intro-1", "question_text": "To start, walk me through your background and what you are working on right now."}
    ]
    history = [
        {
            "question": {
                "id": "intro-1",
                "question_text": "To start, walk me through your background and what you are working on right now?",
            },
            "answer_text": "I am a Python developer working on FastAPI services.",
            "evaluation": {"score": 72, "verdict": "adequate", "feedback_for_agent4": "Clear intro."},
        }
    ]
    report = build_interview_answer_report(
        candidate=candidate,
        evaluations=[],
        planned_oral_questions=planned,
        turn_history=history,
    )
    assert report["items"][0]["status"] == "answered"
    assert "FastAPI" in report["items"][0]["answer_text"]
    assert report["items"][0]["score"] == 72.0


def test_oral_snapshot_turns_show_transcript_without_audio():
    candidate = SimpleNamespace(
        evaluation_snapshot={
            "interview_oral": {
                "turns": [
                    {
                        "question_id": "q-949ce295f6",
                        "question_text": "To start, walk me through your background and what you are working on right now?",
                        "answer_text": "Hello, my name is Ravi. I am a Python developer.",
                        "score": 55,
                        "verdict": "adequate",
                    }
                ]
            }
        }
    )
    planned = [
        {"id": "q-949ce295f6", "question_text": "To start, walk me through your background and what you are working on right now?"}
    ]
    report = build_interview_answer_report(
        candidate=candidate,
        evaluations=[],
        planned_oral_questions=planned,
    )
    assert report["items"][0]["status"] == "answered"
    assert "Python developer" in report["items"][0]["answer_text"]
    assert report["items"][0]["score"] == 55.0
    assert report["items"][0]["has_audio"] is False


def test_dont_know_oral_answer_is_scored_zero():
    candidate = SimpleNamespace(
        evaluation_snapshot={
            "interview_oral": {
                "turns": [
                    {
                        "question_id": "q-f6da344784",
                        "question_text": "If I had two minutes with a hiring manager, what should I remember about you?",
                        "answer_text": "Sorry, I don't know.",
                        "score": 35,
                        "verdict": "insufficient",
                    }
                ]
            }
        }
    )
    planned = [
        {
            "id": "q-f6da344784",
            "question_text": "If I had two minutes with a hiring manager, what should I remember about you?",
        }
    ]
    report = build_interview_answer_report(
        candidate=candidate,
        evaluations=[],
        planned_oral_questions=planned,
    )
    assert report["items"][0]["status"] == "answered"
    assert report["items"][0]["score"] == 0.0
    assert report["items"][0]["verdict"] == "insufficient"
