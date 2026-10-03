"""Audit log persistence."""

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        user_id: int | None = None,
        user_email: str | None = None,
        user_name: str | None = None,
        user_role: str | None = None,
        details: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
        status: str = "SUCCESS",
        location: str | None = None,
        message: str | None = None,
        company_id: int | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            company_id=company_id,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            user_role=user_role,
            details=details,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            status=status,
            location=location,
            message=message,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list_recent(
        self, *, limit: int = 100, company_id: int | None = None
    ) -> list[AuditLog]:
        query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        if company_id is not None:
            query = query.where(AuditLog.company_id == company_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def entity_ids_for_action(self, action: str) -> set[str]:
        result = await self.db.execute(
            select(AuditLog.entity_id).where(
                AuditLog.action == action,
                AuditLog.entity_id.is_not(None),
            )
        )
        return {str(row[0]) for row in result.all() if row[0]}
