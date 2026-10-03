"""Build the Agent 7 HR recommendation from screening, interview, and Chroma cases."""

from __future__ import annotations

import logging
from typing import Any

from agents.recommendation_agent.recommender import recommend_from_similar_cases
from agents.recommendation_agent.schemas import HrRecommendationReport, SimilarPastCase
from agents.shared.llama_client import call_llama_json, llama_available, llama_model_id

logger = logging.getLogger(__name__)

VALID_DECISIONS = {"HIRE", "CONSIDER", "REJECT", "HOLD"}


def decision_from_scores(
    *,
    screening_score: float,
    interview_score: float | None,
    integrity_risk: float,
    interview_turns: int,
    interview_attempted: bool = False,
    incomplete: bool = False,
) -> str:
    """Deterministic hire/consider/reject/hold from the three score signals.

    Interview score must already be computed against the full planned question
    set (unanswered = 0). Screening-only evidence never yields HIRE/CONSIDER.
    """
    if integrity_risk >= 70:
        return "REJECT"
    if not interview_attempted:
        return "HOLD"

    interview = float(interview_score or 0)
    blended = 0.35 * screening_score + 0.55 * interview + 0.10 * max(0.0, 100.0 - integrity_risk)
    if integrity_risk >= 45 and blended < 80:
        return "CONSIDER" if blended >= 60 else "REJECT"
    if blended >= 78 and interview >= 70 and not incomplete:
        return "HIRE"
    if blended >= 78 and interview >= 70 and incomplete:
        return "CONSIDER"
    if blended >= 58:
        return "CONSIDER"
    return "REJECT"


def _as_skill_list(value: Any, *, limit: int = 20) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = list(value.keys())
    else:
        return []
    out: list[str] = []
    for item in items:
        text = str(item.get("skill") if isinstance(item, dict) else item).strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def gather_evidence(
    *,
    candidate: Any,
    evaluations: list[dict[str, Any]],
    interview_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snap = candidate.evaluation_snapshot if isinstance(candidate.evaluation_snapshot, dict) else {}
    parsed = snap.get("parsed_resume") if isinstance(snap.get("parsed_resume"), dict) else {}
    extracted = snap.get("extracted_resume_skills") if isinstance(snap.get("extracted_resume_skills"), dict) else {}
    skills = _as_skill_list(
        snap.get("skills")
        or extracted.get("normalized_skills")
        or parsed.get("skills")
        or []
    )
    breakdown = snap.get("score_breakdown") if isinstance(snap.get("score_breakdown"), dict) else {}
    strengths = list(breakdown.get("strengths") or [])[:5]
    concerns = list(breakdown.get("concerns") or [])[:5]
    agent5 = snap.get("agent5") if isinstance(snap.get("agent5"), dict) else {}
    runtime = snap.get("interview_runtime") if isinstance(snap.get("interview_runtime"), dict) else {}
    risk = agent5.get("risk") if isinstance(agent5.get("risk"), dict) else {}
    integrity_risk = float(risk.get("score") or agent5.get("risk_score") or runtime.get("risk_score") or 0)

    scores = [float(row.get("score") or 0) for row in evaluations if row.get("score") is not None]
    report = interview_report if isinstance(interview_report, dict) else {}
    interview_score = report.get("interview_score")
    if interview_score is None:
        interview_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    else:
        interview_score = float(interview_score)
    screening_score = float(candidate.resume_score or snap.get("overall_score") or 0)
    verdicts = [str(row.get("verdict") or "") for row in evaluations]
    gaps: list[str] = []
    for row in evaluations:
        payload = row.get("evaluation") if isinstance(row.get("evaluation"), dict) else {}
        gaps.extend(str(g) for g in (payload.get("gaps") or [])[:2])

    interview_attempted = bool(report.get("interview_attempted")) or bool(scores)
    incomplete = bool(report.get("incomplete"))
    left_early = bool(report.get("left_early"))
    questions_total = int(report.get("questions_total") or len(evaluations) or 0)
    questions_answered = int(report.get("questions_answered") or len(scores) or 0)
    stage = "final" if interview_attempted and not incomplete else "preliminary"
    return {
        "candidate_id": candidate.candidate_id,
        "full_name": candidate.full_name,
        "role": candidate.job_position or "",
        "status": str(getattr(candidate.status, "value", candidate.status) or ""),
        "skills": skills,
        "screening_score": round(screening_score, 1),
        "interview_score": interview_score,
        "interview_turns": questions_answered,
        "questions_total": questions_total,
        "questions_answered": questions_answered,
        "interview_attempted": interview_attempted,
        "incomplete": incomplete,
        "left_early": left_early,
        "scoring_note": str(report.get("scoring_note") or ""),
        "verdicts": verdicts,
        "screening_strengths": [str(s) for s in strengths],
        "screening_concerns": [str(c) for c in concerns],
        "interview_gaps": gaps[:6],
        "integrity_risk": max(0.0, min(100.0, integrity_risk)),
        "integrity_notes": str(
            risk.get("classification")
            or agent5.get("termination_reason")
            or runtime.get("termination_reason")
            or ""
        ),
        "resume_summary": str(parsed.get("summary") or snap.get("resume_summary") or "")[:800],
        "screening_recommendation": str(snap.get("final_recommendation") or ""),
        "stage": stage,
    }


def build_recommendation_report(evidence: dict[str, Any]) -> HrRecommendationReport:
    """LLM recommendation grounded in similar Chroma cases, with a score fallback."""
    similar = recommend_from_similar_cases(
        candidate_id=str(evidence.get("candidate_id") or ""),
        role=str(evidence.get("role") or ""),
        skills=list(evidence.get("skills") or []),
        summary=str(evidence.get("resume_summary") or evidence.get("screening_recommendation") or ""),
        score=float(evidence.get("interview_score") or evidence.get("screening_score") or 0),
        status=str(evidence.get("status") or ""),
    )
    cases = [SimilarPastCase.model_validate(item) for item in similar.get("similar_past_cases") or []]
    heuristic_decision = decision_from_scores(
        screening_score=float(evidence.get("screening_score") or 0),
        interview_score=float(evidence.get("interview_score") or 0),
        integrity_risk=float(evidence.get("integrity_risk") or 0),
        interview_turns=int(evidence.get("interview_turns") or 0),
        interview_attempted=bool(evidence.get("interview_attempted")),
        incomplete=bool(evidence.get("incomplete")),
    )
    overall = _overall_score(evidence)

    if llama_available():
        try:
            return _llm_report(
                evidence,
                similar_note=str(similar.get("chroma_recommendation") or ""),
                cases=cases,
                fallback_decision=heuristic_decision,
                overall=overall,
            )
        except Exception:
            logger.exception("Agent 7 LLM recommendation failed; using heuristic")

    return _heuristic_report(
        evidence,
        decision=heuristic_decision,
        overall=overall,
        similar_note=str(similar.get("chroma_recommendation") or ""),
        cases=cases,
    )


def _overall_score(evidence: dict[str, Any]) -> float:
    screening = float(evidence.get("screening_score") or 0)
    interview = float(evidence.get("interview_score") or 0)
    risk = float(evidence.get("integrity_risk") or 0)
    if not evidence.get("interview_attempted"):
        blended = 0.85 * screening + 0.15 * max(0.0, 100.0 - risk)
    else:
        blended = 0.35 * screening + 0.55 * interview + 0.10 * max(0.0, 100.0 - risk)
    return round(max(0.0, min(100.0, blended)), 1)


def _llm_report(
    evidence: dict[str, Any],
    *,
    similar_note: str,
    cases: list[SimilarPastCase],
    fallback_decision: str,
    overall: float,
) -> HrRecommendationReport:
    system = (
        "You are Agent 7, the final HR recommendation agent. "
        "Write a concise hiring recommendation for a human recruiter. "
        "Ground the decision in screening score, live interview scores, integrity risk, "
        "and similar past cases. Do not invent facts. "
        "Interview score is already averaged across ALL planned questions; unanswered count as 0. "
        "If the interview was incomplete or the candidate left early, do not choose HIRE. "
        "If the interview was never attempted, choose HOLD. "
        "Return JSON with keys: decision (HIRE|CONSIDER|REJECT|HOLD), "
        "executive_summary, strengths (array), risks (array), rationale, "
        "next_steps (array), integrity_notes."
    )
    case_lines = "\n".join(
        f"- {c.decision or 'n/a'} score {c.score}: {(c.excerpt or '')[:180]}"
        for c in cases[:5]
    ) or "n/a"
    user = f"""Candidate: {evidence.get("full_name")} ({evidence.get("candidate_id")})
Role: {evidence.get("role") or "n/a"}
Stage: {evidence.get("stage")}
Screening score: {evidence.get("screening_score")}
Interview average: {evidence.get("interview_score")} from {evidence.get("questions_answered")} of {evidence.get("questions_total")} planned questions
Incomplete: {evidence.get("incomplete")}
Left early: {evidence.get("left_early")}
Scoring: {evidence.get("scoring_note") or "n/a"}
Integrity risk: {evidence.get("integrity_risk")}
Skills: {", ".join(evidence.get("skills") or []) or "n/a"}
Resume summary: {evidence.get("resume_summary") or "n/a"}
Screening strengths: {evidence.get("screening_strengths")}
Screening concerns: {evidence.get("screening_concerns")}
Interview gaps: {evidence.get("interview_gaps")}
Interview verdicts: {evidence.get("verdicts")}
Suggested baseline decision: {fallback_decision}
Chroma similar-case note: {similar_note or "n/a"}
Similar past cases:
{case_lines}
"""
    data = call_llama_json(system, user, temperature=0.2, max_tokens=1200)
    decision = str(data.get("decision") or fallback_decision).upper()
    if decision not in VALID_DECISIONS:
        decision = fallback_decision
    if not evidence.get("interview_attempted"):
        decision = "HOLD"
    elif evidence.get("incomplete") and decision == "HIRE":
        decision = "CONSIDER"
    return HrRecommendationReport(
        decision=decision,  # type: ignore[arg-type]
        overall_score=overall,
        screening_score=float(evidence.get("screening_score") or 0),
        interview_score=float(evidence.get("interview_score") or 0),
        integrity_risk=float(evidence.get("integrity_risk") or 0),
        interview_attempted=bool(evidence.get("interview_attempted")),
        incomplete=bool(evidence.get("incomplete")),
        left_early=bool(evidence.get("left_early")),
        questions_total=int(evidence.get("questions_total") or 0),
        questions_answered=int(evidence.get("questions_answered") or 0),
        stage="final" if evidence.get("interview_attempted") and not evidence.get("incomplete") else "preliminary",
        executive_summary=str(data.get("executive_summary") or "")[:1200],
        strengths=list(data.get("strengths") or [])[:5],
        risks=list(data.get("risks") or [])[:5],
        rationale=str(data.get("rationale") or "")[:1500],
        next_steps=list(data.get("next_steps") or [])[:5],
        integrity_notes=str(data.get("integrity_notes") or evidence.get("integrity_notes") or "")[:500],
        chroma_recommendation=similar_note or None,
        similar_past_cases=cases,
        model=llama_model_id(),
        provider="meta_llama_groq",
    )


def _heuristic_report(
    evidence: dict[str, Any],
    *,
    decision: str,
    overall: float,
    similar_note: str,
    cases: list[SimilarPastCase],
) -> HrRecommendationReport:
    name = evidence.get("full_name") or "This candidate"
    role = evidence.get("role") or "the role"
    attempted = bool(evidence.get("interview_attempted"))
    incomplete = bool(evidence.get("incomplete"))
    left_early = bool(evidence.get("left_early"))
    answered = int(evidence.get("questions_answered") or 0)
    total = int(evidence.get("questions_total") or 0)
    if not attempted:
        summary = (
            f"{name} scored {evidence.get('screening_score')} on screening for {role}. "
            "The HR report is on hold because Agent 6 has not scored any interview answers yet."
        )
        next_steps = ["Wait for the live interview (MCQ + oral) before making a hiring decision."]
    else:
        coverage = f"{answered} of {total} planned questions" if total else f"{answered} answers"
        left_note = " The candidate left the interview before finishing." if left_early else ""
        incomplete_note = " Unanswered questions were scored as 0." if incomplete else ""
        summary = (
            f"{name} scored {evidence.get('screening_score')} at screening and "
            f"{evidence.get('interview_score')} on the interview ({coverage}) for {role}."
            f"{left_note}{incomplete_note} Recommended decision: {decision}."
        )
        next_steps = {
            "HIRE": ["Move to offer discussion and confirm notice period."],
            "CONSIDER": ["Schedule a focused human follow-up on the listed risks."],
            "REJECT": ["Close the loop with a polite rejection and archive the profile."],
            "HOLD": ["Wait for remaining interview evidence before deciding."],
        }.get(decision, ["Review the report with the hiring manager."])

    strengths = list(evidence.get("screening_strengths") or [])[:4]
    risks = list(evidence.get("screening_concerns") or [])[:3]
    risks.extend(list(evidence.get("interview_gaps") or [])[:3])
    if float(evidence.get("integrity_risk") or 0) >= 45:
        risks.insert(0, f"Integrity risk score {evidence.get('integrity_risk')}.")

    return HrRecommendationReport(
        decision=decision,  # type: ignore[arg-type]
        overall_score=overall,
        screening_score=float(evidence.get("screening_score") or 0),
        interview_score=float(evidence.get("interview_score") or 0),
        integrity_risk=float(evidence.get("integrity_risk") or 0),
        interview_attempted=attempted,
        incomplete=incomplete,
        left_early=left_early,
        questions_total=total,
        questions_answered=answered,
        stage="final" if attempted and not incomplete else "preliminary",
        executive_summary=summary,
        strengths=strengths or ["Screening completed."],
        risks=risks[:5],
        rationale=(
            f"Blended score {overall}. Screening {evidence.get('screening_score')}, "
            f"interview {evidence.get('interview_score')}, integrity risk "
            f"{evidence.get('integrity_risk')}. {similar_note or ''}"
        ).strip(),
        next_steps=next_steps,
        integrity_notes=str(evidence.get("integrity_notes") or ""),
        chroma_recommendation=similar_note or None,
        similar_past_cases=cases,
        model="heuristic",
        provider="fallback",
    )
