"""Secure scheduling token generation and validation."""

import uuid
from datetime import datetime, timedelta, timezone

from core.config import Settings, get_settings, public_frontend_url
from models.schedule_token import ScheduleToken
from repositories.token_repository import TokenRepository


class TokenService:
    def __init__(self, token_repo: TokenRepository, settings: Settings | None = None) -> None:
        self.token_repo = token_repo
        self.settings = settings or get_settings()

    def generate_token_value(self) -> str:
        return str(uuid.uuid4())

    def build_scheduling_link(self, token: str) -> str:
        return f"{public_frontend_url()}/schedule/{token}"

    async def create_token(self, candidate_id: str) -> tuple[ScheduleToken, str]:
        await self.token_repo.expire_unused_tokens(candidate_id)
        token_value = self.generate_token_value()
        expiry = datetime.now(timezone.utc) + timedelta(hours=self.settings.token_expiry_hours)
        schedule_token = await self.token_repo.create(candidate_id, token_value, expiry)
        return schedule_token, self.build_scheduling_link(token_value)

    async def validate_token(self, token: str) -> tuple[ScheduleToken | None, str | None]:
        schedule_token = await self.token_repo.get_by_token(token)
        if not schedule_token:
            return None, "Invalid scheduling token."
        if schedule_token.used:
            return schedule_token, "This scheduling link has already been used."
        if not self.token_repo.is_valid(schedule_token):
            return schedule_token, "This scheduling link has expired."
        return schedule_token, None

    async def invalidate_token(self, schedule_token: ScheduleToken) -> None:
        await self.token_repo.mark_used(schedule_token)
