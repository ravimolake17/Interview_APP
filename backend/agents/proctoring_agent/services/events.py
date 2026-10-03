from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import FraudEvent, InterviewSession
from .risk import event_contribution, recalculate_session_risk


DEFAULT_COOLDOWNS = {
    "face_mismatch": 10,
    "no_face": 8,
    "multiple_faces": 8,
    "face_spoof_concern": 15,
    "gaze_violation": 8,
    "head_pose_violation": 8,
    "attention_look_away": 8,
    "voice_mismatch": 12,
    "possible_additional_speaker": 12,
    "background_conversation": 12,
    "overlapping_speech": 12,
    "camera_interruption": 5,
    "microphone_interruption": 5,
    "connection_loss": 5,
    "recording_failure": 10,
}


def create_event(
    db: Session,
    session: InterviewSession,
    *,
    event_type: str,
    confidence: float,
    explanation: str,
    relative_ms: int = 0,
    start_ms: int | None = None,
    end_ms: int | None = None,
    measurements: dict[str, Any] | None = None,
    client_timestamp: datetime | None = None,
    dedupe_key: str | None = None,
    force: bool = False,
    state: str = "confirmed",
    risk_contribution: float | None = None,
) -> tuple[FraudEvent, bool]:
    now = datetime.now(timezone.utc)
    if not force:
        cooldown = get_settings().event_cooldowns().get(event_type, DEFAULT_COOLDOWNS.get(event_type, 2))
        recent = db.scalar(
            select(FraudEvent)
            .where(FraudEvent.session_id == session.id, FraudEvent.event_type == event_type)
            .order_by(desc(FraudEvent.server_timestamp))
            .limit(1)
        )
        if recent:
            recent_at = recent.server_timestamp if recent.server_timestamp.tzinfo else recent.server_timestamp.replace(tzinfo=timezone.utc)
        if recent and (now - recent_at).total_seconds() < cooldown:
            if dedupe_key is None or recent.dedupe_key == dedupe_key:
                return recent, False
    start = relative_ms if start_ms is None else start_ms
    end = relative_ms if end_ms is None else end_ms
    event = FraudEvent(
        session_id=session.id,
        event_type=event_type,
        state=state,
        client_timestamp=client_timestamp,
        server_timestamp=now,
        relative_ms=relative_ms,
        start_ms=start,
        end_ms=end,
        duration_ms=max(0, end - start),
        confidence=max(0.0, min(1.0, confidence)),
        measurements=measurements or {},
        risk_contribution=event_contribution(event_type, confidence) if risk_contribution is None else max(0.0, float(risk_contribution)),
        explanation=explanation,
        dedupe_key=dedupe_key,
    )
    db.add(event)
    db.flush()
    recalculate_session_risk(db, session)
    return event, True
