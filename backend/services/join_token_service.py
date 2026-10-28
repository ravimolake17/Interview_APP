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
    """Return (opens_at, starts_at, closes_at) in company local time.

    First entry is allowed only while opens_at <= now < closes_at
    (e.g. 10:00 start, 30 min → join until 10:30).

    After the candidate has started once, rejoin uses
    ``assert_candidate_entry_allowed`` (first_start + duration), and an
    open room visit is never cut off mid-interview.
    """
    duration = duration_minutes or InterviewAvailabilitySettings().slot_minutes
    start = interview_start_local(scheduled_date, scheduled_time, tz_name)
    opens_at = start - timedelta(minutes=CANDIDATE_JOIN_LEAD_MINUTES)
    closes_at = start + timedelta(minutes=max(int(duration), 5))
    return opens_at, start, closes_at


def format_join_window_time(value: datetime) -> str:
    clock = value.strftime("%I:%M %p").lstrip("0")
    return f"{clock} on {value.strftime('%d %B %Y')}"


def join_window_closed_message(closes_at: datetime) -> str:
    return (
        f"This interview join window closed at {format_join_window_time(closes_at)}. "
        "You must join before the scheduled end time. Please contact HR if you need assistance."
    )


def rejoin_closes_at(first_started_at: datetime, duration_minutes: int) -> datetime:
    """Deadline for leaving and coming back: first start + assigned duration."""
    return first_started_at + timedelta(minutes=max(int(duration_minutes or 30), 5))


def rejoin_closed_message(closes_at: datetime) -> str:
    return (
        f"Your interview time ended at {format_join_window_time(closes_at)}. "
        "You can no longer rejoin this session. Please contact HR if you need assistance."
    )


def parse_runtime_datetime(value: object, *, tz_name: str | None = None) -> datetime | None:
    """Parse ISO timestamps stored on interview_runtime (UTC or offset-aware)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_company_tz(tz_name))


_ACTIVE_SESSION_STATUSES = frozenset(
    {
        "ready",
        "active",
        "terminating",
        "device_checked",
        "face_enrolled",
        "face_enrollment_pending",
        "face_verified",
        "voice_enrolled",
        "initial_voice_verified",
    }
)


def assert_candidate_entry_allowed(
    *,
    scheduled_date: date,
    scheduled_time: time,
    duration_minutes: int | None,
    tz_name: str | None,
    now: datetime | None = None,
    room_visit_open: bool = False,
    first_started_at: datetime | None = None,
    session_status: str | None = None,
) -> None:
    """Gate first join and rejoin without ending a continuous live session.

    Rules:
    - Open room visit or active Agent5 session: always allow — interview may overrun.
    - Already started once, then left: allow until first_start + duration (+ grace).
    - Never started: allow only in the scheduled join window.
    """
    from fastapi import HTTPException

    from services.slot_service import company_now

    try:
        duration = int(duration_minutes or 30)
    except (TypeError, ValueError):
        duration = 30
    duration = max(duration, 5)

    clock = now or company_now(tz_name)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=_company_tz(tz_name))

    status = str(session_status or "").strip().lower()
    if room_visit_open or status in _ACTIVE_SESSION_STATUSES:
        return

    if first_started_at is not None:
        started = first_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        started = started.astimezone(_company_tz(tz_name))
        # Grace so a 15–30 min planned interview is not cut mid-answer if the
        # tab briefly lost room_visit_open (refresh / network blip).
        grace = max(15, duration)
        deadline = rejoin_closes_at(started, duration + grace)
        if clock >= deadline:
            raise HTTPException(status_code=410, detail=rejoin_closed_message(deadline))
        return

    opens_at, _starts_at, closes_at = candidate_join_window(
        scheduled_date,
        scheduled_time,
        duration_minutes=duration,
        tz_name=tz_name,
    )
    if clock < opens_at:
        raise HTTPException(
            status_code=403,
            detail=(
                f"The interview room opens at {format_join_window_time(opens_at)}. "
                "Please join then to complete identity verification and start your interview."
            ),
        )
    if clock >= closes_at:
        raise HTTPException(
            status_code=410,
            detail=join_window_closed_message(closes_at),
        )


def _duration_timezone_sql() -> str:
    return """
                       COALESCE(
                         (
                           SELECT NULLIF(
                             (bp.blueprint_json->'time_allocation'->>'total_duration_minutes')::int,
                             0
                           )
                           FROM public.interview_blueprint bp
                           WHERE bp.candidate_id = i.candidate_id
                           ORDER BY bp.created_at DESC
                           LIMIT 1
                         ),
                         (
                           SELECT NULLIF(qs.total_duration_minutes, 0)
                           FROM public.interview_question_sets qs
                           WHERE qs.candidate_id = i.candidate_id
                           ORDER BY qs.created_at DESC
                           LIMIT 1
                         ),
                         (
                           SELECT NULLIF((s.data->>'slot_minutes')::int, 0)
                           FROM public.application_settings s
                           WHERE s.scope_key = 'company:' || c.company_id::text
                             AND s.namespace = 'interview_availability'
                           LIMIT 1
                         ),
                         (
                           SELECT NULLIF((s.data->>'slot_minutes')::int, 0)
                           FROM public.application_settings s
                           WHERE s.scope_key = 'global'
                             AND s.namespace = 'interview_availability'
                           LIMIT 1
                         ),
                         30
                       ) AS duration_minutes,
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
                       ) AS timezone,
                       c.evaluation_snapshot
    """


def enforce_rr_candidate_join_window(
    candidate_id: str,
    *,
    session_started_at: datetime | None = None,
    session_status: str | None = None,
) -> None:
    """Block Agent 5 candidate APIs outside first-join / rejoin rules.

    Continuous open visits / active Agent5 sessions are not time-killed.
    Rejoin after leave is limited to first_start + duration (+ grace).
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

    with SessionLocal() as db:
        row = db.execute(
            text(
                f"""
                SELECT i.scheduled_date, i.scheduled_time, i.status::text,
{_duration_timezone_sql()}
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

    scheduled_date, scheduled_time, status, duration_minutes, tz_name, snapshot = row
    status_text = str(status or "").upper()
    if "SCHEDULED" not in status_text:
        raise HTTPException(
            status_code=409,
            detail="This interview is no longer active.",
        )

    snap = dict(snapshot or {}) if isinstance(snapshot, dict) else {}
    agent5 = dict(snap.get("agent5") or {})
    runtime = dict(agent5.get("interview_runtime") or {})
    room_visit_open = bool(runtime.get("room_visit_open"))
    first_started = parse_runtime_datetime(
        runtime.get("first_room_join_at"),
        tz_name=tz_name,
    )
    if first_started is None and session_started_at is not None:
        first_started = parse_runtime_datetime(session_started_at, tz_name=tz_name)

    assert_candidate_entry_allowed(
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        duration_minutes=duration_minutes,
        tz_name=tz_name,
        room_visit_open=room_visit_open,
        first_started_at=first_started,
        session_status=session_status,
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
        # Token dies when the first-join window closes (not 24h later).
        # Rejoin after first start uses first_room_join_at + duration and may
        # ignore this expiry when the candidate already started once.
        return closes_at.astimezone(timezone.utc)
