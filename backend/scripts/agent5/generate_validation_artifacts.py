from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "docs" / "validation"
RUNTIME = VALIDATION / "runtime_media"
shutil.rmtree(RUNTIME, ignore_errors=True)
RUNTIME.mkdir(parents=True, exist_ok=True)
os.environ.update(
    {
        "AGENT5_ROOT": str(ROOT),
        "AGENT5_STORAGE_DIR": str(RUNTIME),
        "AGENT5_DATABASE_URL": f"sqlite:///{(RUNTIME / 'validation.db').as_posix()}",
        "AGENT5_SECRET_KEY": "agent5-validation-only-secret-not-for-deployment",
        "AGENT5_TEST_MODE": "1",
    }
)
sys.path.insert(0, str(ROOT / "backend"))

from agents.proctoring_agent.db import Base, SessionLocal, engine  # noqa: E402
from agents.proctoring_agent.models import Candidate, InterviewSession  # noqa: E402
from agents.proctoring_agent.services.events import create_event  # noqa: E402
from agents.proctoring_agent.services.evidence import extract_event_clip, save_audio, save_screenshot  # noqa: E402
from agents.proctoring_agent.services.recordings import finalize_recording, ingest_chunk, mark_recording_upload_complete  # noqa: E402
from agents.proctoring_agent.services.reports import generate_report  # noqa: E402


def generate_media(path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=12:duration=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=330:sample_rate=48000:duration=30",
        "-c:v",
        "libvpx-vp9",
        "-deadline",
        "realtime",
        "-cpu-used",
        "8",
        "-b:v",
        "220k",
        "-c:a",
        "libopus",
        "-b:a",
        "40k",
        "-shortest",
        str(path),
    ]
    subprocess.run(command, check=True, capture_output=True)


def generate_audio(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=240:sample_rate=16000:duration=4", "-ac", "1", str(path)],
        check=True,
        capture_output=True,
    )


def screenshot_bytes() -> bytes:
    image = np.zeros((360, 640, 3), dtype=np.uint8)
    for y in range(image.shape[0]):
        image[y, :, :] = (35 + y // 4, 55 + y // 5, 90 + y // 6)
    cv2.putText(image, "Agent5 validation evidence", (65, 165), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (245, 245, 245), 2, cv2.LINE_AA)
    cv2.putText(image, "Synthetic fixture - not a real candidate", (45, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 230, 255), 2, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError("failed to encode validation screenshot")
    return encoded.tobytes()


def main() -> int:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    source = RUNTIME / "validation_source.webm"
    audio_source = RUNTIME / "validation_audio.wav"
    generate_media(source)
    generate_audio(audio_source)
    screenshot = screenshot_bytes()
    audio = audio_source.read_bytes()

    event_types = [
        "face_mismatch",
        "no_face",
        "multiple_faces",
        "face_spoof_concern",
        "gaze_violation",
        "head_pose_violation",
        "voice_mismatch",
        "possible_additional_speaker",
        "background_conversation",
        "overlapping_speech",
        "first_tab_switch",
        "repeated_tab_switch",
        "camera_interruption",
        "microphone_interruption",
        "connection_loss",
        "recording_failure",
    ]
    audio_types = {"voice_mismatch", "possible_additional_speaker", "background_conversation", "overlapping_speech", "microphone_interruption"}
    with SessionLocal() as db:
        candidate = Candidate(full_name="Synthetic Validation Candidate", email="validation@example.invalid")
        started = datetime.now(timezone.utc) - timedelta(seconds=30)
        session = InterviewSession(
            candidate=candidate,
            status="terminated",
            started_at=started,
            ended_at=started + timedelta(seconds=30),
            termination_reason="repeated_tab_switch",
            face_enrolled=True,
            voice_enrolled=True,
            initial_face_verified=True,
            initial_voice_verified=True,
            tab_switch_count=2,
        )
        db.add_all([candidate, session])
        db.flush()
        ingest_chunk(
            db,
            session.id,
            0,
            source.read_bytes(),
            "video/webm",
            None,
            segment_id="segment-0",
            segment_sequence=0,
            is_final=True,
            duration_ms=30_000,
        )
        upload_status = mark_recording_upload_complete(db, session, expected_total=1, segment_ids=["segment-0"])
        if not upload_status.get("complete"):
            raise RuntimeError(f"validation fixture upload did not complete: {upload_status}")
        recording = finalize_recording(db, session.id)
        rows = []
        for index, event_type in enumerate(event_types):
            relative_ms = 1000 + index * 2000
            event, _ = create_event(
                db,
                session,
                event_type=event_type,
                confidence=0.88,
                explanation=f"Synthetic validation event for {event_type}; not a detector accuracy result.",
                relative_ms=relative_ms,
                start_ms=max(0, relative_ms - 500),
                end_ms=relative_ms + 1200,
                measurements={"synthetic_fixture": True, "purpose": "media/database/report validation"},
                dedupe_key=f"validation:{event_type}",
                force=True,
            )
            evidence = [save_screenshot(db, event, screenshot)]
            if event_type in audio_types:
                evidence.append(save_audio(db, event, audio, suffix=".wav"))
            clip = extract_event_clip(db, event, recording)
            if clip:
                evidence.append(clip)
            rows.append(
                {
                    "event_type": event_type,
                    "event_id": event.id,
                    "relative_seconds": relative_ms / 1000,
                    "risk_contribution": event.risk_contribution,
                    "evidence": [
                        {
                            "kind": item.kind,
                            "filename": Path(item.path).name,
                            "size_bytes": item.size_bytes,
                            "duration_seconds": item.duration_seconds,
                            "status": item.creation_status,
                            "exists": Path(item.path).exists(),
                        }
                        for item in evidence
                    ],
                }
            )
        report = generate_report(db, session.id)
        db.commit()
        recording_row = {
            "session_id": session.id,
            "filename": Path(recording.path).name,
            "file_size": recording.size_bytes,
            "duration": recording.duration_seconds,
            "video_codec": recording.video_codec,
            "audio_codec": recording.audio_codec,
            "ffprobe_status": recording.validation_status,
            "playback_status": "range-streaming integration test passed; manual browser playback not run in build container",
            "checksum": recording.checksum,
        }
        result = {
            "scope": "synthetic FFmpeg fixture validates media/database/evidence/report plumbing; it is not detector accuracy validation",
            "recording": recording_row,
            "evidence": rows,
            "report": {
                "id": report.id,
                "html": str(Path(report.html_path).relative_to(ROOT)),
                "pdf": str(Path(report.pdf_path).relative_to(ROOT)),
                "checksum": report.checksum,
            },
        }
    (VALIDATION / "media_evidence_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# Synthetic Media and Evidence Validation",
        "",
        result["scope"],
        "",
        "## Recording validation",
        "",
        "| Session ID | Filename | Size | Duration | Video | Audio | FFprobe | Playback |",
        "|---|---|---:|---:|---|---|---|---|",
        f"| {recording_row['session_id']} | {recording_row['filename']} | {recording_row['file_size']} | {recording_row['duration']:.3f}s | {recording_row['video_codec']} | {recording_row['audio_codec']} | {recording_row['ffprobe_status']} | {recording_row['playback_status']} |",
        "",
        "## Evidence validation",
        "",
        "| Event | Time | Screenshot | Video | Audio | Risk |",
        "|---|---:|---|---|---|---:|",
    ]
    for row in rows:
        by_kind = {item["kind"]: item for item in row["evidence"]}
        value = lambda kind: "ready" if by_kind.get(kind, {}).get("exists") and by_kind.get(kind, {}).get("status") == "ready" else "n/a"
        lines.append(f"| {row['event_type']} | {row['relative_seconds']:.1f}s | {value('screenshot')} | {value('video')} | {value('audio')} | {row['risk_contribution']:.2f} |")
    (VALIDATION / "MEDIA_EVIDENCE_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
