"""LangGraph workflow for Agent 7 HR recommendation."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.recommendation_agent.report_builder import build_recommendation_report
from core.langgraph_runtime import ainvoke_graph, get_checkpointer, thread_config

logger = logging.getLogger(__name__)


class RecommendationGraphState(TypedDict, total=False):
    CandidateID: str
    Evidence: dict[str, Any]
    Report: dict[str, Any]
    Status: str
    Error: str | None


def recommend_node(state: RecommendationGraphState) -> dict[str, Any]:
    try:
        report = build_recommendation_report(dict(state.get("Evidence") or {}))
        return {
            "Report": report.model_dump(mode="json"),
            "Status": "COMPLETED",
            "Error": None,
        }
    except Exception as exc:
        logger.exception("Agent 7 recommend_node failed")
        return {"Status": "FAILED", "Error": str(exc), "Report": {}}


def build_recommendation_graph():
    graph = StateGraph(RecommendationGraphState)
    graph.add_node("recommend", recommend_node)
    graph.add_edge(START, "recommend")
    graph.add_edge("recommend", END)
    return graph.compile(checkpointer=get_checkpointer())


class RecommendationLangGraphAgent:
    """Agent 7 facade — final HR report grounded in similar past cases."""

    def __init__(self) -> None:
        self.graph = build_recommendation_graph()

    async def generate(self, *, candidate_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
        initial: RecommendationGraphState = {
            "CandidateID": candidate_id,
            "Evidence": evidence,
            "Status": "STARTED",
        }
        result = await ainvoke_graph(
            self.graph,
            initial,
            config=thread_config("recommendation", candidate_id),
        )
        return dict(result)
