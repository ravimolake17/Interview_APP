from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from services.join_token_service import (
    JoinTokenService,
    assert_candidate_entry_allowed,
    candidate_join_window,
    format_join_window_time,
    join_window_closed_message,
    rejoin_closes_at,
    rejoin_closed_message,
)


def test_join_window_opens_five_minutes_before_slot():
    opens, start, closes = candidate_join_window(
        date(2026, 9, 24),
        time(10, 0),
        duration_minutes=30,
        tz_name="Asia/Kolkata",
    )
    tz = ZoneInfo("Asia/Kolkata")
    assert start == datetime(2026, 9, 24, 10, 0, tzinfo=tz)
    assert opens == datetime(2026, 9, 24, 9, 55, tzinfo=tz)
    assert closes == datetime(2026, 9, 24, 10, 30, tzinfo=tz)


def test_join_window_message_is_candidate_friendly():
    opens = datetime(2026, 9, 24, 9, 55, tzinfo=ZoneInfo("Asia/Kolkata"))
    text = format_join_window_time(opens)
    assert "9:55 AM" in text
    assert "24 September 2026" in text
    assert opens + timedelta(minutes=5)


def test_join_token_expires_at_scheduled_end_not_plus_24h():
    expires = JoinTokenService().compute_expiry(
        date(2026, 9, 24),
        time(10, 0),
        duration_minutes=30,
    )
    # 10:30 Asia/Kolkata == 05:00 UTC
    assert expires == datetime(2026, 9, 24, 5, 0, tzinfo=timezone.utc)


def test_closed_join_window_message_mentions_deadline():
    closes = datetime(2026, 9, 24, 10, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    text = join_window_closed_message(closes)
    assert "10:30 AM" in text
    assert "before the scheduled end" in text.lower()


def test_rejoin_deadline_is_first_start_plus_duration():
    tz = ZoneInfo("Asia/Kolkata")
    started = datetime(2026, 9, 24, 10, 30, tzinfo=tz)
    assert rejoin_closes_at(started, 30) == datetime(2026, 9, 24, 11, 0, tzinfo=tz)


def test_first_join_blocked_after_scheduled_end():
    tz = ZoneInfo("Asia/Kolkata")
    with pytest.raises(HTTPException) as exc:
        assert_candidate_entry_allowed(
            scheduled_date=date(2026, 9, 24),
            scheduled_time=time(10, 0),
            duration_minutes=30,
            tz_name="Asia/Kolkata",
            now=datetime(2026, 9, 24, 10, 31, tzinfo=tz),
        )
    assert exc.value.status_code == 410


def test_rejoin_allowed_within_first_start_plus_duration():
    tz = ZoneInfo("Asia/Kolkata")
    # Joined at 10:30, left, back at 10:40 — still within 30 min allotment.
    assert_candidate_entry_allowed(
        scheduled_date=date(2026, 9, 24),
        scheduled_time=time(10, 0),
        duration_minutes=30,
        tz_name="Asia/Kolkata",
        now=datetime(2026, 9, 24, 10, 40, tzinfo=tz),
        first_started_at=datetime(2026, 9, 24, 10, 30, tzinfo=tz),
        room_visit_open=False,
    )


def test_rejoin_blocked_after_allotted_duration():
    tz = ZoneInfo("Asia/Kolkata")
    # Rejoin window = duration + grace (max(15, duration)); 30+30 = 60 min from start.
    with pytest.raises(HTTPException) as exc:
        assert_candidate_entry_allowed(
            scheduled_date=date(2026, 9, 24),
            scheduled_time=time(10, 0),
            duration_minutes=30,
            tz_name="Asia/Kolkata",
            now=datetime(2026, 9, 24, 12, 0, tzinfo=tz),
            first_started_at=datetime(2026, 9, 24, 10, 30, tzinfo=tz),
            room_visit_open=False,
        )
    assert exc.value.status_code == 410
    assert "no longer rejoin" in str(exc.value.detail).lower()


def test_active_agent5_session_not_killed_past_deadline():
    tz = ZoneInfo("Asia/Kolkata")
    assert_candidate_entry_allowed(
        scheduled_date=date(2026, 9, 24),
        scheduled_time=time(10, 0),
        duration_minutes=30,
        tz_name="Asia/Kolkata",
        now=datetime(2026, 9, 24, 11, 20, tzinfo=tz),
        first_started_at=datetime(2026, 9, 24, 10, 30, tzinfo=tz),
        room_visit_open=False,
        session_status="active",
    )


def test_rejoin_blocked_hours_or_days_later():
    tz = ZoneInfo("Asia/Kolkata")
    with pytest.raises(HTTPException) as exc:
        assert_candidate_entry_allowed(
            scheduled_date=date(2026, 9, 24),
            scheduled_time=time(10, 0),
            duration_minutes=30,
            tz_name="Asia/Kolkata",
            now=datetime(2026, 9, 26, 10, 0, tzinfo=tz),
            first_started_at=datetime(2026, 9, 24, 10, 30, tzinfo=tz),
            room_visit_open=False,
        )
    assert exc.value.status_code == 410


def test_continuous_open_visit_not_killed_past_deadline():
    tz = ZoneInfo("Asia/Kolkata")
    # Still in the room at 11:20 — do not end the meeting.
    assert_candidate_entry_allowed(
        scheduled_date=date(2026, 9, 24),
        scheduled_time=time(10, 0),
        duration_minutes=30,
        tz_name="Asia/Kolkata",
        now=datetime(2026, 9, 24, 11, 20, tzinfo=tz),
        first_started_at=datetime(2026, 9, 24, 10, 30, tzinfo=tz),
        room_visit_open=True,
    )


def test_rejoin_closed_message():
    closes = datetime(2026, 9, 24, 11, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert "11:00 AM" in rejoin_closed_message(closes)
