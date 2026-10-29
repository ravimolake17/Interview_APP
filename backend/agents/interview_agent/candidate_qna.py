"""End-of-interview candidate Q&A with a guarded AI reply."""

from __future__ import annotations

import logging
import re
from typing import Any

from agents.shared.llama_client import call_llama_json, llama_available

logger = logging.getLogger(__name__)

# Keep the wrap-up short — each turn can cost an LLM call.
MAX_QNA_TURNS = 2

QNA_OPENING = (
    "Those were my interview questions. You may ask one brief question about the role "
    "or next steps, or say you are done."
)

CLOSING_THANK_YOU = (
    "Thank you for your time today. Our team will follow up with next steps. "
    "Wishing you all the best."
)

_WRAP_UP_REPLY = (
    "Thanks for your questions. That wraps up our time today. "
    "HR will share next steps. Take care."
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

_QNA_SYSTEM = """You are an AI interviewer wrapping up a job interview briefly.
Keep replies to 1–2 short spoken sentences. Do not chat or invite more questions.

Return JSON only:
{
  "closing": boolean,
  "allowed": boolean,
  "reply": "1 to 2 spoken sentences"
}

Set closing=true when the candidate is finished, says thank you, repeats a prior question,
asks something off-topic, or this is the last allowed turn.

REFERENCE TEXTS are the only source of truth. Paraphrase; do not invent facts.

Still unknown (do not guess): salaries, CTC, named managers, exact headcount,
reporting lines, office seating, shifts — say HR can follow up, then close.

Safe topics only: role (from reference), department (from reference), company intro
(from reference), and that HR shares next steps.

DECLINE (allowed=false): politics, religion, caste, race, adult content, illegal topics,
hacking, confidential internals, or cheating. Decline briefly and close.
"""


def build_qna_opening(*, role_summary: str = "") -> str:
    """End-of-questions opener; includes a short role overview when available."""
    summary = (role_summary or "").strip()
    if summary:
        # Keep spoken opening short — long overviews burn TTS and invite long Q&A.
        brief = summary if len(summary) <= 280 else f"{summary[:277].rstrip()}..."
        return (
            f"Those were my interview questions. Briefly about the role: {brief} "
            "You may ask one short question about the role or next steps, or say you are done."
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


def _norm_qna(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def looks_repeated_qna(text: str, prior_answers: list[str] | None = None) -> bool:
    """True when the candidate asks essentially the same thing again."""
    current = _norm_qna(text)
    if len(current) < 8:
        return False
    for prior in prior_answers or []:
        prev = _norm_qna(prior)
        if len(prev) < 8:
            continue
        if current == prev or current in prev or prev in current:
            return True
        cur_tokens = set(current.split())
        prev_tokens = set(prev.split())
        if not cur_tokens or not prev_tokens:
            continue
        overlap = len(cur_tokens & prev_tokens) / max(len(cur_tokens), len(prev_tokens))
        if overlap >= 0.72:
            return True
    return False


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
    prior_answers: list[str] | None = None,
) -> dict[str, Any]:
    """Classify the candidate utterance and return a short spoken reply."""
    text = (candidate_text or "").strip()
    # Last allowed turn, farewell, or a repeat → close without more chat.
    if is_closing_utterance(text) or turn >= MAX_QNA_TURNS:
        return {"closing": True, "allowed": True, "reply": CLOSING_THANK_YOU}
    if looks_repeated_qna(text, prior_answers):
        return {"closing": True, "allowed": True, "reply": _WRAP_UP_REPLY}

    if looks_controversial(text):
        return {"closing": True, "allowed": False, "reply": f"{_DECLINE_REPLY} {_WRAP_UP_REPLY}"}

    if _HARD_UNKNOWN.search(text) or looks_unknown_internal(text):
        # One short unknown reply, then end — avoid multi-turn salary/next-step loops.
        return {
            "closing": True,
            "allowed": True,
            "reply": f"{_UNKNOWN_REPLY} {_WRAP_UP_REPLY}",
        }

    refs = _reference_block(
        role_summary=role_summary,
        department_name=department_name,
        department_brief=department_brief,
        company_intro=company_intro,
    )

    # Prefer free template answers from JD/dept/company briefs before calling the LLM.
    brief_reply = _fallback_from_briefs(
        text,
        role_summary=role_summary,
        department_brief=department_brief,
        company_intro=company_intro,
    )
    if brief_reply:
        closing = turn >= MAX_QNA_TURNS - 1
        reply = brief_reply if not closing else f"{brief_reply} {_WRAP_UP_REPLY}"
        return {"closing": closing, "allowed": True, "reply": reply}

    if llama_available():
        try:
            data = call_llama_json(
                _QNA_SYSTEM,
                (
                    f"Job position: {job_position or 'the open role'}\n"
                    f"Q&A turn: {turn} of {MAX_QNA_TURNS} — close after this if possible\n"
                    f"REFERENCE TEXTS:\n{refs}\n\n"
                    f"Candidate said: {text}"
                ),
                temperature=0.2,
                max_tokens=180,
            )
            closing = bool(data.get("closing")) or turn >= MAX_QNA_TURNS - 1
            allowed = bool(data.get("allowed", True))
            reply = str(data.get("reply") or "").strip()
            if not allowed:
                reply = reply or _DECLINE_REPLY
                closing = True
            if closing:
                reply = reply or CLOSING_THANK_YOU
            if not reply:
                reply = _WRAP_UP_REPLY
                closing = True
            if _HARD_UNKNOWN.search(text):
                reply = f"{_UNKNOWN_REPLY} {_WRAP_UP_REPLY}"
                closing = True
            return {"closing": closing, "allowed": allowed, "reply": reply}
        except Exception:
            logger.exception("Candidate Q&A LLM reply failed; using fallback.")

    return {
        "closing": True,
        "allowed": True,
        "reply": _WRAP_UP_REPLY,
    }
