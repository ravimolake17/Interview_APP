"""Locked interview-language helpers shared by prompts and speech services."""

from __future__ import annotations

from typing import Any

InterviewLanguage = str


def normalize_interview_language(value: Any) -> InterviewLanguage:
    raw = str(value or "").strip().casefold().replace("_", "-")
    if raw in {"hi", "hi-in", "hindi", "हिंदी"}:
        return "hi"
    return "en"


def azure_stt_locale(value: Any) -> str:
    return "hi-IN" if normalize_interview_language(value) == "hi" else "en-IN"


def whisper_language(value: Any) -> str:
    return "hi" if normalize_interview_language(value) == "hi" else "en"


def tts_voice_and_xml_lang(value: Any, gender: str = "female") -> tuple[str, str]:
    language = normalize_interview_language(value)
    male = str(gender or "").strip().casefold() == "male"
    if language == "hi":
        return ("hi-IN-MadhurNeural" if male else "hi-IN-SwaraNeural", "hi-IN")
    return ("en-IN-PrabhatNeural" if male else "en-IN-NeerjaNeural", "en-IN")


def prompt_language_instruction(value: Any) -> str:
    if normalize_interview_language(value) == "hi":
        return (
            "Conduct the interview entirely in natural, professional Hindi written in "
            "Devanagari. Keep technical terms in English where that is clearer. The "
            "candidate may answer in Hindi, English, or Hinglish; understand the content "
            "but never switch your own interview language away from Hindi."
        )
    return (
        "Conduct the interview entirely in clear professional English. The candidate may "
        "answer in English, Hindi, or Hinglish; understand the content but never switch "
        "your own interview language away from English."
    )


def language_from_snapshot(snapshot: dict[str, Any] | None) -> InterviewLanguage:
    data = snapshot or {}
    agent5 = data.get("agent5") if isinstance(data.get("agent5"), dict) else {}
    runtime = (
        agent5.get("interview_runtime")
        if isinstance(agent5.get("interview_runtime"), dict)
        else {}
    )
    # Prefer screening snapshot (source of truth). Runtime only fills gaps for
    # older rows that locked language after the room already opened.
    return normalize_interview_language(
        data.get("interview_language") or runtime.get("interview_language")
    )
