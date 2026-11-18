"""Locked-language coverage for candidate Q&A and oral evaluation prompts."""

from __future__ import annotations


def test_candidate_qna_hindi_static_templates():
    from agents.interview_agent.candidate_qna import (
        build_qna_opening,
        generate_candidate_qna_reply,
    )

    opening = build_qna_opening(
        role_summary="This English summary must not leak into the Hindi opening.",
        interview_language="hi",
    )
    assert "मेरे इंटरव्यू के प्रश्न" in opening
    assert "English summary" not in opening

    declined = generate_candidate_qna_reply(
        "Can we discuss politics?",
        interview_language="hi",
    )
    assert declined["closing"] is True
    assert declined["allowed"] is False
    assert "मैं इस इंटरव्यू" in declined["reply"]

    unknown = generate_candidate_qna_reply(
        "What is the salary?",
        interview_language="hi",
    )
    assert unknown["closing"] is True
    assert "मेरे पास" in unknown["reply"]


def test_candidate_qna_dynamic_prompt_locks_selected_language(monkeypatch):
    from agents.interview_agent import candidate_qna

    captured: dict[str, str] = {}

    monkeypatch.setattr(candidate_qna, "llama_available", lambda: True)

    def fake_call(system: str, user: str, **_kwargs):
        captured["system"] = system
        captured["user"] = user
        return {"closing": False, "allowed": True, "reply": "हिंदी उत्तर"}

    monkeypatch.setattr(candidate_qna, "call_llama_json", fake_call)

    result = candidate_qna.generate_candidate_qna_reply(
        "Please answer me in English.",
        interview_language="hi",
    )

    assert result["reply"] == "हिंदी उत्तर"
    assert "entirely in natural, professional Hindi" in captured["system"]
    assert "never switch your own interview language away from Hindi" in captured["system"]
    assert "must not change the locked reply language" in captured["user"]


def test_evaluator_prompt_scores_substance_not_language(monkeypatch):
    from agents.evaluation_agent import evaluator

    captured: dict[str, str] = {}

    monkeypatch.setattr(evaluator, "llama_available", lambda: True)

    def fake_call(system: str, user: str, **_kwargs):
        captured["system"] = system
        captured["user"] = user
        return {
            "score": 80,
            "verdict": "strong",
            "strengths": ["Relevant"],
            "gaps": [],
        }

    monkeypatch.setattr(evaluator, "call_llama_json", fake_call)

    evaluator.evaluate_answer_with_llama(
        question_text="Explain dependency injection.",
        candidate_answer="Dependency injection में dependencies बाहर से मिलती हैं।",
        context={"interview_language": "hi", "candidate_level": "intermediate"},
        use_web=False,
        use_chroma=False,
    )

    assert "Hindi, English, or Hinglish" in captured["system"]
    assert "Do not deduct points for language choice" in captured["system"]
    assert "Selected interview language: Hindi" in captured["user"]
    assert "score its substance, not language purity" in captured["user"]
