"""LangGraph state for Agent 4 live interview turns (with Agent 6 feedback)."""

from typing import Any, TypedDict


class InterviewAgentState(TypedDict, total=False):
    CandidateID: str
    QuestionSetId: int | None
    Questions: list[dict[str, Any]]
    CurrentIndex: int
    CurrentQuestion: dict[str, Any] | None
    AnswerText: str | None
    FollowUps: list[dict[str, Any]]
    TurnHistory: list[dict[str, Any]]
    EvaluationContext: dict[str, str]
    LatestEvaluation: dict[str, Any] | None
    Agent6Feedback: str | None
    PendingFollowUpMode: bool
    Status: str
    Error: str | None
    TotalQuestions: int
    RemainingQuestions: int
    Model: str
    HrAction: str | None
    HrTargetIndex: int | None
    PlannedDurationMinutes: int | None
    SessionStartedAt: str | None
    DurationExtended: bool
    InterviewPhase: str
    CandidateQnaTurns: int
    PendingAiReply: str | None
    TurnAck: str | None
