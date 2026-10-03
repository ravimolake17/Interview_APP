"""Lightweight web research for Agent 6 evaluation context."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)


def fetch_web_context(query: str, *, max_snippets: int = 3) -> list[dict[str, str]]:
    """Fetch short public web snippets (DuckDuckGo Instant Answer API)."""
    cleaned = " ".join((query or "").split())[:180]
    if not cleaned:
        return []

    url = (
        "https://api.duckduckgo.com/"
        f"?q={quote_plus(cleaned)}&format=json&no_html=1&skip_disambig=1"
    )
    snippets: list[dict[str, str]] = []
    try:
        with httpx.Client(timeout=2.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "InterviewAgenticAI/1.0"})
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.debug("Web research unavailable for query=%r", cleaned, exc_info=True)
        return []

    abstract = str(data.get("AbstractText") or "").strip()
    abstract_url = str(data.get("AbstractURL") or "").strip()
    if abstract:
        snippets.append(
            {
                "title": str(data.get("Heading") or "Summary"),
                "snippet": abstract[:500],
                "url": abstract_url,
            }
        )

    for topic in list(data.get("RelatedTopics") or [])[: max_snippets + 2]:
        if len(snippets) >= max_snippets:
            break
        if not isinstance(topic, dict):
            continue
        text = str(topic.get("Text") or "").strip()
        first_url = str(topic.get("FirstURL") or "").strip()
        if text:
            snippets.append(
                {
                    "title": text.split(" - ")[0][:80],
                    "snippet": text[:500],
                    "url": first_url,
                }
            )

    return snippets[:max_snippets]


def format_web_context(snippets: list[dict[str, Any]]) -> str:
    if not snippets:
        return "No external web snippets available."
    lines = []
    for i, item in enumerate(snippets, start=1):
        title = item.get("title") or f"Source {i}"
        snippet = item.get("snippet") or ""
        url = item.get("url") or ""
        lines.append(f"{i}. {title}: {snippet}" + (f" ({url})" if url else ""))
    return "\n".join(lines)
