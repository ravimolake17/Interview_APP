"""Schemas for Agent 4 interview runtime."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Difficulty = Literal["easy", "medium", "hard"]
SessionStatus = Literal[
    "READY",
    "QUESTIONS_GENERATED",
    "SPEAK_PREPARING",
    "SPEAK_PARTIAL",
    "SPEAK_READY",
    "IN_PROGRESS",
    "COMPLETED",
]


class InterviewQuestion(BaseModel):
    id: str
    order: int = Field(ge=1)
    category_id: str
    category_name: str
    difficulty: Difficulty
    question_text: str
    intent: str = ""
    follow_up_hints: list[str] = Field(default_factory=list)
    estimated_seconds: int = Field(default=120, ge=30, le=600)
    skill_tags: list[str] = Field(default_factory=list)
    audio_ready: bool = False


class FollowUpQuestion(BaseModel):
    id: str
    parent_question_id: str
    question_text: str
    reason: str = ""
    difficulty: Difficulty = "medium"


class QuestionSetResponse(BaseModel):
    id: int
    candidate_id: str
    blueprint_id: int | None = None
    status: SessionStatus
    candidate_level: str | None = None
    total_questions: int = 0
    total_duration_minutes: int | None = None
    questions: list[InterviewQuestion] = Field(default_factory=list)
    tts_ready: bool = False
    tts_ready_count: int = 0
    tts_preparing: bool = False
    stt_provider: str = "whisper"
    capabilities: list[str] = Field(
        default_factory=lambda: [
            "whisper_stt",
            "indic_parler_tts",
            "tts_audio_cache",
            "question_generation",
            "follow_up_questions",
        ]
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GenerateQuestionsRequest(BaseModel):
    force: bool = False
    prepare_tts: bool = True


class ManualQuestionRequest(BaseModel):
    question_text: str = Field(min_length=8, max_length=600)
    insert_at: int | None = Field(default=None, ge=1, le=200)
    category_id: str | None = Field(default=None, max_length=80)
    category_name: str | None = Field(default=None, max_length=120)
    difficulty: Difficulty = "medium"
    skill_tags: list[str] = Field(default_factory=list)
    estimated_seconds: int = Field(default=120, ge=30, le=600)
    prepare_tts: bool = True


class FollowUpRequest(BaseModel):
    question_id: str
    question_text: str
    candidate_answer: str = Field(min_length=1, max_length=8000)
    max_followups: int = Field(default=2, ge=1, le=5)


class FollowUpResponse(BaseModel):
    parent_question_id: str
    transcript_excerpt: str
    follow_ups: list[FollowUpQuestion]


class TranscriptCorrection(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    from_text: str = Field(alias="from")
    to: str
    reason: str = ""


class TranscribeResponse(BaseModel):
    text: str
    raw_text: str | None = None
    language: str | None = None
    duration_seconds: float | None = None
    provider: str = "groq_whisper"
    model: str = "whisper-large-v3"
    resume_corrected: bool = False
    partial: bool = False
    corrections: list[TranscriptCorrection] = Field(default_factory=list)


class InterviewAgentStatusResponse(BaseModel):
    candidate_id: str
    blueprint_ready: bool
    questions_ready: bool
    speak_ready: bool = False
    question_set: QuestionSetResponse | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    langgraph_session: dict[str, Any] | None = None
    question_edits: dict[str, Any] = Field(default_factory=dict)


class InterviewSessionStartRequest(BaseModel):
    force_questions: bool = False


class InterviewSessionAnswerRequest(BaseModel):
    answer_text: str = Field(min_length=1, max_length=8000)


class InterviewSessionStateResponse(BaseModel):
    candidate_id: str
    status: str
    current_question: dict[str, Any] | None = None
    current_index: int = 0
    total_questions: int = 0
    remaining_questions: int = 0
    follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    turn_history: list[dict[str, Any]] = Field(default_factory=list)
    latest_evaluation: dict[str, Any] | None = None
    agent6_feedback: str | None = None
    model: str | None = None
    error: str | None = None
    langgraph: bool = True
    welcome_message: str | None = None
    questions: list[dict[str, Any]] = Field(default_factory=list)
    planned_duration_minutes: int | None = None
    elapsed_seconds: int = 0
    duration_extended: bool = False
    interview_phase: str | None = None
    turn_ack: str | None = None


class SpeakRequest(BaseModel):
    text: str | None = Field(default=None, max_length=4000)
    question_id: str | None = None
    voice: str | None = Field(default="female", description="female | male")


class McqOption(BaseModel):
    id: str
    text: str


class McqQuestionPublic(BaseModel):
    id: str
    order: int = 0
    question_text: str = ""
    options: list[McqOption] = Field(default_factory=list)


class McqStateResponse(BaseModel):
    status: str
    total_questions: int = 0
    current_index: int = 0
    remaining_seconds: int = 0
    duration_seconds: int = 0
    current_question: McqQuestionPublic | None = None
    intro_message: str = ""
    rules_message: str = ""
    oral_rules_message: str = ""
    result: dict[str, int] | None = None


class McqAnswerRequest(BaseModel):
    option_id: str | None = Field(default=None, max_length=8)
    skip: bool = False
    question_id: str | None = Field(default=None, max_length=32)


class McqFinishRequest(BaseModel):
    timed_out: bool = False
