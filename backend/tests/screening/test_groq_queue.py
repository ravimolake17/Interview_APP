from agents.screening_agent.services.groq_queue import GroqRateLimitError, GroqResumeQueue
from agents.screening_agent.services.ai_parser import extract_resume_data


class _RateLimit(Exception):
    status_code = 429

    def __str__(self) -> str:
        return "429 Too Many Requests: tokens per minute"


def test_groq_queue_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(
        "agents.screening_agent.services.groq_queue.settings.GROQ_RATE_LIMIT_WAIT_SECONDS",
        30,
    )
    monkeypatch.setattr("agents.screening_agent.services.groq_queue.time.sleep", lambda _s: None)

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _RateLimit()
        return "ok"

    assert GroqResumeQueue().call(flaky) == "ok"
    assert calls["n"] == 3


def test_groq_queue_raises_instead_of_returning_fallback(monkeypatch):
    monkeypatch.setattr(
        "agents.screening_agent.services.groq_queue.settings.GROQ_RATE_LIMIT_WAIT_SECONDS",
        0.01,
    )
    monkeypatch.setattr("agents.screening_agent.services.groq_queue.time.sleep", lambda _s: None)

    def always_busy():
        raise _RateLimit()

    try:
        GroqResumeQueue().call(always_busy)
        assert False, "expected GroqRateLimitError"
    except GroqRateLimitError as exc:
        assert "not parsed or saved" in str(exc)


def test_extract_resume_data_does_not_fallback_on_429(monkeypatch):
    monkeypatch.setattr(
        "agents.screening_agent.services.ai_parser.settings.USE_LLM_FOR_RESUME_PARSING",
        True,
    )
    monkeypatch.setattr(
        "agents.screening_agent.services.ai_parser._groq_client",
        lambda: object(),
    )
    monkeypatch.setattr(
        "agents.screening_agent.services.groq_queue.settings.GROQ_RATE_LIMIT_WAIT_SECONDS",
        0.01,
    )
    monkeypatch.setattr("agents.screening_agent.services.groq_queue.time.sleep", lambda _s: None)

    def busy(*_args, **_kwargs):
        raise _RateLimit()

    monkeypatch.setattr("agents.screening_agent.services.ai_parser._call_groq", busy)
    q = GroqResumeQueue()
    monkeypatch.setattr(
        "agents.screening_agent.services.ai_parser.get_groq_resume_queue",
        lambda: q,
    )

    try:
        extract_resume_data("Anita Sharma\nanita@example.com\nSkills\nPython")
        assert False, "expected GroqRateLimitError"
    except GroqRateLimitError:
        pass
