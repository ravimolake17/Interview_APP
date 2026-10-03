from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Annotated, Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..ai.audio import decode_audio_bytes
from ..ai.common import ModelUnavailableError, cosine_similarity
from ..ai.sentence import choose_sentence, evaluate_sentence
from ..config import get_settings
from ..dependencies import DbSession, require_candidate_bearer_payload, require_candidate_session
from ..models import BiometricBaseline, Candidate, DeviceCheck, InterviewSession, VerificationAttempt, VoiceSentenceAttempt
from ..runtime import face_engine, pose_gaze_engine, speaker_engine
from ..schemas import CandidateCreate, DeviceCheckIn, SessionStartIn
from ..security import create_token, decrypt_embedding, encrypt_embedding
from ..services.audit import audit
from ..services.stt import transcribe_verification_sentence
from .common import decode_image, get_baseline, read_upload_limited, require_own_session, utcnow

router = APIRouter(prefix="/api", tags=["candidate"])

_TERMINATION_COPY = {
    "repeated_tab_switch": "the interview was ended because the interview window was left more than once",
    "normal_completion": "the interview was already completed",
}


def _company_brand_from_token(db: Session, token_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    code = str(token_payload.get("company_code") or "").strip().upper() or None
    rr_candidate_id = str(token_payload.get("rr_candidate_id") or "").strip()
    if not rr_candidate_id:
        return code, None
    try:
        row = db.execute(
            text(
                "SELECT co.code, co.name FROM public.companies co "
                "JOIN public.candidate c ON c.company_id = co.id "
                "WHERE c.candidate_id = :cid"
            ),
            {"cid": rr_candidate_id},
        ).first()
    except Exception:
        row = None
    if row and row[0]:
        return str(row[0]).strip().upper(), (str(row[1]).strip() if row[1] else None)
    return code, None


def _join_status_payload(session: InterviewSession) -> dict[str, Any]:
    status = str(session.status or "")
    reason = session.termination_reason
    can_join = status not in {"terminated", "completed"}
    if status == "terminated":
        title = "This interview has been terminated"
        detail = _TERMINATION_COPY.get(
            str(reason or ""),
            "this interview session was ended by the proctoring system and cannot be reopened",
        )
        message = f"You cannot join this interview because {detail}. Please contact HR if you need further information."
    elif status == "completed":
        title = "This interview is already complete"
        message = "You have already finished this interview. Please contact HR if you need further information."
    else:
        title = "Interview session found"
        message = "You can continue identity verification and join the interview."
    return {
        "session_id": session.id,
        "status": status,
        "termination_reason": reason,
        "can_join": can_join,
        "title": title,
        "message": message,
    }


def _mandatory_model_readiness() -> dict[str, dict[str, Any]]:
    """Return fail-closed readiness, not merely model-file presence.

    The candidate workflow previously treated ``engine.available`` as proof that
    a mandatory model could load. A corrupt ONNX/task file or an ECAPA import
    failure could therefore leave ``/ready`` false while the Start Interview
    button still reported all prerequisites as complete. Production checks now
    exercise each lazy loader once; subsequent calls are inexpensive because the
    engines cache their loaded model objects. Test fixtures retain their simple
    ``available`` contract.
    """
    settings = get_settings()
    engines = {"face": face_engine, "speaker": speaker_engine, "attention": pose_gaze_engine}
    details: dict[str, dict[str, Any]] = {}
    for name, engine in engines.items():
        available = bool(getattr(engine, "available", True))
        error: str | None = None
        ready = available
        if available and not settings.test_mode:
            try:
                if name == "speaker" and hasattr(engine, "readiness"):
                    status = engine.readiness(load=True)
                    ready = bool(status.get("ready"))
                    error = status.get("error")
                elif name == "face" and hasattr(engine, "_load"):
                    engine._load()
                elif name == "attention":
                    provider = getattr(engine, "provider", None)
                    if provider is None:
                        raise RuntimeError("attention landmark provider is unavailable")
                    provider._load()
            except Exception as exc:  # mandatory models fail closed
                ready = False
                error = f"{type(exc).__name__}: {exc}"
        elif not available:
            error = "required model files or runtime dependency are unavailable"
        details[name] = {"ready": bool(ready), "available": available, "error": error}
    return details


def _mandatory_model_status() -> dict[str, bool]:
    return {name: bool(item["ready"]) for name, item in _mandatory_model_readiness().items()}


@router.post("/candidate/register")
def register_candidate(payload: CandidateCreate, db: DbSession):
    raise HTTPException(
        status_code=403,
        detail="Direct registration is disabled. Open the interview link from your confirmation email.",
    )


@router.get("/sessions/{session_id}/join-status")
def session_join_status(session_id: str, db: DbSession):
    """Public lookup so expired tokens still show a terminated/completed message."""
    clean = (session_id or "").strip()
    if len(clean) > 80 or not clean.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid session identifier")
    session = db.get(InterviewSession, clean)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return _join_status_payload(session)


@router.get("/sessions/{session_id}/state")
def session_state(
    session_id: str,
    db: DbSession,
    auth_session: InterviewSession = Depends(require_candidate_session),
    token_payload: dict[str, Any] = Depends(require_candidate_bearer_payload),
):
    session = require_own_session(auth_session, session_id)
    face_baseline = db.scalar(select(BiometricBaseline).where(BiometricBaseline.session_id == session.id, BiometricBaseline.kind == "face"))
    face_quality = dict(face_baseline.quality or {}) if face_baseline else {}
    latest_check = db.scalar(select(DeviceCheck).where(DeviceCheck.session_id == session.id).order_by(DeviceCheck.created_at.desc()))
    model_details = _mandatory_model_readiness()
    models = {name: bool(item["ready"]) for name, item in model_details.items()}
    company_code, company_name = _company_brand_from_token(db, token_payload)
    payload = {
        "id": session.id,
        "status": session.status,
        "face_enrolled": session.face_enrolled,
        "face_enrollment": {
            "sample_count": int(face_quality.get("sample_count", 0)),
            "required_samples": int(face_quality.get("required_samples", get_settings().face_enrollment_min_samples)),
            "complete": session.face_enrolled,
        },
        "voice_enrolled": session.voice_enrolled,
        "device_checks_passed": bool(latest_check and latest_check.camera_ok and latest_check.microphone_ok),
        "mandatory_models": models,
        "mandatory_models_ready": all(models.values()),
        "initial_face_verified": session.initial_face_verified,
        "initial_voice_verified": session.initial_voice_verified,
        "voice_sentence": None if not session.voice_sentence_id else {
            "id": session.voice_sentence_id,
            "text": session.voice_sentence_text,
            "issued_at": session.voice_sentence_issued_at.isoformat() if session.voice_sentence_issued_at else None,
        },
        "tab_switch_count": session.tab_switch_count,
        "termination_reason": session.termination_reason,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "current_client_elapsed_ms": session.current_client_elapsed_ms,
        "recording_expected_chunks": session.recording_expected_chunks,
        "recording_upload_complete": session.recording_upload_complete,
        "termination_requested_at": session.termination_requested_at.isoformat() if session.termination_requested_at else None,
        "company_code": company_code,
        "company_name": company_name,
    }
    settings = get_settings()
    if settings.test_mode or settings.candidate_debug_payloads:
        payload["mandatory_model_details"] = model_details
        payload["risk_score"] = session.risk_score
        payload["risk_classification"] = session.risk_classification
    return payload


@router.post("/sessions/{session_id}/device-check")
def device_check(session_id: str, payload: DeviceCheckIn, db: DbSession, auth_session: InterviewSession = Depends(require_candidate_session)):
    session = require_own_session(auth_session, session_id)
    record = DeviceCheck(session_id=session.id, camera_ok=payload.camera_ok, microphone_ok=payload.microphone_ok, details=payload.details)
    db.add(record)
    session.status = "device_checked" if payload.camera_ok and payload.microphone_ok else "device_check_failed"
    audit(db, "candidate", "device_check_recorded", actor_id=session.candidate_id, target_type="session", target_id=session.id, details=payload.model_dump())
    db.commit()
    return {"accepted": payload.camera_ok and payload.microphone_ok, "status": session.status}



def _issue_voice_sentence(session: InterviewSession, *, rotate: bool = False) -> dict[str, Any]:
    if rotate or not session.voice_sentence_id or not session.voice_sentence_text:
        sentence_id, sentence_text = choose_sentence(exclude_id=session.voice_sentence_id if rotate else None)
        session.voice_sentence_id = sentence_id
        session.voice_sentence_text = sentence_text
        session.voice_sentence_issued_at = utcnow()
    return {
        "id": session.voice_sentence_id,
        "text": session.voice_sentence_text,
        "issued_at": session.voice_sentence_issued_at.isoformat() if session.voice_sentence_issued_at else None,
    }


@router.get("/sessions/{session_id}/voice/sentence")
def get_voice_sentence(session_id: str, db: DbSession, auth_session: InterviewSession = Depends(require_candidate_session)):
    session = require_own_session(auth_session, session_id)
    payload = _issue_voice_sentence(session)
    db.commit()
    return payload


@router.post("/sessions/{session_id}/voice/sentence/change")
def change_voice_sentence(session_id: str, db: DbSession, auth_session: InterviewSession = Depends(require_candidate_session)):
    session = require_own_session(auth_session, session_id)
    if session.voice_enrolled or session.initial_voice_verified or session.status in {"active", "terminating", "completed", "terminated"}:
        raise HTTPException(status_code=409, detail="verification sentence cannot be changed after voice enrollment starts")
    payload = _issue_voice_sentence(session, rotate=True)
    audit(db, "candidate", "voice_sentence_changed", actor_id=session.candidate_id, target_type="session", target_id=session.id, details={"sentence_id": payload["id"]})
    db.commit()
    return payload


def _record_sentence_attempt(
    db: Session,
    session: InterviewSession,
    *,
    stage: str,
    sentence_id: str | None,
    recognized_transcript: str | None,
    recognition_available: bool,
    recognition_error: str | None,
) -> dict[str, Any]:
    issued = _issue_voice_sentence(session)
    failure_reason: str | None = None
    if sentence_id != issued["id"]:
        failure_reason = "verification_sentence_changed_or_invalid"
        evaluation = evaluate_sentence(str(issued["text"]), "")
    elif not recognition_available:
        failure_reason = "speech_recognition_unavailable"
        evaluation = evaluate_sentence(str(issued["text"]), "")
    else:
        settings = get_settings()
        evaluation = evaluate_sentence(
            str(issued["text"]),
            recognized_transcript,
            minimum_completion=settings.sentence_min_completion,
            maximum_skipped=settings.sentence_max_skipped,
            maximum_incorrect=settings.sentence_max_incorrect,
        )
        failure_reason = evaluation.failure_reason
    details = evaluation.as_dict()
    details["recognition_error"] = recognition_error
    if failure_reason:
        details["failure_reason"] = failure_reason
    passed = evaluation.passed and failure_reason is None
    attempt = VoiceSentenceAttempt(
        session_id=session.id,
        stage=stage,
        sentence_id=str(issued["id"]),
        sentence_text=str(issued["text"]),
        recognized_transcript=recognized_transcript or "",
        recognition_available=recognition_available,
        word_results=details["word_results"],
        completion_percentage=float(details["completion_percentage"]),
        passed=passed,
        failure_reason=failure_reason,
        details=details,
    )
    db.add(attempt)
    db.flush()
    return {
        **details,
        "passed": passed,
        "failure_reason": failure_reason,
        "attempt_id": attempt.id,
        "sentence_id": issued["id"],
        "sentence_text": issued["text"],
        "recognized_transcript": recognized_transcript or "",
        "recognition_available": recognition_available,
        "recognition_error": recognition_error,
    }

def _replace_baseline(db: Session, session_id: str, kind: str, vector, engine: str, quality: dict[str, Any]) -> BiometricBaseline:
    baseline = db.scalar(select(BiometricBaseline).where(BiometricBaseline.session_id == session_id, BiometricBaseline.kind == kind))
    encrypted = encrypt_embedding(vector)
    if baseline is None:
        baseline = BiometricBaseline(session_id=session_id, kind=kind, encrypted_embedding=encrypted, engine=engine, quality=quality)
    else:
        baseline.encrypted_embedding = encrypted
        baseline.engine = engine
        baseline.quality = quality
    db.add(baseline)
    db.flush()
    return baseline


@router.post("/sessions/{session_id}/face/enroll")
async def face_enroll(session_id: str, db: DbSession, image: UploadFile = File(...), auth_session: InterviewSession = Depends(require_candidate_session)):
    session = require_own_session(auth_session, session_id)
    settings = get_settings()
    data = await read_upload_limited(image, allowed_prefixes=("image/",), kind="image", max_mb=10)
    frame = decode_image(data)
    try:
        result = await run_in_threadpool(face_engine.enroll, frame)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    measurements = dict(result.measurements)
    baseline = db.scalar(select(BiometricBaseline).where(BiometricBaseline.session_id == session.id, BiometricBaseline.kind == "face"))
    prior_quality = dict(baseline.quality or {}) if baseline else {}
    prior_count = int(prior_quality.get("sample_count", 0))
    sample_count = prior_count
    sample_accepted = False
    duplicate_similarity: float | None = None

    if result.passed and result.vector is not None:
        vector = np.asarray(result.vector, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if vector.size == 0 or not np.isfinite(vector).all() or not np.isfinite(norm) or norm <= 1e-8:
            result.passed = False
            result.label = "invalid_face_embedding"
            measurements["embedding_creation_status"] = "invalid"
        elif prior_count >= settings.face_enrollment_max_samples:
            measurements.update({"sample_count": prior_count, "required_samples": settings.face_enrollment_min_samples, "enrollment_complete": session.face_enrolled, "sample_accepted": False})
            result.label = "face_enrollment_already_complete" if session.face_enrolled else "face_enrollment_limit_reached"
        else:
            vector = vector / norm
            if baseline is not None and prior_count > 0:
                previous = decrypt_embedding(baseline.encrypted_embedding)
                previous = np.asarray(previous, dtype=np.float32).reshape(-1)
                previous /= max(float(np.linalg.norm(previous)), 1e-8)
                duplicate_similarity = cosine_similarity(vector, previous)
                is_duplicate = duplicate_similarity >= settings.face_enrollment_duplicate_similarity and not settings.test_mode
                if is_duplicate:
                    result.passed = False
                    result.label = "duplicate_face_sample"
                    measurements.update({
                        "sample_count": prior_count,
                        "required_samples": settings.face_enrollment_min_samples,
                        "duplicate_similarity": duplicate_similarity,
                        "duplicate_threshold": settings.face_enrollment_duplicate_similarity,
                        "sample_accepted": False,
                        "enrollment_complete": session.face_enrolled,
                    })
                else:
                    aggregate = previous * float(prior_count) + vector
                    aggregate /= max(float(np.linalg.norm(aggregate)), 1e-8)
                    vector = aggregate
                    sample_accepted = True
            else:
                sample_accepted = True

            if sample_accepted:
                sample_count = prior_count + 1
                sample_details = {
                    "sample_index": sample_count,
                    "captured_at": utcnow().isoformat(),
                    "confidence": result.confidence,
                    "quality": measurements.get("quality", {}),
                    "face_count": measurements.get("face_count"),
                    "engine": measurements.get("engine", getattr(face_engine, "engine_name", "opencv-yunet-sface")),
                    "model_version": measurements.get("model_version", getattr(face_engine, "model_version", "unknown")),
                    "embedding_creation_status": "created",
                    "similarity_to_existing_baseline": duplicate_similarity,
                }
                samples = list(prior_quality.get("samples", []))
                samples.append(sample_details)
                enrollment_complete = sample_count >= settings.face_enrollment_min_samples
                baseline_quality = {
                    "sample_count": sample_count,
                    "required_samples": settings.face_enrollment_min_samples,
                    "maximum_samples": settings.face_enrollment_max_samples,
                    "aggregate_method": "normalized_weighted_mean",
                    "samples": samples,
                }
                _replace_baseline(db, session.id, "face", vector, "opencv-yunet-sface", baseline_quality)
                session.face_enrolled = enrollment_complete
                session.status = "face_enrolled" if enrollment_complete else "face_enrollment_pending"
                measurements.update({
                    "sample_count": sample_count,
                    "required_samples": settings.face_enrollment_min_samples,
                    "maximum_samples": settings.face_enrollment_max_samples,
                    "sample_accepted": True,
                    "enrollment_complete": enrollment_complete,
                    "duplicate_similarity": duplicate_similarity,
                    "aggregate_method": "normalized_weighted_mean",
                })
                result.label = "face_enrolled" if enrollment_complete else "face_enrollment_progress"

    enrollment_complete = bool(session.face_enrolled)
    measurements.setdefault("sample_count", sample_count)
    measurements.setdefault("required_samples", settings.face_enrollment_min_samples)
    measurements.setdefault("sample_accepted", sample_accepted)
    measurements.setdefault("enrollment_complete", enrollment_complete)
    attempt = VerificationAttempt(
        session_id=session.id,
        kind="face",
        stage="enrollment",
        passed=sample_accepted,
        confidence=result.confidence,
        measurements=measurements,
    )
    db.add(attempt)
    db.commit()
    return {"passed": enrollment_complete, "label": result.label, "confidence": result.confidence, "measurements": measurements}


@router.post("/sessions/{session_id}/face/verify")
async def face_verify(session_id: str, db: DbSession, image: UploadFile = File(...), auth_session: InterviewSession = Depends(require_candidate_session)):
    session = require_own_session(auth_session, session_id)
    if not session.face_enrolled:
        raise HTTPException(status_code=409, detail="face enrollment requires the configured number of accepted samples")
    baseline, _record = get_baseline(db, session.id, "face")
    data = await read_upload_limited(image, allowed_prefixes=("image/",), kind="image", max_mb=10)
    frame = decode_image(data)
    result = await run_in_threadpool(face_engine.verify, frame, baseline)
    attempt = VerificationAttempt(session_id=session.id, kind="face", stage="initial_verification", passed=result.passed, similarity=result.measurements.get("similarity"), confidence=result.confidence, measurements=result.measurements)
    db.add(attempt)
    session.initial_face_verified = result.passed
    if result.passed:
        session.status = "face_verified"
    db.commit()
    return {"passed": result.passed, "label": result.label, "confidence": result.confidence, "measurements": result.measurements}


async def _transcribe_voice_attempt(
    session: InterviewSession,
    *,
    audio_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    issued = _issue_voice_sentence(session)
    stt = await run_in_threadpool(
        transcribe_verification_sentence,
        audio_bytes,
        filename=filename,
        sentence_text=str(issued["text"]),
    )
    payload = stt.as_dict()
    payload["sentence_id"] = issued["id"]
    payload["sentence_text"] = issued["text"]
    return payload


@router.post("/sessions/{session_id}/voice/enroll")
async def voice_enroll(
    session_id: str,
    db: DbSession,
    audio: UploadFile = File(...),
    sentence_id: Annotated[str | None, Form()] = None,
    auth_session: InterviewSession = Depends(require_candidate_session),
):
    session = require_own_session(auth_session, session_id)
    data = await read_upload_limited(audio, allowed_prefixes=("audio/", "video/webm"), kind="audio")
    stt = await _transcribe_voice_attempt(
        session,
        audio_bytes=data,
        filename=audio.filename or "voice.webm",
    )
    sentence = _record_sentence_attempt(
        db,
        session,
        stage="enrollment",
        sentence_id=sentence_id or stt.get("sentence_id"),
        recognized_transcript=stt.get("text"),
        recognition_available=bool(stt.get("recognition_available")),
        recognition_error=stt.get("recognition_error"),
    )
    sentence["stt_provider"] = stt.get("provider")
    sentence["stt_model"] = stt.get("model")
    try:
        signal, sample_rate = await run_in_threadpool(decode_audio_bytes, data, audio.content_type or "audio/webm")
        speaker_result = await run_in_threadpool(speaker_engine.enroll, signal, sample_rate)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    combined_passed = bool(sentence["passed"] and speaker_result.passed)
    label = speaker_result.label if sentence["passed"] else str(sentence["failure_reason"] or "sentence_verification_failed")
    measurements = {**speaker_result.measurements, "sentence_verification": sentence, "speaker_verification": {"passed": speaker_result.passed, "label": speaker_result.label, "confidence": speaker_result.confidence, "engine": speaker_engine.mode}}
    attempt = VerificationAttempt(session_id=session.id, kind="voice", stage="enrollment", passed=combined_passed, confidence=speaker_result.confidence, measurements=measurements)
    db.add(attempt)
    if combined_passed and speaker_result.vector is not None:
        _replace_baseline(db, session.id, "voice", speaker_result.vector, speaker_engine.mode, measurements)
        session.voice_enrolled = True
        session.status = "voice_enrolled"
    db.commit()
    return {"passed": combined_passed, "label": label, "confidence": speaker_result.confidence, "measurements": measurements, "engine": speaker_engine.mode, "sentence_verification": sentence, "speaker_verification": measurements["speaker_verification"]}


@router.post("/sessions/{session_id}/voice/verify")
async def voice_verify(
    session_id: str,
    db: DbSession,
    audio: UploadFile = File(...),
    sentence_id: Annotated[str | None, Form()] = None,
    auth_session: InterviewSession = Depends(require_candidate_session),
):
    session = require_own_session(auth_session, session_id)
    baseline, _baseline_record = get_baseline(db, session.id, "voice")
    data = await read_upload_limited(audio, allowed_prefixes=("audio/", "video/webm"), kind="audio")
    stt = await _transcribe_voice_attempt(
        session,
        audio_bytes=data,
        filename=audio.filename or "voice.webm",
    )
    sentence = _record_sentence_attempt(
        db,
        session,
        stage="initial_verification",
        sentence_id=sentence_id or stt.get("sentence_id"),
        recognized_transcript=stt.get("text"),
        recognition_available=bool(stt.get("recognition_available")),
        recognition_error=stt.get("recognition_error"),
    )
    sentence["stt_provider"] = stt.get("provider")
    sentence["stt_model"] = stt.get("model")
    try:
        signal, sample_rate = await run_in_threadpool(decode_audio_bytes, data, audio.content_type or "audio/webm")
        speaker_result = await run_in_threadpool(speaker_engine.verify, signal, baseline, sample_rate)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    combined_passed = bool(sentence["passed"] and speaker_result.passed)
    label = speaker_result.label if sentence["passed"] else str(sentence["failure_reason"] or "sentence_verification_failed")
    measurements = {**speaker_result.measurements, "sentence_verification": sentence, "speaker_verification": {"passed": speaker_result.passed, "label": speaker_result.label, "confidence": speaker_result.confidence, "similarity": speaker_result.measurements.get("similarity"), "engine": speaker_engine.mode}}
    attempt = VerificationAttempt(session_id=session.id, kind="voice", stage="initial_verification", passed=combined_passed, similarity=speaker_result.measurements.get("similarity"), confidence=speaker_result.confidence, measurements=measurements)
    db.add(attempt)
    session.initial_voice_verified = combined_passed
    if combined_passed:
        session.status = "ready"
    db.commit()
    return {"passed": combined_passed, "label": label, "confidence": speaker_result.confidence, "measurements": measurements, "engine": speaker_engine.mode, "sentence_verification": sentence, "speaker_verification": measurements["speaker_verification"]}


@router.post("/sessions/{session_id}/start")
def start_interview(
    session_id: str,
    payload: SessionStartIn,
    db: DbSession,
    auth_session: InterviewSession = Depends(require_candidate_session),
    token_payload: dict = Depends(require_candidate_bearer_payload),
):
    session = require_own_session(auth_session, session_id)
    is_hr = str(token_payload.get("participant_role") or "").lower() == "hr"
    if not is_hr:
        latest_check = db.scalar(select(DeviceCheck).where(DeviceCheck.session_id == session.id).order_by(DeviceCheck.created_at.desc()))
        missing = []
        if not latest_check or not (latest_check.camera_ok and latest_check.microphone_ok):
            missing.append("device_checks")
        if not session.face_enrolled or not session.initial_face_verified:
            missing.append("face_enrollment_and_verification")
        if not session.voice_enrolled or not session.initial_voice_verified:
            missing.append("voice_enrollment_and_verification")
        model_details = _mandatory_model_readiness()
        if not model_details["speaker"]["ready"]:
            missing.append("mandatory_speaker_model")
        if not model_details["face"]["ready"]:
            missing.append("mandatory_face_models")
        if not model_details["attention"]["ready"]:
            missing.append("mandatory_attention_landmark_model")
        if missing:
            raise HTTPException(status_code=409, detail={"message": "mandatory prerequisites are incomplete", "missing": sorted(set(missing))})
        from services.interview_room_service import register_room_join_sync

        register_room_join_sync(str(token_payload.get("rr_candidate_id") or ""))
    if session.status in {"terminated", "completed"}:
        raise HTTPException(status_code=409, detail="session is already finalized")
    if session.status != "active":
        session.status = "active"
        session.started_at = session.started_at or utcnow()
        audit(
            db,
            "hr" if is_hr else "candidate",
            "interview_started",
            actor_id=session.candidate_id,
            target_type="session",
            target_id=session.id,
            details={"participant_role": "hr" if is_hr else "candidate"},
        )
        db.commit()
    return {"status": session.status, "started_at": session.started_at.isoformat() if session.started_at else None}


@router.get("/sessions/{session_id}/interview-room")
def get_interview_room(
    session_id: str,
    db: DbSession,
    auth_session: InterviewSession = Depends(require_candidate_session),
    token_payload: dict[str, Any] = Depends(require_candidate_bearer_payload),
):
    """Return the in-app interview room URL after identity verification. No Google Meet."""
    session = require_own_session(auth_session, session_id)
    if not session.initial_face_verified or not session.initial_voice_verified:
        raise HTTPException(status_code=403, detail="Complete face and voice verification before entering the interview room.")
    if session.status not in {"ready", "active", "terminating"}:
        raise HTTPException(status_code=409, detail="Interview session is not ready.")

    rr_candidate_id = str(token_payload.get("rr_candidate_id") or "").strip()
    if not rr_candidate_id:
        raise HTTPException(status_code=404, detail="Interview room is unavailable for this session.")

    from sqlalchemy import text

    row = db.execute(
        text(
            "SELECT meeting_link FROM interview "
            "WHERE candidate_id = :candidate_id AND status = 'SCHEDULED' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"candidate_id": rr_candidate_id},
    ).first()
    room_url = row[0] if row else None
    return {
        "room": "in_app",
        "provider": "agent5_webrtc",
        "interview_url": room_url,
        "session_id": session.id,
    }
