"""Agent 7 — HR recommendation grounded in similar past cases from Chroma."""

from __future__ import annotations

from collections import Counter
from typing import Any

from core.chroma_store import retrieve_hr_outcomes, summarize_similar_hits


def _profile_query(
    *,
    role: str,
    skills: list[str] | None,
    summary: str,
    score: float,
    status: str,
) -> str:
    skill_text = ", ".join((skills or [])[:20])
    return (
        f"Role {role or 'open'}. Status {status}. Score {score:.0f}. "
        f"Skills: {skill_text or 'n/a'}. {summary[:800]}"
    )


def recommend_from_similar_cases(
    *,
    candidate_id: str,
    role: str,
    skills: list[str] | None = None,
    summary: str = "",
    score: float = 0.0,
    status: str = "",
) -> dict[str, Any]:
    """Return similar past HR outcomes and a short recommendation sentence."""
    hits = retrieve_hr_outcomes(
        query_text=_profile_query(
            role=role,
            skills=skills,
            summary=summary,
            score=score,
            status=status,
        ),
        role=role,
        n_results=6,
    )
    cases = summarize_similar_hits(hits, exclude_id=candidate_id)
    if not cases:
        return {
            "chroma_recommendation": None,
            "similar_past_cases": [],
        }

    decisions = [
        str(case.get("decision") or "").strip()
        for case in cases
        if case.get("decision")
    ]
    if not decisions:
        return {
            "chroma_recommendation": None,
            "similar_past_cases": cases,
        }

    top, count = Counter(decisions).most_common(1)[0]
    total = len(decisions)
    chroma_recommendation = (
        f"Similar to {total} past case(s) for this kind of role. "
        f"Most common outcome was {top} ({count}/{total}). "
        "Use this as context, not as an automatic decision."
    )
    return {
        "chroma_recommendation": chroma_recommendation,
        "similar_past_cases": cases,
    }
