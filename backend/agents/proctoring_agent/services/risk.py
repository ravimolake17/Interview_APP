from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FraudEvent, InterviewSession


@dataclass(frozen=True)
class RiskRule:
    weight: float
    cap: float
    confidence_scaled: bool = True


RULES: dict[str, RiskRule] = {
    "face_mismatch": RiskRule(25, 50),
    "no_face": RiskRule(8, 24),
    "multiple_faces": RiskRule(18, 36),
    "face_spoof_concern": RiskRule(12, 24),
    "gaze_violation": RiskRule(5, 20),
    "head_pose_violation": RiskRule(5, 20),
    "attention_look_away": RiskRule(7, 24),
    "voice_mismatch": RiskRule(22, 44),
    "possible_additional_speaker": RiskRule(8, 24),
    "background_conversation": RiskRule(8, 24),
    "overlapping_speech": RiskRule(10, 30),
    "first_tab_switch": RiskRule(12, 12, False),
    "tab_switch": RiskRule(12, 12, False),
    "repeated_tab_switch": RiskRule(30, 30, False),
    "camera_interruption": RiskRule(10, 20),
    "microphone_interruption": RiskRule(10, 20),
    "connection_loss": RiskRule(5, 15),
    "recording_failure": RiskRule(15, 30),
}


def event_contribution(event_type: str, confidence: float) -> float:
    rule = RULES.get(event_type, RiskRule(0, 0))
    factor = max(0.0, min(1.0, confidence)) if rule.confidence_scaled else 1.0
    return round(rule.weight * factor, 2)


def attention_contribution(state: str, confidence: float, duration_ms: int) -> float:
    """Deterministic duration/confidence contribution for coordinated attention.

    Confirmation time itself contributes no extra multiplier. Risk grows slowly
    after confirmation and is capped per event; low-confidence values are
    deliberately damped rather than treated as conclusive evidence.
    """
    confidence = max(0.0, min(1.0, float(confidence)))
    duration_seconds = max(0.0, float(duration_ms) / 1000.0)
    base = {"eye_only_look_away": 3.0, "head_only_look_away": 3.5, "combined_look_away": 5.0}.get(state, 0.0)
    duration_factor = min(2.0, max(0.5, duration_seconds / 3.0))
    return round(min(10.0, base * duration_factor * confidence), 2)


def calculate_score(events: Iterable[FraudEvent]) -> tuple[float, str, dict[str, float]]:
    totals: dict[str, float] = {}
    attention_types = {"gaze_violation", "head_pose_violation", "attention_look_away"}
    attention_total = 0.0
    for event in events:
        rule = RULES.get(event.event_type, RiskRule(0, 0))
        if event.event_type in attention_types:
            totals[event.event_type] = min(rule.cap, round(totals.get(event.event_type, 0.0) + event.risk_contribution, 2))
        else:
            totals[event.event_type] = min(rule.cap, totals.get(event.event_type, 0.0) + event.risk_contribution)
    attention_total = min(24.0, sum(value for key, value in totals.items() if key in attention_types))
    non_attention = sum(value for key, value in totals.items() if key not in attention_types)
    score = round(min(100.0, non_attention + attention_total), 2)
    if attention_total:
        totals["attention_combined_cap"] = round(attention_total, 2)
    classification = "low" if score < 25 else "moderate" if score < 55 else "high" if score < 80 else "critical"
    return score, classification, totals


def recalculate_session_risk(db: Session, session: InterviewSession) -> tuple[float, str, dict[str, float]]:
    events = db.scalars(select(FraudEvent).where(FraudEvent.session_id == session.id).order_by(FraudEvent.server_timestamp)).all()
    score, classification, totals = calculate_score(events)
    session.risk_score = score
    session.risk_classification = classification
    db.add(session)
    return score, classification, totals
