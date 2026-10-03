"""Data access layer for available interview slots."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.available_slot import AvailableSlot


class SlotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_available_slots(
        self, from_date: date | None = None, *, company_id: int | None = None
    ) -> list[AvailableSlot]:
        query = select(AvailableSlot).where(AvailableSlot.is_booked.is_(False))
        if company_id is not None:
            query = query.where(AvailableSlot.company_id == company_id)
        if from_date:
            query = query.where(AvailableSlot.date >= from_date)
        query = query.order_by(AvailableSlot.date, AvailableSlot.start_time)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, slot_id: int) -> AvailableSlot | None:
        result = await self.db.execute(select(AvailableSlot).where(AvailableSlot.id == slot_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, slot_id: int) -> AvailableSlot | None:
        """Row-level lock to prevent concurrent double booking."""
        result = await self.db.execute(
            select(AvailableSlot).where(AvailableSlot.id == slot_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def reserve_slot(self, slot_id: int, candidate_id: str) -> AvailableSlot | None:
        slot = await self.get_by_id_for_update(slot_id)
        if not slot or slot.is_booked:
            return None
        slot.is_booked = True
        slot.booked_candidate = candidate_id
        await self.db.flush()
        return slot

    async def create_slots(self, slots: list[AvailableSlot]) -> list[AvailableSlot]:
        self.db.add_all(slots)
        await self.db.flush()
        return slots

    async def delete_unbooked_before(
        self, before_date: date, *, company_id: int | None = None
    ) -> int:
        query = select(AvailableSlot).where(
            AvailableSlot.is_booked.is_(False),
            AvailableSlot.date < before_date,
        )
        if company_id is not None:
            query = query.where(AvailableSlot.company_id == company_id)
        result = await self.db.execute(query)
        removed = 0
        for slot in result.scalars().all():
            await self.db.delete(slot)
            removed += 1
        if removed:
            await self.db.flush()
        return removed

    async def list_unbooked_from(
        self, from_date: date, *, company_id: int | None = None
    ) -> list[AvailableSlot]:
        query = select(AvailableSlot).where(
            AvailableSlot.is_booked.is_(False),
            AvailableSlot.date >= from_date,
        )
        if company_id is not None:
            query = query.where(AvailableSlot.company_id == company_id)
        result = await self.db.execute(
            query.order_by(AvailableSlot.date, AvailableSlot.start_time)
        )
        return list(result.scalars().all())

    async def delete_unbooked_not_in(
        self,
        from_date: date,
        keep: set[tuple[date, object]],
        *,
        company_id: int | None = None,
    ) -> int:
        existing = await self.list_unbooked_from(from_date, company_id=company_id)
        removed = 0
        for slot in existing:
            if (slot.date, slot.start_time) not in keep:
                await self.db.delete(slot)
                removed += 1
        if removed:
            await self.db.flush()
        return removed

    async def bulk_create_if_missing(self, slots: list[AvailableSlot]) -> int:
        created = 0
        for slot in slots:
            existing = await self.db.execute(
                select(AvailableSlot).where(
                    AvailableSlot.date == slot.date,
                    AvailableSlot.start_time == slot.start_time,
                    AvailableSlot.company_id == slot.company_id,
                )
            )
            if existing.scalar_one_or_none() is None:
                self.db.add(slot)
                created += 1
        await self.db.flush()
        return created
