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

_QNA_SYSTEM = """You are an AI interviewer wrapping up a job interview for RR Parkon, part of RR Global.
The candidate may share feedback or ask questions.

Return JSON only:
{
  "closing": boolean,
  "allowed": boolean,
  "reply": "2 to 4 spoken sentences, professional and warm"
}

Set closing=true when the candidate is finished, has no questions, or only says thank you.

You do NOT have internal company facts. Never invent them.
Unknown (do not guess): team structure, headcount, reporting lines, named managers,
salaries, benefits numbers, office seating, shifts, or unannounced plans.
If asked those, allowed=true, say you do not have that information and HR can follow up.

Safe topics: the role in general, the interview process, and that HR will share next steps.

DECLINE (allowed=false): politics, religion, caste, race, gender attacks, adult content,
illegal activity, hacking, confidential internals, medical/legal advice, or cheating.

If declining, politely refuse and offer to talk about the role or next steps instead.
"""


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


def generate_candidate_qna_reply(
    candidate_text: str,
    *,
    job_position: str = "",
    turn: int = 1,
) -> dict[str, Any]:
    """Classify the candidate utterance and return a spoken reply."""
    text = (candidate_text or "").strip()
    if is_closing_utterance(text) or turn >= MAX_QNA_TURNS:
        return {"closing": True, "allowed": True, "reply": CLOSING_THANK_YOU}

    if looks_controversial(text):
        return {"closing": False, "allowed": False, "reply": _DECLINE_REPLY}

    if looks_unknown_internal(text):
        return {"closing": False, "allowed": True, "reply": _UNKNOWN_REPLY}

    if llama_available():
        try:
            data = call_llama_json(
                _QNA_SYSTEM,
                (
                    f"Job position: {job_position or 'the open role'}\n"
                    f"Q&A turn: {turn} of {MAX_QNA_TURNS}\n"
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
            if looks_unknown_internal(text):
                reply = _UNKNOWN_REPLY
            return {"closing": closing, "allowed": allowed, "reply": reply}
        except Exception:
            logger.exception("Candidate Q&A LLM reply failed; using fallback.")

    return {
        "closing": False,
        "allowed": True,
        "reply": (
            "Thank you for sharing that. I can talk about the role or what happens "
            "after this interview. What would you like to know?"
        ),
    }
