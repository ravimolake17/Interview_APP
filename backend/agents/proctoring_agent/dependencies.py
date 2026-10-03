from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import InterviewSession
from .security import decode_token

DbSession = Annotated[Session, Depends(get_db)]


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def require_candidate_session(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> InterviewSession:
    try:
        payload = decode_token(_bearer(authorization), expected_type="candidate")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid candidate token") from exc
    session_id = str(payload.get("session_id", ""))
    session = db.scalar(select(InterviewSession).where(InterviewSession.id == session_id))
    if session is None:
        raise HTTPException(status_code=401, detail="candidate session not found")
    if str(payload.get("sub", "")) != session.candidate_id:
        raise HTTPException(status_code=401, detail="candidate token is not bound to this session")
    if str(payload.get("participant_role") or "candidate").lower() != "hr":
        live = (
            str(session.status or "") in {"active", "terminating"}
            and getattr(session, "started_at", None) is not None
        )
        if not live:
            from services.join_token_service import enforce_rr_candidate_join_window

            enforce_rr_candidate_join_window(str(payload.get("rr_candidate_id") or ""))
    return session


def require_candidate_bearer_payload(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    try:
        return decode_token(_bearer(authorization), expected_type="candidate")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid candidate token") from exc


def require_hr_reviewer(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Accept main HR application JWT (roles HR or ADMIN). No Agent5-local admin login."""
    from core.config import get_settings as main_settings
    from core.security import decode_access_token

    try:
        payload = decode_access_token(_bearer(authorization), main_settings())
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid HR access token") from exc
    role = str(payload.get("role", "")).upper()
    if role not in {"HR", "ADMIN", "SUPERADMIN"}:
        raise HTTPException(status_code=403, detail="HR or admin access required")
    return payload
