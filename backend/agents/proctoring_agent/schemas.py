from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field


class CandidateCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    consent: bool


class DeviceCheckIn(BaseModel):
    camera_ok: bool
    microphone_ok: bool
    details: dict[str, Any] = Field(default_factory=dict)


class SessionStartIn(BaseModel):
    client_timestamp: datetime | None = None


class TabSwitchIn(BaseModel):
    signal: str = Field(pattern="^(visibility_episode|visibilitychange|blur|pagehide|focus_loss|application_switch)$")
    episode_id: str | None = Field(default=None, min_length=8, max_length=120)
    client_timestamp: datetime | None = None
    relative_ms: int = Field(ge=0, default=0)
    visibility_state: str | None = None
    hidden_started_at: datetime | None = None
    visible_returned_at: datetime | None = None
    hidden_duration_ms: int = Field(ge=0, default=0)
    focus_lost: bool = False
    triggering_events: list[str] = Field(default_factory=list, max_length=20)


class EventIn(BaseModel):
    event_type: str = Field(min_length=2, max_length=80)
    client_timestamp: datetime | None = None
    relative_ms: int = Field(ge=0, default=0)
    start_ms: int = Field(ge=0, default=0)
    end_ms: int = Field(ge=0, default=0)
    confidence: float = Field(ge=0, le=1, default=1.0)
    measurements: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(min_length=2, max_length=2000)
    dedupe_key: str | None = Field(default=None, max_length=180)


class AdminLogin(BaseModel):
    username: str
    password: str


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(clear|confirmed_concern|needs_more_review)$")
    notes: str = Field(default="", max_length=5000)


class RecordingCompleteIn(BaseModel):
    expected_total_chunks: int = Field(ge=1, le=100000)
    segment_ids: list[str] = Field(min_length=1, max_length=1000)

