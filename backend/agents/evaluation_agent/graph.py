"""LangGraph workflow for Agent 6 answer evaluation."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.evaluation_agent.evaluator import evaluate_answer_with_llama
from core.langgraph_runtime import ainvoke_graph, get_checkpointer, thread_config

logger = logging.getLogger(__name__)


class EvaluationGraphState(TypedDict, total=False):
    CandidateID: str
    QuestionID: str
    QuestionText: str
    CandidateAnswer: str
    SkillTags: list[str]
    Context: dict[str, str]
    UseWeb: bool
    Evaluation: dict[str, Any]
    Status: str
    Error: str | None


def evaluate_node(state: EvaluationGraphState) -> dict[str, Any]:
    try:
        result = evaluate_answer_with_llama(
            question_text=str(state.get("QuestionText") or ""),
            candidate_answer=str(state.get("CandidateAnswer") or ""),
            context=dict(state.get("Context") or {}),
            skill_tags=list(state.get("SkillTags") or []),
            use_web=bool(state.get("UseWeb", True)),
        )
        return {
            "Evaluation": result.model_dump(mode="json"),
            "Status": "EVALUATED",
            "Error": None,
        }
    except Exception as exc:
        logger.exception("Agent 6 evaluate_node failed")
        return {"Status": "FAILED", "Error": str(exc), "Evaluation": {}}


def build_evaluation_graph():
    graph = StateGraph(EvaluationGraphState)
    graph.add_node("evaluate", evaluate_node)
    graph.add_edge(START, "evaluate")
    graph.add_edge("evaluate", END)
    return graph.compile(checkpointer=get_checkpointer())


class EvaluationLangGraphAgent:
    """Standalone Agent 6 facade (also invoked inline by Agent 4)."""

    def __init__(self) -> None:
        self.graph = build_evaluation_graph()

    async def evaluate(
        self,
        *,
        candidate_id: str,
        question_id: str,
        question_text: str,
        candidate_answer: str,
        context: dict[str, str],
        skill_tags: list[str] | None = None,
        use_web: bool = True,
        turn_key: str | None = None,
    ) -> dict[str, Any]:
        initial: EvaluationGraphState = {
            "CandidateID": candidate_id,
            "QuestionID": question_id,
            "QuestionText": question_text,
            "CandidateAnswer": candidate_answer,
            "SkillTags": list(skill_tags or []),
            "Context": context,
            "UseWeb": use_web,
            "Status": "STARTED",
        }
        thread = turn_key or f"{candidate_id}-{question_id or 'q'}"
        result = await ainvoke_graph(
            self.graph,
            initial,
            config=thread_config("evaluation", thread),
        )
        return dict(result)
