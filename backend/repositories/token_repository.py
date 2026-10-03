"""Data access layer for scheduling tokens."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.trusted_time import trusted_utc_now
from models.schedule_token import ScheduleToken


class TokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, candidate_id: str, token: str, expiry_time: datetime) -> ScheduleToken:
        schedule_token = ScheduleToken(
            candidate_id=candidate_id,
            token=token,
            expiry_time=expiry_time,
            used=False,
        )
        self.db.add(schedule_token)
        await self.db.flush()
        return schedule_token

    async def get_by_token(self, token: str) -> ScheduleToken | None:
        result = await self.db.execute(select(ScheduleToken).where(ScheduleToken.token == token))
        return result.scalar_one_or_none()

    async def mark_used(self, schedule_token: ScheduleToken) -> ScheduleToken:
        schedule_token.used = True
        await self.db.flush()
        return schedule_token

    async def has_any_token(self, candidate_id: str) -> bool:
        result = await self.db.execute(
            select(ScheduleToken.id)
            .where(ScheduleToken.candidate_id == candidate_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def candidate_ids_with_tokens(self) -> set[str]:
        result = await self.db.execute(select(ScheduleToken.candidate_id).distinct())
        return set(result.scalars().all())

    async def has_used_token(self, candidate_id: str) -> bool:
        result = await self.db.execute(
            select(ScheduleToken.id)
            .where(ScheduleToken.candidate_id == candidate_id)
            .where(ScheduleToken.used.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def expire_unused_tokens(self, candidate_id: str) -> int:
        """Expire all unused tokens when a new invite link is issued."""
        now = trusted_utc_now()
        result = await self.db.execute(
            select(ScheduleToken).where(
                ScheduleToken.candidate_id == candidate_id,
                ScheduleToken.used.is_(False),
            )
        )
        tokens = list(result.scalars().all())
        for token in tokens:
            token.expiry_time = now
        if tokens:
            await self.db.flush()
        return len(tokens)

    def is_valid(self, schedule_token: ScheduleToken) -> bool:
        if schedule_token.used:
            return False
        expiry = schedule_token.expiry_time
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return trusted_utc_now() < expiry
