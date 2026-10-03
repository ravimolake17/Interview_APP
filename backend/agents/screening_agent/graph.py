"""
Agent 1 LangGraph screening pipeline (enterprise orchestration wrapper).

START → evaluate → END

Wraps the existing deterministic ATS services so Agent 1 shares the same
LangGraph checkpoint runtime as Agents 2 and 4 (durable per-job threads).
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.screening_agent.schemas.ats import EvaluationResponse, ParsedJD
from agents.screening_agent.schemas.resume import ParsedResume
from agents.screening_agent.services.evaluation_service import evaluate_candidate
from core.langgraph_runtime import ainvoke_graph, get_checkpointer, thread_config

logger = logging.getLogger(__name__)


class ScreeningState(TypedDict, total=False):
    JobId: str
    ParsedResume: dict[str, Any]
    JdText: str | None
    ParsedJd: dict[str, Any] | None
    ResumeFilename: str | None
    Evaluation: dict[str, Any]
    Status: str
    Error: str | None


def evaluate_node(state: ScreeningState) -> dict[str, Any]:
    try:
        resume = ParsedResume.model_validate(state["ParsedResume"])
        parsed_jd = (
            ParsedJD.model_validate(state["ParsedJd"]) if state.get("ParsedJd") else None
        )
        evaluation = evaluate_candidate(
            resume,
            jd_text=state.get("JdText"),
            parsed_jd=parsed_jd,
            resume_original_filename=state.get("ResumeFilename"),
        )
        return {
            "Evaluation": evaluation.model_dump(mode="json"),
            "Status": "COMPLETED",
            "Error": None,
        }
    except Exception as exc:
        logger.exception("Screening graph evaluate failed for job %s", state.get("JobId"))
        return {"Status": "FAILED", "Error": str(exc)}


def build_screening_graph():
    graph = StateGraph(ScreeningState)
    graph.add_node("evaluate", evaluate_node)
    graph.add_edge(START, "evaluate")
    graph.add_edge("evaluate", END)
    return graph.compile(checkpointer=get_checkpointer())


async def run_screening_graph(
    *,
    job_id: str,
    parsed_resume: ParsedResume | dict[str, Any],
    jd_text: str | None = None,
    parsed_jd: ParsedJD | None = None,
    resume_original_filename: str | None = None,
) -> EvaluationResponse:
    """Execute Agent 1 evaluation through LangGraph with durable checkpoints."""
    graph = build_screening_graph()
    resume_payload = (
        parsed_resume.model_dump(mode="json")
        if isinstance(parsed_resume, ParsedResume)
        else parsed_resume
    )
    initial: ScreeningState = {
        "JobId": str(job_id),
        "ParsedResume": resume_payload,
        "JdText": jd_text,
        "ParsedJd": parsed_jd.model_dump(mode="json") if parsed_jd else None,
        "ResumeFilename": resume_original_filename,
        "Status": "STARTED",
    }
    result = await ainvoke_graph(
        graph,
        initial,
        config=thread_config("screening", str(job_id)),
    )
    if result.get("Status") == "FAILED":
        raise ValueError(result.get("Error") or "Screening graph failed.")
    return EvaluationResponse.model_validate(result["Evaluation"])
