from datetime import date, time

from schemas.settings import InterviewAvailabilitySettings
from services.slot_service import daily_slot_windows, upcoming_working_dates


def test_default_availability_is_monday_to_saturday_nine_to_seven():
    policy = InterviewAvailabilitySettings()
    assert policy.weekdays == [0, 1, 2, 3, 4, 5]
    assert 6 not in policy.weekdays
    assert policy.start_time == time(9, 0)
    assert policy.end_time == time(19, 0)
    assert policy.slot_minutes == 30


def test_custom_slot_minutes_is_company_default_duration():
    policy = InterviewAvailabilitySettings(slot_minutes=60)
    assert policy.slot_minutes == 60


def test_daily_windows_cover_full_day_without_crossing_end():
    windows = daily_slot_windows(time(9, 0), time(19, 0), 30)
    assert windows[0] == (time(9, 0), time(9, 30))
    assert windows[-1] == (time(18, 30), time(19, 0))
    assert len(windows) == 20


def test_upcoming_dates_skip_sunday():
    monday = date(2026, 9, 14)  # Monday
    dates = upcoming_working_dates([0, 1, 2, 3, 4, 5], 1, today=monday)
    assert all(item.weekday() != 6 for item in dates)
    assert {item.weekday() for item in dates} == {0, 1, 2, 3, 4, 5}


def test_holidays_are_deduped_and_sorted():
    policy = InterviewAvailabilitySettings(
        holidays=[
            {"date": "2026-10-02", "name": "Gandhi Jayanti"},
            {"date": "2026-10-02", "name": "Holiday"},
            {"date": "2026-01-26", "name": "Republic Day"},
        ]
    )
    assert [item.date for item in policy.holidays] == [date(2026, 1, 26), date(2026, 10, 2)]
    assert policy.holidays[1].name == "Holiday"
    assert policy.holiday_dates() == {date(2026, 1, 26), date(2026, 10, 2)}


def test_upcoming_dates_skip_holidays():
    monday = date(2026, 9, 14)
    holiday = date(2026, 9, 17)  # Thursday
    dates = upcoming_working_dates([0, 1, 2, 3, 4, 5], 1, today=monday, holidays={holiday})
    assert holiday not in dates
    assert all(item.weekday() != 6 for item in dates)
    assert len(dates) == 6


def test_availability_rejects_empty_days_and_inverted_hours():
    try:
        InterviewAvailabilitySettings(weekdays=[])
        assert False, "empty weekdays must fail"
    except ValueError:
        pass
    try:
        InterviewAvailabilitySettings(start_time=time(19, 0), end_time=time(9, 0))
        assert False, "inverted hours must fail"
    except ValueError:
        pass
