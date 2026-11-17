"""Focused tests for local join/MCQ timeout fixes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_ensure_mcq_runs_generation_off_event_loop(monkeypatch):
    from services import interview_mcq_service as svc

    calls = {"thread": 0}

    async def fake_to_thread(fn, /, *args, **kwargs):
        # Prove we go through to_thread rather than calling sync LLM on the loop.
        assert callable(fn)
        calls["thread"] += 1
        return fn(*args, **kwargs)

    def fake_generate(**_kwargs):
        return [
            {
                "id": "q1",
                "question_text": "Q?",
                "options": [
                    {"id": "A", "text": "a"},
                    {"id": "B", "text": "b"},
                    {"id": "C", "text": "c"},
                    {"id": "D", "text": "d"},
                ],
                "correct_option_id": "A",
            }
        ]

    monkeypatch.setattr(svc, "generate_mcq_questions", fake_generate)
    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(svc, "_planned_minutes", AsyncMock(return_value=30))
    monkeypatch.setattr(svc, "_company_name", AsyncMock(return_value="RR"))
    monkeypatch.setattr(svc, "_company_intro_spoken", AsyncMock(return_value="Welcome"))
    monkeypatch.setattr(svc, "build_candidate_context", lambda **_k: {})
    monkeypatch.setattr(svc, "primary_interviewer_name", lambda: "Alex")
    monkeypatch.setattr(svc, "_record", lambda _c: None)
    saved = {}

    async def fake_save(_db, _c, record):
        saved.update(record)
        return record

    monkeypatch.setattr(svc, "_save", fake_save)

    candidate = SimpleNamespace(
        candidate_id="CAND-TEST",
        full_name="Test User",
        job_position="Engineer",
        jd_text="",
        evaluation_snapshot={},
    )
    record = await svc.ensure_mcq(MagicMock(), candidate, planned_minutes=30)
    assert record["status"] == "pending"
    assert len(record["questions"]) >= 1
    assert calls["thread"] == 1


@pytest.mark.asyncio
async def test_start_mcq_is_idempotent(monkeypatch):
    from services import interview_mcq_service as svc

    existing = {
        "status": "in_progress",
        "started_at": "2026-11-13T10:00:00+00:00",
        "current_index": 2,
        "questions": [{"id": "q1"}],
        "duration_seconds": 600,
    }
    monkeypatch.setattr(svc, "ensure_mcq", AsyncMock(return_value=dict(existing)))
    monkeypatch.setattr(svc, "_expire_if_needed", lambda r: r)

    saved = {}

    async def fake_save(_db, _c, record):
        saved.update(record)
        return record

    monkeypatch.setattr(svc, "_save", fake_save)
    out = await svc.start_mcq(MagicMock(), SimpleNamespace(candidate_id="CAND-X"))
    assert out["status"] == "in_progress"
    assert out["current_index"] == 2
    assert out["started_at"] == existing["started_at"]


@pytest.mark.asyncio
async def test_start_mcq_flips_pending_to_in_progress(monkeypatch):
    from services import interview_mcq_service as svc

    pending = {
        "status": "pending",
        "started_at": None,
        "current_index": 0,
        "questions": [{"id": "q1"}],
        "duration_seconds": 600,
    }
    monkeypatch.setattr(svc, "ensure_mcq", AsyncMock(return_value=dict(pending)))
    monkeypatch.setattr(svc, "_expire_if_needed", lambda r: r)

    async def fake_save(_db, _c, record):
        return record

    monkeypatch.setattr(svc, "_save", fake_save)
    out = await svc.start_mcq(MagicMock(), SimpleNamespace(candidate_id="CAND-Y"))
    assert out["status"] == "in_progress"
    assert out["started_at"]


def test_mcq_panel_locked_only_when_not_in_progress():
    # Mirror McqPanel lock rule used by the UI.
    def locked(status: str, busy: bool = False, locked_option: str | None = None, is_hr: bool = False) -> bool:
        return bool(locked_option) or busy or is_hr or status != "in_progress"

    assert locked("pending") is True
    assert locked("in_progress") is False
    assert locked("in_progress", busy=True) is True
