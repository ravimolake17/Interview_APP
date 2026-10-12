"""SuperAdmin click-to-test for one catalog chat, STT, or TTS row."""

from __future__ import annotations

import base64

from agents.shared.model_catalog import (
    catalog_entry,
    interviewer_display_name,
    voice_for_entry,
)
from schemas.settings import CatalogModelTestRequest, CatalogModelTestResponse


def _base_response(entry, *, kind: str, catalog_id: str) -> dict:
    return {
        "ok": True,
        "kind": kind,
        "catalog_id": catalog_id,
        "name": entry.name,
        "provider": entry.provider,
        "model_id": entry.model_id,
        "text": "",
        "audio_base64": None,
        "audio_content_type": None,
        "message": "",
    }


def test_catalog_model(payload: CatalogModelTestRequest) -> CatalogModelTestResponse:
    entry = catalog_entry(payload.kind, payload.catalog_id)
    if entry is None:
        raise ValueError("That model is not in the saved catalog.")
    if payload.kind == "chat":
        return _test_chat(entry, payload.prompt)
    if payload.kind == "tts":
        return _test_tts(entry, payload.prompt)
    raise ValueError("Speech-to-text tests need an audio clip.")


def test_catalog_stt(catalog_id: str, content: bytes, filename: str) -> CatalogModelTestResponse:
    entry = catalog_entry("stt", catalog_id)
    if entry is None:
        raise ValueError("That model is not in the saved catalog.")
    from agents.interview_agent.stt_service import transcribe_for_entry

    result = transcribe_for_entry(entry, content, filename=filename or "audio.webm")
    data = _base_response(entry, kind="stt", catalog_id=catalog_id)
    data["text"] = result.text or ""
    data["message"] = (
        f"{entry.name} heard: {data['text']}" if data["text"] else f"{entry.name} returned empty transcript."
    )
    return CatalogModelTestResponse.model_validate(data)


def _test_chat(entry, prompt: str) -> CatalogModelTestResponse:
    from agents.shared.llama_client import call_llama_for_entry

    user_prompt = prompt or "Reply with one short sentence confirming you are ready for interviews."
    reply = call_llama_for_entry(
        entry,
        "You are a recruitment assistant. Reply in one or two short plain sentences. No JSON.",
        user_prompt,
        json_mode=False,
    )
    data = _base_response(entry, kind="chat", catalog_id=entry.id)
    data["text"] = reply
    data["message"] = f"{entry.name} replied."
    return CatalogModelTestResponse.model_validate(data)


def _test_tts(entry, prompt: str) -> CatalogModelTestResponse:
    from agents.interview_agent.tts_service import synthesize_speech_for_entry

    persona = interviewer_display_name(entry) or entry.name
    gender = voice_for_entry(entry)
    accent = "Indian English"
    spoken = prompt or (
        f"Hello. I am {persona}. I speak with a clear {accent} "
        f"{'female' if gender == 'female' else 'male'} voice."
    )
    result = synthesize_speech_for_entry(entry, spoken)
    data = _base_response(entry, kind="tts", catalog_id=entry.id)
    data["text"] = result.get("text") or spoken
    data["audio_base64"] = base64.b64encode(result["audio_bytes"]).decode("ascii")
    data["audio_content_type"] = result.get("content_type") or "audio/wav"
    data["message"] = f"{entry.name} is speaking."
    return CatalogModelTestResponse.model_validate(data)


def preview_tts_voice(
    *,
    provider: str,
    model_id: str,
    voice: str = "female",
    prompt: str = "",
) -> CatalogModelTestResponse:
    """Preview one Azure/Edge neural voice without saving a catalog row."""
    from agents.interview_agent.tts_service import synthesize_speech_for_entry
    from schemas.settings import AICatalogEntry

    gender = "male" if str(voice).strip().lower() == "male" else "female"
    short_name = str(model_id or "").split(":")[0].split("-")[-1] or "Voice"
    short_name = short_name.replace("Neural", "").replace("Indic", "") or "Voice"
    entry = AICatalogEntry(
        id="preview-tts",
        name=short_name,
        kind="tts",
        provider="edge" if provider == "edge" else "azure",
        model_id=model_id,
        enabled=True,
        voice=gender,
    )
    spoken = prompt or (
        f"Hello. This is the {short_name} Indian English "
        f"{gender} voice for interview questions."
    )
    result = synthesize_speech_for_entry(entry, spoken)
    data = _base_response(entry, kind="tts", catalog_id="preview-tts")
    data["text"] = result.get("text") or spoken
    data["audio_base64"] = base64.b64encode(result["audio_bytes"]).decode("ascii")
    data["audio_content_type"] = result.get("content_type") or "audio/wav"
    data["message"] = f"Playing {model_id}."
    return CatalogModelTestResponse.model_validate(data)
