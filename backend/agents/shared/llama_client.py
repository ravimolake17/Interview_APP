"""Groq chat client (openai/gpt-oss-120b by default).

Agent 4 (interview) and Agent 6 (evaluation) both call this module so they
share one Groq stack and settings (GROQ_API_KEY / GROQ_MODEL).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.screening_agent.config import settings
from agents.shared.model_catalog import (
    describe_target,
    get_runtime_catalog,
    normalize_azure_openai_endpoint,
    ordered_targets,
    should_fallback,
)
from schemas.settings import AICatalogEntry

logger = logging.getLogger(__name__)

DEFAULT_LLAMA_MODEL = "openai/gpt-oss-120b"

# Groq retired these IDs for free/developer tiers on 16 Aug 2026.
# SuperAdmin/settings may still store the old names.
DEPRECATED_GROQ_MODELS = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.1-70b-versatile": "openai/gpt-oss-120b",
}
_warned_models: set[str] = set()


def _azure_ready(entry: AICatalogEntry | None = None) -> bool:
    endpoint = str(
        (entry.endpoint if entry and entry.endpoint else None)
        or getattr(settings, "AZURE_OPENAI_ENDPOINT", "")
        or ""
    ).strip()
    deployment = str(
        (entry.model_id if entry else None)
        or getattr(settings, "AZURE_OPENAI_DEPLOYMENT", "")
        or settings.GROQ_MODEL
        or ""
    ).strip()
    return bool(getattr(settings, "AZURE_OPENAI_API_KEY", None) and endpoint and deployment)


def _groq_ready() -> bool:
    return bool(settings.GROQ_API_KEY)


def llama_available() -> bool:
    targets = ordered_targets("chat")
    if targets:
        return any(
            (_azure_ready(entry) if entry.provider == "azure" else _groq_ready())
            for entry in targets
        )
    provider = str(getattr(settings, "LLM_PROVIDER", "groq") or "groq").strip().lower()
    if provider == "azure":
        return _azure_ready()
    return _groq_ready()


def resolve_groq_model(model_id: str | None) -> str:
    """Map retired Groq model IDs onto a current production replacement."""
    configured = (model_id or DEFAULT_LLAMA_MODEL).strip() or DEFAULT_LLAMA_MODEL
    replacement = DEPRECATED_GROQ_MODELS.get(configured)
    if not replacement:
        return configured
    if configured not in _warned_models:
        _warned_models.add(configured)
        logger.warning(
            "Groq model %s is retired; using %s instead",
            configured,
            replacement,
        )
    return replacement


def llama_model_id() -> str:
    targets = ordered_targets("chat")
    if targets:
        return targets[0].model_id
    return resolve_groq_model(settings.GROQ_MODEL)


def _client():
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
    except ImportError:
        logger.warning("groq package unavailable; Meta Llama calls disabled.")
        return None
    return Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=getattr(settings, "GROQ_TIMEOUT_SECONDS", 45),
        max_retries=getattr(settings, "GROQ_MAX_RETRIES", 1),
    )


_AZURE_API_VERSION_OK = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:-preview)?$",
    re.IGNORECASE,
)


def _is_gpt5_family(deployment: str) -> bool:
    name = str(deployment or "").casefold().replace("_", "-")
    return "gpt-5" in name or name.startswith("o1") or name.startswith("o3") or name.startswith("o4")


def _resolve_azure_api_version(
    *,
    entry: AICatalogEntry | None,
    catalog,
    deployment: str,
) -> str:
    shared = str(
        catalog.azure_openai_api_version
        or getattr(settings, "AZURE_OPENAI_API_VERSION", "")
        or "2024-10-21"
    ).strip() or "2024-10-21"
    raw = str(entry.api_version if entry and entry.api_version else shared).strip() or shared
    # Portal "model version" (e.g. 2025-08-07) is often pasted here by mistake.
    # Prefer a real chat API version for GPT-5 / reasoning deployments.
    if _is_gpt5_family(deployment) and raw == "2025-08-07":
        return shared if shared != "2025-08-07" else "2024-12-01-preview"
    if not _AZURE_API_VERSION_OK.match(raw):
        return shared
    return raw


def _call_azure_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
    entry: AICatalogEntry | None = None,
) -> str:
    import httpx

    catalog = get_runtime_catalog()
    endpoint = normalize_azure_openai_endpoint(
        str(
            (entry.endpoint if entry and entry.endpoint else None)
            or catalog.azure_openai_endpoint
            or getattr(settings, "AZURE_OPENAI_ENDPOINT", "")
            or ""
        )
    )
    deployment = str(
        (entry.model_id if entry else None)
        or catalog.azure_openai_deployment
        or getattr(settings, "AZURE_OPENAI_DEPLOYMENT", "")
        or settings.GROQ_MODEL
    ).strip()
    api_version = _resolve_azure_api_version(entry=entry, catalog=catalog, deployment=deployment)
    api_key = getattr(settings, "AZURE_OPENAI_API_KEY", None)
    if not endpoint or not deployment or not api_key:
        raise RuntimeError(
            "Azure OpenAI is not configured. Set key, endpoint, and deployment in SuperAdmin."
        )
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions"
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    # GPT-5 / reasoning deployments reject max_tokens and often only allow default temperature.
    if _is_gpt5_family(deployment):
        payload["max_completion_tokens"] = int(max_tokens)
    else:
        payload["temperature"] = temperature
        payload["max_tokens"] = int(max_tokens)
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    response = httpx.post(
        url,
        params={"api-version": api_version},
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=getattr(settings, "GROQ_TIMEOUT_SECONDS", 45),
    )
    if response.status_code >= 400:
        detail = ""
        try:
            err_body = response.json()
            err = err_body.get("error") if isinstance(err_body, dict) else None
            if isinstance(err, dict):
                detail = str(err.get("message") or err.get("code") or "").strip()
            elif isinstance(err_body, dict):
                detail = str(err_body.get("message") or "").strip()
        except Exception:
            detail = (response.text or "").strip()
        detail = detail[:240] or response.reason_phrase or "bad request"
        raise RuntimeError(
            f"Azure OpenAI rejected {deployment} ({response.status_code}): {detail}. "
            "Use the resource endpoint https://….openai.azure.com/ (not the Foundry project URL), "
            "deployment name exactly as in Azure, and API version like 2024-10-21 — not the model version."
        )
    body = response.json()
    content = (
        ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
        if isinstance(body, dict)
        else None
    )
    if not content:
        raise ValueError("Azure OpenAI returned an empty response.")
    return str(content).strip()


def _call_groq_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
    model: str | None = None,
) -> str:
    client = _client()
    if client is None:
        raise RuntimeError("Groq is not configured (set GROQ_API_KEY).")

    chosen = resolve_groq_model(model or llama_model_id())
    kwargs: dict[str, Any] = {
        "model": chosen,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        message = str(exc).lower()
        if chosen != DEFAULT_LLAMA_MODEL and (
            "model_not_found" in message or "does not exist" in message
        ):
            logger.warning(
                "Groq model %s is unavailable; retrying with %s",
                chosen,
                DEFAULT_LLAMA_MODEL,
            )
            kwargs["model"] = DEFAULT_LLAMA_MODEL
            response = client.chat.completions.create(**kwargs)
        else:
            raise
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Groq returned an empty response.")
    return content.strip()


def _invoke_chat_target(
    entry: AICatalogEntry | None,
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
    model: str | None,
) -> str:
    provider = (entry.provider if entry else str(getattr(settings, "LLM_PROVIDER", "groq") or "groq")).strip().lower()
    if provider == "azure":
        return _call_azure_chat(
            system_prompt,
            user_prompt,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
            entry=entry,
        )
    return _call_groq_chat(
        system_prompt,
        user_prompt,
        json_mode=json_mode,
        temperature=temperature,
        max_tokens=max_tokens,
        model=(entry.model_id if entry else None) or model,
    )


def call_llama_for_entry(
    entry: AICatalogEntry,
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call one catalog chat row only (SuperAdmin test). No fallback."""
    temp = settings.GROQ_TEMPERATURE if temperature is None else temperature
    tokens = settings.GROQ_MAX_TOKENS if max_tokens is None else max_tokens
    return _invoke_chat_target(
        entry,
        system_prompt,
        user_prompt,
        json_mode=json_mode,
        temperature=temp,
        max_tokens=min(int(tokens), 512),
        model=entry.model_id,
    )


def call_llama(
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool = True,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    """Call primary chat model, then fallback on overload or server errors."""
    temp = settings.GROQ_TEMPERATURE if temperature is None else temperature
    tokens = settings.GROQ_MAX_TOKENS if max_tokens is None else max_tokens
    targets = ordered_targets("chat") or [None]
    last_error: Exception | None = None
    for index, entry in enumerate(targets):
        try:
            return _invoke_chat_target(
                entry,
                system_prompt,
                user_prompt,
                json_mode=json_mode,
                temperature=temp,
                max_tokens=tokens,
                model=model,
            )
        except Exception as exc:
            last_error = exc
            has_next = index < len(targets) - 1
            if has_next and should_fallback(exc):
                nxt = targets[index + 1]
                logger.warning(
                    "Chat model %s failed (%s); falling back to %s",
                    describe_target(entry) if entry else "primary",
                    exc,
                    describe_target(nxt) if nxt else "fallback",
                )
                continue
            raise
    raise last_error or RuntimeError("No chat model is configured.")


def call_llama_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Call Meta Llama and parse a JSON object response."""
    raw = call_llama(
        system_prompt,
        user_prompt,
        json_mode=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {"value": data}
