"""Re-screen should preserve interview history for same JD and reset for different JD."""

from __future__ import annotations

from models.candidate import Candidate
from services.screening_integration_service import (
    merge_evaluation_snapshot,
    same_job_description,
)


def _candidate(**kwargs) -> Candidate:
    return Candidate(
        candidate_id=kwargs.get("candidate_id", "CAND-TEST"),
        full_name=kwargs.get("full_name", "Test User"),
        email=kwargs.get("email", "test@example.com"),
        resume_score=kwargs.get("resume_score", 80.0),
        job_position=kwargs.get("job_position", "Engineer"),
        status=kwargs.get("status", "INTERVIEW_SCHEDULED"),
        jd_text=kwargs.get("jd_text"),
        jd_file_url=kwargs.get("jd_file_url"),
        jd_original_filename=kwargs.get("jd_original_filename"),
    )


def test_same_job_description_by_file_url():
    existing = _candidate(jd_file_url="/uploads/jds/python-dev.pdf")
    assert same_job_description(
        existing,
        resolved_jd="Different extracted text should not matter",
        jd_file_url="/uploads/jds/python-dev.pdf",
    )


def test_same_job_description_by_normalized_text():
    existing = _candidate(jd_text="Python Developer\nRequired: FastAPI")
    assert same_job_description(
        existing,
        resolved_jd="  python developer\nrequired: fastapi  ",
    )


def test_different_job_description_for_same_email():
    existing = _candidate(jd_text="Python Developer role")
    assert not same_job_description(
        existing,
        resolved_jd="Java Developer role with Spring Boot",
    )


def test_same_job_description_ignores_new_upload_url_when_text_matches():
    existing = _candidate(
        jd_text="Python Developer\nRequired: FastAPI",
        jd_file_url="/uploads/jds/uuid-old.pdf",
    )
    assert same_job_description(
        existing,
        resolved_jd="Python Developer\nRequired: FastAPI",
        jd_file_url="/uploads/jds/uuid-new.pdf",
    )


def test_different_jd_text_not_same_even_if_filename_matches():
    existing = _candidate(
        jd_text="Python Developer role",
        jd_original_filename="JD.pdf",
    )
    assert not same_job_description(
        existing,
        resolved_jd="Java Developer role with Spring Boot",
        jd_original_filename="JD.pdf",
    )


def test_merge_evaluation_snapshot_preserves_agent5():
    old = {
        "agent5": {"session_id": "sess-123", "join_link": "/interview/abc"},
        "score_breakdown": {"overall_score": 70},
    }
    new = {
        "score_breakdown": {"overall_score": 93},
        "shortlist_status": "Shortlisted",
    }
    merged = merge_evaluation_snapshot(new, old, preserve_interview_history=True)
    assert merged["agent5"]["session_id"] == "sess-123"
    assert merged["score_breakdown"]["overall_score"] == 93


def test_merge_evaluation_snapshot_skips_history_for_fresh_candidate():
    old = {"agent5": {"session_id": "sess-123"}}
    new = {"score_breakdown": {"overall_score": 93}}
    merged = merge_evaluation_snapshot(new, old, preserve_interview_history=False)
    assert "agent5" not in merged
