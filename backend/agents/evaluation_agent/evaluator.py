"""Agent 6 evaluator — Meta Llama scoring against resume, JD, and web context."""

from __future__ import annotations

import logging
import re
from typing import Any

from agents.evaluation_agent.schemas import EvaluationResult
from agents.evaluation_agent.web_research import fetch_web_context, format_web_context
from agents.shared.llama_client import call_llama_json, llama_available, llama_model_id
from core.chroma_store import format_evaluation_examples, retrieve_evaluation_examples

logger = logging.getLogger(__name__)

_FILLER_WORDS = {
    "sorry",
    "thanks",
    "thank",
    "you",
    "please",
    "okay",
    "ok",
    "yeah",
    "yes",
    "no",
    "uh",
    "um",
    "hmm",
    "like",
    "actually",
    "well",
    "so",
    "its",
    "it",
    "is",
    "this",
    "that",
    "question",
    "for",
    "the",
    "a",
    "an",
    "i",
    "am",
    "dont",
    "do",
    "not",
    "know",
    "have",
    "answer",
    "idea",
    "skip",
    "skipped",
    "pass",
    "words",
    "word",
    "hello",
    "hi",
    "right",
    "now",
    "just",
}

_REFUSAL_RE = re.compile(
    r"\b("
    r"i\s+don'?t\s+know|"
    r"i\s+do\s+not\s+know|"
    r"don'?t\s+know\s+(the\s+)?answer|"
    r"i\s+don'?t\s+have\s+(an\s+)?answer|"
    r"i\s+have\s+no\s+answer|"
    r"no\s+idea|"
    r"cannot\s+answer|"
    r"can'?t\s+answer|"
    r"skip(?:ped)?(?:\s+this)?|"
    r"no\s+answer|"
    r"not\s+sure|"
    r"i\s+don'?t\s+remember"
    r")\b",
    re.IGNORECASE,
)


def is_non_answer(text: str) -> bool:
    """True when the candidate declined or gave no substance (not a weak attempt)."""
    raw = " ".join(str(text or "").split()).strip()
    if not raw:
        return True
    lowered = raw.lower()
    if lowered in {"not answered", "[skipped by hr]", "skipped", "n/a", "na", "-"}:
        return True
    compact = re.sub(r"[^a-z0-9'\s]+", " ", lowered)
    compact = re.sub(r"\s+", " ", compact).strip()
    if _REFUSAL_RE.search(compact):
        remainder = _REFUSAL_RE.sub(" ", compact)
        leftover = [
            word
            for word in remainder.split()
            if word not in _FILLER_WORDS and len(word) > 1
        ]
        return len(leftover) <= 6
    tokens = compact.split()
    if len(tokens) <= 10:
        leftover = [word for word in tokens if word not in _FILLER_WORDS and len(word) > 1]
        return not leftover
    return False


def _non_answer_result() -> EvaluationResult:
    return EvaluationResult(
        score=0.0,
        verdict="insufficient",
        strengths=[],
        gaps=["Candidate did not answer the question."],
        resume_alignment="No answer to align with the resume.",
        jd_alignment="No answer to align with the job description.",
        web_insights=[],
        feedback_for_agent4=(
            "Candidate said they do not know or otherwise declined. "
            "Score 0. Move on; do not treat this as a partial answer."
        ),
        suggested_next_focus="next planned question",
        suggest_followup=False,
        followup_hints=[],
        model="heuristic",
        provider="fallback",
    )


def _truncate(text: str, limit: int = 3500) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _as_skill_list(value: Any, *, limit: int = 30) -> list[str]:
    """Normalize skills/requirements that may be list, dict, or scalar."""
    if value is None:
        return []
    if isinstance(value, dict):
        items = list(value.keys())
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]

    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("skill") or item.get("name") or item.get("skill_name") or ""
            text = str(name).strip()
        else:
            text = str(item).strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def build_candidate_context(
    *,
    jd_text: str | None,
    evaluation_snapshot: dict[str, Any] | None,
    job_position: str | None = None,
) -> dict[str, str]:
    """Flatten resume/JD signals from Agent 1 snapshot for evaluation prompts."""
    snap = evaluation_snapshot if isinstance(evaluation_snapshot, dict) else {}
    parsed = snap.get("parsed_resume") if isinstance(snap.get("parsed_resume"), dict) else {}
    skill_list = _as_skill_list(snap.get("skills") or parsed.get("skills") or [])

    experience = parsed.get("experience") or snap.get("experience") or []
    exp_bits: list[str] = []
    if isinstance(experience, list):
        for item in experience[:6]:
            if isinstance(item, dict):
                title = item.get("title") or item.get("role") or ""
                company = item.get("company") or ""
                summary = item.get("summary") or item.get("description") or ""
                exp_bits.append(f"{title} @ {company}: {summary}".strip(": "))
            else:
                exp_bits.append(str(item))

    resume_summary = str(
        parsed.get("summary")
        or snap.get("resume_summary")
        or snap.get("candidate_summary")
        or ""
    ).strip()

    jd_requirements = snap.get("extracted_jd_requirements") or snap.get("jd_requirements") or {}
    if isinstance(jd_requirements, dict):
        must = (
            jd_requirements.get("must_have_skills")
            or jd_requirements.get("required_skills")
            or jd_requirements.get("skills")
            or []
        )
        jd_req_text = ", ".join(_as_skill_list(must, limit=20))
    elif isinstance(jd_requirements, list):
        jd_req_text = ", ".join(_as_skill_list(jd_requirements, limit=20))
    else:
        jd_req_text = str(jd_requirements or "").strip()

    return {
        "job_position": (job_position or "").strip(),
        "resume_summary": _truncate(resume_summary, 1200),
        "skills": ", ".join(skill_list[:30]),
        "experience": _truncate("\n".join(exp_bits), 1800),
        "jd_text": _truncate(jd_text or "", 2500),
        "jd_requirements": _truncate(jd_req_text, 800),
        "resume_score": str(snap.get("overall_score") or snap.get("score") or ""),
    }


def evaluate_answer_with_llama(
    *,
    question_text: str,
    candidate_answer: str,
    context: dict[str, str],
    skill_tags: list[str] | None = None,
    use_web: bool = True,
    use_chroma: bool = True,
) -> EvaluationResult:
    """Score an answer with Meta Llama using resume, JD, and optional web research."""
    if is_non_answer(candidate_answer):
        return _non_answer_result()
    skills = [s for s in (skill_tags or []) if s]
    web_snippets: list[dict[str, str]] = []
    if use_web:
        query = " ".join(
            filter(
                None,
                [
                    context.get("job_position"),
                    " ".join(skills[:3]),
                    question_text[:120],
                    "best practices interview evaluation",
                ],
            )
        )
        web_snippets = fetch_web_context(query)

    chroma_hits = (
        retrieve_evaluation_examples(
            question_text=question_text,
            candidate_answer=candidate_answer,
            role=str(context.get("job_position") or ""),
            skills=skills,
            n_results=4,
        )
        if use_chroma
        else []
    )
    chroma_block = format_evaluation_examples(chroma_hits)
    chroma_labels = [
        str((hit.get("metadata") or {}).get("quality") or "example")
        for hit in chroma_hits[:4]
    ]

    if not llama_available():
        result = _heuristic_evaluation(
            question_text=question_text,
            candidate_answer=candidate_answer,
            skill_tags=skills,
            web_snippets=web_snippets,
        )
        return result.model_copy(update={"chroma_examples": chroma_labels})

    system = (
        "You are Agent 6, an expert technical interview evaluator. "
        "Score the candidate answer using the interview question, resume evidence, "
        "job description requirements, similar past answers (yardstick), "
        "and optional internet research snippets. "
        "If similar STRONG examples are close, require comparable concreteness. "
        "If similar WEAK examples are close, do not inflate the score. "
        "Scoring rules: "
        "an answer that is only 'I don't know', 'sorry I don't know', skip, "
        "no idea, or equivalent with no real content MUST score 0 and verdict "
        "insufficient — never give consolation points such as 20 or 35. "
        "Only score above 0 if the candidate actually attempted the question. "
        "Return JSON with keys: score (0-100), verdict "
        "(strong|adequate|weak|insufficient|off_topic), strengths (array), "
        "gaps (array), resume_alignment (string), jd_alignment (string), "
        "web_insights (array), feedback_for_agent4 (string — concrete guidance "
        "for the interviewer on what to ask next), suggested_next_focus (string), "
        "suggest_followup (boolean), followup_hints (array of short probes)."
    )
    user = f"""Question:
{question_text}

Candidate answer:
{candidate_answer}

Skill tags: {", ".join(skills) or "n/a"}

Job position: {context.get("job_position") or "n/a"}
Resume score (ATS): {context.get("resume_score") or "n/a"}
Resume summary:
{context.get("resume_summary") or "n/a"}

Resume skills:
{context.get("skills") or "n/a"}

Resume experience:
{context.get("experience") or "n/a"}

JD requirements:
{context.get("jd_requirements") or "n/a"}

JD text excerpt:
{context.get("jd_text") or "n/a"}

Internet research snippets:
{format_web_context(web_snippets)}

Similar past answers (scoring yardstick):
{chroma_block or "n/a"}
"""
    try:
        if is_non_answer(candidate_answer):
            return _non_answer_result()
        data = call_llama_json(system, user, temperature=0.2, max_tokens=1200)
        result = EvaluationResult.model_validate(
            {
                "score": float(data.get("score", 50)),
                "verdict": data.get("verdict") or "adequate",
                "strengths": list(data.get("strengths") or [])[:5],
                "gaps": list(data.get("gaps") or [])[:5],
                "resume_alignment": str(data.get("resume_alignment") or ""),
                "jd_alignment": str(data.get("jd_alignment") or ""),
                "web_insights": list(data.get("web_insights") or [])[:5]
                or [s.get("snippet", "")[:180] for s in web_snippets[:2]],
                "feedback_for_agent4": str(data.get("feedback_for_agent4") or ""),
                "suggested_next_focus": str(data.get("suggested_next_focus") or ""),
                "suggest_followup": bool(data.get("suggest_followup", False))
                and str(data.get("verdict") or "") in {"weak", "adequate"},
                "followup_hints": list(data.get("followup_hints") or [])[:4],
                "chroma_examples": chroma_labels,
                "model": llama_model_id(),
                "provider": "meta_llama_groq",
            }
        )
        return result
    except Exception:
        logger.exception("Agent 6 Meta Llama evaluation failed; using heuristic")
        result = _heuristic_evaluation(
            question_text=question_text,
            candidate_answer=candidate_answer,
            skill_tags=skills,
            web_snippets=web_snippets,
        )
        return result.model_copy(update={"chroma_examples": chroma_labels})


def _heuristic_evaluation(
    *,
    question_text: str,
    candidate_answer: str,
    skill_tags: list[str],
    web_snippets: list[dict[str, str]],
) -> EvaluationResult:
    answer = (candidate_answer or "").strip()
    if is_non_answer(answer):
        return _non_answer_result()
    words = len(answer.split())
    score = 15.0
    if words >= 40:
        score += 20
    if words >= 90:
        score += 15
    matched = [s for s in skill_tags if s.lower() in answer.lower()]
    score += min(20.0, 8.0 * len(matched))
    if any(w in answer.lower() for w in ("because", "for example", "i implemented", "result")):
        score += 10
    score = max(0.0, min(100.0, score))

    if score >= 75:
        verdict = "strong"
    elif score >= 55:
        verdict = "adequate"
    elif words < 12:
        verdict = "insufficient"
    else:
        verdict = "weak"

    gaps = []
    if not matched and skill_tags:
        gaps.append(f"Did not clearly evidence: {', '.join(skill_tags[:2])}")
    if words < 40:
        gaps.append("Answer lacks depth / concrete examples.")

    return EvaluationResult(
        score=score,
        verdict=verdict,  # type: ignore[arg-type]
        strengths=["Provided a relevant spoken/typed response."] if words else [],
        gaps=gaps,
        resume_alignment="Heuristic mode — configure GROQ_API_KEY for Meta Llama scoring.",
        jd_alignment="Heuristic alignment only.",
        web_insights=[s.get("snippet", "")[:180] for s in web_snippets[:2]],
        feedback_for_agent4=(
            f"Probe deeper on {', '.join(skill_tags[:2]) or 'practical examples'} "
            f"after the answer to: {question_text[:80]}"
        ),
        suggested_next_focus=skill_tags[0] if skill_tags else "concrete outcomes",
        suggest_followup=verdict == "weak" and words >= 40,
        followup_hints=[
            "Ask for metrics or outcome.",
            "Ask what they personally owned vs the team.",
        ],
        model="heuristic",
        provider="fallback",
    )
