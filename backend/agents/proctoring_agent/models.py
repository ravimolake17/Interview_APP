from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base


def utcnow() -> datetime:
    try:
        from core.trusted_time import trusted_utc_now

        return trusted_utc_now()
    except Exception:
        return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid.uuid4())


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sessions: Mapped[list[InterviewSession]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="admin", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class InterviewSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="created", nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    termination_reason: Mapped[str | None] = mapped_column(String(120))
    face_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voice_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    initial_face_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    initial_voice_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voice_sentence_id: Mapped[str | None] = mapped_column(String(40))
    voice_sentence_text: Mapped[str | None] = mapped_column(Text)
    voice_sentence_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tab_switch_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_tab_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk_classification: Mapped[str] = mapped_column(String(30), default="low", nullable=False)
    current_client_elapsed_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recording_expected_chunks: Mapped[int | None] = mapped_column(Integer)
    recording_upload_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    termination_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    candidate: Mapped[Candidate] = relationship(back_populates="sessions")
    events: Mapped[list[FraudEvent]] = relationship(back_populates="session", cascade="all, delete-orphan")
    recordings: Mapped[list[Recording]] = relationship(back_populates="session", cascade="all, delete-orphan")
    chunks: Mapped[list[RecordingChunk]] = relationship(back_populates="session", cascade="all, delete-orphan")
    reports: Mapped[list[Report]] = relationship(back_populates="session", cascade="all, delete-orphan")
    voice_sentence_attempts: Mapped[list[VoiceSentenceAttempt]] = relationship(back_populates="session", cascade="all, delete-orphan")
    detector_metrics: Mapped[list[DetectorMetric]] = relationship(back_populates="session", cascade="all, delete-orphan")


class DeviceCheck(Base):
    __tablename__ = "device_checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    camera_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    microphone_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BiometricBaseline(Base):
    __tablename__ = "biometric_baselines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    engine: Mapped[str] = mapped_column(String(100), nullable=False)
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("session_id", "kind", name="uq_baseline_session_kind"),)




class AttentionCalibration(Base):
    __tablename__ = "attention_calibrations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    pose_calibrated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gaze_calibrated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    samples: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AttentionBaseline(Base):
    """Passive in-interview neutral baseline.

    The older ``attention_calibrations`` table remains untouched for historical
    compatibility, but new sessions use this table and require no candidate
    calibration actions.
    """

    __tablename__ = "attention_baselines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="collecting", nullable=False)
    accepted_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    baseline_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    neutral_yaw: Mapped[float | None] = mapped_column(Float)
    neutral_pitch: Mapped[float | None] = mapped_column(Float)
    neutral_roll: Mapped[float | None] = mapped_column(Float)
    neutral_gaze_x: Mapped[float | None] = mapped_column(Float)
    neutral_gaze_y: Mapped[float | None] = mapped_column(Float)
    started_relative_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ready_relative_ms: Mapped[int | None] = mapped_column(Integer)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    technical_warning: Mapped[str | None] = mapped_column(String(255))
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class VerificationAttempt(Base):
    __tablename__ = "verification_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    similarity: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class VoiceSentenceAttempt(Base):
    __tablename__ = "voice_sentence_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    sentence_id: Mapped[str] = mapped_column(String(40), nullable=False)
    sentence_text: Mapped[str] = mapped_column(Text, nullable=False)
    recognized_transcript: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recognition_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    word_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    completion_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(120))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    session: Mapped[InterviewSession] = relationship(back_populates="voice_sentence_attempts")
    __table_args__ = (Index("ix_voice_sentence_session_stage_time", "session_id", "stage", "created_at"),)


class DetectorMetric(Base):
    __tablename__ = "detector_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    detector: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    inference_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    api_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dropped_stale: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="ok", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    session: Mapped[InterviewSession] = relationship(back_populates="detector_metrics")
    __table_args__ = (Index("ix_detector_metric_session_detector_time", "session_id", "detector", "created_at"),)


class FraudEvent(Base):
    __tablename__ = "fraud_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(30), default="confirmed", nullable=False)
    client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    relative_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    risk_contribution: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(180), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped[InterviewSession] = relationship(back_populates="events")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="event", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_event_session_type_time", "session_id", "event_type", "server_timestamp"),)


class RecordingChunk(Base):
    __tablename__ = "recording_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_id: Mapped[str] = mapped_column(String(80), default="segment-0", nullable=False)
    segment_sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    session: Mapped[InterviewSession] = relationship(back_populates="chunks")
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_chunk_session_sequence"),
        UniqueConstraint("session_id", "segment_id", "segment_sequence", name="uq_chunk_session_segment_sequence"),
        Index("ix_chunk_session_segment", "session_id", "segment_id", "segment_sequence"),
    )


class Recording(Base):
    __tablename__ = "recordings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="full_interview", nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    video_codec: Mapped[str | None] = mapped_column(String(40))
    audio_codec: Mapped[str | None] = mapped_column(String(40))
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    validation_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    session: Mapped[InterviewSession] = relationship(back_populates="recordings")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_id: Mapped[str] = mapped_column(ForeignKey("fraud_events.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    creation_status: Mapped[str] = mapped_column(String(30), default="ready", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    event: Mapped[FraudEvent] = relationship(back_populates="evidence")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    json_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    json_path: Mapped[str | None] = mapped_column(Text)
    html_path: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    # ``checksum`` is retained for backward compatibility and mirrors the HTML checksum.
    checksum: Mapped[str | None] = mapped_column(String(64))
    json_checksum: Mapped[str | None] = mapped_column(String(64))
    html_checksum: Mapped[str | None] = mapped_column(String(64))
    pdf_checksum: Mapped[str | None] = mapped_column(String(64))
    integrity_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    session: Mapped[InterviewSession] = relationship(back_populates="reports")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    admin_id: Mapped[str] = mapped_column(ForeignKey("admin_users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(36), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SystemError(Base):
    __tablename__ = "system_errors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    component: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
