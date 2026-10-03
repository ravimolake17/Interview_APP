"""Hashed interview join tokens for candidate verification gate."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from core.config import Settings, get_settings
from core.security import generate_refresh_token_value, hash_refresh_token
from schemas.settings import InterviewAvailabilitySettings

CANDIDATE_JOIN_LEAD_MINUTES = 5


def _company_tz(tz_name: str | None) -> tzinfo:
    name = (tz_name or "Asia/Kolkata").strip() or "Asia/Kolkata"
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=5, minutes=30))


def interview_start_local(
    scheduled_date: date,
    scheduled_time: time,
    tz_name: str | None = None,
) -> datetime:
    return datetime.combine(scheduled_date, scheduled_time, tzinfo=_company_tz(tz_name))


def candidate_join_window(
    scheduled_date: date,
    scheduled_time: time,
    *,
    duration_minutes: int | None = None,
    tz_name: str | None = None,
) -> tuple[datetime, datetime, datetime]:
    """Return (opens_at, starts_at, closes_at) in company local time."""
    duration = duration_minutes or InterviewAvailabilitySettings().slot_minutes
    start = interview_start_local(scheduled_date, scheduled_time, tz_name)
    opens_at = start - timedelta(minutes=CANDIDATE_JOIN_LEAD_MINUTES)
    closes_at = start + timedelta(minutes=max(int(duration), 5))
    return opens_at, start, closes_at


def format_join_window_time(value: datetime) -> str:
    clock = value.strftime("%I:%M %p").lstrip("0")
    return f"{clock} on {value.strftime('%d %B %Y')}"


def enforce_rr_candidate_join_window(candidate_id: str) -> None:
    """Block Agent 5 candidate APIs until the company-local join window opens.

    Uses the trusted server clock so a laptop date/time change cannot open the room early.
    """
    from fastapi import HTTPException

    cid = (candidate_id or "").strip()
    if not cid:
        raise HTTPException(
            status_code=403,
            detail="This session is not linked to a scheduled interview.",
        )

    from sqlalchemy import text

    from agents.proctoring_agent.db import SessionLocal
    from services.slot_service import company_now

    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT i.scheduled_date, i.scheduled_time, i.status::text,
                       COALESCE(
                         (
                           SELECT s.data->>'timezone'
                           FROM public.application_settings s
                           WHERE s.scope_key = 'company:' || c.company_id::text
                             AND s.namespace = 'company'
                           LIMIT 1
                         ),
                         (
                           SELECT s.data->>'timezone'
                           FROM public.application_settings s
                           WHERE s.scope_key = 'global'
                             AND s.namespace = 'company'
                           LIMIT 1
                         ),
                         'Asia/Kolkata'
                       ) AS timezone
                FROM public.interview i
                JOIN public.candidate c ON c.candidate_id = i.candidate_id
                WHERE i.candidate_id = :cid
                ORDER BY i.created_at DESC
                LIMIT 1
                """
            ),
            {"cid": cid},
        ).first()

    if not row:
        raise HTTPException(
            status_code=409,
            detail="No scheduled interview was found for this candidate.",
        )

    scheduled_date, scheduled_time, status, tz_name = row
    status_text = str(status or "").upper()
    if "SCHEDULED" not in status_text:
        raise HTTPException(
            status_code=409,
            detail="This interview is no longer active.",
        )

    now = company_now(tz_name)
    opens_at, _starts_at, closes_at = candidate_join_window(
        scheduled_date,
        scheduled_time,
        tz_name=tz_name,
    )
    if now < opens_at:
        raise HTTPException(
            status_code=403,
            detail=(
                f"The interview room opens at {format_join_window_time(opens_at)}. "
                "Please join then to complete identity verification and start your interview."
            ),
        )
    if now > closes_at:
        raise HTTPException(
            status_code=410,
            detail=(
                "This interview session is no longer available. "
                "Please contact HR if you need assistance."
            ),
        )


class JoinTokenService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def generate_token_value(self) -> str:
        return generate_refresh_token_value()

    def hash_token(self, token: str) -> str:
        return hash_refresh_token(token)

    def build_join_link(self, token: str) -> str:
        return f"{self.settings.frontend_url.rstrip('/')}/interview/{token}"

    def compute_expiry(
        self,
        scheduled_date: date,
        scheduled_time: time,
        *,
        duration_minutes: int | None = None,
    ) -> datetime:
        duration = duration_minutes or InterviewAvailabilitySettings().slot_minutes
        _opens_at, _start, closes_at = candidate_join_window(
            scheduled_date,
            scheduled_time,
            duration_minutes=duration,
        )
        return closes_at.astimezone(timezone.utc) + timedelta(hours=24)
