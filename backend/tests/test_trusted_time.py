from datetime import date, datetime, timedelta, time as time_cls, timezone

from core import trusted_time as mod
from services.slot_service import is_future_slot


def test_trusted_clock_advances_with_monotonic_not_wall_clock(monkeypatch):
    mod.reset_trusted_clock_for_tests()
    fixed = datetime(2026, 9, 24, 6, 51, tzinfo=timezone.utc)
    monkeypatch.setattr(mod, "_http_utc", lambda: fixed)
    mono = {"value": 1000.0}
    monkeypatch.setattr(mod.time, "monotonic", lambda: mono["value"])
    first = mod.sync_trusted_clock(force=True)
    monkeypatch.setattr(
        mod,
        "datetime",
        type(
            "FakeDateTime",
            (),
            {
                "now": staticmethod(
                    lambda tz=None: datetime(2019, 1, 1, tzinfo=tz or timezone.utc)
                )
            },
        ),
    )
    mono["value"] = 1060.0
    later = mod.trusted_utc_now()
    assert first.year == 2026
    assert later.year == 2026
    assert later - first == timedelta(seconds=60)


def test_past_slot_is_closed_against_server_now():
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert not is_future_slot(date(2026, 9, 23), time_cls(10, 0), now)
    assert not is_future_slot(date(2026, 9, 24), time_cls(11, 0), now)
    assert is_future_slot(date(2026, 9, 24), time_cls(12, 30), now)
