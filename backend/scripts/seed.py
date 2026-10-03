"""Seed script for demo candidates and slots."""

import asyncio

from core.database import AsyncSessionLocal
from models.candidate import Candidate, CandidateStatus
from repositories.candidate_repository import CandidateRepository
from repositories.slot_repository import SlotRepository
from services.slot_service import SlotService


async def seed():
    async with AsyncSessionLocal() as db:
        repo = CandidateRepository(db)
        existing = await repo.get_by_candidate_id("CAND-001")
        if not existing:
            db.add(
                Candidate(
                    company_id=1,
                    candidate_id="CAND-001",
                    full_name="John Doe",
                    email="john.doe@example.com",
                    phone="+1-555-0100",
                    resume_score=87.5,
                    status=CandidateStatus.SHORTLISTED,
                )
            )
            db.add(
                Candidate(
                    company_id=1,
                    candidate_id="CAND-002",
                    full_name="Jane Smith",
                    email="jane.smith@example.com",
                    phone="+1-555-0101",
                    resume_score=92.0,
                    status=CandidateStatus.SHORTLISTED,
                )
            )

        slot_service = SlotService(SlotRepository(db))
        created = await slot_service.create_available_slots(company_id=1)
        await db.commit()
        print(f"Seed complete. Slots created={created.get('created')} removed={created.get('removed')}.")


if __name__ == "__main__":
    asyncio.run(seed())
