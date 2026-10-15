"""End-of-interview candidate Q&A with a guarded AI reply."""

from __future__ import annotations

import logging
import re
from typing import Any

from agents.shared.llama_client import call_llama_json, llama_available

logger = logging.getLogger(__name__)

MAX_QNA_TURNS = 5

QNA_OPENING = (
    "Those were my interview questions. You now have time to share any feedback "
    "or ask about the role or next steps. If you have no questions, just say you are done."
)

CLOSING_THANK_YOU = (
    "Thank you for your time today. We appreciate your questions and feedback. "
    "Our team will follow up with next steps. Wishing you all the best."
)

_DECLINE_REPLY = (
    "I can't discuss that topic in this interview. "
    "If you have a question about the role or the hiring process, I'm happy to help."
)

_UNKNOWN_REPLY = (
    "I don't have that information to share in this interview. "
    "HR can follow up with those details after we wrap up. "
    "If you have a question about the role or next steps, I'm happy to help."
)

_HARD_UNKNOWN = re.compile(
    r"\b("
    r"salary|ctc|compensation|pay scale|bond|notice period|"
    r"office address|seating|shift (?:timing|roster)|named employees|"
    r"manager(?:'s)? name|who (?:is|are) (?:the )?(?:manager|lead|boss|head)|"
    r"team size|how many (?:people|members|engineers|employees)|headcount|"
    r"org chart|reporting line|reporting structure|who (?:do|would) i report"
    r")\b",
    re.IGNORECASE,
)

_CLOSING_PATTERNS = re.compile(
    r"\b(no questions?|nothing else|that's all|thats all|i'm done|im done|"
    r"no thanks|nothing to ask|i'm good|im good|all good|no more|"
    r"that is all|i have none|don't have any|do not have any)\b",
    re.IGNORECASE,
)

_CONTROVERSIAL_PATTERNS = re.compile(
    r"\b(politic|election|religion|caste|racist|racism|sexist|sexual|"
    r"porn|nude|kill|murder|bomb|terror|hack(?:ing)?|password|drug|"
    r"bribe|illegal|how to cheat|exam leak|discriminat)\b",
    re.IGNORECASE,
)

_UNKNOWN_INTERNAL_PATTERNS = re.compile(
    r"\b("
    r"team structure|org(?:ani[sz]ation)? structure|reporting line|reporting structure|"
    r"who (?:do|would) i report|who (?:is|are) (?:the )?(?:manager|lead|boss|head)|"
    r"manager(?:'s)? name|team size|how many (?:people|members|engineers|employees)|"
    r"headcount|org chart|hierarchy|who (?:works|is) (?:on|in) (?:the )?team|"
    r"about the team|how (?:is|are) the team|team (?:setup|set up|organized|organised)|"
    r"who (?:will|would) i work with|who are (?:my|the) teammates|"
    r"salary|ctc|compensation|pay scale|bond|notice period|"
    r"office address|seating|shift (?:timing|roster)|named employees"
    r")\b",
    re.IGNORECASE,
)

_QNA_SYSTEM = """You are an AI interviewer wrapping up a job interview.
The candidate may share feedback or ask questions.

Return JSON only:
{
  "closing": boolean,
  "allowed": boolean,
  "reply": "2 to 4 spoken sentences, professional and warm"
}

Set closing=true when the candidate is finished, has no questions, or only says thank you.

REFERENCE TEXTS below are the source of truth for company, department, and role answers.
When the candidate asks about the company, department, role, or responsibilities,
answer using those texts. Paraphrase naturally; do not invent facts beyond them.

Still unknown (do not guess): salaries, CTC, named managers, exact headcount,
reporting lines, office seating, shifts, or unannounced plans — say HR can follow up.

Safe topics: role responsibilities (from reference), department overview (from reference),
company intro (from reference), the interview process, and that HR shares next steps.

DECLINE (allowed=false): politics, religion, caste, race, gender attacks, adult content,
illegal activity, hacking, confidential internals, medical/legal advice, or cheating.

If declining, politely refuse and offer to talk about the role or next steps instead.
"""


def build_qna_opening(*, role_summary: str = "") -> str:
    """End-of-questions opener; includes role overview when available."""
    summary = (role_summary or "").strip()
    if summary:
        return (
            f"Those were my interview questions. As promised, here is a brief overview of the role: "
            f"{summary} "
            "You now have time to share feedback or ask about the role, the department, "
            "the company, or next steps. If you have no questions, just say you are done."
        )
    return QNA_OPENING


def is_closing_utterance(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return True
    if len(cleaned.split()) <= 12 and _CLOSING_PATTERNS.search(cleaned):
        return True
    return False


def looks_controversial(text: str) -> bool:
    return bool(_CONTROVERSIAL_PATTERNS.search(text or ""))


def looks_unknown_internal(text: str) -> bool:
    return bool(_UNKNOWN_INTERNAL_PATTERNS.search(text or ""))


def qna_prompt_question(text: str, *, turn: int = 0, closing: bool = False) -> dict[str, Any]:
    kind = "close" if closing else ("reply" if turn else "open")
    return {
        "id": f"qna-{kind}-{turn}",
        "order": 0,
        "category_id": "candidate_qna",
        "category_name": "Your questions",
        "difficulty": "easy",
        "question_text": text,
        "intent": "Candidate feedback and questions at the end of the interview",
        "skill_tags": [],
        "is_candidate_qna": True,
        "is_closing": closing,
        "is_followup": False,
    }


def _reference_block(
    *,
    role_summary: str,
    department_name: str,
    department_brief: str,
    company_intro: str,
) -> str:
    parts = [
        f"Role overview: {role_summary or '(none provided)'}",
        f"Department ({department_name or 'n/a'}): {department_brief or '(none provided)'}",
        f"Company intro: {company_intro or '(none provided)'}",
    ]
    return "\n".join(parts)


def _fallback_from_briefs(
    text: str,
    *,
    role_summary: str,
    department_brief: str,
    company_intro: str,
) -> str | None:
    lowered = text.lower()
    if any(k in lowered for k in ("role", "responsibilit", "jd", "job description", "day to day", "day-to-day")) and role_summary:
        return role_summary
    if any(k in lowered for k in ("department", "team", "org")) and department_brief:
        return department_brief
    if any(k in lowered for k in ("company", "about us", "organisation", "organization")) and company_intro:
        return company_intro
    return None


def generate_candidate_qna_reply(
    candidate_text: str,
    *,
    job_position: str = "",
    turn: int = 1,
    role_summary: str = "",
    department_brief: str = "",
    department_name: str = "",
    company_intro: str = "",
) -> dict[str, Any]:
    """Classify the candidate utterance and return a spoken reply."""
    text = (candidate_text or "").strip()
    if is_closing_utterance(text) or turn >= MAX_QNA_TURNS:
        return {"closing": True, "allowed": True, "reply": CLOSING_THANK_YOU}

    if looks_controversial(text):
        return {"closing": False, "allowed": False, "reply": _DECLINE_REPLY}

    if _HARD_UNKNOWN.search(text):
        return {"closing": False, "allowed": True, "reply": _UNKNOWN_REPLY}

    refs = _reference_block(
        role_summary=role_summary,
        department_name=department_name,
        department_brief=department_brief,
        company_intro=company_intro,
    )

    if llama_available():
        try:
            data = call_llama_json(
                _QNA_SYSTEM,
                (
                    f"Job position: {job_position or 'the open role'}\n"
                    f"Q&A turn: {turn} of {MAX_QNA_TURNS}\n"
                    f"REFERENCE TEXTS:\n{refs}\n\n"
                    f"Candidate said: {text}"
                ),
                temperature=0.3,
                max_tokens=400,
            )
            closing = bool(data.get("closing"))
            allowed = bool(data.get("allowed", True))
            reply = str(data.get("reply") or "").strip()
            if not allowed:
                reply = reply or _DECLINE_REPLY
            if closing:
                reply = reply or CLOSING_THANK_YOU
            if not reply:
                reply = (
                    "Thank you. If you have another question about the role or next steps, "
                    "please go ahead. Otherwise, say you are done."
                )
            if _HARD_UNKNOWN.search(text):
                reply = _UNKNOWN_REPLY
            return {"closing": closing, "allowed": allowed, "reply": reply}
        except Exception:
            logger.exception("Candidate Q&A LLM reply failed; using fallback.")

    brief_reply = _fallback_from_briefs(
        text,
        role_summary=role_summary,
        department_brief=department_brief,
        company_intro=company_intro,
    )
    if brief_reply:
        return {"closing": False, "allowed": True, "reply": brief_reply}

    return {
        "closing": False,
        "allowed": True,
        "reply": (
            "Thank you for sharing that. I can talk about the role or what happens "
            "after this interview. What would you like to know?"
        ),
    }
