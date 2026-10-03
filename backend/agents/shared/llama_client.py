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


def llama_available() -> bool:
    provider = str(getattr(settings, "LLM_PROVIDER", "groq") or "groq").strip().lower()
    if provider == "azure":
        return bool(
            getattr(settings, "AZURE_OPENAI_API_KEY", None)
            and getattr(settings, "AZURE_OPENAI_ENDPOINT", "")
            and (
                getattr(settings, "AZURE_OPENAI_DEPLOYMENT", "")
                or settings.GROQ_MODEL
            )
        )
    return bool(settings.GROQ_API_KEY)


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


def _call_azure_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
) -> str:
    import httpx

    endpoint = str(getattr(settings, "AZURE_OPENAI_ENDPOINT", "") or "").rstrip("/")
    deployment = str(
        getattr(settings, "AZURE_OPENAI_DEPLOYMENT", "") or settings.GROQ_MODEL
    ).strip()
    api_version = str(
        getattr(settings, "AZURE_OPENAI_API_VERSION", "") or "2024-10-21"
    ).strip()
    api_key = getattr(settings, "AZURE_OPENAI_API_KEY", None)
    if not endpoint or not deployment or not api_key:
        raise RuntimeError(
            "Azure OpenAI is not configured. Set key, endpoint, and deployment in SuperAdmin."
        )
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions"
    payload: dict[str, Any] = {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    response = httpx.post(
        url,
        params={"api-version": api_version},
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=getattr(settings, "GROQ_TIMEOUT_SECONDS", 45),
    )
    response.raise_for_status()
    body = response.json()
    content = (
        ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
        if isinstance(body, dict)
        else None
    )
    if not content:
        raise ValueError("Azure OpenAI returned an empty response.")
    return str(content).strip()


def call_llama(
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool = True,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    """Call the configured chat model (Groq or Azure OpenAI) and return assistant text."""
    provider = str(getattr(settings, "LLM_PROVIDER", "groq") or "groq").strip().lower()
    temp = settings.GROQ_TEMPERATURE if temperature is None else temperature
    tokens = settings.GROQ_MAX_TOKENS if max_tokens is None else max_tokens
    if provider == "azure":
        return _call_azure_chat(
            system_prompt,
            user_prompt,
            json_mode=json_mode,
            temperature=temp,
            max_tokens=tokens,
        )

    client = _client()
    if client is None:
        raise RuntimeError("Meta Llama is not configured (set GROQ_API_KEY).")

    chosen = resolve_groq_model(model or llama_model_id())
    kwargs: dict[str, Any] = {
        "model": chosen,
        "temperature": settings.GROQ_TEMPERATURE if temperature is None else temperature,
        "max_tokens": settings.GROQ_MAX_TOKENS if max_tokens is None else max_tokens,
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
        raise ValueError("Meta Llama returned an empty response.")
    return content.strip()


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
