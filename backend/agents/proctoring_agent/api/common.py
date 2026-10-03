from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BiometricBaseline, InterviewSession
from ..security import decrypt_embedding


def require_own_session(auth_session: InterviewSession, session_id: str) -> InterviewSession:
    if auth_session.id != session_id:
        raise HTTPException(status_code=403, detail="token does not authorize this session")
    return auth_session


def get_baseline(db: Session, session_id: str, kind: str) -> tuple[np.ndarray, BiometricBaseline]:
    baseline = db.scalar(select(BiometricBaseline).where(BiometricBaseline.session_id == session_id, BiometricBaseline.kind == kind))
    if baseline is None:
        raise HTTPException(status_code=409, detail=f"{kind} baseline is not enrolled")
    return decrypt_embedding(baseline.encrypted_embedding), baseline



async def read_upload_limited(
    upload: UploadFile,
    *,
    allowed_prefixes: tuple[str, ...],
    kind: str,
    max_mb: int | None = None,
) -> bytes:
    """Read an upload with MIME validation and a hard streaming size limit."""
    from ..config import get_settings

    content_type = (upload.content_type or "application/octet-stream").lower()
    if not any(content_type.startswith(prefix) for prefix in allowed_prefixes):
        raise HTTPException(status_code=415, detail=f"unsupported {kind} content type: {content_type}")
    limit = (max_mb or get_settings().max_upload_mb) * 1024 * 1024
    chunks: list[bytes] = []
    size = 0
    while True:
        block = await upload.read(min(1024 * 1024, limit - size + 1))
        if not block:
            break
        size += len(block)
        if size > limit:
            raise HTTPException(status_code=413, detail=f"{kind} upload exceeds {max_mb or get_settings().max_upload_mb} MB limit")
        chunks.append(block)
    if size == 0:
        raise HTTPException(status_code=400, detail=f"empty {kind} upload")
    return b"".join(chunks)

def decode_image(data: bytes) -> np.ndarray:
    if len(data) < 128:
        raise HTTPException(status_code=400, detail="image payload is too small")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise HTTPException(status_code=400, detail="invalid image")
    if image.shape[0] > 2160 or image.shape[1] > 3840:
        raise HTTPException(status_code=413, detail="image dimensions exceed limit")
    return image


def utcnow() -> datetime:
    from core.trusted_time import trusted_utc_now

    return trusted_utc_now()


def safe_file(path_text: str) -> Path:
    """Resolve a persisted artifact path and keep it inside Agent5 storage."""
    from ..config import get_settings

    base = get_settings().resolved_storage_dir.resolve()
    path = Path(path_text).expanduser().resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="media path is outside Agent5 storage") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="media file not found")
    return path


def event_dict(event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.event_type,
        "state": event.state,
        "relative_ms": event.relative_ms,
        "start_ms": event.start_ms,
        "end_ms": event.end_ms,
        "duration_ms": event.duration_ms,
        "confidence": event.confidence,
        "measurements": event.measurements,
        "risk_contribution": event.risk_contribution,
        "explanation": event.explanation,
        "review_status": event.review_status,
        "server_timestamp": event.server_timestamp.isoformat(),
    }
