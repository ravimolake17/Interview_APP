"""Shared LangGraph runtime for enterprise multi-agent workflows.

Use LangGraph when an agent needs:
  - multi-step stateful orchestration
  - human / candidate interrupts (wait for input)
  - durable checkpoints across API restarts / workers

Agents that stay outside LangGraph (by design):
  - Simple CRUD / settings routes
"""

from __future__ import annotations

import logging
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)

_checkpointer: Any = None
_checkpointer_cm: Any = None
_backend: str = "memory"


def _sync_postgres_uri() -> str:
    settings = get_settings()
    uri = (settings.checkpoint_db_url or settings.database_url or "").strip()
    if "+asyncpg" in uri:
        uri = uri.replace("postgresql+asyncpg://", "postgresql://", 1)
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri


def _init_memory() -> None:
    global _checkpointer, _checkpointer_cm, _backend
    from langgraph.checkpoint.memory import MemorySaver

    _checkpointer = MemorySaver()
    _checkpointer_cm = None
    _backend = "memory"
    logger.info("LangGraph checkpointer ready (MemorySaver)")


async def init_langgraph_runtime() -> None:
    """Initialize shared checkpointer (Postgres preferred, Memory fallback)."""
    global _checkpointer, _checkpointer_cm, _backend

    settings = get_settings()
    prefer_postgres = (
        getattr(settings, "langgraph_checkpoint_backend", "postgres") != "memory"
    )
    if not prefer_postgres:
        _init_memory()
        return

    uri = _sync_postgres_uri()

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(uri)
        _checkpointer = await _checkpointer_cm.__aenter__()
        try:
            await _checkpointer.setup()
        except Exception as exc:
            # A previous version already applied part of the schema (e.g. task_path).
            if "already exists" not in str(exc).lower():
                raise
            logger.warning(
                "LangGraph checkpointer schema already present (%s); using Postgres anyway",
                exc,
            )
        _backend = "postgres"
        logger.info("LangGraph checkpointer ready (Postgres async)")
        return
    except Exception:
        logger.warning(
            "Postgres LangGraph checkpointer unavailable; falling back to MemorySaver",
            exc_info=True,
        )

    _init_memory()


async def shutdown_langgraph_runtime() -> None:
    global _checkpointer, _checkpointer_cm, _backend
    if _checkpointer_cm is not None:
        try:
            await _checkpointer_cm.__aexit__(None, None, None)
        except Exception:
            logger.debug("LangGraph async checkpointer shutdown error", exc_info=True)
    _checkpointer = None
    _checkpointer_cm = None
    _backend = "memory"


def get_checkpointer() -> Any:
    """Return the process-wide LangGraph checkpointer."""
    global _checkpointer
    if _checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        logger.warning("get_checkpointer() called before init; using MemorySaver")
    return _checkpointer


def get_checkpointer_backend() -> str:
    return _backend


def thread_config(agent: str, entity_id: str, **extra: Any) -> dict[str, Any]:
    """Standard thread config for resumable agent workflows."""
    configurable = {"thread_id": f"{agent}-{entity_id}", **extra}
    return {"configurable": configurable}


async def ainvoke_graph(graph: Any, input_state: Any, *, config: dict[str, Any]) -> Any:
    """Invoke a compiled graph; always uses ainvoke for async-node compatibility."""
    return await graph.ainvoke(input_state, config=config)


async def aget_graph_state(graph: Any, config: dict[str, Any]) -> Any:
    """Read graph checkpoint state."""
    return await graph.aget_state(config)
