"""Agent 7 — HR recommendation from similar past cases."""

from agents.recommendation_agent.recommender import recommend_from_similar_cases
from agents.recommendation_agent.report_builder import build_recommendation_report, decision_from_scores

__all__ = [
    "recommend_from_similar_cases",
    "build_recommendation_report",
    "decision_from_scores",
]
