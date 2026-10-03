"""Bootstrap Agent5 fraud detection inside the unified HR backend."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_initialized = False


def startup_agent5() -> dict[str, object]:
    """Initialize Agent5 DB, admin user, and lazy AI runtimes."""
    global _initialized
    if _initialized:
        return {"ok": True, "already_initialized": True}

    from agents.proctoring_agent.config import get_settings
    from agents.proctoring_agent.db import engine, init_db

    settings = get_settings()
    try:
        settings.validate_runtime_security()
        settings.validate_runtime_configuration()
        settings.ensure_directories()
    except RuntimeError as exc:
        logger.warning("Agent5 disabled: %s", exc)
        return {"ok": False, "error": str(exc)}

    init_db()
    # HR reviewers authenticate with the main app JWT; candidates use join-link tokens.
    _initialized = True
    logger.info(
        "Agent5 fraud detection initialized (db=postgresql schema=agent5, storage=%s, models=%s)",
        settings.resolved_storage_dir,
        settings.models_dir,
    )
    return {"ok": True, "database": "postgresql (schema=agent5)"}


def shutdown_agent5() -> None:
    global _initialized
    if not _initialized:
        return
    try:
        from agents.proctoring_agent.db import engine

        engine.dispose()
    except Exception:
        logger.debug("Agent5 engine dispose failed", exc_info=True)
    _initialized = False


def agent5_ready() -> bool:
    if not _initialized:
        return False
    try:
        from agents.proctoring_agent.main import readiness

        payload = readiness()
        return bool(payload.get("ready"))
    except Exception:
        logger.debug("Agent5 readiness check failed", exc_info=True)
        return False
