from agents.screening_agent.schemas.ats import CandidateEvaluateRequest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

PARSED_RESUME = {
    "sections": [
        {
            "section_id": "contact_information",
            "heading": "Contact Information",
            "heading_source": "inferred",
            "order": 0,
            "content_type": "text",
            "items": [],
            "raw_text": "Asha Patil\nasha@example.com",
        },
        {
            "section_id": "skills",
            "heading": "Technical Skills",
            "heading_source": "original",
            "order": 1,
            "content_type": "list",
            "items": ["Python", "FastAPI", "Postgres"],
            "raw_text": "Python, FastAPI, Postgres",
        },
        {
            "section_id": "experience",
            "heading": "Experience",
            "heading_source": "original",
            "order": 2,
            "content_type": "text",
            "items": [],
            "raw_text": "Backend Developer\nJan 2023 - Present\nBuilt REST APIs.",
        },
    ],
    "extraction_method": "ai",
}


def test_health_and_root_routes():
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["ats"] == "enabled"


def test_complete_evaluation_endpoint():
    response = client.post(
        "/api/candidates/evaluate",
        json={
            "parsed_resume": PARSED_RESUME,
            "jd_text": "Job Title: Backend Developer\nRequired Skills: Python, FastAPI, PostgreSQL\nPreferred Skills: Docker\nMinimum 2 years experience",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate_details"]["name"] == "Asha Patil"
    assert "Python" in body["extracted_resume_skills"]["normalized_skills"]
    assert body["shortlist_status"] in {"Shortlisted", "Needs Review", "Rejected"}


def test_evaluate_request_send_invite_email_defaults_on():
    req = CandidateEvaluateRequest(
        parsed_resume=PARSED_RESUME,
        jd_text="Job Title: Backend Developer\nRequired Skills: Python, FastAPI",
    )
    assert req.send_invite_email is True
    skipped = CandidateEvaluateRequest(
        parsed_resume=PARSED_RESUME,
        jd_text="Job Title: Backend Developer\nRequired Skills: Python, FastAPI",
        send_invite_email=False,
    )
    assert skipped.send_invite_email is False


def test_evaluation_requires_exactly_one_jd_input():
    response = client.post(
        "/api/candidates/evaluate", json={"parsed_resume": PARSED_RESUME}
    )
    assert response.status_code == 422


def test_invalid_file_extension_is_rejected():
    response = client.post(
        "/extract", files={"file": ("resume.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 400


def test_frontend_is_served():
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "Resume Screening ATS" in response.text


def test_score_endpoint_ignores_inconsistent_client_match_analysis():
    response = client.post(
        "/api/candidates/score",
        json={
            "candidate_profile": {
                "skills": {"normalized_skills": ["Python"]},
                "education": [],
                "certifications": [],
                "keywords": [],
                "source_text": "Python",
            },
            "parsed_jd": {
                "required_skills": {"normalized": ["Python"]},
                "preferred_skills": {"normalized": []},
            },
            "match_analysis": {
                "matched_required_skills": [],
                "missing_required_skills": ["Python"],
                "required_match_ratio": 0,
                "preferred_match_ratio": 1,
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["required_skill_score"] == 45.0


def test_renamed_zip_is_rejected_as_docx():
    response = client.post(
        "/extract",
        files={
            "file": (
                "resume.docx",
                b"PK\x03\x04not-a-docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400


def test_frontend_renders_experience_fields():
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    assert "experienceRequirement" in response.text
    assert "countedExperience" in response.text


def test_evaluation_rejects_malformed_resume_schema():
    response = client.post(
        "/api/candidates/evaluate",
        json={
            "parsed_resume": {"sections": "not-a-list"},
            "jd_text": "Backend Developer\nRequired Skills: Python",
        },
    )

    assert response.status_code == 422
