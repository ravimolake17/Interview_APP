"""Helpers for serving the HR React SPA alongside FastAPI routes."""

from __future__ import annotations

# First path segment reserved for APIs / static mounts — must NOT use startswith
# prefixes like "candidate", which incorrectly blocked SPA route "/candidates/...".
SPA_SKIP_ROOTS = frozenset(
    {
        "api",
        "docs",
        "redoc",
        "openapi.json",
        "health",
        "ready",
        "screening",
        "screening-files",
        "proctoring",
        "monitor",
        "candidate",  # Agent 5 singular (/candidate/...) — not /candidates
        "extract",
        "jd",
        "matching",
        "ws",
        "ui",
        "assets",
    }
)


def spa_path_is_api_or_static(full_path: str) -> bool:
    """True when the catch-all must not serve index.html for this path."""
    root = str(full_path or "").lstrip("/").split("/", 1)[0]
    return root in SPA_SKIP_ROOTS
