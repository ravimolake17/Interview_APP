"""LangGraph state definition for the Interview Scheduler Agent."""

from typing import Any, TypedDict


class SchedulerState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes."""

    # Candidate info
    Candidate: dict[str, Any]
    CandidateID: str
    Email: str
    CandidateName: str
    ResumeScore: float
    JobPosition: str
    CompanyName: str
    CompanyCode: str

    # Scheduling
    Token: str
    SchedulingLink: str
    SelectedSlot: dict[str, Any] | None
    SlotId: int | None

    # In-app interview room
    MeetingLink: str
    JoinLink: str
    JoinToken: str
    CalendarEventID: str

    # Workflow status
    Status: str
    Error: str | None
    ThreadId: str
