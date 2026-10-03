from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Evidence, FraudEvent, Recording
from .audit import record_error
from .recordings import ffprobe, sha256_file


def save_screenshot(db: Session, event: FraudEvent, image_bytes: bytes) -> Evidence:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ValueError("invalid screenshot image")
    if float(image.std()) < 1.0:
        raise ValueError("blank screenshot rejected")
    directory = get_settings().resolved_storage_dir / "evidence" / "screenshots"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{event.id}.jpg"
    if not cv2.imwrite(str(path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 90]):
        raise RuntimeError("failed to write screenshot")
    evidence = Evidence(
        event_id=event.id,
        kind="screenshot",
        path=str(path),
        mime_type="image/jpeg",
        checksum=sha256_file(path),
        size_bytes=path.stat().st_size,
    )
    db.add(evidence)
    db.flush()
    return evidence


def save_audio(db: Session, event: FraudEvent, audio_bytes: bytes, suffix: str = ".webm") -> Evidence:
    if len(audio_bytes) < 128:
        raise ValueError("audio evidence too small")
    directory = get_settings().resolved_storage_dir / "evidence" / "audio"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{event.id}{suffix}"
    path.write_bytes(audio_bytes)
    evidence = Evidence(
        event_id=event.id,
        kind="audio",
        path=str(path),
        mime_type="audio/webm" if suffix == ".webm" else "audio/wav",
        checksum=sha256_file(path),
        size_bytes=path.stat().st_size,
    )
    db.add(evidence)
    db.flush()
    return evidence


def save_metadata(db: Session, event: FraudEvent, payload: dict) -> Evidence:
    """Persist browser/server event metadata as reviewable evidence.

    Tab/application visibility events cannot capture the external application by
    browser design. A checksum-protected JSON record is therefore the primary
    immediate evidence, while a candidate-facing video clip can be derived from
    the completed interview recording during finalization.
    """
    directory = get_settings().resolved_storage_dir / "evidence" / "metadata"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{event.id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    evidence = Evidence(
        event_id=event.id,
        kind="metadata",
        path=str(path),
        mime_type="application/json",
        checksum=sha256_file(path),
        size_bytes=path.stat().st_size,
    )
    db.add(evidence)
    db.flush()
    return evidence


def extract_event_clip(db: Session, event: FraudEvent, recording: Recording) -> Evidence | None:
    settings = get_settings()
    source = Path(recording.path)
    if not source.exists():
        record_error(
            db,
            "evidence_clip",
            "Event video evidence could not be created because the finalized recording is missing",
            session_id=event.session_id,
            details={"event_id": event.id, "recording_id": recording.id, "recording_path": str(source)},
        )
        return None
    event_start_ms = event.start_ms if event.start_ms is not None else max(0, event.relative_ms - event.duration_ms)
    event_end_ms = event.end_ms if event.end_ms is not None else event.relative_ms
    event_seconds = max((event_end_ms - event_start_ms) / 1000.0, event.duration_ms / 1000.0, 1.0)
    start = max(0.0, event_start_ms / 1000.0 - settings.evidence_pre_seconds)
    duration = settings.evidence_pre_seconds + event_seconds + settings.evidence_post_seconds
    directory = settings.resolved_storage_dir / "evidence" / "video"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{event.id}.mp4"
    command = [
        settings.ffmpeg_path,
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "25",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        record_error(
            db,
            "evidence_clip",
            "FFmpeg timed out while creating event video evidence",
            session_id=event.session_id,
            details={"event_id": event.id, "recording_id": recording.id, "timeout_seconds": exc.timeout},
        )
        return None
    if result.returncode != 0 or not path.exists() or path.stat().st_size == 0:
        record_error(
            db,
            "evidence_clip",
            "FFmpeg failed to create a non-empty event video clip",
            session_id=event.session_id,
            details={
                "event_id": event.id,
                "recording_id": recording.id,
                "returncode": result.returncode,
                "stderr_tail": result.stderr[-2000:],
                "requested_start_seconds": start,
                "requested_duration_seconds": duration,
            },
        )
        path.unlink(missing_ok=True)
        return None
    validation = ffprobe(path)
    if not validation.get("ok") or not validation.get("has_video"):
        record_error(
            db,
            "evidence_clip",
            "Event video clip failed FFprobe playback validation",
            session_id=event.session_id,
            details={"event_id": event.id, "recording_id": recording.id, "validation": validation},
        )
    evidence = Evidence(
        event_id=event.id,
        kind="video",
        path=str(path),
        mime_type="video/mp4",
        checksum=sha256_file(path),
        size_bytes=path.stat().st_size,
        duration_seconds=validation.get("duration"),
        creation_status="ready" if validation.get("has_video") else "invalid",
    )
    db.add(evidence)
    db.flush()
    return evidence
