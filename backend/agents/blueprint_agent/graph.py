"""
Agent 3 LangGraph — blueprint generation with retry + fallback.

START → generate → validate → (ok? done : retry?) → fallback → done → END

Why LangGraph here:
  Primary planner is deterministic, but enterprise flows still need
  durable retries and a guaranteed fallback so Agent 4 is never blocked.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.blueprint_agent.fallback import build_fallback_blueprint
from agents.blueprint_agent.generator import generate_interview_blueprint
from agents.blueprint_agent.schemas import (
    InterviewBlueprintRequest,
    InterviewBlueprintResponse,
)
from core.langgraph_runtime import ainvoke_graph, get_checkpointer, thread_config

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


class BlueprintGraphState(TypedDict, total=False):
    CandidateID: str
    RequestPayload: dict[str, Any]
    Blueprint: dict[str, Any] | None
    Attempt: int
    MaxAttempts: int
    Status: str
    Error: str | None
    UsedFallback: bool
    GenerationSource: str


def generate_node(state: BlueprintGraphState) -> dict[str, Any]:
    attempt = int(state.get("Attempt") or 0) + 1
    payload = InterviewBlueprintRequest.model_validate(state["RequestPayload"])
    try:
        blueprint = generate_interview_blueprint(payload)
        return {
            "Attempt": attempt,
            "Blueprint": blueprint.model_dump(mode="json"),
            "Status": "GENERATED",
            "Error": None,
            "UsedFallback": False,
            "GenerationSource": blueprint.generation_source,
        }
    except Exception as exc:
        logger.warning(
            "Agent 3 primary generation failed (attempt %s/%s) for %s: %s",
            attempt,
            state.get("MaxAttempts") or MAX_ATTEMPTS,
            state.get("CandidateID"),
            exc,
        )
        return {
            "Attempt": attempt,
            "Blueprint": None,
            "Status": "GENERATE_FAILED",
            "Error": str(exc),
            "UsedFallback": False,
        }


def validate_node(state: BlueprintGraphState) -> dict[str, Any]:
    if state.get("Status") == "GENERATE_FAILED" or not state.get("Blueprint"):
        return {"Status": "INVALID"}
    try:
        InterviewBlueprintResponse.model_validate(state["Blueprint"])
        return {"Status": "VALID"}
    except Exception as exc:
        return {"Status": "INVALID", "Error": str(exc), "Blueprint": None}


def fallback_node(state: BlueprintGraphState) -> dict[str, Any]:
    payload = InterviewBlueprintRequest.model_validate(state["RequestPayload"])
    blueprint = build_fallback_blueprint(
        payload,
        error=state.get("Error"),
        candidate_level=payload.candidate_level,
        total_duration_minutes=payload.total_duration_minutes,
    )
    logger.warning(
        "Agent 3 using fallback blueprint for %s after failure: %s",
        state.get("CandidateID"),
        state.get("Error"),
    )
    return {
        "Blueprint": blueprint.model_dump(mode="json"),
        "Status": "FALLBACK",
        "UsedFallback": True,
        "GenerationSource": blueprint.generation_source,
        "Error": state.get("Error"),
    }


def done_node(state: BlueprintGraphState) -> dict[str, Any]:
    if state.get("Blueprint"):
        return {
            "Status": "COMPLETED_FALLBACK" if state.get("UsedFallback") else "COMPLETED",
        }
    return {"Status": "FAILED", "Error": state.get("Error") or "Blueprint unavailable."}


def _route_after_validate(state: BlueprintGraphState) -> str:
    if state.get("Status") == "VALID":
        return "done"
    attempt = int(state.get("Attempt") or 0)
    max_attempts = int(state.get("MaxAttempts") or MAX_ATTEMPTS)
    if attempt < max_attempts:
        return "retry"
    return "fallback"


def build_blueprint_graph():
    graph = StateGraph(BlueprintGraphState)
    graph.add_node("generate", generate_node)
    graph.add_node("validate", validate_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("done", done_node)

    graph.add_edge(START, "generate")
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "done": "done",
            "retry": "generate",
            "fallback": "fallback",
        },
    )
    graph.add_edge("fallback", "done")
    graph.add_edge("done", END)
    return graph.compile(checkpointer=get_checkpointer())


async def run_blueprint_graph(
    payload: InterviewBlueprintRequest,
    *,
    candidate_id: str = "adhoc",
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[InterviewBlueprintResponse, dict[str, Any]]:
    """Run Agent 3 with retry + fallback. Returns (blueprint, graph_meta)."""
    graph = build_blueprint_graph()
    initial: BlueprintGraphState = {
        "CandidateID": candidate_id,
        "RequestPayload": payload.model_dump(mode="json"),
        "Attempt": 0,
        "MaxAttempts": max_attempts,
        "Status": "STARTED",
        "UsedFallback": False,
    }
    # Unique thread so a later invite/booking can generate even if an earlier
    # run left a completed or failed checkpoint on this candidate.
    result = await ainvoke_graph(
        graph,
        initial,
        config=thread_config("blueprint", f"{candidate_id}-{uuid.uuid4().hex[:12]}"),
    )
    if not result.get("Blueprint"):
        raise ValueError(result.get("Error") or "Agent 3 blueprint graph failed.")
    blueprint = InterviewBlueprintResponse.model_validate(result["Blueprint"])
    meta = {
        "status": result.get("Status"),
        "used_fallback": bool(result.get("UsedFallback")),
        "attempts": int(result.get("Attempt") or 0),
        "generation_source": result.get("GenerationSource") or blueprint.generation_source,
        "error": result.get("Error"),
    }
    return blueprint, meta
