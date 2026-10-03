from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import InterviewSession, Recording, RecordingChunk


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_session_dir(session_id: str) -> Path:
    if not session_id.replace("-", "").isalnum():
        raise ValueError("invalid session identifier")
    path = get_settings().resolved_storage_dir / "chunks" / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_segment_id(segment_id: str) -> str:
    value = segment_id.strip()
    if not value or len(value) > 80 or not value.replace("-", "").replace("_", "").isalnum():
        raise ValueError("invalid recording segment identifier")
    return value


def ingest_chunk(
    db: Session,
    session_id: str,
    sequence: int,
    data: bytes,
    mime_type: str,
    checksum: str | None,
    *,
    segment_id: str = "segment-0",
    segment_sequence: int = 0,
    is_final: bool = False,
    captured_at: datetime | None = None,
    duration_ms: int | None = None,
) -> tuple[RecordingChunk, bool]:
    if sequence < 0 or segment_sequence < 0:
        raise ValueError("recording sequence values must be non-negative")
    segment_id = _safe_segment_id(segment_id)
    actual = hashlib.sha256(data).hexdigest()
    if checksum and checksum.lower() != actual:
        raise ValueError("chunk checksum mismatch")
    existing = db.scalar(select(RecordingChunk).where(RecordingChunk.session_id == session_id, RecordingChunk.sequence == sequence))
    if existing:
        if existing.checksum != actual:
            raise ValueError("sequence already exists with different checksum")
        if existing.segment_id != segment_id or existing.segment_sequence != segment_sequence:
            raise ValueError("sequence already exists with different segment metadata")
        if is_final and not existing.is_final:
            existing.is_final = True
        return existing, False
    duplicate_segment = db.scalar(
        select(RecordingChunk).where(
            RecordingChunk.session_id == session_id,
            RecordingChunk.segment_id == segment_id,
            RecordingChunk.segment_sequence == segment_sequence,
        )
    )
    if duplicate_segment:
        raise ValueError("segment sequence already exists with a different global sequence")
    ext = ".webm" if "webm" in mime_type else ".mp4" if "mp4" in mime_type else ".bin"
    path = safe_session_dir(session_id) / f"{segment_id}_{segment_sequence:08d}_{sequence:08d}{ext}"
    path.write_bytes(data)
    record = RecordingChunk(
        session_id=session_id,
        sequence=sequence,
        segment_id=segment_id,
        segment_sequence=segment_sequence,
        is_final=is_final,
        captured_at=captured_at,
        duration_ms=duration_ms,
        checksum=actual,
        path=str(path),
        size_bytes=len(data),
        mime_type=mime_type[:100],
    )
    db.add(record)
    db.flush()
    return record, True


def recording_status_payload(db: Session, session: InterviewSession, expected_total: int | None = None) -> dict[str, Any]:
    chunks = db.scalars(select(RecordingChunk).where(RecordingChunk.session_id == session.id).order_by(RecordingChunk.sequence)).all()
    sequences = [item.sequence for item in chunks]
    upper = expected_total if expected_total is not None else session.recording_expected_chunks
    if upper is None:
        upper = (max(sequences) + 1) if sequences else 0
    missing = sorted(set(range(0, upper)) - set(sequences))
    unexpected_sequences = sorted(sequence for sequence in sequences if sequence >= upper)
    segment_map: dict[str, list[RecordingChunk]] = defaultdict(list)
    for chunk in chunks:
        segment_map[chunk.segment_id].append(chunk)
    segments = []
    for segment_id, items in sorted(segment_map.items(), key=lambda pair: min(item.sequence for item in pair[1])):
        items.sort(key=lambda item: item.segment_sequence)
        segment_sequences = [item.segment_sequence for item in items]
        segment_missing = sorted(set(range(0, max(segment_sequences) + 1)) - set(segment_sequences)) if segment_sequences else []
        premature_final_sequences = [item.segment_sequence for item in items[:-1] if item.is_final]
        segments.append(
            {
                "segment_id": segment_id,
                "sequences": segment_sequences,
                "missing_sequences": segment_missing,
                "final_received": bool(items and items[-1].is_final),
                "premature_final_sequences": premature_final_sequences,
                "chunk_count": len(items),
            }
        )
    return {
        "acknowledged_sequences": sequences,
        "missing_sequences": missing,
        "unexpected_sequences": unexpected_sequences,
        "expected_total_chunks": upper,
        "total_bytes": sum(item.size_bytes for item in chunks),
        "segments": segments,
        "upload_complete": session.recording_upload_complete,
    }


def mark_recording_upload_complete(db: Session, session: InterviewSession, expected_total: int, segment_ids: list[str]) -> dict[str, Any]:
    clean_ids = list(dict.fromkeys(_safe_segment_id(value) for value in segment_ids))
    status = recording_status_payload(db, session, expected_total)
    by_id = {item["segment_id"]: item for item in status["segments"]}
    missing_segments = [segment_id for segment_id in clean_ids if segment_id not in by_id]
    unclosed_segments = [segment_id for segment_id in clean_ids if segment_id in by_id and not by_id[segment_id]["final_received"]]
    premature_final_segments = [segment_id for segment_id in clean_ids if segment_id in by_id and by_id[segment_id]["premature_final_sequences"]]
    unexpected_segments = [segment_id for segment_id in by_id if segment_id not in clean_ids]
    complete = (
        not status["missing_sequences"]
        and not status["unexpected_sequences"]
        and not missing_segments
        and not unclosed_segments
        and not premature_final_segments
        and not unexpected_segments
    )
    session.recording_expected_chunks = expected_total
    session.recording_upload_complete = complete
    db.add(session)
    status.update(
        {
            "complete": complete,
            "missing_segments": missing_segments,
            "unclosed_segments": unclosed_segments,
            "premature_final_segments": premature_final_segments,
            "unexpected_segments": unexpected_segments,
        }
    )
    return status


def ffprobe(path: Path) -> dict[str, Any]:
    settings = get_settings()
    command = [settings.ffprobe_path, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    if completed.returncode != 0:
        return {"ok": False, "error": completed.stderr.strip(), "returncode": completed.returncode}
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid ffprobe JSON: {exc}"}
    streams = parsed.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = parsed.get("format", {})
    duration = float(fmt.get("duration") or 0.0)
    return {
        "ok": bool(video and audio and duration > 0),
        "duration": duration,
        "video_codec": video.get("codec_name") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "format_name": fmt.get("format_name"),
        "size": int(fmt.get("size") or path.stat().st_size),
        "has_video": bool(video),
        "has_audio": bool(audio),
        "raw": parsed,
    }


def _run(command: list[str], timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _assemble_segment(segment_id: str, chunks: list[RecordingChunk], work_dir: Path) -> Path:
    chunks.sort(key=lambda item: item.segment_sequence)
    sequences = [item.segment_sequence for item in chunks]
    if sequences != list(range(0, sequences[-1] + 1)):
        missing = sorted(set(range(0, sequences[-1] + 1)) - set(sequences))
        raise ValueError(f"recording segment {segment_id} is missing chunks: {missing}")
    if not chunks[-1].is_final:
        raise ValueError(f"recording segment {segment_id} was not closed with a final chunk")
    premature = [item.segment_sequence for item in chunks[:-1] if item.is_final]
    if premature:
        raise ValueError(f"recording segment {segment_id} has premature final markers: {premature}")
    raw = work_dir / f"{segment_id}_raw.webm"
    with raw.open("wb") as target:
        for chunk in chunks:
            with Path(chunk.path).open("rb") as source:
                shutil.copyfileobj(source, target)
    normalized = work_dir / f"{segment_id}_normalized.webm"
    settings = get_settings()
    remux = _run(
        [
            settings.ffmpeg_path,
            "-y",
            "-fflags",
            "+genpts",
            "-i",
            str(raw),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            str(normalized),
        ]
    )
    if remux.returncode != 0 or not ffprobe(normalized).get("ok"):
        raise ValueError(f"segment {segment_id} remux failed: {remux.stderr[-800:]}")
    return normalized


def _concat_segments(paths: list[Path], output: Path) -> None:
    settings = get_settings()
    if len(paths) == 1:
        shutil.copy2(paths[0], output)
        return
    concat_file = output.with_suffix(".concat.txt")
    lines = ["ffconcat version 1.0"]
    for path in paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    copied = _run([settings.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(output)], timeout=360)
    if copied.returncode == 0 and ffprobe(output).get("ok"):
        return

    # Stream-copy may fail when a refreshed MediaRecorder changes time bases.
    # Fall back to a deterministic CPU re-encode so the logical interview remains playable.
    command = [settings.ffmpeg_path, "-y"]
    for path in paths:
        command.extend(["-i", str(path)])
    inputs = "".join(f"[{index}:v:0][{index}:a:0]" for index in range(len(paths)))
    command.extend(
        [
            "-filter_complex",
            f"{inputs}concat=n={len(paths)}:v=1:a=1[v][a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libvpx-vp9",
            "-deadline",
            "realtime",
            "-cpu-used",
            "6",
            "-b:v",
            "900k",
            "-c:a",
            "libopus",
            "-b:a",
            "64k",
            str(output),
        ]
    )
    encoded = _run(command, timeout=900)
    if encoded.returncode != 0 or not ffprobe(output).get("ok"):
        raise ValueError(f"multi-segment FFmpeg concat failed: {encoded.stderr[-1200:] or copied.stderr[-1200:]}")


def finalize_recording(db: Session, session_id: str) -> Recording:
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise ValueError("interview session not found")
    if not session.recording_upload_complete or not session.recording_expected_chunks:
        raise ValueError("recording upload has not completed the two-phase drain protocol")
    chunks = db.scalars(select(RecordingChunk).where(RecordingChunk.session_id == session_id).order_by(RecordingChunk.sequence)).all()
    if not chunks:
        raise ValueError("no recording chunks received")
    status = recording_status_payload(db, session, session.recording_expected_chunks)
    if status["missing_sequences"]:
        raise ValueError(f"missing recording chunks: {status['missing_sequences']}")

    settings = get_settings()
    recordings = settings.resolved_storage_dir / "recordings"
    recordings.mkdir(parents=True, exist_ok=True)
    work_dir = settings.resolved_storage_dir / "tmp" / f"finalize_{session_id}"
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[RecordingChunk]] = defaultdict(list)
    first_sequence: dict[str, int] = {}
    for chunk in chunks:
        grouped[chunk.segment_id].append(chunk)
        first_sequence[chunk.segment_id] = min(first_sequence.get(chunk.segment_id, chunk.sequence), chunk.sequence)
    ordered_ids = sorted(grouped, key=lambda value: first_sequence[value])
    normalized = [_assemble_segment(segment_id, grouped[segment_id], work_dir) for segment_id in ordered_ids]
    final_path = recordings / f"{session_id}_full.webm"
    _concat_segments(normalized, final_path)
    validation = ffprobe(final_path)
    validation["segment_count"] = len(ordered_ids)
    validation["chunk_count"] = len(chunks)
    validation["missing_chunk_count"] = len(status["missing_sequences"])
    if not validation.get("ok"):
        raise ValueError(f"final recording failed FFprobe validation: {validation}")

    checksum = sha256_file(final_path)
    existing = db.scalar(select(Recording).where(Recording.session_id == session_id, Recording.kind == "full_interview"))
    if existing:
        recording = existing
    else:
        recording = Recording(session_id=session_id, kind="full_interview", path=str(final_path), mime_type="video/webm", checksum="", size_bytes=0)
    recording.path = str(final_path)
    recording.mime_type = "video/webm"
    recording.checksum = checksum
    recording.size_bytes = final_path.stat().st_size
    recording.duration_seconds = validation.get("duration")
    recording.video_codec = validation.get("video_codec")
    recording.audio_codec = validation.get("audio_codec")
    recording.validation_status = "valid"
    recording.validation_details = validation
    db.add(recording)
    db.flush()
    return recording


def iter_file_range(path: Path, start: int, end: int, block_size: int = 1024 * 512) -> Iterator[bytes]:
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = handle.read(min(block_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def content_type_for(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
