from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
import time
from typing import Annotated, Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, select
from starlette.concurrency import run_in_threadpool

from ..ai.audio import decode_audio_bytes
from ..ai.common import ModelUnavailableError
from ..ai.attention import automatic_baseline_sample, conservative_fallback_baseline, finalize_automatic_baseline
from ..config import get_settings
from ..dependencies import DbSession, require_candidate_bearer_payload, require_candidate_session
from ..models import AttentionBaseline, DetectorMetric, FraudEvent, InterviewSession, VerificationAttempt
from ..runtime import anti_spoof_engine, attention_tracker, confirmation_tracker, face_engine, pose_gaze_engine, speaker_engine
from ..schemas import TabSwitchIn
from ..services.audit import audit, record_error
from ..services.evidence import save_audio, save_metadata, save_screenshot
from ..services.events import create_event
from ..services.risk import attention_contribution, recalculate_session_risk
from .common import decode_image, event_dict, get_baseline, read_upload_limited, require_own_session, utcnow

router = APIRouter(prefix="/api/sessions", tags=["monitoring"])


def _hr_participant(token_payload: dict[str, Any]) -> bool:
    return str(token_payload.get("participant_role") or "").lower() == "hr"

_VISUAL_WORKERS = asyncio.Semaphore(2)


def _candidate_stream_response(payload: dict[str, Any], stream: str) -> dict[str, Any]:
    """Hide detector internals and fraud scores from production candidates.

    Administrators read the complete persisted detector output from the admin
    API and reports. Candidate clients receive only operational health and
    generic guidance, preventing threshold/risk gaming through browser tools.
    """
    settings = get_settings()
    if settings.test_mode or settings.candidate_debug_payloads:
        return payload
    raw_status = str(payload.get("status") or "processed")
    technical = raw_status in {
        "stale_frame", "stale_audio_window", "low_quality_frame", "frame_decode_error",
        "face_inference_timeout", "face_model_unavailable", "audio_decode_error",
        "speaker_inference_error", "speaker_model_unavailable",
    }
    if stream == "visual":
        face_count = payload.get("face_count")
        camera = "active" if isinstance(face_count, int) and face_count >= 1 else ("processing_issue" if technical else "attention_required")
        monitoring = "processing_issue" if technical else "active"
        guidance = "Camera monitoring is active. Remain clearly visible and face the interview screen."
        if camera == "attention_required":
            guidance = "Please remain clearly visible and face the interview screen."
        elif technical:
            guidance = "Camera analysis is temporarily degraded; keep the interview page open while the system retries."
        return {
            "status": "degraded" if technical else "processed",
            "frame_sequence": payload.get("frame_sequence"),
            "monitoring": {"camera": camera, "analysis": monitoring},
            "guidance": guidance,
        }
    microphone = "processing_issue" if technical else "active"
    guidance = "Microphone monitoring is active. Continue speaking naturally when prompted."
    if technical:
        guidance = "Audio analysis is temporarily degraded; keep the microphone enabled while the system retries."
    return {
        "status": "degraded" if technical else "processed",
        "monitoring": {"microphone": microphone, "analysis": "processing_issue" if technical else "active"},
        "guidance": guidance,
    }


def _candidate_policy_response(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if settings.test_mode or settings.candidate_debug_payloads:
        return payload
    return {
        key: payload.get(key)
        for key in ("counted", "tab_switch_count", "action", "message", "status", "termination_reason")
        if key in payload
    }


def _technical_face_response(
    session: InterviewSession,
    *,
    status: str,
    reason: str,
    sequence_number: int,
    captured_at: datetime | None,
) -> dict[str, Any]:
    """Return a non-fraud technical state without inventing a zero face count."""
    return _candidate_stream_response({
        "status": status,
        "face_state": status,
        "face_count": None,
        "failure_reason": reason,
        "frame_sequence": sequence_number,
        "capture_timestamp": captured_at.isoformat() if captured_at else None,
        "events": [],
        "risk_score": session.risk_score,
        "risk_classification": session.risk_classification,
    }, "visual")


def _technical_audio_response(
    session: InterviewSession,
    *,
    status: str,
    reason: str,
    sequence_number: int,
    dropped_stale: int = 0,
) -> dict[str, Any]:
    return _candidate_stream_response({
        "status": status,
        "speaker_verification": {
            "passed": False,
            "label": status,
            "confidence": 0.0,
            "failure_reason": reason,
        },
        "events": [],
        "risk_score": session.risk_score,
        "risk_classification": session.risk_classification,
        "performance": {"sequence_number": sequence_number, "dropped_stale": dropped_stale},
    }, "audio")


def _face_from_dense_landmarks(landmarks: np.ndarray, width: int, height: int) -> np.ndarray | None:
    """Construct a YuNet-compatible face row from MediaPipe landmarks.

    This is a conservative presence fallback for frames where YuNet misses a
    clearly trackable face. It prevents a dense-landmark success from being
    converted into a false no-face result and keeps SFace alignment available.
    """
    if landmarks is None or len(landmarks) < 478 or not np.isfinite(landmarks).all():
        return None
    xy = np.asarray(landmarks[:, :2], dtype=np.float64)
    xy[:, 0] *= width
    xy[:, 1] *= height
    x1, y1 = np.percentile(xy, 1, axis=0)
    x2, y2 = np.percentile(xy, 99, axis=0)
    pad_x, pad_y = (x2 - x1) * 0.08, (y2 - y1) * 0.10
    x1, y1 = max(0.0, x1 - pad_x), max(0.0, y1 - pad_y)
    x2, y2 = min(float(width - 1), x2 + pad_x), min(float(height - 1), y2 + pad_y)
    if x2 - x1 < 40 or y2 - y1 < 40:
        return None

    def point(index: int) -> tuple[float, float]:
        return float(xy[index, 0]), float(xy[index, 1])

    left_eye = np.mean(xy[[33, 133]], axis=0)
    right_eye = np.mean(xy[[362, 263]], axis=0)
    nose = point(1)
    left_mouth = point(61)
    right_mouth = point(291)
    return np.asarray([
        x1, y1, x2 - x1, y2 - y1,
        left_eye[0], left_eye[1], right_eye[0], right_eye[1],
        nose[0], nose[1], left_mouth[0], left_mouth[1], right_mouth[0], right_mouth[1],
        0.65,
    ], dtype=np.float32)


async def _run_cpu(db, monitored_session_id: str, component: str, timeout_seconds: float, function, *args, **kwargs):
    """Run blocking CPU inference outside the event loop with a hard timeout."""
    try:
        return await asyncio.wait_for(
            run_in_threadpool(function, *args, **kwargs),
            timeout=max(0.1, timeout_seconds),
        )
    except TimeoutError as exc:
        db.rollback()
        record_error(
            db,
            component,
            f"{component} exceeded the configured {timeout_seconds:.1f}s timeout",
            session_id=monitored_session_id,
            details={"timeout_seconds": timeout_seconds},
        )
        db.commit()
        raise HTTPException(status_code=504, detail=f"{component} timed out; the sample was not classified") from exc


async def _visual_event(db, session, event_type: str, confidence: float, explanation: str, relative_ms: int, measurements: dict[str, Any], image_bytes: bytes, duration_ms: int = 0):
    event, created = create_event(
        db,
        session,
        event_type=event_type,
        confidence=confidence,
        explanation=explanation,
        relative_ms=relative_ms,
        start_ms=max(0, relative_ms - duration_ms),
        end_ms=relative_ms,
        measurements=measurements,
    )
    if created:
        try:
            save_screenshot(db, event, image_bytes)
        except Exception as exc:
            record_error(db, "evidence_screenshot", str(exc), session_id=session.id, details={"event_id": event.id})
    return event, created


def _default_attention_thresholds(settings) -> dict[str, float]:
    return {
        "yaw_enter_degrees": float(settings.attention_yaw_enter_degrees),
        "pitch_enter_degrees": float(settings.attention_pitch_enter_degrees),
        "roll_enter_degrees": float(settings.attention_roll_enter_degrees),
        "gaze_horizontal_offset": float(settings.attention_gaze_horizontal_offset),
        "gaze_vertical_offset": float(settings.attention_gaze_vertical_offset),
        "hysteresis_ratio": float(settings.attention_hysteresis_ratio),
        "pose_min_confidence": float(settings.head_pose_min_confidence),
        "gaze_min_confidence": float(settings.gaze_min_confidence),
        "blink_ear_threshold": float(settings.attention_blink_ear_threshold),
    }


def _create_attention_baseline(db, session: InterviewSession, relative_ms: int) -> AttentionBaseline:
    row = db.scalar(select(AttentionBaseline).where(AttentionBaseline.session_id == session.id))
    if row is not None:
        return row
    row = AttentionBaseline(
        session_id=session.id,
        status="collecting",
        accepted_samples=0,
        rejected_samples=0,
        baseline_confidence=0.0,
        started_relative_ms=max(0, int(relative_ms)),
        measurements={
            "mode": "automatic_passive",
            "status": "collecting",
            "ready": False,
            "samples": [],
            "technical_warning": "collecting_initial_neutral_pose_frames",
        },
        quality={},
        technical_warning="collecting_initial_neutral_pose_frames",
        model_name=getattr(getattr(pose_gaze_engine, "provider", None), "model_name", getattr(pose_gaze_engine, "engine_name", "attention-engine")),
        model_version=getattr(pose_gaze_engine, "model_version", "unknown"),
    )
    db.add(row)
    db.flush()
    return row


def _effective_attention_baseline(row: AttentionBaseline, settings) -> dict[str, Any]:
    measurements = dict(row.measurements or {})
    if row.status == "ready":
        return {
            **measurements,
            "mode": "automatic_passive",
            "status": "ready",
            "ready": True,
            "baseline_confidence": float(row.baseline_confidence),
            "uncertainty": str(measurements.get("uncertainty", "low")),
            "technical_warning": row.technical_warning,
        }
    if row.status == "fallback":
        return {
            **conservative_fallback_baseline(
                _default_attention_thresholds(settings),
                settings.attention_baseline_fallback_threshold_multiplier,
            ),
            "accepted_samples": int(row.accepted_samples),
            "rejected_samples": int(row.rejected_samples),
            "sample_quality": dict(row.quality or {}),
        }
    return {
        "mode": "automatic_passive",
        "status": "collecting",
        "ready": False,
        "neutral_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
        "neutral_gaze": {"x_ratio": 0.5, "y_ratio": 0.5},
        "baseline_confidence": float(row.baseline_confidence),
        "uncertainty": "high",
        "technical_warning": row.technical_warning or "collecting_initial_neutral_pose_frames",
    }


def _attention_baseline_public(row: AttentionBaseline) -> dict[str, Any]:
    measurements = dict(row.measurements or {})
    return {
        "mode": "automatic_passive",
        "status": row.status,
        "ready": row.status == "ready",
        "accepted_samples": int(row.accepted_samples),
        "rejected_samples": int(row.rejected_samples),
        "baseline_confidence": float(row.baseline_confidence),
        "neutral_pose": measurements.get("neutral_pose", {}),
        "neutral_gaze": measurements.get("neutral_gaze", {}),
        "natural_pose_range": measurements.get("natural_pose_range", {}),
        "gaze_center_ready": bool(measurements.get("gaze_center_ready", False)),
        "quality": dict(row.quality or {}),
        "technical_warning": row.technical_warning,
        "started_relative_ms": int(row.started_relative_ms),
        "ready_relative_ms": row.ready_relative_ms,
        "model_name": row.model_name,
        "model_version": row.model_version,
    }


def _record_attention_baseline_rejection(row: AttentionBaseline, reason: str, relative_ms: int) -> None:
    if row.status == "ready":
        return
    row.rejected_samples += 1
    measurements = dict(row.measurements or {})
    measurements.update({
        "mode": "automatic_passive",
        "status": row.status,
        "last_rejection_reason": reason,
        "last_observed_relative_ms": max(0, int(relative_ms)),
    })
    row.measurements = measurements
    row.technical_warning = reason


def _update_automatic_attention_baseline(
    db,
    session: InterviewSession,
    row: AttentionBaseline,
    result: dict[str, Any],
    relative_ms: int,
    settings,
) -> dict[str, Any]:
    if row.status == "ready":
        return _attention_baseline_public(row)
    sample, rejection = automatic_baseline_sample(
        result,
        relative_ms=relative_ms,
        minimum_confidence=float(settings.attention_baseline_min_confidence),
        max_abs_yaw=float(settings.attention_baseline_max_abs_yaw_degrees),
        max_abs_pitch=float(settings.attention_baseline_max_abs_pitch_degrees),
        max_abs_roll=float(settings.attention_baseline_max_abs_roll_degrees),
    )
    measurements = dict(row.measurements or {})
    samples = list(measurements.get("samples", []))
    if sample is None:
        _record_attention_baseline_rejection(row, rejection or "invalid_passive_baseline_frame", relative_ms)
    else:
        samples.append(sample)
        samples = samples[-max(int(settings.attention_baseline_window_samples), int(settings.attention_baseline_min_samples)):]
        row.accepted_samples += 1
        measurements["samples"] = samples
        measurements["last_observed_relative_ms"] = max(0, int(relative_ms))
        result_summary = finalize_automatic_baseline(
            samples,
            minimum_samples=int(settings.attention_baseline_min_samples),
            minimum_span_ms=int(float(settings.attention_baseline_min_span_seconds) * 1000),
            max_mad_yaw=float(settings.attention_baseline_max_mad_yaw_degrees),
            max_mad_pitch=float(settings.attention_baseline_max_mad_pitch_degrees),
            max_mad_roll=float(settings.attention_baseline_max_mad_roll_degrees),
            minimum_confidence=float(settings.attention_baseline_min_confidence),
        )
        measurements.update(result_summary)
        row.baseline_confidence = float(result_summary.get("baseline_confidence", 0.0))
        row.quality = dict(result_summary.get("quality", {}))
        row.technical_warning = result_summary.get("technical_warning")
        if result_summary.get("ready"):
            neutral_pose = dict(result_summary.get("neutral_pose", {}))
            neutral_gaze = dict(result_summary.get("neutral_gaze", {}))
            row.status = "ready"
            row.ready_relative_ms = max(0, int(relative_ms))
            row.neutral_yaw = float(neutral_pose.get("yaw", 0.0))
            row.neutral_pitch = float(neutral_pose.get("pitch", 0.0))
            row.neutral_roll = float(neutral_pose.get("roll", 0.0))
            row.neutral_gaze_x = float(neutral_gaze.get("x_ratio", 0.5))
            row.neutral_gaze_y = float(neutral_gaze.get("y_ratio", 0.5))
            row.technical_warning = None
            measurements.pop("detector_thresholds", None)
            measurements.update({"status": "ready", "ready": True, "technical_warning": None, "uncertainty": result_summary.get("uncertainty", "low")})
        row.measurements = measurements

    elapsed_ms = max(0, int(relative_ms) - int(row.started_relative_ms))
    if row.status != "ready" and elapsed_ms >= int(float(settings.attention_baseline_fallback_seconds) * 1000):
        first_fallback = row.status != "fallback"
        row.status = "fallback"
        fallback = conservative_fallback_baseline(
            _default_attention_thresholds(settings),
            settings.attention_baseline_fallback_threshold_multiplier,
        )
        row.baseline_confidence = float(fallback["baseline_confidence"])
        row.technical_warning = str(fallback["technical_warning"])
        row.measurements = {
            **dict(row.measurements or {}),
            **fallback,
            "samples": list((row.measurements or {}).get("samples", [])),
            "accepted_samples": int(row.accepted_samples),
            "rejected_samples": int(row.rejected_samples),
        }
        if first_fallback:
            record_error(
                db,
                "automatic_attention_baseline",
                row.technical_warning,
                session_id=session.id,
                details={
                    "accepted_samples": row.accepted_samples,
                    "rejected_samples": row.rejected_samples,
                    "relative_ms": relative_ms,
                },
            )
    return _attention_baseline_public(row)


def _legacy_attention_result(pose: dict[str, Any], gaze: dict[str, Any]) -> dict[str, Any]:
    pose_direction = str(pose.get("direction", "center"))
    gaze_direction = str(gaze.get("direction", "center"))
    pose_confidence = float(pose.get("confidence", 0.99))
    gaze_confidence = float(gaze.get("confidence", 0.0))
    pose_away = pose_direction not in {"center", "unknown"}
    gaze_away = gaze_direction not in {"center", "unknown"}
    if pose_away and gaze_away:
        combined_state, dominant, duplicate = "combined_look_away", "coordinated", "single_coordinated_event"
    elif pose_away:
        combined_state, dominant, duplicate = "head_only_look_away", "head_pose", "pose_only"
    elif gaze_away:
        combined_state, dominant, duplicate = "eye_only_look_away", "gaze", "gaze_only"
    else:
        combined_state, dominant, duplicate = "screen_focused", "none", "no_duplicate"
    return {
        "status": "valid",
        "pose_status": "valid",
        "pose_failure_reason": None,
        "gaze_status": "valid" if gaze_confidence > 0 else "low_confidence",
        "gaze_failure_reason": None if gaze_confidence > 0 else "fixture_gaze_confidence_unavailable",
        "raw_yaw": float(pose.get("yaw", 0.0)),
        "raw_pitch": float(pose.get("pitch", 0.0)),
        "raw_roll": float(pose.get("roll", 0.0)),
        "smoothed_yaw": float(pose.get("yaw", 0.0)),
        "smoothed_pitch": float(pose.get("pitch", 0.0)),
        "smoothed_roll": float(pose.get("roll", 0.0)),
        "neutral_relative_yaw": float(pose.get("yaw", 0.0)),
        "neutral_relative_pitch": float(pose.get("pitch", 0.0)),
        "neutral_relative_roll": float(pose.get("roll", 0.0)),
        "raw_neutral_relative_yaw": float(pose.get("yaw", 0.0)),
        "raw_neutral_relative_pitch": float(pose.get("pitch", 0.0)),
        "raw_neutral_relative_roll": float(pose.get("roll", 0.0)),
        "neutral_offset": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "gaze_x": 0.5, "gaze_y": 0.5},
        "pose_confidence": pose_confidence,
        "landmark_confidence": max(pose_confidence, gaze_confidence),
        "pose_direction": pose_direction,
        "gaze_direction": gaze_direction,
        "gaze_confidence": gaze_confidence,
        "left_eye_confidence": gaze_confidence,
        "right_eye_confidence": gaze_confidence,
        "eyes_closed": bool(gaze.get("eyes_closed", False)),
        "blink_detected": bool(gaze.get("blink_detected", False)),
        "gaze_x_ratio": float(gaze.get("x_ratio", 0.5)),
        "gaze_y_ratio": float(gaze.get("y_ratio", 0.5)),
        "combined_state": combined_state,
        "dominant_detector": dominant,
        "duplicate_suppression": duplicate,
        "combined_confidence": max(pose_confidence, gaze_confidence),
        "direction": pose_direction if pose_away else gaze_direction,
        "engine": pose.get("engine", gaze.get("engine", "fixture")),
        "model_version": pose.get("model_version", gaze.get("model_version", "fixture")),
        "failure_reason": None,
    }


def _attention_event_type(state: str) -> str:
    return {
        "eye_only_look_away": "gaze_violation",
        "head_only_look_away": "head_pose_violation",
        "combined_look_away": "attention_look_away",
    }[state]


def _attention_explanation(state: str, direction: str, confidence: float, duration_ms: int) -> str:
    detector = {
        "eye_only_look_away": "eye direction while the passive neutral head baseline remained stable",
        "head_only_look_away": "head pose relative to the passive neutral baseline while eye direction remained near the screen",
        "combined_look_away": "coordinated eye and head movement",
    }[state]
    return f"Sustained {direction} look-away was confirmed from {detector} for {duration_ms / 1000.0:.1f}s at {confidence:.2f} confidence. Human review is required."


async def _run_attention_pipeline(db, session: InterviewSession, frame, face, settings, baseline: dict[str, Any], dense_landmarks=None) -> dict[str, Any]:
    if dense_landmarks is not None and hasattr(pose_gaze_engine, "analyze_with_landmarks"):
        return await _run_cpu(
            db,
            session.id,
            "attention_reused_landmarks_pose_gaze",
            settings.frame_request_timeout_seconds,
            pose_gaze_engine.analyze_with_landmarks,
            frame,
            face,
            dense_landmarks,
            session_id=session.id,
            baseline=baseline,
        )
    if hasattr(pose_gaze_engine, "analyze"):
        return await _run_cpu(
            db,
            session.id,
            "attention_landmarks_pose_gaze",
            settings.frame_request_timeout_seconds,
            pose_gaze_engine.analyze,
            frame,
            face,
            session_id=session.id,
            baseline=baseline,
        )
    pose = await _run_cpu(db, session.id, "head_pose", settings.frame_request_timeout_seconds, pose_gaze_engine.head_pose, frame, face)
    gaze = await _run_cpu(db, session.id, "gaze", settings.frame_request_timeout_seconds, pose_gaze_engine.gaze, frame, face)
    return _legacy_attention_result(pose, gaze)


@router.post("/{session_id}/analyze-frame")
async def analyze_frame(
    session_id: str,
    db: DbSession,
    image: UploadFile = File(...),
    relative_ms: Annotated[int, Form(ge=0)] = 0,
    captured_at: Annotated[datetime | None, Form()] = None,
    sequence_number: Annotated[int, Form(ge=0)] = 0,
    dropped_stale: Annotated[int, Form(ge=0)] = 0,
    queue_depth: Annotated[int, Form(ge=0)] = 0,
    auth_session: InterviewSession = Depends(require_candidate_session),
    token_payload: dict = Depends(require_candidate_bearer_payload),
):
    if _hr_participant(token_payload):
        return {
            "status": "hr_observer",
            "monitoring": {"camera": "disabled", "analysis": "skipped"},
            "guidance": "Fraud detection is disabled for HR participants.",
            "risk_score": auth_session.risk_score,
            "risk_classification": auth_session.risk_classification,
        }
    async with _VISUAL_WORKERS:
        api_started = time.perf_counter()
        session = require_own_session(auth_session, session_id)
        if session.status != "active":
            raise HTTPException(status_code=409, detail="session is not active")
        settings = get_settings()

        last_metric = db.scalar(
            select(DetectorMetric)
            .where(DetectorMetric.session_id == session.id, DetectorMetric.detector == "visual_pipeline")
            .order_by(desc(DetectorMetric.sequence_number))
            .limit(1)
        )
        if last_metric is not None and last_metric.sequence_number is not None and sequence_number <= last_metric.sequence_number:
            metric = DetectorMetric(
                session_id=session.id,
                detector="visual_pipeline",
                sequence_number=sequence_number,
                captured_at=captured_at,
                queue_depth=queue_depth,
                dropped_stale=dropped_stale + 1,
                status="stale_frame",
                details={"last_accepted_sequence": last_metric.sequence_number, "relative_ms": relative_ms},
            )
            db.add(metric)
            db.commit()
            return _technical_face_response(
                session,
                status="stale_frame",
                reason="A newer frame sequence was already processed",
                sequence_number=sequence_number,
                captured_at=captured_at,
            )

        image_bytes = await read_upload_limited(image, allowed_prefixes=("image/",), kind="image", max_mb=10)
        try:
            frame = decode_image(image_bytes)
        except HTTPException as exc:
            record_error(db, "frame_decode", str(exc.detail), session_id=session.id, details={"sequence_number": sequence_number})
            db.commit()
            return _technical_face_response(
                session,
                status="frame_decode_error",
                reason=str(exc.detail),
                sequence_number=sequence_number,
                captured_at=captured_at,
            )
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if float(gray.mean()) < 3.0 or float(gray.std()) < 1.5:
            return _technical_face_response(
                session,
                status="low_quality_frame",
                reason="The captured camera frame is blank or has insufficient visual information",
                sequence_number=sequence_number,
                captured_at=captured_at,
            )
        baseline, _ = get_baseline(db, session.id, "face")
        inference_started = time.perf_counter()
        try:
            faces = await _run_cpu(db, session.id, "face_detection", settings.frame_request_timeout_seconds, face_engine.detect, frame)
        except HTTPException as exc:
            if exc.status_code == 504:
                return _technical_face_response(
                    session,
                    status="face_inference_timeout",
                    reason=str(exc.detail),
                    sequence_number=sequence_number,
                    captured_at=captured_at,
                )
            raise
        except FileNotFoundError as exc:
            record_error(db, "face_detection", str(exc), session_id=session.id)
            db.commit()
            return _technical_face_response(
                session,
                status="face_model_unavailable",
                reason=str(exc),
                sequence_number=sequence_number,
                captured_at=captured_at,
            )

        face_detection_source = "yunet"
        dense_presence_landmarks = None
        if len(faces) == 0 and hasattr(pose_gaze_engine, "provider"):
            try:
                dense = await _run_cpu(
                    db,
                    session.id,
                    "face_presence_fallback",
                    settings.frame_request_timeout_seconds,
                    pose_gaze_engine.provider.detect,
                    frame,
                )
                fallback_face = _face_from_dense_landmarks(dense, frame.shape[1], frame.shape[0])
                if fallback_face is not None:
                    faces = np.asarray([fallback_face], dtype=np.float32)
                    dense_presence_landmarks = dense
                    face_detection_source = "mediapipe_presence_fallback"
            except Exception as exc:
                # A fallback failure is technical context only; YuNet's valid
                # no-face result remains the authoritative presence result.
                record_error(db, "face_presence_fallback", str(exc), session_id=session.id, details={"sequence_number": sequence_number})

        face_count = int(len(faces))
        face_state = "face_detected" if face_count == 1 else ("multiple_faces" if face_count > 1 else "no_face")
        detection_confidence = float(np.max(faces[:, 14])) if face_count and faces.shape[1] > 14 else 0.0
        output: dict[str, Any] = {
            "status": "valid",
            "face_state": face_state,
            "face_count": face_count,
            "face_detection_confidence": round(detection_confidence, 4),
            "face_detection_source": face_detection_source,
            "events": [],
            "frame_sequence": sequence_number,
            "capture_timestamp": captured_at.isoformat() if captured_at else None,
        }
        attention_baseline_row = _create_attention_baseline(db, session, relative_ms)
        baseline_elapsed_ms = max(0, int(relative_ms) - int(attention_baseline_row.started_relative_ms))
        attention_event_warmup = baseline_elapsed_ms < int(float(settings.attention_baseline_event_suppression_seconds) * 1000)
        output["attention_baseline"] = _attention_baseline_public(attention_baseline_row)
        # Backward-compatible response key; this warm-up is attention-only and
        # must never suppress face presence, identity, or anti-spoof checks.
        output["visual_event_warmup"] = attention_event_warmup
        output["attention_event_warmup"] = attention_event_warmup
        no_face_confirmed, no_face_duration = confirmation_tracker.update(
            session.id, "no_face", len(faces) == 0,
            required_seconds=settings.no_face_confirm_seconds,
            required_count=settings.no_face_confirm_count,
            observed_ms=relative_ms,
        )
        if no_face_confirmed:
            event, created = await _visual_event(db, session, "no_face", 0.95, "No face was continuously visible for the configured confirmation window.", relative_ms, {"face_count": 0}, image_bytes, no_face_duration)
            if created:
                output["events"].append(event_dict(event))

        multiple_confirmed, multiple_duration = confirmation_tracker.update(
            session.id, "multiple_faces", len(faces) > 1,
            required_seconds=settings.multiple_faces_confirm_seconds,
            required_count=settings.multiple_faces_confirm_count,
            observed_ms=relative_ms,
        )
        if multiple_confirmed:
            confidence = min(1.0, 0.70 + 0.10 * len(faces))
            event, created = await _visual_event(db, session, "multiple_faces", confidence, f"{len(faces)} faces were detected across a sustained confirmation window.", relative_ms, {"face_count": int(len(faces))}, image_bytes, multiple_duration)
            if created:
                output["events"].append(event_dict(event))

        attention_result: dict[str, Any] | None = None
        if len(faces) == 1:
            try:
                verify_function = getattr(face_engine, "verify_detected", None)
                if verify_function is not None:
                    result = await _run_cpu(db, session.id, "face_verification", settings.frame_request_timeout_seconds, verify_function, frame, faces[0], baseline)
                else:
                    result = await _run_cpu(db, session.id, "face_verification", settings.frame_request_timeout_seconds, face_engine.verify, frame, baseline)
            except (ValueError, RuntimeError) as exc:
                record_error(db, "face_verification", str(exc), session_id=session.id)
                output["face_state"] = "face_inference_error"
                output["face_verification"] = {
                    "passed": False,
                    "label": "face_inference_error",
                    "confidence": 0.0,
                    "face_count": 1,
                    "failure_reason": str(exc),
                }
                result = None
            if result is not None:
                label = "low_quality_frame" if result.label == "poor_quality" else result.label
                output["face_state"] = label if label in {"face_match", "face_mismatch", "low_quality_frame"} else "face_detected"
                output["face_verification"] = {"passed": result.passed, "label": label, "confidence": result.confidence, **result.measurements}
                db.add(VerificationAttempt(session_id=session.id, kind="face", stage="continuous", passed=result.passed, similarity=result.measurements.get("similarity"), confidence=result.confidence, measurements=result.measurements))
                mismatch_active = result.label == "face_mismatch" and result.confidence >= settings.face_mismatch_min_confidence
            else:
                mismatch_active = False
            mismatch_confirmed, mismatch_duration = confirmation_tracker.update(
                session.id, "face_mismatch", mismatch_active,
                required_seconds=settings.face_mismatch_confirm_seconds,
                required_count=settings.face_mismatch_confirm_count,
                observed_ms=relative_ms,
            )
            if mismatch_confirmed:
                assert result is not None
                event, created = await _visual_event(db, session, "face_mismatch", result.confidence, "The continuously observed face did not match the enrolled face over consecutive verification windows.", relative_ms, result.measurements, image_bytes, mismatch_duration)
                if created:
                    output["events"].append(event_dict(event))

            previous_baseline_status = attention_baseline_row.status
            effective_baseline = _effective_attention_baseline(attention_baseline_row, settings)
            attention_result = await _run_attention_pipeline(db, session, frame, faces[0], settings, effective_baseline, dense_presence_landmarks)
            baseline_public = _update_automatic_attention_baseline(db, session, attention_baseline_row, attention_result, relative_ms, settings)
            if previous_baseline_status != "ready" and attention_baseline_row.status == "ready":
                if hasattr(pose_gaze_engine, "clear_session"):
                    pose_gaze_engine.clear_session(session.id)
                attention_tracker.clear_session(session.id)
            attention_result.update({
                "frame_sequence": sequence_number,
                "capture_timestamp": captured_at.isoformat() if captured_at else None,
                "baseline_status": baseline_public["status"],
                "baseline_confidence": baseline_public["baseline_confidence"],
                "baseline_uncertainty": "high" if baseline_public["status"] in {"collecting", "fallback"} else "low",
                "baseline_technical_warning": baseline_public.get("technical_warning"),
                "neutral_offset": {
                    "yaw": float((baseline_public.get("neutral_pose") or {}).get("yaw", 0.0)),
                    "pitch": float((baseline_public.get("neutral_pose") or {}).get("pitch", 0.0)),
                    "roll": float((baseline_public.get("neutral_pose") or {}).get("roll", 0.0)),
                    "gaze_x": float((baseline_public.get("neutral_gaze") or {}).get("x_ratio", 0.5)),
                    "gaze_y": float((baseline_public.get("neutral_gaze") or {}).get("y_ratio", 0.5)),
                },
            })
            output["attention_baseline"] = baseline_public
            output["attention"] = attention_result
            output["head_pose"] = {
                key: attention_result.get(key)
                for key in (
                    "pose_status", "raw_yaw", "raw_pitch", "raw_roll", "smoothed_yaw", "smoothed_pitch", "smoothed_roll",
                    "neutral_relative_yaw", "neutral_relative_pitch", "neutral_relative_roll", "raw_neutral_relative_yaw", "raw_neutral_relative_pitch", "raw_neutral_relative_roll", "neutral_offset",
                    "baseline_status", "baseline_confidence", "baseline_uncertainty", "baseline_technical_warning",
                    "pose_direction", "pose_confidence", "landmark_confidence", "head_pose_inference_latency_ms", "landmark_inference_latency_ms", "inference_latency_ms", "engine", "model_name", "model_version", "pose_failure_reason",
                )
            }
            output["gaze"] = {
                key: attention_result.get(key)
                for key in (
                    "gaze_status", "gaze_direction", "gaze_confidence", "left_eye_confidence", "right_eye_confidence", "eyes_closed",
                    "blink_detected", "gaze_x_ratio", "gaze_y_ratio", "smoothed_gaze_x", "smoothed_gaze_y", "glasses_reflection",
                    "baseline_status", "baseline_confidence", "baseline_uncertainty", "baseline_technical_warning",
                    "gaze_inference_latency_ms", "landmark_inference_latency_ms", "inference_latency_ms", "engine", "model_name", "model_version", "gaze_failure_reason",
                )
            }

            baseline_status = attention_baseline_row.status
            baseline_elapsed_ms = max(0, int(relative_ms) - int(attention_baseline_row.started_relative_ms))
            warmup_active = baseline_status == "collecting" or baseline_elapsed_ms < int(float(settings.attention_baseline_event_suppression_seconds) * 1000)
            state = str(attention_result.get("combined_state", "low_confidence"))
            confidence = float(attention_result.get("combined_confidence", 0.0))
            direction = str(attention_result.get("direction", "unknown"))
            if warmup_active:
                transition = attention_tracker.update(
                    session.id,
                    combined_state="low_confidence",
                    direction="unknown",
                    confidence=0.0,
                    relative_ms=relative_ms,
                    confirm_ms=int(max(settings.gaze_confirm_seconds, settings.head_pose_confirm_seconds) * 1000),
                    confirm_count=max(settings.gaze_confirm_count, settings.head_pose_confirm_count),
                    recovery_ms=int(settings.attention_recovery_seconds * 1000),
                )
                output["attention_transition"] = {**transition.__dict__, "suppressed": True, "reason": "automatic_neutral_baseline_warmup", "baseline_elapsed_ms": baseline_elapsed_ms}
            else:
                confirm_seconds = settings.gaze_confirm_seconds if state == "eye_only_look_away" else settings.head_pose_confirm_seconds
                if state == "combined_look_away":
                    confirm_seconds = max(settings.gaze_confirm_seconds, settings.head_pose_confirm_seconds)
                risk_scale = 1.0
                if baseline_status == "fallback":
                    confirm_seconds *= float(settings.attention_baseline_fallback_confirmation_multiplier)
                    risk_scale = float(settings.attention_baseline_fallback_risk_scale)
                transition = attention_tracker.update(
                    session.id,
                    combined_state=state,
                    direction=direction,
                    confidence=confidence,
                    relative_ms=relative_ms,
                    confirm_ms=int(confirm_seconds * 1000),
                    confirm_count=max(settings.gaze_confirm_count, settings.head_pose_confirm_count) if state == "combined_look_away" else (settings.gaze_confirm_count if state == "eye_only_look_away" else settings.head_pose_confirm_count),
                    recovery_ms=int(settings.attention_recovery_seconds * 1000),
                )
                output["attention_transition"] = {**transition.__dict__, "suppressed": False, "baseline_status": baseline_status, "risk_scale": risk_scale}
                if transition.action == "open":
                    event_type = _attention_event_type(transition.state)
                    measurements = {**attention_result, "automatic_attention_baseline": baseline_public, "combined_state": transition.state, "event_start_ms": transition.start_ms, "event_end_ms": transition.end_ms, "event_duration_ms": transition.duration_ms, "consecutive_confirmation_count": transition.count, "baseline_risk_scale": risk_scale}
                    contribution = round(attention_contribution(transition.state, transition.confidence, transition.duration_ms) * risk_scale, 2)
                    event, created = create_event(
                        db,
                        session,
                        event_type=event_type,
                        confidence=transition.confidence,
                        explanation=_attention_explanation(transition.state, transition.direction, transition.confidence, transition.duration_ms),
                        relative_ms=transition.end_ms,
                        start_ms=transition.start_ms,
                        end_ms=transition.end_ms,
                        measurements=measurements,
                        client_timestamp=captured_at,
                        dedupe_key=f"attention:{transition.direction}:{transition.start_ms}",
                        force=True,
                        state="active",
                        risk_contribution=contribution,
                    )
                    if created:
                        attention_tracker.bind_event(session.id, event.id)
                        try:
                            save_screenshot(db, event, image_bytes)
                        except Exception as exc:
                            record_error(db, "evidence_screenshot", str(exc), session_id=session.id, details={"event_id": event.id})
                        output["events"].append(event_dict(event))
                elif transition.action in {"update", "close"} and transition.event_id:
                    event = db.get(FraudEvent, transition.event_id)
                    if event is not None:
                        event.event_type = _attention_event_type(transition.state)
                        event.end_ms = transition.end_ms
                        event.relative_ms = transition.end_ms
                        event.duration_ms = transition.duration_ms
                        event.confidence = transition.confidence
                        event.state = "confirmed" if transition.action == "close" else "active"
                        event.measurements = {**(event.measurements or {}), **attention_result, "automatic_attention_baseline": baseline_public, "event_start_ms": transition.start_ms, "event_end_ms": transition.end_ms, "event_duration_ms": transition.duration_ms, "consecutive_confirmation_count": transition.count, "combined_state": transition.state, "baseline_risk_scale": risk_scale}
                        event.risk_contribution = round(attention_contribution(transition.state, transition.confidence, transition.duration_ms) * risk_scale, 2)
                        event.explanation = _attention_explanation(transition.state, transition.direction, transition.confidence, transition.duration_ms)
                        recalculate_session_risk(db, session)

            if result is not None and result.label in {"face_match", "face_mismatch"}:
                spoof = await _run_cpu(db, session.id, "anti_spoof", settings.frame_request_timeout_seconds, anti_spoof_engine.analyze, frame, faces[0])
                output["anti_spoof"] = spoof
                spoof_active = spoof.get("label") == "spoof_concern" and float(spoof.get("confidence", 0)) >= 0.75
                spoof_confirmed, spoof_duration = confirmation_tracker.update(
                    session.id, "face_spoof_concern", spoof_active,
                    required_seconds=2.0, required_count=3, observed_ms=relative_ms,
                )
                if spoof_confirmed:
                    event, created = await _visual_event(db, session, "face_spoof_concern", float(spoof["confidence"]), "Passive RGB anti-spoofing produced a sustained presentation-attack concern. Human review is required.", relative_ms, spoof, image_bytes, spoof_duration)
                    if created:
                        output["events"].append(event_dict(event))
        else:
            baseline_public = _update_automatic_attention_baseline(
                db,
                session,
                attention_baseline_row,
                {
                    "status": "landmark_unavailable",
                    "pose_status": "landmark_unavailable",
                    "failure_reason": "no_face" if len(faces) == 0 else "multiple_faces",
                },
                relative_ms,
                settings,
            )
            output["attention_baseline"] = baseline_public
            attention_tracker.update(session.id, combined_state="landmark_unavailable", direction="unknown", confidence=0.0, relative_ms=relative_ms, confirm_ms=2500, confirm_count=3, recovery_ms=int(settings.attention_recovery_seconds * 1000))

        session.current_client_elapsed_ms = max(session.current_client_elapsed_ms, relative_ms)
        inference_ms = round((time.perf_counter() - inference_started) * 1000.0, 3)
        api_ms = round((time.perf_counter() - api_started) * 1000.0, 3)
        metric_status = str(attention_result.get("status", "ok")) if attention_result else ("no_face" if len(faces) == 0 else "multiple_faces")
        metric = DetectorMetric(
            session_id=session.id,
            detector="visual_pipeline",
            sequence_number=sequence_number,
            captured_at=captured_at,
            inference_ms=inference_ms,
            api_ms=api_ms,
            queue_depth=queue_depth,
            dropped_stale=dropped_stale,
            status=metric_status,
            details={
                "relative_ms": relative_ms,
                "face_count": int(len(faces)),
                "event_count": len(output["events"]),
                "attention": attention_result or {},
            },
        )
        db.add(metric)
        db.commit()
        output.update({
            "risk_score": session.risk_score,
            "risk_classification": session.risk_classification,
            "performance": {
                "inference_ms": inference_ms,
                "api_ms": api_ms,
                "sequence_number": sequence_number,
                "queue_depth": queue_depth,
                "dropped_stale": dropped_stale,
            },
        })
        return _candidate_stream_response(output, "visual")


@router.post("/{session_id}/analyze-audio")
async def analyze_audio(
    session_id: str,
    db: DbSession,
    audio: UploadFile = File(...),
    window_start_ms: Annotated[int, Form(ge=0)] = 0,
    window_end_ms: Annotated[int | None, Form(ge=0)] = None,
    duration_ms: Annotated[int | None, Form(ge=0)] = None,
    captured_at: Annotated[datetime | None, Form()] = None,
    sequence_number: Annotated[int, Form(ge=0)] = 0,
    segment_id: Annotated[str, Form(min_length=1, max_length=80)] = "audio-segment-0",
    queue_depth: Annotated[int, Form(ge=0)] = 0,
    dropped_stale: Annotated[int, Form(ge=0)] = 0,
    relative_ms: Annotated[int | None, Form(ge=0)] = None,
    auth_session: InterviewSession = Depends(require_candidate_session),
    token_payload: dict = Depends(require_candidate_bearer_payload),
):
    if _hr_participant(token_payload):
        return {
            "status": "hr_observer",
            "monitoring": {"microphone": "disabled", "analysis": "skipped"},
            "guidance": "Fraud detection is disabled for HR participants.",
            "risk_score": auth_session.risk_score,
            "risk_classification": auth_session.risk_classification,
        }
    api_started = time.perf_counter()
    inference_started = api_started
    session = require_own_session(auth_session, session_id)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="session is not active")
    settings = get_settings()
    last_audio_metric = db.scalar(
        select(DetectorMetric)
        .where(DetectorMetric.session_id == session.id, DetectorMetric.detector == "speaker_pipeline")
        .order_by(desc(DetectorMetric.sequence_number))
        .limit(1)
    )
    if last_audio_metric is not None and last_audio_metric.sequence_number is not None and sequence_number <= last_audio_metric.sequence_number:
        return _candidate_stream_response({
            "status": "stale_audio_window",
            "speaker_verification": {
                "passed": False,
                "label": "stale_audio_window",
                "confidence": 0.0,
                "failure_reason": "A newer audio sequence was already processed",
            },
            "events": [],
            "risk_score": session.risk_score,
            "risk_classification": session.risk_classification,
            "performance": {"sequence_number": sequence_number, "dropped_stale": dropped_stale + 1},
        }, "audio")
    baseline, _ = get_baseline(db, session.id, "voice")
    audio_bytes = await read_upload_limited(audio, allowed_prefixes=("audio/", "video/webm"), kind="audio")
    try:
        signal, sample_rate = await _run_cpu(db, session.id, "audio_decode", settings.audio_request_timeout_seconds, decode_audio_bytes, audio_bytes, audio.content_type or "audio/webm")
    except HTTPException as exc:
        status = "speaker_inference_error" if exc.status_code == 504 else "audio_decode_error"
        record_error(db, status, str(exc.detail), session_id=session.id, details={"sequence_number": sequence_number})
        db.commit()
        return _technical_audio_response(session, status=status, reason=str(exc.detail), sequence_number=sequence_number)
    except (ValueError, RuntimeError) as exc:
        record_error(db, "audio_decode_error", str(exc), session_id=session.id, details={"sequence_number": sequence_number})
        db.commit()
        return _technical_audio_response(session, status="audio_decode_error", reason=str(exc), sequence_number=sequence_number)

    try:
        result = await _run_cpu(db, session.id, "speaker_verification", settings.audio_request_timeout_seconds, speaker_engine.verify, signal, baseline, sample_rate)
    except ModelUnavailableError as exc:
        record_error(db, "speaker_model_unavailable", str(exc), session_id=session.id, details={"sequence_number": sequence_number})
        db.commit()
        return _technical_audio_response(session, status="speaker_model_unavailable", reason=str(exc), sequence_number=sequence_number)
    except HTTPException as exc:
        status = "speaker_inference_error"
        record_error(db, status, str(exc.detail), session_id=session.id, details={"sequence_number": sequence_number})
        db.commit()
        return _technical_audio_response(session, status=status, reason=str(exc.detail), sequence_number=sequence_number)
    except (ValueError, RuntimeError) as exc:
        record_error(db, "speaker_inference_error", str(exc), session_id=session.id, details={"sequence_number": sequence_number})
        db.commit()
        return _technical_audio_response(session, status="speaker_inference_error", reason=str(exc), sequence_number=sequence_number)
    derived_duration_ms = int(duration_ms if duration_ms is not None else round(len(signal) * 1000 / max(sample_rate, 1)))
    end_ms = int(window_end_ms if window_end_ms is not None else (relative_ms if relative_ms is not None else window_start_ms + derived_duration_ms))
    start_ms = int(window_start_ms)
    if end_ms < start_ms:
        raise HTTPException(status_code=422, detail="window_end_ms must be greater than or equal to window_start_ms")
    actual_duration_ms = end_ms - start_ms
    window_measurements = {
        **result.measurements,
        "audio_window": {
            "window_start_ms": start_ms,
            "window_end_ms": end_ms,
            "duration_ms": actual_duration_ms,
            "captured_at": captured_at.isoformat() if captured_at else None,
            "sequence_number": sequence_number,
            "segment_id": segment_id,
        },
    }
    db.add(VerificationAttempt(session_id=session.id, kind="voice", stage="continuous", passed=result.passed, similarity=result.measurements.get("similarity"), confidence=result.confidence, measurements=window_measurements))
    output: dict[str, Any] = {"status": result.label, "speaker_verification": {"passed": result.passed, "label": result.label, "confidence": result.confidence, "measurements": window_measurements, **result.measurements}, "events": []}

    quality = dict(result.measurements.get("quality") or {})
    valid_embedding_result = (
        result.label == "voice_mismatch"
        and bool(quality.get("accepted"))
        and result.measurements.get("similarity") is not None
        and math.isfinite(float(result.measurements.get("similarity")))
        and int(result.measurements.get("verification_window_count", 0)) >= 1
        and int(result.measurements.get("embedding_dimension", 0)) > 0
    )
    mismatch_active = valid_embedding_result and result.confidence >= settings.voice_mismatch_min_confidence
    confirmed, duration_ms = confirmation_tracker.update(
        session.id, "voice_mismatch", mismatch_active,
        required_seconds=settings.voice_mismatch_confirm_seconds,
        required_count=settings.voice_mismatch_confirm_count,
        observed_ms=end_ms,
    )
    if confirmed:
        event, created = create_event(
            db,
            session,
            event_type="voice_mismatch",
            confidence=result.confidence,
            explanation="Usable voiced speech did not match the enrolled speaker over consecutive windows.",
            relative_ms=end_ms,
            start_ms=max(start_ms, end_ms - duration_ms),
            end_ms=end_ms,
            measurements=window_measurements,
        )
        if created:
            try:
                suffix = ".wav" if "wav" in (audio.content_type or "") else ".webm"
                save_audio(db, event, audio_bytes, suffix=suffix)
            except Exception as exc:
                record_error(db, "evidence_audio", str(exc), session_id=session.id, details={"event_id": event.id})
            output["events"].append(event_dict(event))

    review = await _run_cpu(db, session.id, "additional_speech_review", settings.audio_request_timeout_seconds, speaker_engine.additional_speech_review, signal, sample_rate, identity_label=result.label)
    review = {**review, "audio_window": window_measurements["audio_window"]}
    output["additional_speech_review"] = review
    possible_active = review.get("state") in {"possible_additional_speaker", "probable_additional_speaker"}
    possible_confirmed, possible_duration = confirmation_tracker.update(
        session.id, "possible_additional_speaker", possible_active,
        required_seconds=settings.additional_speaker_confirm_seconds,
        required_count=settings.additional_speaker_confirm_count,
        observed_ms=end_ms,
    )
    if possible_confirmed:
        event, created = create_event(
            db,
            session,
            event_type="possible_additional_speaker",
            confidence=float(review.get("overlap_confidence", 0.0)),
            explanation="Audio characteristics suggest possible additional or overlapping speech. This is review-only, not a confirmed identity claim.",
            relative_ms=end_ms,
            start_ms=max(start_ms, end_ms - possible_duration),
            end_ms=end_ms,
            measurements=review,
        )
        if created:
            try:
                save_audio(db, event, audio_bytes, suffix=".wav" if "wav" in (audio.content_type or "") else ".webm")
            except Exception as exc:
                record_error(db, "evidence_audio", str(exc), session_id=session.id, details={"event_id": event.id})
            output["events"].append(event_dict(event))

    overlap_active = review.get("state") not in {"no_speech", "insufficient_speech", "audio_too_noisy", "audio_clipped"} and bool(review.get("overlapping_speech_likely"))
    overlap_confirmed, overlap_duration = confirmation_tracker.update(
        session.id, "overlapping_speech", overlap_active,
        required_seconds=settings.overlap_confirm_seconds,
        required_count=settings.overlap_confirm_count,
        observed_ms=end_ms,
    )
    if overlap_confirmed:
        event, created = create_event(
            db,
            session,
            event_type="overlapping_speech",
            confidence=float(review.get("overlap_confidence", 0.0)),
            explanation="A sustained, high-confidence overlapping-speech proxy was detected. This remains review-only evidence, not definitive diarization.",
            relative_ms=end_ms,
            start_ms=max(start_ms, end_ms - overlap_duration),
            end_ms=end_ms,
            measurements=review,
        )
        if created:
            try:
                save_audio(db, event, audio_bytes, suffix=".wav" if "wav" in (audio.content_type or "") else ".webm")
            except Exception as exc:
                record_error(db, "evidence_audio", str(exc), session_id=session.id, details={"event_id": event.id})
            output["events"].append(event_dict(event))

    session.current_client_elapsed_ms = max(session.current_client_elapsed_ms, end_ms)
    inference_ms = round((time.perf_counter() - inference_started) * 1000.0, 3)
    api_ms = round((time.perf_counter() - api_started) * 1000.0, 3)
    metric = DetectorMetric(
        session_id=session.id,
        detector="speaker_pipeline",
        sequence_number=sequence_number,
        captured_at=captured_at,
        inference_ms=inference_ms,
        api_ms=api_ms,
        queue_depth=queue_depth,
        dropped_stale=dropped_stale,
        status=result.label,
        details={"window_start_ms": start_ms, "window_end_ms": end_ms, "segment_id": segment_id, "classification": result.label, "event_count": len(output["events"])},
    )
    db.add(metric)
    db.commit()
    output.update({"risk_score": session.risk_score, "risk_classification": session.risk_classification, "performance": {"inference_ms": inference_ms, "api_ms": api_ms, "sequence_number": sequence_number, "segment_id": segment_id}})
    return _candidate_stream_response(output, "audio")


@router.post("/{session_id}/tab-switch")
def tab_switch(
    session_id: str,
    payload: TabSwitchIn,
    db: DbSession,
    auth_session: InterviewSession = Depends(require_candidate_session),
    token_payload: dict = Depends(require_candidate_bearer_payload),
):
    """Record one meaningful browser-visibility episode.

    Focus/blur notifications are useful metadata only. The backend increments
    the authoritative counter only for an idempotent visibility episode whose
    hidden duration exceeds the configured minimum. This prevents permission
    prompts, address-bar focus, duplicate browser events, and React remounts
    from terminating an interview.
    """
    if _hr_participant(token_payload):
        return {
            "counted": False,
            "tab_switch_count": auth_session.tab_switch_count,
            "action": "none",
            "status": auth_session.status,
            "classification": "hr_observer",
        }
    session = require_own_session(auth_session, session_id)
    if session.status not in {"active", "terminating"}:
        raise HTTPException(status_code=409, detail="session is not active")

    settings = get_settings()
    minimum_hidden_ms = int(round(settings.tab_switch_min_hidden_seconds * 1000))
    episode_id = (payload.episode_id or "").strip()
    event_names = [str(item)[:100] for item in payload.triggering_events]
    is_visibility_episode = payload.signal == "visibility_episode"
    meaningfully_hidden = (
        is_visibility_episode
        and bool(episode_id)
        and payload.hidden_duration_ms >= minimum_hidden_ms
        and payload.hidden_started_at is not None
        and payload.visible_returned_at is not None
    )

    if not meaningfully_hidden:
        return _candidate_policy_response({
            "counted": False,
            "tab_switch_count": session.tab_switch_count,
            "action": "none",
            "status": session.status,
            "classification": "transient_or_unverified",
            "minimum_hidden_ms": minimum_hidden_ms,
            "message": "Transient focus or visibility change ignored.",
        })

    dedupe_key = f"tab-episode:{episode_id}"
    existing = db.scalar(
        select(FraudEvent).where(
            FraudEvent.session_id == session.id,
            FraudEvent.dedupe_key == dedupe_key,
        )
    )
    if existing is not None:
        return _candidate_policy_response({
            "counted": False,
            "tab_switch_count": session.tab_switch_count,
            "action": "duplicate_ignored",
            "status": session.status,
            "classification": "duplicate_episode",
            "event": event_dict(existing),
        })

    now = utcnow()
    session.last_tab_signal_at = now
    session.tab_switch_count += 1
    count = session.tab_switch_count
    event_type = "first_tab_switch" if count == 1 else "repeated_tab_switch"
    explanation = (
        "The interview page was continuously hidden beyond the configured threshold. This is the first backend-confirmed visibility episode; a second confirmed episode terminates the interview."
        if count == 1
        else "A second distinct, duration-qualified hidden-page episode occurred after the warning; the interview was terminated by policy."
    )
    measurements = {
        "episode_id": episode_id,
        "signal": payload.signal,
        "visibility_state": payload.visibility_state,
        "hidden_started_at": payload.hidden_started_at.isoformat(),
        "visible_returned_at": payload.visible_returned_at.isoformat(),
        "hidden_duration_ms": payload.hidden_duration_ms,
        "minimum_hidden_ms": minimum_hidden_ms,
        "focus_lost": payload.focus_lost,
        "triggering_browser_events": event_names,
        "authoritative_count": count,
        "deduplication_result": "new_episode",
        "evidence_scope": "Browser visibility/focus metadata and candidate-facing recording only; external application content cannot be captured by the browser.",
    }
    event, _ = create_event(
        db,
        session,
        event_type=event_type,
        confidence=1.0,
        explanation=explanation,
        relative_ms=payload.relative_ms,
        start_ms=max(0, payload.relative_ms - payload.hidden_duration_ms),
        end_ms=payload.relative_ms,
        measurements=measurements,
        client_timestamp=payload.client_timestamp,
        dedupe_key=dedupe_key,
        force=True,
    )
    try:
        save_metadata(
            db,
            event,
            {
                "event_id": event.id,
                "session_id": session.id,
                "event_type": event_type,
                "client_timestamp": payload.client_timestamp,
                "server_timestamp": event.server_timestamp,
                "recording_relative_ms": payload.relative_ms,
                **measurements,
            },
        )
    except Exception as exc:
        record_error(db, "tab_switch_metadata_evidence", str(exc), session_id=session.id, details={"event_id": event.id, "episode_id": episode_id})

    action = "warn"
    message = "Warning: the interview page was hidden. A second confirmed switch will terminate the interview."
    if count >= 2:
        action = "terminate"
        message = "Interview terminated due to repeated tab switching. Recording recovery will continue safely if queued chunks remain."
        session.status = "terminated"
        session.termination_reason = "repeated_tab_switch"
        session.termination_requested_at = now
        session.ended_at = session.ended_at or now

    audit(
        db,
        "candidate",
        "tab_switch_recorded",
        actor_id=session.candidate_id,
        target_type="session",
        target_id=session.id,
        details={"count": count, "episode_id": episode_id, "hidden_duration_ms": payload.hidden_duration_ms, "action": action},
    )
    db.commit()
    return _candidate_policy_response({
        "counted": True,
        "tab_switch_count": count,
        "action": action,
        "message": message,
        "status": session.status,
        "classification": "confirmed_visibility_episode",
        "event": event_dict(event),
        "termination_reason": session.termination_reason,
    })


@router.post("/{session_id}/device-interruption")
def device_interruption(
    session_id: str,
    kind: Annotated[str, Form(pattern="^(camera|microphone|connection|recording)$")],
    relative_ms: Annotated[int, Form(ge=0)],
    db: DbSession,
    auth_session: InterviewSession = Depends(require_candidate_session),
):
    session = require_own_session(auth_session, session_id)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="session is not active")
    event_type = {
        "camera": "camera_interruption",
        "microphone": "microphone_interruption",
        "connection": "connection_loss",
        "recording": "recording_failure",
    }[kind]
    event, created = create_event(db, session, event_type=event_type, confidence=1.0, explanation=f"A {kind} interruption was reported and confirmed by the client health monitor.", relative_ms=relative_ms, measurements={"kind": kind})
    db.commit()
    return _candidate_policy_response({"created": created, "status": session.status})
