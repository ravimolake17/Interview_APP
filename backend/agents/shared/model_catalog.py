"""Runtime AI catalog: primary + fallback for chat, STT, and TTS."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from schemas.settings import AICatalogEntry, AIModelSettings

logger = logging.getLogger(__name__)

# How long a worker may keep an in-memory catalog before reloading from DB.
# Keeps SuperAdmin ON/OFF and preference changes live without process restart,
# including multi-worker production.
_RUNTIME_TTL_SECONDS = 2.0

_FALLBACK_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_FALLBACK_TEXT = (
    "429",
    "rate limit",
    "too many requests",
    "timeout",
    "timed out",
    "temporar",
    "unavailable",
    "overloaded",
    "capacity",
    "tpm",
    "tokens per minute",
    "upstream",
    "connect error",
    "connection reset",
    "connection termination",
    "connection failure",
    "no healthy upstream",
    "server error",
    "internal server",
    "502",
    "503",
    "504",
)

_runtime: AIModelSettings | None = None
_runtime_loaded_at: float = 0.0
_CATALOG_KEYS = ("chat_models", "stt_models", "tts_models")


def set_runtime_catalog(payload: AIModelSettings) -> None:
    global _runtime, _runtime_loaded_at
    _runtime = hydrate_catalog(payload)
    _runtime_loaded_at = time.monotonic()


def get_runtime_catalog() -> AIModelSettings:
    if _runtime is None:
        return hydrate_catalog(AIModelSettings())
    return _runtime


def catalog_needs_refresh(ttl_seconds: float = _RUNTIME_TTL_SECONDS) -> bool:
    """True when this process should reload AI catalog from the database."""
    if _runtime is None:
        return True
    return (time.monotonic() - _runtime_loaded_at) >= max(0.0, float(ttl_seconds))


def default_catalog(base: AIModelSettings | None = None) -> AIModelSettings:
    data = base.model_dump() if base is not None else AIModelSettings().model_dump()
    endpoint = str(data.get("azure_openai_endpoint") or "").strip()
    api_version = str(data.get("azure_openai_api_version") or "2024-10-21")
    region = str(data.get("azure_speech_region") or "eastus2")
    stt_endpoint = str(data.get("azure_speech_stt_endpoint") or "")
    tts_endpoint = str(data.get("azure_speech_tts_endpoint") or "")
    chat_models = [
        AICatalogEntry(
            id="azure-gpt-4o",
            name="Azure GPT-4o",
            kind="chat",
            provider="azure",
            model_id="gpt-4o",
            endpoint=endpoint,
            api_version=api_version,
            enabled=True,
        ),
        AICatalogEntry(
            id="azure-gpt-4o-mini",
            name="Azure GPT-4o mini",
            kind="chat",
            provider="azure",
            model_id="gpt-4o-mini",
            endpoint=endpoint,
            api_version=api_version,
            enabled=True,
        ),
        AICatalogEntry(
            id="groq-gpt-oss-120b",
            name="Groq GPT-OSS 120B",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-120b",
            enabled=True,
        ),
        AICatalogEntry(
            id="groq-gpt-oss-20b",
            name="Groq GPT-OSS 20B",
            kind="chat",
            provider="groq",
            model_id="openai/gpt-oss-20b",
            enabled=True,
        ),
    ]
    stt_models = [
        AICatalogEntry(
            id="azure-speech-stt",
            name="Azure Speech STT",
            kind="stt",
            provider="azure",
            model_id="azure-speech",
            endpoint=stt_endpoint,
            region=region,
            enabled=True,
        ),
        AICatalogEntry(
            id="groq-whisper",
            name="Groq Whisper large-v3",
            kind="stt",
            provider="groq",
            model_id="whisper-large-v3",
            enabled=True,
        ),
    ]
    tts_models = [
        AICatalogEntry(
            id="azure-speech-tts",
            name="Azure Speech TTS",
            kind="tts",
            provider="azure",
            model_id="en-IN-NeerjaNeural",
            endpoint=tts_endpoint,
            region=region,
            enabled=True,
            voice="female",
        ),
        AICatalogEntry(
            id="edge-neural",
            name="Edge neural TTS (Indian English)",
            kind="tts",
            provider="edge",
            model_id="en-IN-NeerjaNeural",
            enabled=True,
            voice="female",
        ),
    ]
    provider = str(data.get("provider") or "groq").strip().lower()
    stt_provider = str(data.get("stt_provider") or "groq").strip().lower()
    tts_provider = str(data.get("tts_provider") or "edge").strip().lower()
    if provider == "azure":
        chat_primary, chat_fallback = "azure-gpt-4o", "groq-gpt-oss-120b"
    else:
        chat_primary, chat_fallback = "groq-gpt-oss-120b", "azure-gpt-4o"
    if stt_provider == "azure":
        stt_primary, stt_fallback = "azure-speech-stt", "groq-whisper"
    else:
        stt_primary, stt_fallback = "groq-whisper", "azure-speech-stt"
    if tts_provider == "azure":
        tts_primary, tts_fallback = "azure-speech-tts", "edge-neural"
    else:
        tts_primary, tts_fallback = "edge-neural", "azure-speech-tts"
    data.update(
        {
            "chat_models": chat_models,
            "stt_models": stt_models,
            "tts_models": tts_models,
            "chat_primary_id": chat_primary,
            "chat_fallback_id": chat_fallback,
            "stt_primary_id": stt_primary,
            "stt_fallback_id": stt_fallback,
            "tts_primary_id": tts_primary,
            "tts_fallback_id": tts_fallback,
        }
    )
    return AIModelSettings.model_validate(data)


def _index_models(models: list[AICatalogEntry]) -> dict[str, AICatalogEntry]:
    return {entry.id: entry for entry in models if entry.id}


def _dump_catalog_entries(raw: Any) -> list[Any]:
    dumped: list[Any] = []
    for item in raw or []:
        if hasattr(item, "model_dump"):
            dumped.append(item.model_dump(mode="json"))
        else:
            dumped.append(item)
    return dumped


def merge_ai_model_payload(current: dict[str, Any], payload: AIModelSettings) -> dict[str, Any]:
    """Patch AI settings while honoring SuperAdmin catalog add/delete.

    SuperAdmin sends the full chat/STT/TTS lists. That exact list is stored, so
    a deleted built-in (for example gpt-4o-mini) stays deleted. HR Settings omits
    those lists; Pydantic then fills []. Ignore that empty default so custom rows
    such as gpt-5-mini are not wiped.
    """
    incoming = payload.model_dump(exclude_unset=True)
    merged = dict(current)
    for key, value in incoming.items():
        if key in _CATALOG_KEYS:
            continue
        merged[key] = value
    for key in _CATALOG_KEYS:
        dumped = _dump_catalog_entries(getattr(payload, key, None) or incoming.get(key) or [])
        if key in payload.model_fields_set:
            merged[key] = dumped
        elif dumped:
            merged[key] = dumped
    return merged


_FOUNDRY_PROJECT_ENDPOINT = re.compile(
    r"^https?://(?P<resource>[a-z0-9-]+)\.services\.ai\.azure\.com(?:/api/projects/[^/?#]+)?/?$",
    re.IGNORECASE,
)


def normalize_azure_openai_endpoint(endpoint: str) -> str:
    """Map Foundry project URLs onto the classic OpenAI resource host this app uses."""
    raw = str(endpoint or "").strip().rstrip("/")
    if not raw:
        return ""
    match = _FOUNDRY_PROJECT_ENDPOINT.match(raw)
    if match:
        return f"https://{match.group('resource')}.openai.azure.com"
    return raw


def _normalize_chat_entry(entry: AICatalogEntry) -> AICatalogEntry:
    """Keep Azure chat rows on the classic OpenAI host; drop pasted model versions."""
    updates: dict = {}
    if entry.provider == "azure" and entry.endpoint:
        cleaned = normalize_azure_openai_endpoint(entry.endpoint)
        if cleaned != entry.endpoint:
            updates["endpoint"] = cleaned
    # Model snapshot dates are not REST api-versions.
    if entry.provider == "azure" and str(entry.api_version or "").strip() == "2025-08-07":
        updates["api_version"] = ""
    return entry.model_copy(update=updates) if updates else entry


def hydrate_catalog(payload: AIModelSettings) -> AIModelSettings:
    defaults = default_catalog(payload)
    data = payload.model_dump()

    def merge(kind: str) -> list[AICatalogEntry]:
        # Stored catalog is authoritative. Do not re-insert built-in models
        # (gpt-4o-mini, etc.) that SuperAdmin deleted.
        if f"{kind}_models" in payload.model_fields_set or data.get(f"{kind}_models"):
            stored: list[AICatalogEntry] = []
            for item in data.get(f"{kind}_models") or []:
                try:
                    entry = AICatalogEntry.model_validate(item)
                    if kind == "chat":
                        entry = _normalize_chat_entry(entry)
                    stored.append(entry)
                except Exception:
                    logger.warning("Skipping invalid %s catalog entry: %s", kind, item)
            return stored
        return list(getattr(defaults, f"{kind}_models"))

    chat_models = merge("chat")
    stt_models = merge("stt")
    tts_models = merge("tts")
    chat_ids = _index_models(chat_models)
    stt_ids = _index_models(stt_models)
    tts_ids = _index_models(tts_models)

    def pick(current: str, fallback: str, available: dict[str, AICatalogEntry]) -> str:
        if current in available:
            return current
        if fallback in available:
            return fallback
        return next(iter(available), "")

    chat_primary = pick(data.get("chat_primary_id") or "", defaults.chat_primary_id, chat_ids)
    chat_fallback = pick(data.get("chat_fallback_id") or "", defaults.chat_fallback_id, chat_ids)
    if chat_fallback == chat_primary:
        chat_fallback = next((key for key in chat_ids if key != chat_primary), "")
    stt_primary = pick(data.get("stt_primary_id") or "", defaults.stt_primary_id, stt_ids)
    stt_fallback = pick(data.get("stt_fallback_id") or "", defaults.stt_fallback_id, stt_ids)
    if stt_fallback == stt_primary:
        stt_fallback = next((key for key in stt_ids if key != stt_primary), "")
    tts_primary = pick(data.get("tts_primary_id") or "", defaults.tts_primary_id, tts_ids)
    tts_fallback = pick(data.get("tts_fallback_id") or "", defaults.tts_fallback_id, tts_ids)
    if tts_fallback == tts_primary:
        tts_fallback = next((key for key in tts_ids if key != tts_primary), "")

    primary_chat = chat_ids.get(chat_primary)
    primary_stt = stt_ids.get(stt_primary)
    primary_tts = tts_ids.get(tts_primary)
    data.update(
        {
            "chat_models": chat_models,
            "stt_models": stt_models,
            "tts_models": tts_models,
            "chat_primary_id": chat_primary,
            "chat_fallback_id": chat_fallback,
            "stt_primary_id": stt_primary,
            "stt_fallback_id": stt_fallback,
            "tts_primary_id": tts_primary,
            "tts_fallback_id": tts_fallback,
        }
    )
    if primary_chat:
        data["provider"] = primary_chat.provider if primary_chat.provider in {"azure", "groq"} else "groq"
        data["model_id"] = primary_chat.model_id
        if primary_chat.provider == "azure":
            data["azure_openai_deployment"] = primary_chat.model_id
            if primary_chat.endpoint:
                data["azure_openai_endpoint"] = normalize_azure_openai_endpoint(
                    primary_chat.endpoint
                )
            if primary_chat.api_version and primary_chat.api_version != "2025-08-07":
                data["azure_openai_api_version"] = primary_chat.api_version
    if data.get("azure_openai_endpoint"):
        data["azure_openai_endpoint"] = normalize_azure_openai_endpoint(
            str(data.get("azure_openai_endpoint") or "")
        )
    if primary_stt:
        data["stt_provider"] = "azure" if primary_stt.provider == "azure" else "groq"
        if primary_stt.endpoint:
            data["azure_speech_stt_endpoint"] = primary_stt.endpoint
        if primary_stt.region:
            data["azure_speech_region"] = primary_stt.region
    if primary_tts:
        data["tts_provider"] = "azure" if primary_tts.provider == "azure" else "edge"
        if primary_tts.endpoint:
            data["azure_speech_tts_endpoint"] = primary_tts.endpoint
        if primary_tts.region:
            data["azure_speech_region"] = primary_tts.region
    return AIModelSettings.model_validate(data)


_GENERIC_PERSONA_TOKENS = (
    "tts",
    "stt",
    "speech",
    "whisper",
    "gpt",
    "groq",
    "azure",
    "edge",
    "neural",
    "model",
    "chat",
    "openai",
)


def interviewer_display_name(entry: AICatalogEntry | None) -> str:
    """Use SuperAdmin display name as the spoken interviewer identity when it is a person name."""
    if entry is None:
        return ""
    name = str(entry.name or "").strip()
    if not name:
        return ""
    lowered = name.casefold()
    if any(token in lowered for token in _GENERIC_PERSONA_TOKENS):
        return ""
    return name


def primary_interviewer_name() -> str:
    targets = ordered_targets("tts")
    return interviewer_display_name(targets[0] if targets else None)


def voice_for_entry(entry: AICatalogEntry | None) -> str:
    if entry is None:
        return "female"
    raw = str(getattr(entry, "voice", "") or "").strip().lower()
    if raw in {"female", "male"}:
        return raw
    model_id = str(entry.model_id or "").casefold()
    if "prabhat" in model_id or "aarav" in model_id or "kunal" in model_id:
        return "male"
    return "female"


def catalog_entry(kind: str, entry_id: str) -> AICatalogEntry | None:
    catalog = get_runtime_catalog()
    models = getattr(catalog, f"{kind}_models", [])
    return next((item for item in models if item.id == entry_id), None)


def ordered_targets(kind: str) -> list[AICatalogEntry]:
    """Try order: first preference → named fallback → all other enabled catalog rows.

    Extra ON models are backups after the two dropdowns (traffic / server errors only).
    """
    catalog = get_runtime_catalog()
    models = list(getattr(catalog, f"{kind}_models", []) or [])
    primary_id = str(getattr(catalog, f"{kind}_primary_id", "") or "")
    fallback_id = str(getattr(catalog, f"{kind}_fallback_id", "") or "")
    by_id = _index_models(models)
    ordered: list[AICatalogEntry] = []
    seen: set[str] = set()

    def _add(entry: AICatalogEntry | None) -> None:
        if entry is None or not entry.enabled or entry.id in seen:
            return
        ordered.append(entry)
        seen.add(entry.id)

    _add(by_id.get(primary_id))
    _add(by_id.get(fallback_id))
    for entry in models:
        _add(entry)
    return ordered


def uses_groq_primary_chat() -> bool:
    targets = ordered_targets("chat")
    return bool(targets and targets[0].provider == "groq")


def should_fallback(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    response = getattr(exc, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    if status in _FALLBACK_STATUS:
        return True
    text = str(exc or "").casefold()
    return any(token in text for token in _FALLBACK_TEXT)


def describe_target(entry: AICatalogEntry) -> str:
    return f"{entry.name} ({entry.provider}/{entry.model_id})"


def sync_legacy_fields(payload: AIModelSettings) -> dict[str, Any]:
    hydrated = hydrate_catalog(payload)
    return hydrated.model_dump(mode="json")
