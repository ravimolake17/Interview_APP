"""Authenticated WebSocket for Azure Speech continuous STT (interview room)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.interview_agent.streaming_stt import (
    SAMPLE_RATE,
    StreamingSttSession,
    end_silence_ms,
    finalization_timeout_seconds,
    interview_stt_mode,
    streaming_stt_available,
)
from core.database import AsyncSessionLocal
from services.interview_room_service import require_room_payload, require_scheduled_interview

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interview/room", tags=["In-app interview STT stream"])

# One active recognizer per room session — prevents cross-talk / frame mixing.
_active_sessions: dict[str, StreamingSttSession] = {}
_active_lock = asyncio.Lock()


def _auth_header_from_ws(websocket: WebSocket) -> str | None:
    token = websocket.query_params.get("token") or ""
    if token:
        return f"Bearer {token}"
    auth = websocket.headers.get("authorization")
    return auth


async def _close_active(session_id: str) -> None:
    async with _active_lock:
        existing = _active_sessions.pop(session_id, None)
    if existing is not None:
        await asyncio.to_thread(existing.close)


@router.get("/sessions/{session_id}/ai/stt-mode")
async def get_stt_mode(session_id: str):
    mode = interview_stt_mode()
    available = streaming_stt_available()
    effective = mode if (mode != "streaming" or available) else "batch"
    return {
        "session_id": session_id,
        "interview_stt_mode": mode,
        "streaming_available": available,
        "effective_mode": effective,
        "sample_rate": SAMPLE_RATE,
        "format": "pcm_s16le",
        "channels": 1,
        "end_silence_ms": end_silence_ms(),
        "finalization_timeout_ms": int(finalization_timeout_seconds() * 1000),
    }


@router.websocket("/sessions/{session_id}/ai/stt-stream")
async def interview_stt_stream(websocket: WebSocket, session_id: str):
    """Binary PCM frames in; JSON partial/final events out. Keys never leave the server."""
    authorization = _auth_header_from_ws(websocket)
    try:
        payload = require_room_payload(authorization, session_id)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or "unauthorized"
        await websocket.close(code=4401, reason=str(detail)[:100])
        return

    if str(payload.get("participant_role") or "").lower() == "hr":
        await websocket.close(code=4403, reason="Only the candidate can stream interview STT")
        return

    candidate_id = str(payload.get("rr_candidate_id") or "")
    interview_language = "en"
    async with AsyncSessionLocal() as db:
        try:
            candidate, _interview = await require_scheduled_interview(db, candidate_id)
            from agents.interview_agent.interview_language import language_from_snapshot

            interview_language = language_from_snapshot(
                candidate.evaluation_snapshot
                if isinstance(candidate.evaluation_snapshot, dict)
                else {}
            )
        except Exception as exc:
            detail = getattr(exc, "detail", None) or "interview not found"
            await websocket.close(code=4404, reason=str(detail)[:100])
            return

    if interview_stt_mode() != "streaming" or not streaming_stt_available():
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "code": "streaming_disabled",
                "message": "Streaming STT is not enabled or Azure Speech SDK is unavailable. Use batch mode.",
            }
        )
        await websocket.close(code=4403)
        return

    await websocket.accept()
    loop = asyncio.get_running_loop()
    outbound: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def on_event(message: dict[str, Any]) -> None:
        await outbound.put(message)

    await _close_active(session_id)
    from agents.interview_agent.interview_language import azure_stt_locale

    session = StreamingSttSession(
        session_id=session_id,
        candidate_id=candidate_id,
        loop=loop,
        on_event=on_event,
        language=azure_stt_locale(interview_language),
    )
    async with _active_lock:
        _active_sessions[session_id] = session

    writer_task = asyncio.create_task(_pump_outbound(websocket, outbound), name=f"stt-ws-out-{session_id}")
    question_id: str | None = None
    turn_id: str | None = None
    started = False
    frames_in = 0
    bytes_in = 0

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                if not started:
                    continue
                raw = message["bytes"]
                if not raw:
                    continue
                # Starlette may deliver bytearray; Azure Speech requires bytes.
                pcm = raw if isinstance(raw, bytes) else bytes(raw)
                frames_in += 1
                bytes_in += len(pcm)
                try:
                    await asyncio.to_thread(session.write, pcm)
                except Exception as exc:
                    logger.warning(
                        "streaming_stt_frame_drop session=%s err=%s",
                        session_id,
                        str(exc)[:160],
                    )
                continue
            text = message.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                await outbound.put({"type": "error", "code": "bad_json", "message": "Invalid control message"})
                continue
            msg_type = str(data.get("type") or "").strip().lower()
            if msg_type == "start":
                if started:
                    await outbound.put({"type": "error", "code": "already_started", "message": "Turn already started"})
                    continue
                question_id = str(data.get("question_id") or "").strip() or None
                turn_id = str(data.get("turn_id") or "").strip() or None
                try:
                    await asyncio.to_thread(session.start)
                    started = True
                    logger.info("streaming_stt_turn_start session=%s question=%s", session_id, question_id)
                except Exception as exc:
                    logger.exception("Failed to start streaming STT for %s", session_id)
                    await outbound.put(
                        {"type": "error", "code": "start_failed", "message": str(exc)[:200] or "start failed"}
                    )
                    break
            elif msg_type in {"stop", "end_of_speech"}:
                if not started:
                    await outbound.put({"type": "error", "code": "not_started", "message": "Call start first"})
                    continue
                await asyncio.to_thread(session.mark_speech_end)
                result = await asyncio.to_thread(session.stop)
                raw_text = str(result.get("raw_text") or "")
                metrics = dict(result.get("metrics") or {})
                error = result.get("error")
                logger.info(
                    "streaming_stt_turn_stop session=%s question=%s frames=%s bytes=%s audio_s=%.1f text_chars=%s",
                    session_id,
                    question_id,
                    frames_in,
                    bytes_in,
                    bytes_in / (SAMPLE_RATE * 2),
                    len(raw_text),
                )
                if not raw_text:
                    logger.warning(
                        "streaming_stt_empty_final session=%s candidate=%s error=%s bytes=%s segments=%s",
                        session_id,
                        candidate_id,
                        (str(error)[:120] if error else None),
                        metrics.get("stt_audio_bytes"),
                        metrics.get("segment_count"),
                    )
                final_payload = await _finalize_transcript(
                    candidate_id=candidate_id,
                    question_id=question_id,
                    turn_id=turn_id,
                    raw_text=raw_text,
                    metrics=metrics,
                    error=error,
                )
                await outbound.put(final_payload)
                break
            elif msg_type == "ping":
                await outbound.put({"type": "pong"})
            else:
                await outbound.put({"type": "error", "code": "unknown_type", "message": f"Unknown type: {msg_type}"})
    except WebSocketDisconnect:
        logger.info("STT websocket disconnected session=%s", session_id)
    except Exception:
        logger.exception("STT websocket failed session=%s", session_id)
        try:
            await outbound.put({"type": "error", "code": "server_error", "message": "Streaming STT failed"})
        except Exception:
            pass
    finally:
        logger.info(
            "streaming_stt_socket_closed session=%s started=%s frames=%s bytes=%s",
            session_id,
            started,
            frames_in,
            bytes_in,
        )
        await _close_active(session_id)
        await outbound.put(None)
        writer_task.cancel()
        try:
            await writer_task
        except asyncio.CancelledError:
            pass


async def _pump_outbound(websocket: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        item = await queue.get()
        if item is None:
            return
        try:
            await websocket.send_json(item)
        except Exception:
            return


async def _finalize_transcript(
    *,
    candidate_id: str,
    question_id: str | None,
    turn_id: str | None,
    raw_text: str,
    metrics: dict[str, Any],
    error: str | None,
) -> dict[str, Any]:
    """Apply Phase 1 deterministic correction; defer LLM to eval worker when needed."""
    from agents.interview_agent.stt_corrector import build_stt_context, correct_transcript_with_resume
    from agents.shared.latency_trace import LatencyTurn
    from repositories.candidate_repository import CandidateRepository
    from repositories.interview_question_set_repository import InterviewQuestionSetRepository
    from services.interview_oral_store import upsert_oral_turn
    from services.interview_speed_cache import store_pending_stt_correction

    if not (raw_text or "").strip():
        return {
            "type": "final",
            "ok": False,
            "text": "",
            "raw_text": "",
            "error": error or "empty_transcript",
            "metrics": metrics,
            "turn_id": turn_id,
            "question_id": question_id,
        }

    question_text: str | None = None
    text = raw_text
    correction_status: str | None = None
    correction_tier: str | None = None
    needs_llm = False
    fixed: dict[str, Any] = {"raw_text": raw_text, "resume_corrected": False}

    async with AsyncSessionLocal() as db:
        candidate = await CandidateRepository(db).get_by_candidate_id(candidate_id)
        if candidate is None:
            return {
                "type": "final",
                "ok": False,
                "text": raw_text,
                "raw_text": raw_text,
                "error": "candidate_not_found",
                "metrics": metrics,
                "turn_id": turn_id,
            }
        if question_id:
            qs = await InterviewQuestionSetRepository(db).get_latest(candidate_id)
            if qs:
                for item in qs.questions_json or []:
                    if item.get("id") == question_id:
                        question_text = str(item.get("question_text") or "").strip() or None
                        break
        stt_bundle = build_stt_context(
            full_name=candidate.full_name,
            evaluation_snapshot=candidate.evaluation_snapshot,
            jd_text=candidate.jd_text,
            job_position=candidate.job_position,
            question_text=question_text,
        )
        turn = LatencyTurn(turn_id=turn_id, session_id=None, phase="stt_stream_final")
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and str(key).endswith("_ms"):
                turn.set_ms(key, float(value))
            else:
                turn.set_value(key, value)
        fixed = correct_transcript_with_resume(
            raw_text,
            context=stt_bundle.get("context") or {},
            resume_terms=stt_bundle.get("resume_terms") or [],
            question_text=question_text,
            candidate_name=stt_bundle.get("candidate_name") or candidate.full_name,
        )
        text = str(fixed.get("text") or raw_text).strip()
        correction_status = str(fixed.get("correction_status") or "") or None
        correction_tier = str(fixed.get("correction_tier") or "") or None
        needs_llm = bool(fixed.get("needs_llm_correction"))
        if needs_llm and question_id:
            store_pending_stt_correction(
                candidate_id,
                question_id,
                {
                    "raw_transcript": str(fixed.get("raw_text") or raw_text),
                    "visible_text": text,
                    "needs_llm_correction": True,
                    "correction_status": correction_status or "pending_llm",
                    "correction_tier": correction_tier,
                    "resume_terms": list(stt_bundle.get("resume_terms") or [])[:80],
                    "context": dict(stt_bundle.get("context") or {}),
                    "question_text": question_text,
                    "candidate_name": stt_bundle.get("candidate_name") or candidate.full_name,
                },
            )
        upsert_oral_turn(
            candidate,
            {
                "question_id": question_id or "",
                "question_text": question_text or "",
                "answer_text": text,
                "raw_transcript": str(fixed.get("raw_text") or raw_text),
                "corrected_transcript": text,
                "correction_status": correction_status,
                "correction_tier": correction_tier,
                "stt_mode": "streaming",
            },
        )
        await db.commit()
        turn.set_value("correction_status", correction_status)
        turn.set_value("correction_tier", correction_tier)
        turn.emit()

    return {
        "type": "final",
        "ok": True,
        "text": text,
        "raw_text": str(fixed.get("raw_text") or raw_text),
        "correction_status": correction_status,
        "correction_tier": correction_tier,
        "needs_llm_correction": needs_llm,
        "resume_corrected": bool(fixed.get("resume_corrected")),
        "metrics": metrics,
        "turn_id": turn_id,
        "question_id": question_id,
        "error": error,
    }
