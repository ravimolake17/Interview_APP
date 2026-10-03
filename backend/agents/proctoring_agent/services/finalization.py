from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FraudEvent, InterviewSession, Recording, RecordingChunk
from .evidence import extract_event_clip
from .recordings import finalize_recording
from .reports import generate_report


def finalize_session_artifacts(db: Session, session: InterviewSession) -> dict[str, object]:
    result: dict[str, object] = {"recording": None, "evidence_clips_created": 0, "evidence_clips_failed": 0, "report": None}
    # A session can end while a duration-confirmed detector episode is still
    # active. Freeze it as a confirmed audit event at the final client elapsed
    # time so reports never contain an indefinitely open event.
    final_elapsed = max(0, int(session.current_client_elapsed_ms or 0))
    active_events = db.scalars(
        select(FraudEvent).where(FraudEvent.session_id == session.id, FraudEvent.state == "active")
    ).all()
    for event in active_events:
        event.state = "confirmed"
        event.end_ms = max(int(event.end_ms or 0), final_elapsed, int(event.relative_ms or 0))
        event.duration_ms = max(int(event.duration_ms or 0), event.end_ms - int(event.start_ms or 0))
        db.add(event)
    db.flush()
    chunks = db.scalars(select(RecordingChunk).where(RecordingChunk.session_id == session.id)).all()
    recording: Recording | None = None
    if chunks:
        recording = finalize_recording(db, session.id)
        result["recording"] = recording.id
        events = db.scalars(select(FraudEvent).where(FraudEvent.session_id == session.id).order_by(FraudEvent.relative_ms)).all()
        count = 0
        failed = 0
        for event in events:
            existing = any(item.kind == "video" and item.creation_status == "ready" for item in event.evidence)
            if not existing:
                if extract_event_clip(db, event, recording) is not None:
                    count += 1
                else:
                    failed += 1
        result["evidence_clips_created"] = count
        result["evidence_clips_failed"] = failed
    report = generate_report(db, session.id)
    result["report"] = report.id
    return result
