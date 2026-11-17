"""Phase 1: staged STT correction, deferred LLM, bounded executor."""

from __future__ import annotations

import asyncio
import time

import pytest

from agents.interview_agent.stt_corrector import (
    classify_correction_tier,
    correct_transcript_with_resume,
    is_short_answer,
)
from agents.interview_agent.stt_executor import run_stt_blocking
from services.interview_speed_cache import claim_eval_job, clear_pending_stt_correction, get_pending_stt_correction, store_pending_stt_correction


@pytest.mark.parametrize(
    "text",
    ["Yes", "No.", "Okay", "I don't know", "yeah!", "not sure", "N/A"],
)
def test_short_answers_detected(text):
    assert is_short_answer(text)
    assert classify_correction_tier(text) == "short"


def test_short_answer_skips_llm_even_inline(monkeypatch):
    called = {"n": 0}

    def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("LLM must not run for short answers")

    monkeypatch.setenv("STT_RESUME_CORRECTION", "true")
    monkeypatch.setenv("STT_LLM_CORRECTION_MODE", "inline")
    monkeypatch.setattr("agents.interview_agent.stt_corrector.call_llama_json", boom)
    monkeypatch.setattr("agents.interview_agent.stt_corrector.llama_available", lambda: True)

    result = correct_transcript_with_resume(
        "Yes",
        context={"job_position": "Engineer"},
        resume_terms=["FastAPI", "PyTorch"],
        candidate_name="Ada",
    )
    assert result["correction_tier"] == "short"
    assert result["needs_llm_correction"] is False
    assert result["correction_status"] == "deterministic_only"
    assert called["n"] == 0


def test_normal_answer_deferred_skips_hot_path_llm(monkeypatch):
    called = {"n": 0}

    def fake_llm(*_a, **_k):
        called["n"] += 1
        return {"corrections": []}

    monkeypatch.setenv("STT_RESUME_CORRECTION", "true")
    monkeypatch.setenv("STT_LLM_CORRECTION_MODE", "deferred")
    monkeypatch.setattr("agents.interview_agent.stt_corrector.call_llama_json", fake_llm)
    monkeypatch.setattr("agents.interview_agent.stt_corrector.llama_available", lambda: True)

    result = correct_transcript_with_resume(
        "I enjoyed collaborating with colleagues and learning about the role.",
        context={"job_position": "Analyst"},
        resume_terms=["Communication"],
        candidate_name="Ada",
    )
    assert result["correction_tier"] == "normal", result
    assert result["needs_llm_correction"] is False
    assert called["n"] == 0


def test_technical_answer_defers_llm(monkeypatch):
    called = {"n": 0}

    def fake_llm(*_a, **_k):
        called["n"] += 1
        return {"corrections": [{"from": "fast api", "to": "FastAPI", "reason": "resume"}]}

    monkeypatch.setenv("STT_RESUME_CORRECTION", "true")
    monkeypatch.setenv("STT_LLM_CORRECTION_MODE", "deferred")
    monkeypatch.setattr("agents.interview_agent.stt_corrector.call_llama_json", fake_llm)
    monkeypatch.setattr("agents.interview_agent.stt_corrector.llama_available", lambda: True)

    result = correct_transcript_with_resume(
        "I built a FastAPI service with Redis and deployed it on AWS EC2.",
        context={"job_position": "Python Developer", "skills": "FastAPI"},
        resume_terms=["FastAPI", "Redis", "AWS EC2"],
        question_text="How did you implement the backend?",
        candidate_name="Ada",
    )
    assert result["correction_tier"] == "technical"
    assert result["needs_llm_correction"] is True
    assert result["correction_status"] == "pending_llm"
    assert called["n"] == 0  # hot path must not call GPT-4o


def test_uncommon_tech_names_preserved_by_deterministic():
    text, corrections = __import__(
        "agents.interview_agent.stt_corrector", fromlist=["apply_deterministic_corrections"]
    ).apply_deterministic_corrections(
        "We used MeshSegNet with MONAIR on DICOM meshes.",
        resume_terms=["MeshSegNet", "MONAI", "DICOM"],
        candidate_name="Ravi",
        job_position="ML Engineer",
    )
    assert "MONAI" in text
    assert "MeshSegNet" in text
    assert any(c["to"] == "MONAI" for c in corrections)


def test_non_answer_short():
    assert is_short_answer("I don't know")
    result = correct_transcript_with_resume(
        "I don't know",
        context={},
        resume_terms=["Kubernetes"],
    )
    assert result["needs_llm_correction"] is False


def test_pending_stt_correction_roundtrip():
    store_pending_stt_correction(
        "cand-1",
        "q-1",
        {"needs_llm_correction": True, "raw_transcript": "raw", "visible_text": "vis"},
    )
    got = get_pending_stt_correction("cand-1", "q-1")
    assert got and got["raw_transcript"] == "raw"
    clear_pending_stt_correction("cand-1", "q-1")
    assert get_pending_stt_correction("cand-1", "q-1") is None


def test_claim_eval_job_dedupes():
    assert claim_eval_job("c1", "q1", "hello world") is True
    assert claim_eval_job("c1", "q1", "hello world") is False
    assert claim_eval_job("c1", "q1", "different") is True


def test_run_stt_blocking_uses_executor():
    def work(x: int) -> int:
        time.sleep(0.05)
        return x * 2

    async def _run():
        return await run_stt_blocking(work, 21)

    assert asyncio.run(_run()) == 42


def test_hot_path_latency_deferred_vs_inline(monkeypatch):
    """Measured: deferred hot path must not wait for mocked LLM latency."""

    def slow_llm(*_a, **_k):
        time.sleep(0.25)
        return {"corrections": []}

    monkeypatch.setenv("STT_RESUME_CORRECTION", "true")
    monkeypatch.setattr("agents.interview_agent.stt_corrector.call_llama_json", slow_llm)
    monkeypatch.setattr("agents.interview_agent.stt_corrector.llama_available", lambda: True)

    sample = (
        "I implemented a FastAPI microservice with Redis caching and deployed "
        "the containers on AWS EC2 using Docker and CI/CD pipelines."
    )
    terms = ["FastAPI", "Redis", "AWS EC2", "Docker"]

    monkeypatch.setenv("STT_LLM_CORRECTION_MODE", "inline")
    t0 = time.perf_counter()
    correct_transcript_with_resume(
        sample,
        context={"job_position": "Backend"},
        resume_terms=terms,
        question_text="How did you implement the service?",
        force_llm=True,
    )
    inline_ms = (time.perf_counter() - t0) * 1000.0

    monkeypatch.setenv("STT_LLM_CORRECTION_MODE", "deferred")
    t1 = time.perf_counter()
    deferred = correct_transcript_with_resume(
        sample,
        context={"job_position": "Backend"},
        resume_terms=terms,
        question_text="How did you implement the service?",
    )
    deferred_ms = (time.perf_counter() - t1) * 1000.0

    assert deferred["needs_llm_correction"] is True
    assert deferred_ms < 100.0
    assert inline_ms >= 200.0
    assert deferred_ms < inline_ms * 0.5


@pytest.mark.asyncio
async def test_worker_correction_before_eval(monkeypatch):
    from services import interview_eval_queue as q

    order: list[str] = []

    def fake_correct(text, **_kwargs):
        order.append("correct")
        return {
            "text": text + " [corrected]",
            "raw_text": text,
            "resume_corrected": True,
            "corrections": [],
            "correction_status": "complete",
        }

    class FakeEval:
        def model_dump(self, mode="json"):
            return {"score": 7.0, "verdict": "adequate", "model": "test"}

    def fake_eval(**kwargs):
        order.append("eval")
        assert "[corrected]" in kwargs["candidate_answer"]
        return FakeEval()

    monkeypatch.setattr(
        "agents.interview_agent.stt_corrector.apply_deferred_llm_correction",
        fake_correct,
    )
    monkeypatch.setattr(
        "agents.evaluation_agent.evaluator.evaluate_answer_with_llama",
        fake_eval,
    )

    async def noop_persist(*_a, **_k):
        return None

    monkeypatch.setattr(q, "_persist_correction", noop_persist)
    monkeypatch.setattr(q, "_persist_and_maybe_followup", noop_persist)
    monkeypatch.setattr(q, "clear_pending_stt_correction", lambda *_a, **_k: None)

    job = {
        "candidate_id": "c-test",
        "question": {"id": "q1", "question_text": "Explain FastAPI?", "skill_tags": ["FastAPI"]},
        "answer_text": "I used fast api",
        "context": {},
        "needs_llm_correction": True,
        "raw_transcript": "I used fast api",
        "correction_payload": {
            "visible_text": "I used fast api",
            "raw_transcript": "I used fast api",
            "resume_terms": ["FastAPI"],
            "context": {},
        },
        "retry_count": 0,
    }
    await q._run_one(job)
    assert order == ["correct", "eval"]


@pytest.mark.asyncio
async def test_worker_failure_retries_then_evaluates(monkeypatch):
    from services import interview_eval_queue as q

    calls = {"correct": 0, "eval": 0, "requeue": 0}

    def failing_correct(*_a, **_k):
        calls["correct"] += 1
        raise RuntimeError("LLM down")

    class FakeEval:
        def model_dump(self, mode="json"):
            return {"score": 5.0, "verdict": "adequate", "model": "test"}

    def fake_eval(**_k):
        calls["eval"] += 1
        return FakeEval()

    def fake_enqueue(job):
        calls["requeue"] += 1

    monkeypatch.setattr(
        "agents.interview_agent.stt_corrector.apply_deferred_llm_correction",
        failing_correct,
    )
    monkeypatch.setattr(
        "agents.evaluation_agent.evaluator.evaluate_answer_with_llama",
        fake_eval,
    )
    monkeypatch.setattr(q, "enqueue_eval_job", fake_enqueue)

    async def noop(*_a, **_k):
        return None

    monkeypatch.setattr(q, "_persist_correction", noop)
    monkeypatch.setattr(q, "_persist_and_maybe_followup", noop)
    monkeypatch.setattr(q, "clear_pending_stt_correction", lambda *_a, **_k: None)

    base = {
        "candidate_id": "c-fail",
        "question": {"id": "q9", "question_text": "Tech?", "skill_tags": []},
        "answer_text": "I used pytorch",
        "context": {},
        "needs_llm_correction": True,
        "correction_payload": {"visible_text": "I used pytorch", "raw_transcript": "I used pytorch"},
    }

    # First attempts requeue without evaluating.
    await q._run_one({**base, "retry_count": 0})
    assert calls["requeue"] == 1
    assert calls["eval"] == 0

    await q._run_one({**base, "retry_count": 1})
    assert calls["requeue"] == 2
    assert calls["eval"] == 0

    # Exhausted retries → evaluate visible transcript.
    await q._run_one({**base, "retry_count": 2})
    assert calls["eval"] == 1
