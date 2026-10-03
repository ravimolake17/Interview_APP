from __future__ import annotations

from typing import Any

from agents.screening_agent.schemas.ats import EvaluationResponse, ParsedJD
from agents.screening_agent.schemas.resume import ParsedResume
from agents.screening_agent.services.jd_parser import parse_job_description
from agents.screening_agent.services.matching_service import analyze_skill_match
from agents.screening_agent.services.resume_profile_service import build_candidate_profile
from agents.screening_agent.services.scoring_service import score_candidate
from agents.screening_agent.utils.resume_content import prepare_resume_for_ats


def evaluate_candidate(
    parsed_resume: ParsedResume | dict[str, Any],
    *,
    jd_text: str | None = None,
    parsed_jd: ParsedJD | None = None,
    resume_original_filename: str | None = None,
) -> EvaluationResponse:
    """Evaluate a parsed resume against exactly one job description input."""
    validated_resume = (
        parsed_resume
        if isinstance(parsed_resume, ParsedResume)
        else ParsedResume.model_validate(parsed_resume)
    )

    if not validated_resume.sections:
        raise ValueError("Parsed resume contains no sections.")

    # The extraction response may contain both raw_text and structured items.
    # ATS processing uses one canonical representation to prevent duplicate
    # skill, keyword, certification, and experience counting.
    processing_resume = prepare_resume_for_ats(validated_resume)
    filename = resume_original_filename or str(
        processing_resume.get("resume_original_filename") or ""
    )
    candidate = build_candidate_profile(processing_resume, resume_filename=filename)

    if parsed_jd is not None:
        jd = parsed_jd
    else:
        jd = parse_job_description(jd_text or "")

    match = analyze_skill_match(
        candidate.skills,
        jd,
        experience_entries=candidate.experience_entries,
        keywords=candidate.keywords,
        resume_text=candidate.source_text,
    )
    score = score_candidate(candidate, jd, match)

    return EvaluationResponse(
        candidate_details=candidate.candidate_details,
        candidate_experience_years=candidate.total_experience_years,
        candidate_relevant_experience_years=(
            score.experience_assessment.candidate_relevant_experience_years
        ),
        candidate_education=candidate.education,
        candidate_certifications=candidate.certifications,
        extracted_resume_skills=candidate.skills,
        extracted_jd_requirements=jd,
        match_analysis=match,
        experience_assessment=score.experience_assessment,
        score_breakdown=score,
        final_recommendation=score.recommendation,
        shortlist_status=score.decision,
    )
