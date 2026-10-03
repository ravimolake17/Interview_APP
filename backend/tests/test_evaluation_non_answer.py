from agents.evaluation_agent.evaluator import _heuristic_evaluation, is_non_answer


def test_sorry_i_dont_know_is_non_answer():
    assert is_non_answer("Sorry, I don't know.")
    assert is_non_answer(
        "4 words, 4 words, thank you. Sorry, I don't have an answer for this question. No, it's it's okay."
    )
    assert not is_non_answer(
        "I don't know the exact latency number, but I used FastAPI to cut response time in production."
    )


def test_heuristic_scores_dont_know_as_zero():
    result = _heuristic_evaluation(
        question_text="If I had two minutes with a hiring manager, what should I remember about you?",
        candidate_answer="Sorry, I don't know.",
        skill_tags=["Python"],
        web_snippets=[],
    )
    assert result.score == 0.0
    assert result.verdict == "insufficient"
