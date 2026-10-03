"""Interview slot generation and management."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from models.available_slot import AvailableSlot
from repositories.slot_repository import SlotRepository
from schemas.settings import InterviewAvailabilitySettings
from services.application_settings_service import ApplicationSettingsService


def company_now(tz_name: str | None = None) -> datetime:
    """Current company-local time from the trusted server clock (not the OS clock)."""
    from core.trusted_time import trusted_now

    return trusted_now(tz_name)


def is_future_slot(slot_date: date, start_time: time, now: datetime) -> bool:
    start = datetime.combine(slot_date, start_time, tzinfo=now.tzinfo)
    return start > now


def daily_slot_windows(
    start_time: time,
    end_time: time,
    slot_minutes: int,
) -> list[tuple[time, time]]:
    windows: list[tuple[time, time]] = []
    cursor = datetime.combine(date.today(), start_time)
    close = datetime.combine(date.today(), end_time)
    step = timedelta(minutes=slot_minutes)
    while cursor + step <= close:
        end = cursor + step
        windows.append((cursor.time(), end.time()))
        cursor = end
    return windows


def upcoming_working_dates(
    weekdays: list[int],
    weeks_ahead: int,
    *,
    today: date | None = None,
    holidays: set[date] | None = None,
) -> list[date]:
    start = today or date.today()
    allowed = set(weekdays)
    blocked = holidays or set()
    target = weeks_ahead * max(len(allowed), 1)
    dates: list[date] = []
    offset = 0
    limit = max(weeks_ahead * 14, 21) + len(blocked) + 7
    while len(dates) < target and offset <= limit:
        candidate_date = start + timedelta(days=offset)
        if candidate_date.weekday() in allowed and candidate_date not in blocked:
            dates.append(candidate_date)
        offset += 1
    return dates


class SlotService:
    """Creates and manages available interview time slots."""

    def __init__(self, slot_repo: SlotRepository) -> None:
        self.slot_repo = slot_repo

    async def _policy(self, company_id: int | None = None) -> InterviewAvailabilitySettings:
        return await ApplicationSettingsService(self.slot_repo.db).get_interview_availability(company_id)

    async def _now(self, company_id: int | None = None) -> datetime:
        settings = await ApplicationSettingsService(self.slot_repo.db).get_company(company_id)
        return company_now(settings.timezone)

    async def create_available_slots(
        self,
        policy: InterviewAvailabilitySettings | None = None,
        *,
        company_id: int | None = None,
    ) -> dict[str, int]:
        """Create upcoming slots from the admin availability policy and drop stale unbooked ones."""
        if company_id is None:
            raise ValueError("Interview slots are generated per company.")
        policy = policy or await self._policy(company_id)
        now = await self._now(company_id)
        today = now.date()
        await self.slot_repo.delete_unbooked_before(today, company_id=company_id)
        windows = daily_slot_windows(policy.start_time, policy.end_time, policy.slot_minutes)
        dates = upcoming_working_dates(
            policy.weekdays,
            policy.weeks_ahead,
            today=today,
            holidays=policy.holiday_dates(),
        )
        keep: set[tuple[date, time]] = set()
        slots: list[AvailableSlot] = []
        for slot_date in dates:
            for start, end in windows:
                if not is_future_slot(slot_date, start, now):
                    continue
                keep.add((slot_date, start))
                slots.append(
                    AvailableSlot(
                        company_id=company_id,
                        date=slot_date,
                        start_time=start,
                        end_time=end,
                        is_booked=False,
                    )
                )
        removed = await self.slot_repo.delete_unbooked_not_in(
            today, keep, company_id=company_id
        )
        created = await self.slot_repo.bulk_create_if_missing(slots)
        return {"created": created, "removed": removed, "total": len(slots)}

    async def get_available_slots(self, *, company_id: int | None = None) -> list[AvailableSlot]:
        if company_id is None:
            raise ValueError("Interview slots are listed per company.")
        await self.create_available_slots(company_id=company_id)
        now = await self._now(company_id)
        slots = await self.slot_repo.get_available_slots(
            from_date=now.date(), company_id=company_id
        )
        return [slot for slot in slots if is_future_slot(slot.date, slot.start_time, now)]

    async def is_slot_open(self, slot: AvailableSlot) -> bool:
        now = await self._now(slot.company_id)
        return is_future_slot(slot.date, slot.start_time, now)

    async def reserve_slot(self, slot_id: int, candidate_id: str) -> AvailableSlot | None:
        return await self.slot_repo.reserve_slot(slot_id, candidate_id)

    async def get_slot_by_id(self, slot_id: int) -> AvailableSlot | None:
        return await self.slot_repo.get_by_id(slot_id)

    async def is_holiday(self, slot_date: date, company_id: int | None) -> bool:
        policy = await self._policy(company_id)
        return slot_date in policy.holiday_dates()

    def format_slot_datetime(self, slot: AvailableSlot) -> datetime:
        return datetime.combine(slot.date, slot.start_time)
