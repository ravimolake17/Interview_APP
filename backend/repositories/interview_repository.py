"""Data access layer for interviews."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.candidate import Candidate
from models.interview import Interview, InterviewStatus


class InterviewRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_candidate_id(self, candidate_id: str) -> Interview | None:
        result = await self.db.execute(
            select(Interview)
            .where(Interview.candidate_id == candidate_id)
            .order_by(Interview.created_at.desc())
        )
        return result.scalars().first()

    async def list_scheduled_for_week(
        self, week_start: date, week_end: date, *, company_id: int | None = None
    ) -> list[tuple[Interview, Candidate]]:
        query = (
            select(Interview, Candidate)
            .join(Candidate, Interview.candidate_id == Candidate.candidate_id)
            .where(Interview.status == InterviewStatus.SCHEDULED)
            .where(Interview.scheduled_date >= week_start)
            .where(Interview.scheduled_date <= week_end)
        )
        if company_id is not None:
            query = query.where(Interview.company_id == company_id)
        result = await self.db.execute(
            query.order_by(Interview.scheduled_date, Interview.scheduled_time)
        )
        return list(result.all())

    async def get_by_join_token_hash(self, token_hash: str) -> Interview | None:
        result = await self.db.execute(
            select(Interview).where(Interview.join_token_hash == token_hash)
        )
        return result.scalars().first()

    async def create(
        self,
        candidate_id: str,
        scheduled_date,
        scheduled_time,
        meeting_link: str | None,
        calendar_event_id: str | None,
        status: InterviewStatus = InterviewStatus.SCHEDULED,
        join_token_hash: str | None = None,
        join_token_expires_at: datetime | None = None,
        company_id: int | None = None,
    ) -> Interview:
        interview = Interview(
            candidate_id=candidate_id,
            company_id=company_id,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            meeting_link=meeting_link,
            calendar_event_id=calendar_event_id,
            status=status,
            join_token_hash=join_token_hash,
            join_token_expires_at=join_token_expires_at,
        )
        self.db.add(interview)
        await self.db.flush()
        return interview

    async def update_meeting_details(
        self,
        interview: Interview,
        meeting_link: str,
        calendar_event_id: str,
    ) -> Interview:
        interview.meeting_link = meeting_link
        interview.calendar_event_id = calendar_event_id
        interview.status = InterviewStatus.SCHEDULED
        await self.db.flush()
        return interview

    @staticmethod
    def compute_end_time(start: time, duration_minutes: int) -> time:
        start_dt = timedelta(hours=start.hour, minutes=start.minute)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        total_minutes = int(end_dt.total_seconds() // 60)
        return time(total_minutes // 60, total_minutes % 60)
