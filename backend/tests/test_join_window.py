from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from services.join_token_service import candidate_join_window, format_join_window_time


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
