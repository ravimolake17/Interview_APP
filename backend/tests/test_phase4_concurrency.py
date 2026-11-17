"""Phase 4: Azure concurrency gates, retry bounds, eval DLQ."""

from __future__ import annotations

import pytest


def test_azure_slot_rejects_when_exhausted(monkeypatch):
    from agents.shared import azure_concurrency as ac

    monkeypatch.setattr(ac, "_limit_for", lambda kind: 1)
    monkeypatch.setattr(ac, "_wait_seconds", lambda kind: 0.05)
    ac._semaphores.clear()
    ac._limits.clear()
    ac._stats.clear()

    with ac.azure_slot("llm"):
        with pytest.raises(ac.AzureCapacityError):
            with ac.azure_slot("llm"):
                pass

    snap = ac.azure_concurrency_snapshot()
    assert snap["llm"]["rejected"] >= 1
    assert snap["llm"]["in_flight"] == 0


def test_azure_retry_caps_attempts(monkeypatch):
    from agents.shared import azure_retry as ar

    monkeypatch.setattr(ar, "max_azure_retries", lambda: 2)
    monkeypatch.setattr(ar.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    class Boom(RuntimeError):
        status_code = 429
        headers = {"Retry-After": "0"}

    def flaky():
        calls["n"] += 1
        raise Boom("429 rate limit")

    with pytest.raises(Boom):
        ar.call_with_azure_retries("test", flaky, status_of=lambda e: getattr(e, "status_code", None))
    assert calls["n"] == 3  # 1 + 2 retries


def test_azure_retry_skips_non_retryable(monkeypatch):
    from agents.shared import azure_retry as ar

    monkeypatch.setattr(ar, "max_azure_retries", lambda: 3)
    monkeypatch.setattr(ar.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    class Boom(RuntimeError):
        status_code = 400

    def flaky():
        calls["n"] += 1
        raise Boom("bad request")

    with pytest.raises(Boom):
        ar.call_with_azure_retries("test", flaky, status_of=lambda e: getattr(e, "status_code", None))
    assert calls["n"] == 1


def test_parse_retry_after():
    from agents.shared.azure_retry import parse_retry_after_seconds

    assert parse_retry_after_seconds({"Retry-After": "2"}, attempt=0) == 2.0
    delay = parse_retry_after_seconds(None, attempt=0)
    assert 0.25 <= delay <= 30.0


@pytest.mark.asyncio
async def test_eval_worker_dead_letters_after_retries(monkeypatch):
    from services import interview_eval_queue as q

    dead: list[dict] = []
    requeues: list[dict] = []

    monkeypatch.setattr(q, "_max_job_retries", lambda: 1)
    monkeypatch.setattr(q, "_dead_letter", lambda job, reason: dead.append({**job, "reason": reason}))
    monkeypatch.setattr(q, "enqueue_eval_job", lambda job: requeues.append(dict(job)))

    async def fake_correct(job):
        return ("answer", "ok")

    monkeypatch.setattr(q, "_maybe_apply_deferred_correction", fake_correct)

    def boom(*_a, **_k):
        raise RuntimeError("azure down")

    import agents.evaluation_agent.evaluator as ev

    monkeypatch.setattr(ev, "evaluate_answer_with_llama", boom)

    job = {
        "candidate_id": "c1",
        "answer_text": "hello",
        "question": {"id": "q1", "question_text": "Q?", "skill_tags": []},
        "context": {},
        "job_retry_count": 0,
    }
    await q._run_one(job)
    assert len(requeues) == 1
    assert requeues[0]["job_retry_count"] == 1

    await q._run_one(requeues[0])
    assert len(dead) == 1
    assert "azure down" in dead[0]["reason"]


def test_eval_queue_stats_keys():
    from services.interview_eval_queue import eval_queue_stats

    stats = eval_queue_stats()
    assert "queue_depth" in stats
    assert "dlq_depth" in stats
    assert "inflight" in stats


def test_load_test_plan_matrix():
    # Keep in sync with scripts/load_test_interview_concurrency.py::plan_matrix
    ladder = [1, 5, 10, 25, 50]

    def plan_matrix(max_concurrent: int) -> list[int]:
        return [n for n in ladder if n <= max_concurrent]

    assert plan_matrix(5) == [1, 5]
    assert plan_matrix(50) == [1, 5, 10, 25, 50]
    assert plan_matrix(1) == [1]


def test_db_engine_uses_pool_settings():
    from core import database as db

    pool = db.engine.pool
    assert pool.size() >= 1
